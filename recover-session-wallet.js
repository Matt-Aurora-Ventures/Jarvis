/**
 * Session Wallet Recovery Script
 *
 * Economically optimal recovery:
 * 1. Fund wallet with minimal SOL for tx fees (~0.01 SOL)
 * 2. Sell token (4.075013 @ $0.6148 = ~$2.50) via Jupiter
 * 3. Close token account (+0.00203928 SOL rent recovery)
 * 4. Sweep all SOL to destination
 */

const {
  Keypair,
  Connection,
  PublicKey,
  Transaction,
  SystemProgram,
  LAMPORTS_PER_SOL,
  VersionedTransaction,
  TransactionMessage,
} = require('@solana/web3.js');
const {
  TOKEN_PROGRAM_ID,
  getAssociatedTokenAddress,
  createCloseAccountInstruction,
} = require('@solana/spl-token');
const fetch = require('cross-fetch');

// Wallet to recover
const SECRET_KEY = new Uint8Array([
  85, 35, 60, 150, 134, 186, 135, 107, 148, 23, 187, 146, 94, 51, 83, 19,
  137, 234, 49, 154, 206, 139, 250, 174, 71, 97, 11, 171, 71, 126, 164, 78,
  89, 19, 143, 192, 94, 89, 226, 56, 115, 8, 28, 161, 1, 67, 97, 205, 230,
  19, 132, 105, 209, 175, 122, 175, 202, 87, 15, 114, 66, 34, 135, 153,
]);

const SESSION_WALLET = Keypair.fromSecretKey(SECRET_KEY);
const DESTINATION = new PublicKey('7BLHKsHRGjsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf');
const TOKEN_MINT = new PublicKey('4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R');
const TOKEN_ACCOUNT = new PublicKey('BejFKxkxepeBEeMcbxTBFgxJz23e39u8Qz9ft2KExzrW');

// Use your Helius RPC (replace with actual key)
const RPC_URL = process.env.SOLANA_RPC_URL || 'https://api.mainnet-beta.solana.com';
const connection = new Connection(RPC_URL, 'confirmed');

console.log('='.repeat(60));
console.log('SESSION WALLET RECOVERY');
console.log('='.repeat(60));
console.log('Session Wallet:', SESSION_WALLET.publicKey.toBase58());
console.log('Destination:', DESTINATION.toBase58());
console.log('Token to sell:', TOKEN_MINT.toBase58());
console.log('Token Account:', TOKEN_ACCOUNT.toBase58());
console.log('');

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForConfirmation(signature) {
  console.log('Confirming transaction:', signature);
  const startTime = Date.now();

  while (Date.now() - startTime < 60000) {
    try {
      const status = await connection.getSignatureStatus(signature);
      if (status?.value?.confirmationStatus === 'confirmed' || status?.value?.confirmationStatus === 'finalized') {
        console.log('✅ Transaction confirmed');
        return true;
      }
    } catch (err) {
      // Ignore
    }
    await sleep(2000);
  }

  console.log('⚠️  Confirmation timeout (but tx may still land)');
  return false;
}

async function step1_checkAndFund() {
  console.log('\n[STEP 1] Check SOL balance and fund if needed');
  console.log('-'.repeat(60));

  const balance = await connection.getBalance(SESSION_WALLET.publicKey);
  const balanceSol = balance / LAMPORTS_PER_SOL;

  console.log('Current balance:', balanceSol, 'SOL');

  if (balance < 0.005 * LAMPORTS_PER_SOL) {
    console.log('⚠️  Insufficient SOL for transactions');
    console.log('');
    console.log('MANUAL ACTION REQUIRED:');
    console.log('Send ~0.01 SOL to:', SESSION_WALLET.publicKey.toBase58());
    console.log('');
    console.log('After funding, run this script again.');
    process.exit(1);
  }

  console.log('✅ Sufficient SOL for operations');
  return balance;
}

async function step2_sellToken() {
  console.log('\n[STEP 2] Sell token via Jupiter');
  console.log('-'.repeat(60));

  // Get token balance
  const tokenAccountInfo = await connection.getParsedAccountInfo(TOKEN_ACCOUNT);
  const tokenBalance = tokenAccountInfo.value.data.parsed.info.tokenAmount.amount;

  console.log('Token balance:', tokenBalance, 'raw units (4.075013 tokens)');

  // Get Jupiter quote
  console.log('Fetching Jupiter quote...');
  const quoteUrl = `https://quote-api.jup.ag/v6/quote?inputMint=${TOKEN_MINT.toBase58()}&outputMint=So11111111111111111111111111111111111111112&amount=${tokenBalance}&slippageBps=500`;

  const quoteResponse = await fetch(quoteUrl);
  const quoteData = await quoteResponse.json();

  if (!quoteData || quoteData.error) {
    console.log('❌ Jupiter quote failed:', quoteData?.error || 'Unknown error');
    return false;
  }

  const outAmountSol = quoteData.outAmount / LAMPORTS_PER_SOL;
  console.log('Expected output:', outAmountSol, 'SOL (~$' + (outAmountSol * 200).toFixed(2) + ' USD at $200/SOL)');

  // Get swap transaction
  console.log('Building swap transaction...');
  const swapResponse = await fetch('https://quote-api.jup.ag/v6/swap', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      quoteResponse: quoteData,
      userPublicKey: SESSION_WALLET.publicKey.toBase58(),
      wrapAndUnwrapSol: true,
      dynamicComputeUnitLimit: true,
      prioritizationFeeLamports: 'auto',
    }),
  });

  const swapData = await swapResponse.json();

  if (!swapData.swapTransaction) {
    console.log('❌ Failed to build swap transaction');
    return false;
  }

  // Deserialize and sign
  const swapTxBuf = Buffer.from(swapData.swapTransaction, 'base64');
  const tx = VersionedTransaction.deserialize(swapTxBuf);
  tx.sign([SESSION_WALLET]);

  console.log('Sending swap transaction...');
  const signature = await connection.sendRawTransaction(tx.serialize(), {
    skipPreflight: false,
    preflightCommitment: 'confirmed',
  });

  console.log('Swap signature:', signature);
  await waitForConfirmation(signature);

  return true;
}

async function step3_closeTokenAccount() {
  console.log('\n[STEP 3] Close token account (recover rent)');
  console.log('-'.repeat(60));

  // Check if account still has tokens
  try {
    const accountInfo = await connection.getParsedAccountInfo(TOKEN_ACCOUNT);
    const balance = accountInfo.value.data.parsed.info.tokenAmount.uiAmount;

    if (balance > 0) {
      console.log('❌ Token account still has', balance, 'tokens. Cannot close.');
      return false;
    }
  } catch (err) {
    console.log('⚠️  Could not read token account (may already be closed)');
    return false;
  }

  console.log('Building close account transaction...');

  const closeIx = createCloseAccountInstruction(
    TOKEN_ACCOUNT,
    SESSION_WALLET.publicKey, // Rent goes back to owner
    SESSION_WALLET.publicKey, // Owner
    [],
    TOKEN_PROGRAM_ID
  );

  const blockhash = await connection.getLatestBlockhash('confirmed');
  const messageV0 = new TransactionMessage({
    payerKey: SESSION_WALLET.publicKey,
    recentBlockhash: blockhash.blockhash,
    instructions: [closeIx],
  }).compileToV0Message();

  const tx = new VersionedTransaction(messageV0);
  tx.sign([SESSION_WALLET]);

  console.log('Sending close account transaction...');
  const signature = await connection.sendRawTransaction(tx.serialize(), {
    skipPreflight: false,
    preflightCommitment: 'confirmed',
  });

  console.log('Close account signature:', signature);
  await waitForConfirmation(signature);
  console.log('✅ Recovered ~0.00203928 SOL rent');

  return true;
}

async function step4_sweepToDestination() {
  console.log('\n[STEP 4] Sweep all SOL to destination');
  console.log('-'.repeat(60));

  const balance = await connection.getBalance(SESSION_WALLET.publicKey);
  console.log('Current balance:', (balance / LAMPORTS_PER_SOL).toFixed(6), 'SOL');

  // Leave 5000 lamports for tx fee (account will close to 0)
  const FEE = 5000;
  const sweepAmount = balance - FEE;

  if (sweepAmount <= 0) {
    console.log('❌ No SOL to sweep');
    return false;
  }

  console.log('Sweeping', (sweepAmount / LAMPORTS_PER_SOL).toFixed(6), 'SOL to', DESTINATION.toBase58());

  const transferIx = SystemProgram.transfer({
    fromPubkey: SESSION_WALLET.publicKey,
    toPubkey: DESTINATION,
    lamports: sweepAmount,
  });

  const blockhash = await connection.getLatestBlockhash('confirmed');
  const messageV0 = new TransactionMessage({
    payerKey: SESSION_WALLET.publicKey,
    recentBlockhash: blockhash.blockhash,
    instructions: [transferIx],
  }).compileToV0Message();

  const tx = new VersionedTransaction(messageV0);
  tx.sign([SESSION_WALLET]);

  console.log('Sending sweep transaction...');
  const signature = await connection.sendRawTransaction(tx.serialize(), {
    skipPreflight: false,
    preflightCommitment: 'confirmed',
  });

  console.log('Sweep signature:', signature);
  await waitForConfirmation(signature);
  console.log('✅ Sweep complete - account closed to 0 SOL');

  return true;
}

async function main() {
  try {
    await step1_checkAndFund();
    await sleep(2000);

    await step2_sellToken();
    await sleep(5000);

    await step3_closeTokenAccount();
    await sleep(5000);

    await step4_sweepToDestination();

    console.log('\n' + '='.repeat(60));
    console.log('✅ RECOVERY COMPLETE');
    console.log('='.repeat(60));
    console.log('Check destination wallet:', DESTINATION.toBase58());
  } catch (err) {
    console.error('\n❌ Error:', err.message);
    console.error(err);
    process.exit(1);
  }
}

main();
