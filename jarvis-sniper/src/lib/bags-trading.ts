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
import { Buffer } from 'buffer';
import { waitForSignatureStatus } from '@/lib/tx-confirmation';
import { withTimeout } from '@/lib/async-timeout';

export const SOL_MINT = 'So11111111111111111111111111111111111111112';
const SOL_DECIMALS = 9;
const SELL_QUOTE_TIMEOUT_MS = 15_000;
const SELL_SWAP_BUILD_TIMEOUT_MS = 30_000;
const SELL_SEND_TIMEOUT_MS = 25_000;
const SELL_CONFIRM_TIMEOUT_MS = 90_000;
const JITO_POST_TIMEOUT_MS = 10_000;

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
  /** Confirmation outcome for the submitted signature, when known. */
  confirmationState?: 'confirmed' | 'failed' | 'unresolved';
  /** Normalized failure type for retry/backoff policies. */
  failureCode?: 'insufficient_signer_sol' | 'slippage_limit' | 'onchain_failed' | 'unresolved' | 'rpc_error';
  /** Additional failure context from RPC/server responses. */
  failureDetail?: string;
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
    const swapController = new AbortController();
    const swapTimeout = setTimeout(() => swapController.abort(), 30_000); // 30s timeout
    let res: Response;
    try {
      res = await fetch('/api/bags/swap', {
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
        signal: swapController.signal,
      });
    } finally {
      clearTimeout(swapTimeout);
    }

    if (!res.ok) {
      const err = await safeReadJson(res);
      const errorMessage = String(err?.error || err?.message || `Server swap request failed (${res.status})`);
      const failureCode =
        normalizeFailureCode(errorMessage, err?.code) ||
        (res.status === 409 ? 'insufficient_signer_sol' : 'rpc_error');
      return {
        success: false, inputAmount: amountSol, outputAmount: 0, priceImpact: 0,
        error: errorMessage,
        failureCode,
        failureDetail: errorMessage,
        timestamp,
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

    // 3. Replace stale server blockhash with a fresh one.
    // The Bags SDK embeds a blockhash when building the tx on the server.
    // By the time it reaches the client (network round trip + SDK processing),
    // that blockhash can be 10-30s old. On a busy network it expires before landing.
    const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash('confirmed');
    transaction.message.recentBlockhash = blockhash;

    // 4. Sign with fresh blockhash (tx is unsigned from server, safe to mutate)
    const signedTx = await signTransaction(transaction);

    // 5. Send to network
    let txHash: string;
    if (useJito) {
      txHash = await sendWithJito(signedTx, connection);
    } else {
      txHash = await connection.sendRawTransaction(signedTx.serialize(), {
        skipPreflight: false,
        maxRetries: 3,
      });
    }

    // 6. Confirm with blockhash-based polling (HTTP, no WebSocket needed)
    const confirmResult = await confirmWithFallback(connection, txHash, blockhash, lastValidBlockHeight);
    if (confirmResult.state === 'failed') {
      const detail = confirmResult.errorDetail || 'On-chain failure';
      const failureCode = normalizeFailureCode(detail) || 'onchain_failed';
      return {
        success: false, txHash, inputAmount: amountSol, outputAmount: 0,
        confirmationState: 'failed',
        failureCode,
        failureDetail: detail,
        priceImpact: parseFloat(quote.priceImpactPct || '0'),
        error: detail,
        timestamp,
      };
    }
    if (confirmResult.state === 'unresolved') {
      return {
        success: false, txHash, inputAmount: amountSol, outputAmount: 0,
        confirmationState: 'unresolved',
        failureCode: 'unresolved',
        failureDetail: confirmResult.errorDetail || 'Transaction sent but not confirmed on-chain',
        priceImpact: parseFloat(quote.priceImpactPct || '0'),
        error: 'Transaction sent but not confirmed on-chain',
        timestamp,
      };
    }

    const outputDecimals = getMintDecimalsFromQuote(quote as SwapQuote, outputMint) ?? 9;
    const outputAmountLamports = String(quote.outAmount);
    const outputAmount = uiAmountFromRaw(outputAmountLamports, outputDecimals);

    console.log(`[Bags Proxy] Swap ${confirmResult.state === 'confirmed' ? 'confirmed' : 'assumed'}: ${txHash}`);
    return {
      success: true, txHash, inputAmount: amountSol, outputAmount, outputAmountLamports,
      confirmationState: 'confirmed',
      priceImpact: parseFloat(quote.priceImpactPct || '0'), timestamp,
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    if (msg.includes('User rejected') || msg.includes('user rejected')) {
      return { success: false, inputAmount: amountSol, outputAmount: 0, priceImpact: 0, error: 'Transaction rejected by user', timestamp };
    }
    const failureCode = normalizeFailureCode(msg) || 'rpc_error';
    return {
      success: false,
      inputAmount: amountSol,
      outputAmount: 0,
      priceImpact: 0,
      error: msg,
      failureCode,
      failureDetail: msg,
      timestamp,
    };
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
    const quoteController = new AbortController();
    const quoteTimeout = setTimeout(() => quoteController.abort(), SELL_QUOTE_TIMEOUT_MS);
    let res: Response;
    try {
      res = await fetch('/api/bags/quote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // Keep amount as string to avoid accidental float rounding in JS callers.
        body: JSON.stringify({ inputMint: tokenMint, outputMint: SOL_MINT, amount: amountLamports, slippageBps }),
        signal: quoteController.signal,
      });
    } finally {
      clearTimeout(quoteTimeout);
    }
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
    const swapController = new AbortController();
    const swapTimeout = setTimeout(() => swapController.abort(), SELL_SWAP_BUILD_TIMEOUT_MS);
    let res: Response;
    try {
      res = await fetch('/api/bags/swap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quote,
          userPublicKey: walletAddress,
          priorityFeeMicroLamports,
        }),
        signal: swapController.signal,
      });
    } finally {
      clearTimeout(swapTimeout);
    }

    if (!res.ok) {
      const err = await safeReadJson(res);
      const errorMessage = String(err?.error || err?.message || `Server swap request failed (${res.status})`);
      const failureCode =
        normalizeFailureCode(errorMessage, err?.code) ||
        (res.status === 409 ? 'insufficient_signer_sol' : 'rpc_error');
      return {
        success: false, inputAmount: 0, outputAmount: 0,
        priceImpact: parseFloat(quote.priceImpactPct || '0'),
        error: errorMessage,
        failureCode,
        failureDetail: errorMessage,
        timestamp,
      };
    }

    const { transaction: txBase64 } = await res.json();
    const transaction = VersionedTransaction.deserialize(
      new Uint8Array(Buffer.from(txBase64, 'base64')),
    );

    // Replace stale server blockhash with a fresh one (same fix as buy flow)
    const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash('confirmed');
    transaction.message.recentBlockhash = blockhash;

    // Sign with fresh blockhash
    const signedTx = await signTransaction(transaction);

    // Send to network
    let txHash: string;
    if (useJito) {
      txHash = await sendWithJito(signedTx, connection);
    } else {
      txHash = await withTimeout(
        connection.sendRawTransaction(signedTx.serialize(), {
          skipPreflight: false,
          maxRetries: 3,
        }),
        SELL_SEND_TIMEOUT_MS,
        'Sell send timeout',
      );
    }

    // Confirm with blockhash-based polling + fallback signature check
    const confirmResult = await confirmWithFallback(connection, txHash, blockhash, lastValidBlockHeight);
    if (confirmResult.state === 'failed') {
      const detail = confirmResult.errorDetail || 'On-chain failure';
      const failureCode = normalizeFailureCode(detail) || 'onchain_failed';
      return {
        success: false, txHash, inputAmount: 0, outputAmount: 0,
        confirmationState: 'failed',
        failureCode,
        failureDetail: detail,
        priceImpact: parseFloat(quote.priceImpactPct || '0'),
        error: detail,
        timestamp,
      };
    }
    if (confirmResult.state === 'unresolved') {
      return {
        success: false, txHash, inputAmount: 0, outputAmount: 0,
        confirmationState: 'unresolved',
        failureCode: 'unresolved',
        failureDetail: confirmResult.errorDetail || 'Transaction sent but not confirmed on-chain',
        priceImpact: parseFloat(quote.priceImpactPct || '0'),
        error: 'Transaction sent but not confirmed on-chain',
        timestamp,
      };
    }

    const outputAmountLamports = String(quote.outAmount);
    const outputDecimals = getMintDecimalsFromQuote(quote, SOL_MINT) ?? SOL_DECIMALS;
    const outputAmount = uiAmountFromRaw(outputAmountLamports, outputDecimals);

    return {
      success: true, txHash,
      confirmationState: 'confirmed',
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
    const failureCode = normalizeFailureCode(msg) || 'rpc_error';
    return {
      success: false,
      inputAmount: 0,
      outputAmount: 0,
      priceImpact: 0,
      error: msg,
      failureCode,
      failureDetail: msg,
      timestamp,
    };
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
// Confirmation with fallback signature check
// ============================================================

/**
 * Confirm a transaction with graceful fallback.
 * If the primary confirm fails (block height exceeded / timeout),
 * we do a final getSignatureStatus check to see if the tx actually landed.
 * Returns 'confirmed' | 'failed' | 'unresolved' (tx was sent, final state unknown).
 */
async function confirmWithFallback(
  connection: Connection,
  txHash: string,
  _blockhash: string,
  _lastValidBlockHeight: number,
): Promise<{ state: 'confirmed' | 'failed' | 'unresolved'; errorDetail?: string }> {
  try {
    const status = await waitForSignatureStatus(connection, txHash, {
      maxWaitMs: SELL_CONFIRM_TIMEOUT_MS,
      pollMs: 2500,
    });
    if (status.state === 'confirmed') return { state: 'confirmed' };
    if (status.state === 'failed') return { state: 'failed', errorDetail: status.error };
    if (status.state === 'unresolved') {
      return { state: 'unresolved', errorDetail: status.error };
    }
  } catch {
    // ignore and run one final best-effort check below
  }

  // Final best-effort signature status check
  try {
    const statuses = await connection.getSignatureStatuses([txHash], { searchTransactionHistory: true });
    const status = statuses?.value?.[0];
    if (status?.err) {
      return {
        state: 'failed',
        errorDetail: typeof status.err === 'string' ? status.err : JSON.stringify(status.err),
      };
    }
    if (status?.confirmationStatus === 'confirmed' || status?.confirmationStatus === 'finalized') {
      return { state: 'confirmed' };
    }
  } catch {
    // ignore
  }
  // Transaction was sent but finality is still unknown.
  return { state: 'unresolved', errorDetail: `No final signature status within ${SELL_CONFIRM_TIMEOUT_MS}ms` };
}

// ============================================================
// Jito MEV Bundle Submission
// ============================================================

async function sendWithJito(tx: VersionedTransaction, connection: Connection): Promise<string> {
  const serialized = Buffer.from(tx.serialize()).toString('base64');
  for (const endpoint of JITO_ENDPOINTS) {
    try {
      const jitoController = new AbortController();
      const jitoTimeout = setTimeout(() => jitoController.abort(), JITO_POST_TIMEOUT_MS);
      let res: Response;
      try {
        res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0', id: 1,
            method: 'sendTransaction',
            params: [serialized, { encoding: 'base64' }],
          }),
          signal: jitoController.signal,
        });
      } finally {
        clearTimeout(jitoTimeout);
      }
      const result = await res.json();
      if (result.result) return result.result;
    } catch { /* try next endpoint */ }
  }
  // Fallback to standard RPC
  return await withTimeout(
    connection.sendRawTransaction(tx.serialize(), {
      skipPreflight: false,
      maxRetries: 3,
    }),
    SELL_SEND_TIMEOUT_MS,
    'Fallback sendRawTransaction timeout',
  );
}

async function safeReadJson(res: Response): Promise<any> {
  try {
    return await res.json();
  } catch {
    return {};
  }
}

function normalizeFailureCode(
  message: string | undefined,
  explicitCode?: string,
): SwapResult['failureCode'] | undefined {
  const msg = String(message || '').toLowerCase();
  const code = String(explicitCode || '').toLowerCase();

  if (code === 'insufficient_signer_sol' || code === 'insufficient_signer_balance') return 'insufficient_signer_sol';
  if (code === 'slippage_limit') return 'slippage_limit';
  if (code === 'unresolved') return 'unresolved';
  if (code === 'onchain_failed') return 'onchain_failed';
  if (code === 'rpc_error') return 'rpc_error';

  if (msg.includes('insufficient_signer_sol') || msg.includes('insufficient signer sol')) return 'insufficient_signer_sol';
  // Bags/PumpSwap slippage failures can appear as custom Anchor/Solana errors.
  // Keep this map explicit so auto-snipe uses the slippage retry ladder.
  if (
    msg.includes('15001') ||
    msg.includes('slippagelimitexceeded') ||
    msg.includes('slippage') ||
    msg.includes('"custom":3005') ||
    msg.includes('custom:3005') ||
    msg.includes('custom 3005')
  ) return 'slippage_limit';
  if (msg.includes('not confirmed on-chain') || msg.includes('unresolved')) return 'unresolved';
  if (msg.includes('on-chain failure') || msg.includes('transaction failed')) return 'onchain_failed';
  if (msg) return 'rpc_error';
  return undefined;
}
