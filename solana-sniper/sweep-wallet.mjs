// Sweep session wallet: quote all tokens via Jupiter, swap what's possible, close accounts, send SOL
import { Connection, Keypair, PublicKey, Transaction, SystemProgram, VersionedTransaction, TransactionMessage, ComputeBudgetProgram } from "@solana/web3.js";
import { TOKEN_PROGRAM_ID, createCloseAccountInstruction } from "@solana/spl-token";

const RPC = "https://mainnet.helius-rpc.com/?api-key=9b0285c5-30f7-44b3-93da-2241f5637f01";
const SECRET_KEY = new Uint8Array([249,103,173,85,48,176,94,59,152,129,98,44,42,76,18,57,77,114,39,253,7,130,201,238,94,137,145,220,167,55,19,16,59,118,10,45,177,76,182,27,208,149,181,181,112,104,243,178,54,154,245,143,92,211,154,239,83,92,206,196,51,110,63,99]);
const DEST = new PublicKey("7BLHKsHRGjsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf");
const SOL_MINT = "So11111111111111111111111111111111111111112";
const TOKEN_2022_PROGRAM_ID = new PublicKey("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb");

const connection = new Connection(RPC, "confirmed");
const keypair = Keypair.fromSecretKey(SECRET_KEY);

console.log("=== WALLET SWEEP ===");
console.log("Wallet:", keypair.publicKey.toBase58());
console.log("Destination:", DEST.toBase58());
console.log("");

// Step 1: Get all token accounts
const tokenAccounts = await connection.getParsedTokenAccountsByOwner(
  keypair.publicKey,
  { programId: TOKEN_2022_PROGRAM_ID }
);

const accounts = tokenAccounts.value.map(ta => ({
  pubkey: ta.pubkey,
  mint: ta.account.data.parsed.info.mint,
  rawAmount: ta.account.data.parsed.info.tokenAmount.amount,
  uiAmount: ta.account.data.parsed.info.tokenAmount.uiAmount,
  decimals: ta.account.data.parsed.info.tokenAmount.decimals,
}));

console.log(`Found ${accounts.length} token accounts`);
console.log("");

// Step 2: Try Jupiter quotes for each token with balance
const swappable = [];
const unswappable = [];

for (const acct of accounts) {
  if (acct.rawAmount === "0") {
    console.log(`${acct.mint}: zero balance, will just close`);
    unswappable.push(acct);
    continue;
  }

  try {
    const quoteUrl = `https://lite-api.jup.ag/v1/quote?inputMint=${acct.mint}&outputMint=${SOL_MINT}&amount=${acct.rawAmount}&slippageBps=500&onlyDirectRoutes=false`;
    const resp = await fetch(quoteUrl);

    if (!resp.ok) {
      console.log(`${acct.mint}: no Jupiter route (${resp.status}) - balance: ${acct.uiAmount}`);
      unswappable.push(acct);
      continue;
    }

    const quote = await resp.json();
    if (quote.error || !quote.outAmount) {
      console.log(`${acct.mint}: no liquidity - balance: ${acct.uiAmount}`);
      unswappable.push(acct);
      continue;
    }

    const outSol = Number(quote.outAmount) / 1e9;
    console.log(`${acct.mint}: ${acct.uiAmount} tokens → ${outSol.toFixed(9)} SOL`);
    swappable.push({ ...acct, quote });
  } catch (e) {
    console.log(`${acct.mint}: quote error - ${e.message}`);
    unswappable.push(acct);
  }
}

console.log("");
console.log(`Swappable: ${swappable.length}, Unswappable: ${unswappable.length}`);
console.log("");

// Step 3: Execute swaps via Jupiter
for (const item of swappable) {
  console.log(`Swapping ${item.uiAmount} of ${item.mint}...`);

  try {
    const swapResp = await fetch("https://lite-api.jup.ag/v1/swap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        quoteResponse: item.quote,
        userPublicKey: keypair.publicKey.toBase58(),
        wrapAndUnwrapSol: true,
        dynamicComputeUnitLimit: true,
        prioritizationFeeLamports: "auto",
      }),
    });

    if (!swapResp.ok) {
      const errText = await swapResp.text();
      console.log(`  Swap API error: ${swapResp.status} - ${errText}`);
      unswappable.push(item);
      continue;
    }

    const swapData = await swapResp.json();
    const txBuf = Buffer.from(swapData.swapTransaction, "base64");
    const tx = VersionedTransaction.deserialize(txBuf);
    tx.sign([keypair]);

    const sig = await connection.sendRawTransaction(tx.serialize(), {
      skipPreflight: true,
      maxRetries: 3,
    });
    console.log(`  Sent: ${sig}`);

    // Wait for confirmation
    const confirmation = await connection.confirmTransaction(sig, "confirmed");
    if (confirmation.value.err) {
      console.log(`  FAILED: ${JSON.stringify(confirmation.value.err)}`);
      unswappable.push(item);
    } else {
      console.log(`  CONFIRMED!`);
    }

    // Small delay between swaps
    await new Promise(r => setTimeout(r, 2000));
  } catch (e) {
    console.log(`  Swap error: ${e.message}`);
    unswappable.push(item);
  }
}

console.log("");

// Step 4: Refresh token accounts after swaps
console.log("Refreshing token accounts...");
await new Promise(r => setTimeout(r, 3000));

const refreshedAccounts = await connection.getParsedTokenAccountsByOwner(
  keypair.publicKey,
  { programId: TOKEN_2022_PROGRAM_ID }
);

// Also check standard SPL token accounts
const splAccounts = await connection.getParsedTokenAccountsByOwner(
  keypair.publicKey,
  { programId: TOKEN_PROGRAM_ID }
);

const allAccounts = [
  ...refreshedAccounts.value.map(ta => ({ ...ta, program: TOKEN_2022_PROGRAM_ID })),
  ...splAccounts.value.map(ta => ({ ...ta, program: TOKEN_PROGRAM_ID })),
];

console.log(`Total accounts to close: ${allAccounts.length} (${refreshedAccounts.value.length} Token-2022, ${splAccounts.value.length} SPL)`);

// Step 5: Close accounts with zero balance
let closedCount = 0;
const nonZeroAccounts = [];

for (const ta of allAccounts) {
  const info = ta.account.data.parsed.info;
  const rawAmount = info.tokenAmount.amount;

  if (rawAmount !== "0") {
    console.log(`Cannot close ${ta.pubkey.toBase58()} - still has ${info.tokenAmount.uiAmount} of ${info.mint}`);
    nonZeroAccounts.push(ta);
    continue;
  }

  try {
    const closeIx = createCloseAccountInstruction(
      ta.pubkey,
      keypair.publicKey, // destination for rent
      keypair.publicKey, // authority
      [],
      ta.program,
    );

    const { blockhash } = await connection.getLatestBlockhash("confirmed");
    const msg = new TransactionMessage({
      payerKey: keypair.publicKey,
      recentBlockhash: blockhash,
      instructions: [closeIx],
    }).compileToV0Message();

    const closeTx = new VersionedTransaction(msg);
    closeTx.sign([keypair]);

    const sig = await connection.sendRawTransaction(closeTx.serialize(), {
      skipPreflight: false,
      maxRetries: 3,
    });

    const conf = await connection.confirmTransaction(sig, "confirmed");
    if (conf.value.err) {
      console.log(`Failed to close ${ta.pubkey.toBase58()}: ${JSON.stringify(conf.value.err)}`);
    } else {
      console.log(`Closed: ${ta.pubkey.toBase58()} (${sig})`);
      closedCount++;
    }

    await new Promise(r => setTimeout(r, 500));
  } catch (e) {
    console.log(`Error closing ${ta.pubkey.toBase58()}: ${e.message}`);
  }
}

console.log("");
console.log(`Closed ${closedCount} accounts`);

if (nonZeroAccounts.length > 0) {
  console.log(`${nonZeroAccounts.length} accounts still have balance (need manual swap or dust too small)`);
}

// Step 6: Wait and get final SOL balance
await new Promise(r => setTimeout(r, 3000));
const finalBalance = await connection.getBalance(keypair.publicKey);
console.log("");
console.log(`Final SOL Balance: ${finalBalance / 1e9} SOL (${finalBalance} lamports)`);

// Step 7: Send all SOL to destination (leave 5000 lamports for fee)
const txFee = 5000;
const sendAmount = finalBalance - txFee;

if (sendAmount <= 0) {
  console.log("Not enough SOL to cover transfer fee");
  process.exit(0);
}

console.log(`Sending ${sendAmount / 1e9} SOL to ${DEST.toBase58()}...`);

const { blockhash: sendBlockhash } = await connection.getLatestBlockhash("confirmed");
const sendMsg = new TransactionMessage({
  payerKey: keypair.publicKey,
  recentBlockhash: sendBlockhash,
  instructions: [
    SystemProgram.transfer({
      fromPubkey: keypair.publicKey,
      toPubkey: DEST,
      lamports: sendAmount,
    }),
  ],
}).compileToV0Message();

const sendTx = new VersionedTransaction(sendMsg);
sendTx.sign([keypair]);

const sendSig = await connection.sendRawTransaction(sendTx.serialize(), {
  skipPreflight: false,
  maxRetries: 3,
});

console.log(`Transfer tx: ${sendSig}`);
const sendConf = await connection.confirmTransaction(sendSig, "confirmed");
if (sendConf.value.err) {
  console.log(`Transfer FAILED: ${JSON.stringify(sendConf.value.err)}`);
} else {
  console.log("Transfer CONFIRMED!");
}

// Final check
await new Promise(r => setTimeout(r, 2000));
const remainingBalance = await connection.getBalance(keypair.publicKey);
console.log(`\nRemaining balance: ${remainingBalance / 1e9} SOL`);
console.log("=== SWEEP COMPLETE ===");
