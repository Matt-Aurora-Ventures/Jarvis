// Burn all tokens and close all Token-2022 accounts, then send SOL to destination
import { Connection, Keypair, PublicKey, VersionedTransaction, TransactionMessage, SystemProgram } from "@solana/web3.js";
import { createCloseAccountInstruction, createBurnInstruction } from "@solana/spl-token";

const RPC = "https://mainnet.helius-rpc.com/?api-key=9b0285c5-30f7-44b3-93da-2241f5637f01";
const SECRET_KEY = new Uint8Array([249,103,173,85,48,176,94,59,152,129,98,44,42,76,18,57,77,114,39,253,7,130,201,238,94,137,145,220,167,55,19,16,59,118,10,45,177,76,182,27,208,149,181,181,112,104,243,178,54,154,245,143,92,211,154,239,83,92,206,196,51,110,63,99]);
const DEST = new PublicKey("7BLHKsHRGjsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf");
const TOKEN_2022_PROGRAM_ID = new PublicKey("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb");

const connection = new Connection(RPC, "confirmed");
const keypair = Keypair.fromSecretKey(SECRET_KEY);

console.log("=== BURN & CLOSE ===");
console.log("Wallet:", keypair.publicKey.toBase58());

const balance = await connection.getBalance(keypair.publicKey);
console.log(`SOL Balance: ${balance / 1e9} SOL`);

if (balance < 5000) {
  console.log("ERROR: Not enough SOL for gas. Send ~0.005 SOL to this wallet first.");
  process.exit(1);
}

// Get all Token-2022 accounts
const tokenAccounts = await connection.getParsedTokenAccountsByOwner(
  keypair.publicKey,
  { programId: TOKEN_2022_PROGRAM_ID }
);

console.log(`\nFound ${tokenAccounts.value.length} Token-2022 accounts`);

// Batch burn + close into transactions (max 4 accounts per tx to fit compute)
const batches = [];
let batch = [];
for (const ta of tokenAccounts.value) {
  batch.push(ta);
  if (batch.length >= 3) {
    batches.push(batch);
    batch = [];
  }
}
if (batch.length > 0) batches.push(batch);

console.log(`Processing ${batches.length} batches...\n`);

let totalClosed = 0;
let totalFailed = 0;

for (let i = 0; i < batches.length; i++) {
  const currentBatch = batches[i];
  console.log(`--- Batch ${i + 1}/${batches.length} (${currentBatch.length} accounts) ---`);

  const instructions = [];

  for (const ta of currentBatch) {
    const info = ta.account.data.parsed.info;
    const rawAmount = BigInt(info.tokenAmount.amount);
    const mint = new PublicKey(info.mint);
    const decimals = info.tokenAmount.decimals;

    if (rawAmount > 0n) {
      console.log(`  Burning ${info.tokenAmount.uiAmount} of ${info.mint}`);
      instructions.push(
        createBurnInstruction(
          ta.pubkey,           // account
          mint,                // mint
          keypair.publicKey,   // owner
          rawAmount,           // amount
          [],                  // multiSigners
          TOKEN_2022_PROGRAM_ID,
        )
      );
    }

    console.log(`  Closing ${ta.pubkey.toBase58()}`);
    instructions.push(
      createCloseAccountInstruction(
        ta.pubkey,
        keypair.publicKey, // destination for rent
        keypair.publicKey, // authority
        [],
        TOKEN_2022_PROGRAM_ID,
      )
    );
  }

  try {
    const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash("confirmed");
    const msg = new TransactionMessage({
      payerKey: keypair.publicKey,
      recentBlockhash: blockhash,
      instructions,
    }).compileToV0Message();

    const tx = new VersionedTransaction(msg);
    tx.sign([keypair]);

    const sig = await connection.sendRawTransaction(tx.serialize(), {
      skipPreflight: false,
      maxRetries: 3,
    });
    console.log(`  TX: ${sig}`);

    const conf = await connection.confirmTransaction(
      { signature: sig, blockhash, lastValidBlockHeight },
      "confirmed"
    );

    if (conf.value.err) {
      console.log(`  FAILED: ${JSON.stringify(conf.value.err)}`);
      totalFailed += currentBatch.length;
    } else {
      console.log(`  CONFIRMED!`);
      totalClosed += currentBatch.length;
    }

    await new Promise(r => setTimeout(r, 1000));
  } catch (e) {
    console.log(`  Error: ${e.message}`);
    totalFailed += currentBatch.length;

    // If batch fails, try one by one
    console.log("  Retrying individually...");
    for (const ta of currentBatch) {
      const info = ta.account.data.parsed.info;
      const rawAmount = BigInt(info.tokenAmount.amount);
      const mint = new PublicKey(info.mint);

      const ixs = [];
      if (rawAmount > 0n) {
        ixs.push(createBurnInstruction(ta.pubkey, mint, keypair.publicKey, rawAmount, [], TOKEN_2022_PROGRAM_ID));
      }
      ixs.push(createCloseAccountInstruction(ta.pubkey, keypair.publicKey, keypair.publicKey, [], TOKEN_2022_PROGRAM_ID));

      try {
        const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash("confirmed");
        const msg = new TransactionMessage({
          payerKey: keypair.publicKey,
          recentBlockhash: blockhash,
          instructions: ixs,
        }).compileToV0Message();
        const soloTx = new VersionedTransaction(msg);
        soloTx.sign([keypair]);
        const sig = await connection.sendRawTransaction(soloTx.serialize(), { skipPreflight: false, maxRetries: 3 });
        const conf = await connection.confirmTransaction({ signature: sig, blockhash, lastValidBlockHeight }, "confirmed");
        if (conf.value.err) {
          console.log(`    ${ta.pubkey.toBase58()}: FAILED`);
        } else {
          console.log(`    ${ta.pubkey.toBase58()}: CLOSED (${sig})`);
          totalClosed++;
          totalFailed--;
        }
        await new Promise(r => setTimeout(r, 500));
      } catch (e2) {
        console.log(`    ${ta.pubkey.toBase58()}: ERROR ${e2.message}`);
      }
    }
  }
}

console.log(`\nClosed: ${totalClosed}, Failed: ${totalFailed}`);

// Wait for balance to settle
await new Promise(r => setTimeout(r, 3000));

// Verify no more token accounts
const remaining = await connection.getParsedTokenAccountsByOwner(
  keypair.publicKey,
  { programId: TOKEN_2022_PROGRAM_ID }
);
console.log(`Remaining token accounts: ${remaining.value.length}`);

// Send all SOL to destination
const finalBal = await connection.getBalance(keypair.publicKey);
console.log(`\nFinal SOL: ${finalBal / 1e9} SOL`);

const fee = 5000;
const sendAmount = finalBal - fee;

if (sendAmount <= 0) {
  console.log("Not enough SOL to send after fees");
  process.exit(0);
}

console.log(`Sending ${sendAmount / 1e9} SOL to ${DEST.toBase58()}...`);

const { blockhash: sendBh, lastValidBlockHeight: sendLvbh } = await connection.getLatestBlockhash("confirmed");
const sendMsg = new TransactionMessage({
  payerKey: keypair.publicKey,
  recentBlockhash: sendBh,
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

const sendSig = await connection.sendRawTransaction(sendTx.serialize(), { skipPreflight: false, maxRetries: 3 });
console.log(`Transfer TX: ${sendSig}`);
const sendConf = await connection.confirmTransaction({ signature: sendSig, blockhash: sendBh, lastValidBlockHeight: sendLvbh }, "confirmed");

if (sendConf.value.err) {
  console.log(`Transfer FAILED: ${JSON.stringify(sendConf.value.err)}`);
} else {
  console.log("Transfer CONFIRMED!");
}

const endBal = await connection.getBalance(keypair.publicKey);
console.log(`\nWallet final balance: ${endBal / 1e9} SOL`);
console.log("=== SWEEP COMPLETE ===");
