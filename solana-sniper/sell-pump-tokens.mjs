// Try to sell pump.fun tokens via Jupiter standard API and pump.fun API
import { Connection, Keypair, PublicKey, VersionedTransaction, TransactionMessage } from "@solana/web3.js";
import { TOKEN_PROGRAM_ID, createCloseAccountInstruction, createBurnInstruction } from "@solana/spl-token";

const RPC = "https://mainnet.helius-rpc.com/?api-key=9b0285c5-30f7-44b3-93da-2241f5637f01";
const SECRET_KEY = new Uint8Array([249,103,173,85,48,176,94,59,152,129,98,44,42,76,18,57,77,114,39,253,7,130,201,238,94,137,145,220,167,55,19,16,59,118,10,45,177,76,182,27,208,149,181,181,112,104,243,178,54,154,245,143,92,211,154,239,83,92,206,196,51,110,63,99]);
const SOL_MINT = "So11111111111111111111111111111111111111112";
const TOKEN_2022_PROGRAM_ID = new PublicKey("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb");

const connection = new Connection(RPC, "confirmed");
const keypair = Keypair.fromSecretKey(SECRET_KEY);

const tokens = [
  { mint: "8YezvFMcnVX3E9MNSWqPVmsTf4snhx9Hado8xcoUpump", amount: "6001613286", account: "D4cpxe39oS6PbWUVPVGKgDt6LSfiiY5qioSCao82Tpfc" },
  { mint: "72Ed2QEAbZkbRqJ5vhciuyhGbDqpkh1BE98cuMeepump", amount: "780831232", account: "5DLkGGoNqX16NRkaBUiVewYVxnnVciVeLmJXpGNo9wDG" },
  { mint: "V6e9AvFGp1hqE7HZBkTar8t1C7JorqZxaa5iS6kpump", amount: "108945281", account: "7GKyX8DpXtk5Ro4PvS3Zxt77p7Djj9Z7BQ42EiDqxgLs" },
  { mint: "vHXy4HyKLuds72QAM45QZZPzaRvGfKuY6VqXbvMpump", amount: "63655133", account: "DQGzDEXLHxvZwuSWC8DYziBin3BFUDgKxHS6jRp8uR2k" },
  { mint: "Bq9D4BbhVR4kL1qSdsYpQ5JM59q2LzUYzv7zFA1epump", amount: "49938574", account: "2BazR8WTgSU6BjSNATbg3h9x23umtvkNupSE519xFAFe" },
  { mint: "C2AfR223EfWBhFSZXdCkBb68er3mRsZJnafAmqZKpump", amount: "4281237", account: "BjoYvXvihxiGRwSQ6mouJTg7Uaexuc6KJSNt44nrjYCe" },
  { mint: "FpuZM7Nwdy9Tk4eJcvyFumB8iQbHr5pBLJrvTqRSpump", amount: "458865", account: "E9eyYaRGtGP8zgX38k73z8LVbgkqGZuJ5818C372Kbpj" },
  { mint: "EfbHN4cQZEaQUcqcUReWFq5ANKGkEfhqRP2WWKRmpump", amount: "395970", account: "Cc5Sa15HjPvELP8xyAip7iGZBHyM2G98qSPBeKLyUBqU" },
];

console.log("=== PUMP TOKEN SELL ATTEMPT ===");
console.log("Wallet:", keypair.publicKey.toBase58());
console.log(`SOL balance: ${(await connection.getBalance(keypair.publicKey)) / 1e9} SOL`);
console.log("");

// Try Jupiter standard API (not lite)
console.log("--- Trying Jupiter Standard API ---");
for (const token of tokens) {
  try {
    // Try the standard Jupiter quote API
    const url = `https://quote-api.jup.ag/v6/quote?inputMint=${token.mint}&outputMint=${SOL_MINT}&amount=${token.amount}&slippageBps=1000`;
    const resp = await fetch(url);
    const data = await resp.json();

    if (data.error || !data.outAmount) {
      console.log(`${token.mint}: No route on Jupiter v6 (${data.error || 'no outAmount'})`);
    } else {
      console.log(`${token.mint}: ${Number(data.outAmount) / 1e9} SOL via Jupiter v6!`);
    }
  } catch (e) {
    console.log(`${token.mint}: Error - ${e.message}`);
  }
}

console.log("");

// Try pump.fun sell API
console.log("--- Trying Pump.fun Trade API ---");
for (const token of tokens) {
  try {
    const resp = await fetch("https://pumpportal.fun/api/trade-local", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        publicKey: keypair.publicKey.toBase58(),
        action: "sell",
        mint: token.mint,
        amount: token.amount,
        denominatedInSol: "false",
        slippage: 50, // 50% slippage for illiquid tokens
        priorityFee: 0.0001,
        pool: "pump",
      }),
    });

    if (!resp.ok) {
      const errText = await resp.text();
      console.log(`${token.mint}: Pump API error ${resp.status} - ${errText.substring(0, 100)}`);
      continue;
    }

    // pumpportal returns a transaction to sign
    const data = await resp.arrayBuffer();
    if (data.byteLength < 100) {
      const text = new TextDecoder().decode(data);
      console.log(`${token.mint}: Pump API response too small - ${text}`);
      continue;
    }

    const tx = VersionedTransaction.deserialize(new Uint8Array(data));
    tx.sign([keypair]);

    const sig = await connection.sendRawTransaction(tx.serialize(), {
      skipPreflight: true,
      maxRetries: 3,
    });
    console.log(`${token.mint}: Sell tx sent: ${sig}`);

    const conf = await connection.confirmTransaction(sig, "confirmed");
    if (conf.value.err) {
      console.log(`  FAILED: ${JSON.stringify(conf.value.err)}`);
    } else {
      console.log(`  CONFIRMED! Sold successfully`);
    }

    await new Promise(r => setTimeout(r, 2000));
  } catch (e) {
    console.log(`${token.mint}: ${e.message}`);
  }
}

console.log("");
console.log("--- Checking remaining accounts ---");
await new Promise(r => setTimeout(r, 3000));

const remaining = await connection.getParsedTokenAccountsByOwner(
  keypair.publicKey,
  { programId: TOKEN_2022_PROGRAM_ID }
);

const nonZero = remaining.value.filter(ta => ta.account.data.parsed.info.tokenAmount.amount !== "0");
const zero = remaining.value.filter(ta => ta.account.data.parsed.info.tokenAmount.amount === "0");

console.log(`Remaining accounts: ${remaining.value.length} (${nonZero.length} with balance, ${zero.length} empty)`);

// Close empty accounts
for (const ta of zero) {
  try {
    const closeIx = createCloseAccountInstruction(
      ta.pubkey, keypair.publicKey, keypair.publicKey, [], TOKEN_2022_PROGRAM_ID
    );
    const { blockhash } = await connection.getLatestBlockhash("confirmed");
    const msg = new TransactionMessage({
      payerKey: keypair.publicKey,
      recentBlockhash: blockhash,
      instructions: [closeIx],
    }).compileToV0Message();
    const closeTx = new VersionedTransaction(msg);
    closeTx.sign([keypair]);
    const sig = await connection.sendRawTransaction(closeTx.serialize());
    const conf = await connection.confirmTransaction(sig, "confirmed");
    console.log(`Closed empty account: ${ta.pubkey.toBase58()} - ${conf.value.err ? 'FAILED' : 'OK'}`);
    await new Promise(r => setTimeout(r, 500));
  } catch (e) {
    console.log(`Error closing ${ta.pubkey.toBase58()}: ${e.message}`);
  }
}

// Report non-zero accounts
if (nonZero.length > 0) {
  console.log("\nAccounts that still have tokens:");
  for (const ta of nonZero) {
    const info = ta.account.data.parsed.info;
    console.log(`  ${info.mint}: ${info.tokenAmount.uiAmount} tokens in ${ta.pubkey.toBase58()}`);
  }
}

const finalBal = await connection.getBalance(keypair.publicKey);
console.log(`\nFinal SOL: ${finalBal / 1e9} SOL`);
