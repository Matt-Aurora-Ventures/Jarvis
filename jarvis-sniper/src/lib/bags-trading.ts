/**
 * Solana Swap Execution — Bags.fm only
 *
 * BUYS/SELLS → /api/bags/* server proxy (Bags SDK, priority fees, no CORS)
 *
 * The server proxy handles:
 * - Bags SDK execution (bypasses CORS)
 * - Priority fee injection (prevents timeouts like $MAD)
 */

import { Connection, VersionedTransaction } from '@solana/web3.js';

export const SOL_MINT = 'So11111111111111111111111111111111111111112';
const SOL_DECIMALS = 9;

export interface SwapQuote {
  inputMint: string;
  outputMint: string;
  inAmount: string;
  outAmount: string;
  minOutAmount?: string;
  otherAmountThreshold: string;
  priceImpactPct: string;
  routePlan?: Array<{
    inAmount: string;
    inputMint: string;
    inputMintDecimals: number;
    outAmount: string;
    outputMint: string;
    outputMintDecimals: number;
    venue?: string;
    marketKey?: string;
    data?: string;
  }>;
  slippageBps?: number;
  requestId?: string;
}

export interface SwapResult {
  success: boolean;
  txHash?: string;
  inputAmount: number;
  outputAmount: number;
  /** Raw out amount in smallest units (use for sells / exact accounting). */
  outputAmountLamports?: string;
  priceImpact: number;
  error?: string;
  timestamp: number;
}

// Jito MEV bundle submission
const JITO_ENDPOINTS = [
  'https://mainnet.block-engine.jito.wtf/api/v1/transactions',
  'https://amsterdam.mainnet.block-engine.jito.wtf/api/v1/transactions',
  'https://frankfurt.mainnet.block-engine.jito.wtf/api/v1/transactions',
];

// ============================================================
// BUY FLOW — via server proxy (Bags SDK, partner key, priority fees)
// ============================================================

/**
 * Get a quote via server proxy (Bags SDK).
 */
export async function getQuote(
  inputMint: string,
  outputMint: string,
  amountSol: number,
  slippageBps = 100,
): Promise<SwapQuote | null> {
  const lamports = Math.floor(amountSol * 1e9);

  // 1. Bags server proxy (primary)
  try {
    const res = await fetch('/api/bags/quote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ inputMint, outputMint, amount: lamports, slippageBps }),
    });
    if (res.ok) {
      const data = await res.json();
      return data.quote;
    }
    console.warn('[Bags Proxy] Quote failed:', res.status);
  } catch (err) {
    console.warn('[Bags Proxy] Quote exception:', err);
  }
  return null;
}

/**
 * Execute a buy swap via server proxy.
 * Server builds tx with Bags SDK + partner key + priority fees.
 * Client signs with Phantom and sends to network.
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
  const lamports = Math.floor(amountSol * 1e9);

  try {
    // 1. Get quote + transaction from server proxy (includes priority fees)
    console.log(`[Bags Proxy] Swap: ${amountSol} SOL → ${outputMint.slice(0, 8)}...`);
    const res = await fetch('/api/bags/swap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        inputMint,
        outputMint,
        amount: lamports,
        slippageBps,
        userPublicKey: walletAddress,
        priorityFeeMicroLamports: 200_000,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      return {
        success: false, inputAmount: amountSol, outputAmount: 0, priceImpact: 0,
        error: err.error || 'Server swap request failed', timestamp,
      };
    }

    const { transaction: txBase64, quote } = await res.json();

    if (!quote || !quote.outAmount || quote.outAmount === '0') {
      return {
        success: false, inputAmount: amountSol, outputAmount: 0, priceImpact: 0,
        error: 'No route found — token may not be tradeable yet', timestamp,
      };
    }

    console.log(`[Bags Proxy] Quote: ${quote.inAmount} → ${quote.outAmount} (impact: ${quote.priceImpactPct}%)`);

    // 2. Deserialize transaction from base64
    const transaction = VersionedTransaction.deserialize(
      new Uint8Array(Buffer.from(txBase64, 'base64')),
    );

    // 3. Sign with Phantom
    const signedTx = await signTransaction(transaction);

    // 4. Send to network
    let txHash: string;
    if (useJito) {
      txHash = await sendWithJito(signedTx, connection);
    } else {
      txHash = await connection.sendRawTransaction(signedTx.serialize(), {
        skipPreflight: true,
        maxRetries: 3,
      });
    }

    // 5. Confirm with 90s timeout (use 'confirmed' for speed, not 'finalized')
    const confirmPromise = connection.confirmTransaction(txHash, 'confirmed');
    const confirmTimeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error(`TX confirmation timeout (90s): ${txHash}`)), 90_000)
    );
    const confirmation = await Promise.race([confirmPromise, confirmTimeout]) as Awaited<ReturnType<typeof connection.confirmTransaction>>;
    if (confirmation.value.err) {
      return {
        success: false, txHash, inputAmount: amountSol, outputAmount: 0,
        priceImpact: parseFloat(quote.priceImpactPct || '0'), error: 'On-chain failure', timestamp,
      };
    }

    const outputDecimals = getMintDecimalsFromQuote(quote as SwapQuote, outputMint) ?? 9;
    const outputAmountLamports = String(quote.outAmount);
    const outputAmount = uiAmountFromRaw(outputAmountLamports, outputDecimals);

    console.log(`[Bags Proxy] Swap confirmed: ${txHash}`);
    return {
      success: true, txHash, inputAmount: amountSol, outputAmount, outputAmountLamports,
      priceImpact: parseFloat(quote.priceImpactPct || '0'), timestamp,
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    if (msg.includes('User rejected') || msg.includes('user rejected')) {
      return { success: false, inputAmount: amountSol, outputAmount: 0, priceImpact: 0, error: 'Transaction rejected by user', timestamp };
    }
    return { success: false, inputAmount: amountSol, outputAmount: 0, priceImpact: 0, error: msg, timestamp };
  }
}

// ============================================================
// SELL FLOW — via server proxy (Bags SDK, no client API keys)
// ============================================================

/**
 * Get a sell quote (Token→SOL) via the server proxy (Bags SDK).
 * Used by the risk management loop to check exit value.
 */
export async function getSellQuote(
  tokenMint: string,
  amountLamports: string,
  slippageBps = 200,
): Promise<SwapQuote | null> {
  try {
    const res = await fetch('/api/bags/quote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      // Keep amount as string to avoid accidental float rounding in JS callers.
      body: JSON.stringify({ inputMint: tokenMint, outputMint: SOL_MINT, amount: amountLamports, slippageBps }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.quote;
  } catch {
    return null;
  }
}

/**
 * Execute a sell from a pre-fetched quote.
 * Used by the SL/TP loop to execute immediately.
 * Uses Bags server proxy to build the tx.
 */
export async function executeSwapFromQuote(
  connection: Connection,
  walletAddress: string,
  quote: SwapQuote,
  signTransaction: (tx: VersionedTransaction) => Promise<VersionedTransaction>,
  useJito = false,
  priorityFeeMicroLamports: number = 200_000,
): Promise<SwapResult> {
  const timestamp = Date.now();

  try {
    // Build tx on server via Bags SDK (bypasses CORS and keeps API key server-only)
    const res = await fetch('/api/bags/swap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        quote,
        userPublicKey: walletAddress,
        priorityFeeMicroLamports,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return {
        success: false, inputAmount: 0, outputAmount: 0,
        priceImpact: parseFloat(quote.priceImpactPct || '0'),
        error: err.error || 'Server swap request failed', timestamp,
      };
    }

    const { transaction: txBase64 } = await res.json();
    const transaction = VersionedTransaction.deserialize(
      new Uint8Array(Buffer.from(txBase64, 'base64')),
    );

    // Sign with Phantom
    const signedTx = await signTransaction(transaction);

    // Send to network
    let txHash: string;
    if (useJito) {
      txHash = await sendWithJito(signedTx, connection);
    } else {
      txHash = await connection.sendRawTransaction(signedTx.serialize(), {
        skipPreflight: true,
        maxRetries: 3,
      });
    }

    // Confirm
    const confirmation = await connection.confirmTransaction(txHash, 'confirmed');
    if (confirmation.value.err) {
      return {
        success: false, txHash, inputAmount: 0, outputAmount: 0,
        priceImpact: parseFloat(quote.priceImpactPct || '0'), error: 'On-chain failure', timestamp,
      };
    }

    const outputAmountLamports = String(quote.outAmount);
    const outputDecimals = getMintDecimalsFromQuote(quote, SOL_MINT) ?? SOL_DECIMALS;
    const outputAmount = uiAmountFromRaw(outputAmountLamports, outputDecimals);

    return {
      success: true, txHash,
      inputAmount: 0,
      outputAmount,
      outputAmountLamports,
      priceImpact: parseFloat(quote.priceImpactPct || '0'),
      timestamp,
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    if (msg.includes('User rejected') || msg.includes('user rejected')) {
      return { success: false, inputAmount: 0, outputAmount: 0, priceImpact: 0, error: 'Transaction rejected by user', timestamp };
    }
    return { success: false, inputAmount: 0, outputAmount: 0, priceImpact: 0, error: msg, timestamp };
  }
}

function getMintDecimalsFromQuote(quote: SwapQuote, mint: string): number | null {
  const plan = quote.routePlan;
  if (!Array.isArray(plan) || plan.length === 0) return null;

  // Prefer an exact match on the mint in route plan legs.
  for (const leg of plan) {
    if (leg?.outputMint === mint && typeof leg.outputMintDecimals === 'number') {
      return leg.outputMintDecimals;
    }
  }
  for (const leg of plan) {
    if (leg?.inputMint === mint && typeof leg.inputMintDecimals === 'number') {
      return leg.inputMintDecimals;
    }
  }

  // Fallback: last leg output decimals (usually equals quote.outputMint decimals)
  const last = plan[plan.length - 1];
  if (last && typeof last.outputMintDecimals === 'number') return last.outputMintDecimals;

  return null;
}

function uiAmountFromRaw(amountLamports: string, decimals: number): number {
  try {
    const amt = BigInt(amountLamports);
    if (decimals <= 0) return Number(amt);
    const base = BigInt(10) ** BigInt(decimals);
    const whole = amt / base;
    const frac = amt % base;
    const fracStr = frac.toString().padStart(decimals, '0').slice(0, 6); // 6dp is enough for UI
    return Number(`${whole.toString()}.${fracStr}`);
  } catch {
    return 0;
  }
}

// ============================================================
// Jito MEV Bundle Submission
// ============================================================

async function sendWithJito(tx: VersionedTransaction, connection: Connection): Promise<string> {
  const serialized = Buffer.from(tx.serialize()).toString('base64');
  for (const endpoint of JITO_ENDPOINTS) {
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0', id: 1,
          method: 'sendTransaction',
          params: [serialized, { encoding: 'base64' }],
        }),
      });
      const result = await res.json();
      if (result.result) return result.result;
    } catch { /* try next endpoint */ }
  }
  // Fallback to standard RPC
  return await connection.sendRawTransaction(tx.serialize());
}
