/**
 * Solana Swap Execution — Jupiter v6 API (primary) + Bags.fm (fallback)
 *
 * Jupiter v6 is the standard Solana swap aggregator.
 * No API key required. Routes across Raydium, Orca, Meteora, etc.
 */

import { Connection, VersionedTransaction } from '@solana/web3.js';

export const SOL_MINT = 'So11111111111111111111111111111111111111112';

export interface SwapQuote {
  inputMint: string;
  outputMint: string;
  inAmount: string;
  outAmount: string;
  otherAmountThreshold: string;
  priceImpactPct: string;
  routePlan: any[];
}

export interface SwapResult {
  success: boolean;
  txHash?: string;
  inputAmount: number;
  outputAmount: number;
  priceImpact: number;
  error?: string;
  timestamp: number;
}

// Jupiter v6 API — the standard, no auth needed
const JUPITER_QUOTE = 'https://quote-api.jup.ag/v6/quote';
const JUPITER_SWAP = 'https://quote-api.jup.ag/v6/swap';

// Bags.fm fallback
const BAGS_TRADE_API = 'https://public-api-v2.bags.fm/api/v1';

const JITO_ENDPOINTS = [
  'https://mainnet.block-engine.jito.wtf/api/v1/transactions',
  'https://amsterdam.mainnet.block-engine.jito.wtf/api/v1/transactions',
  'https://frankfurt.mainnet.block-engine.jito.wtf/api/v1/transactions',
];

/**
 * Get swap quote from Jupiter v6, falling back to Bags.fm
 */
export async function getQuote(
  inputMint: string,
  outputMint: string,
  amountSol: number,
  slippageBps = 100,
): Promise<SwapQuote | null> {
  // Try Jupiter v6 first
  const jupiterQuote = await getJupiterQuote(inputMint, outputMint, amountSol, slippageBps);
  if (jupiterQuote) return jupiterQuote;

  // Fallback to Bags.fm
  const bagsQuote = await getBagsQuote(inputMint, outputMint, amountSol, slippageBps);
  return bagsQuote;
}

async function getJupiterQuote(
  inputMint: string,
  outputMint: string,
  amountSol: number,
  slippageBps: number,
): Promise<SwapQuote | null> {
  try {
    const lamports = Math.floor(amountSol * 1e9);
    const params = new URLSearchParams({
      inputMint,
      outputMint,
      amount: lamports.toString(),
      slippageBps: slippageBps.toString(),
      swapMode: 'ExactIn',
    });

    const res = await fetch(`${JUPITER_QUOTE}?${params}`, {
      headers: { 'Accept': 'application/json' },
    });

    if (!res.ok) {
      console.warn('[Jupiter] Quote failed:', res.status, await res.text().catch(() => ''));
      return null;
    }

    const data = await res.json();
    if (data.error) {
      console.warn('[Jupiter] Quote error:', data.error);
      return null;
    }

    return data as SwapQuote;
  } catch (err) {
    console.warn('[Jupiter] Quote exception:', err);
    return null;
  }
}

async function getBagsQuote(
  inputMint: string,
  outputMint: string,
  amountSol: number,
  slippageBps: number,
): Promise<SwapQuote | null> {
  try {
    const lamports = Math.floor(amountSol * 1e9);
    const params = new URLSearchParams({
      inputMint,
      outputMint,
      amount: lamports.toString(),
      slippageMode: 'manual',
      slippageBps: slippageBps.toString(),
    });

    const res = await fetch(`${BAGS_TRADE_API}/trade/quote?${params}`, {
      headers: { 'Accept': 'application/json' },
    });

    if (!res.ok) {
      console.warn('[Bags] Quote failed:', res.status);
      return null;
    }

    const result = await res.json();
    return result.success ? result.response : null;
  } catch {
    return null;
  }
}

/**
 * Execute swap: get quote → build tx → sign with wallet → send to Solana
 */
export async function executeSwap(
  connection: Connection,
  walletAddress: string,
  inputMint: string,
  outputMint: string,
  amountSol: number,
  slippageBps: number,
  signTransaction: (tx: VersionedTransaction) => Promise<VersionedTransaction>,
  useJito = false,
): Promise<SwapResult> {
  const timestamp = Date.now();
  try {
    // 1. Get quote (Jupiter first, Bags.fm fallback)
    const quote = await getQuote(inputMint, outputMint, amountSol, slippageBps);
    if (!quote) {
      return { success: false, inputAmount: amountSol, outputAmount: 0, priceImpact: 0, error: 'No route found — token may not be tradeable yet', timestamp };
    }

    // 2. Get serialized swap transaction
    const swapTxBase64 = await getSwapTransaction(walletAddress, quote);
    if (!swapTxBase64) {
      return { success: false, inputAmount: amountSol, outputAmount: 0, priceImpact: parseFloat(quote.priceImpactPct || '0'), error: 'Swap transaction build failed', timestamp };
    }

    // 3. Deserialize and sign with Phantom
    const txBuffer = Buffer.from(swapTxBase64, 'base64');
    const transaction = VersionedTransaction.deserialize(txBuffer);
    const signedTx = await signTransaction(transaction);

    // 4. Send to network
    let txHash: string;
    if (useJito) {
      txHash = await sendWithJito(signedTx, connection);
    } else {
      txHash = await connection.sendRawTransaction(signedTx.serialize(), { skipPreflight: true, maxRetries: 3 });
    }

    // 5. Confirm
    const confirmation = await connection.confirmTransaction(txHash, 'confirmed');
    if (confirmation.value.err) {
      return { success: false, txHash, inputAmount: amountSol, outputAmount: 0, priceImpact: parseFloat(quote.priceImpactPct || '0'), error: 'On-chain failure', timestamp };
    }

    // Calculate output amount (outAmount is in token's smallest unit — assume 6 or 9 decimals)
    const rawOut = parseInt(quote.outAmount);
    // For most Solana tokens, decimals vary. We'll use the raw value / 1e6 as a rough estimate.
    // The position's real value comes from price tracking anyway.
    const outputAmount = rawOut > 1e12 ? rawOut / 1e9 : rawOut / 1e6;

    return { success: true, txHash, inputAmount: amountSol, outputAmount, priceImpact: parseFloat(quote.priceImpactPct || '0'), timestamp };
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    // User rejected in Phantom
    if (msg.includes('User rejected') || msg.includes('user rejected')) {
      return { success: false, inputAmount: amountSol, outputAmount: 0, priceImpact: 0, error: 'Transaction rejected by user', timestamp };
    }
    return { success: false, inputAmount: amountSol, outputAmount: 0, priceImpact: 0, error: msg, timestamp };
  }
}

/**
 * Get serialized swap transaction from Jupiter or Bags.fm
 */
async function getSwapTransaction(walletAddress: string, quote: SwapQuote): Promise<string | null> {
  // Try Jupiter v6 swap endpoint first
  try {
    const res = await fetch(JUPITER_SWAP, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        quoteResponse: quote,
        userPublicKey: walletAddress,
        wrapAndUnwrapSol: true,
        dynamicComputeUnitLimit: true,
        prioritizationFeeLamports: 'auto',
      }),
    });

    if (res.ok) {
      const data = await res.json();
      if (data.swapTransaction) return data.swapTransaction;
    }
  } catch (err) {
    console.warn('[Jupiter] Swap tx build failed:', err);
  }

  // Fallback: Bags.fm swap endpoint
  try {
    const res = await fetch(`${BAGS_TRADE_API}/trade/swap`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userPublicKey: walletAddress, quoteResponse: quote }),
    });

    if (res.ok) {
      const data = await res.json();
      if (data.success && data.response?.swapTransaction) return data.response.swapTransaction;
    }
  } catch {
    // silent
  }

  return null;
}

async function sendWithJito(tx: VersionedTransaction, connection: Connection): Promise<string> {
  const serialized = Buffer.from(tx.serialize()).toString('base64');
  for (const endpoint of JITO_ENDPOINTS) {
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'sendTransaction', params: [serialized, { encoding: 'base64' }] }),
      });
      const result = await res.json();
      if (result.result) return result.result;
    } catch { /* try next endpoint */ }
  }
  // Fallback to standard RPC
  return await connection.sendRawTransaction(tx.serialize());
}
