import axios from 'axios';
import { VersionedTransaction, Connection } from '@solana/web3.js';
import bs58 from 'bs58';
import { getWallet, getConnection } from '../utils/wallet.js';
import { createModuleLogger } from '../utils/logger.js';
import { config } from '../config/index.js';

const log = createModuleLogger('bags-client');

const BAGS_API_BASE = 'https://public-api-v2.bags.fm/api/v1';
const WSOL_MINT = 'So11111111111111111111111111111111111111112';

interface BagsQuoteResponse {
  requestId: string;
  contextSlot: number;
  inAmount: string;
  inputMint: string;
  outAmount: string;
  outputMint: string;
  minOutAmount: string;
  priceImpactPct: string;
  slippageBps: number;
  routePlan: Array<{
    venue: string;
    inAmount: string;
    outAmount: string;
    inputMint: string;
    outputMint: string;
  }>;
  platformFee: {
    amount: string;
    feeBps: number;
    feeAccount: string;
  };
}

interface BagsSwapResponse {
  swapTransaction: string;
  computeUnitLimit: number;
  lastValidBlockHeight: number;
  prioritizationFeeLamports: number;
}

interface BagsApiResponse<T> {
  success: boolean;
  response?: T;
  error?: string;
}

function getHeaders(): Record<string, string> {
  const apiKey = config.bagsApiKey;
  if (!apiKey) throw new Error('BAGS_API_KEY not configured');
  return {
    'x-api-key': apiKey,
    'Content-Type': 'application/json',
  };
}

// ─── Get trade quote ────────────────────────────────────────
export async function getBagsQuote(params: {
  inputMint: string;
  outputMint: string;
  amountLamports: number;
  slippageBps?: number;
}): Promise<BagsQuoteResponse> {
  const { inputMint, outputMint, amountLamports, slippageBps } = params;

  const queryParams = new URLSearchParams({
    inputMint,
    outputMint,
    amount: amountLamports.toString(),
    slippageMode: slippageBps ? 'manual' : 'auto',
  });
  if (slippageBps) queryParams.set('slippageBps', slippageBps.toString());

  const resp = await axios.get<BagsApiResponse<BagsQuoteResponse>>(
    `${BAGS_API_BASE}/trade/quote?${queryParams.toString()}`,
    { headers: getHeaders(), timeout: 10000 },
  );

  if (!resp.data.success || !resp.data.response) {
    throw new Error(`Bags quote failed: ${resp.data.error ?? 'unknown'}`);
  }

  log.info('Bags quote received', {
    inputMint: inputMint.slice(0, 8),
    outputMint: outputMint.slice(0, 8),
    inAmount: resp.data.response.inAmount,
    outAmount: resp.data.response.outAmount,
    priceImpact: resp.data.response.priceImpactPct + '%',
    slippage: resp.data.response.slippageBps + 'bps',
  });

  return resp.data.response;
}

// ─── Create swap transaction ────────────────────────────────
export async function createBagsSwap(
  quoteResponse: BagsQuoteResponse,
): Promise<BagsSwapResponse> {
  const wallet = getWallet();

  const resp = await axios.post<BagsApiResponse<BagsSwapResponse>>(
    `${BAGS_API_BASE}/trade/swap`,
    {
      quoteResponse,
      userPublicKey: wallet.publicKey.toBase58(),
    },
    { headers: getHeaders(), timeout: 15000 },
  );

  if (!resp.data.success || !resp.data.response) {
    throw new Error(`Bags swap create failed: ${resp.data.error ?? 'unknown'}`);
  }

  log.info('Bags swap transaction created', {
    computeUnits: resp.data.response.computeUnitLimit,
    priorityFee: resp.data.response.prioritizationFeeLamports,
    blockHeight: resp.data.response.lastValidBlockHeight,
  });

  return resp.data.response;
}

// ─── Sign and send transaction ──────────────────────────────
export async function signAndSendBagsSwap(
  swapResponse: BagsSwapResponse,
): Promise<string> {
  const wallet = getWallet();
  const conn = getConnection();

  // Deserialize the transaction
  const txBytes = bs58.decode(swapResponse.swapTransaction);
  const tx = VersionedTransaction.deserialize(txBytes);

  // Sign with our wallet
  tx.sign([wallet]);

  // Re-serialize
  const signedTx = bs58.encode(tx.serialize());

  // Send via Bags API for best routing
  const resp = await axios.post<BagsApiResponse<string>>(
    `${BAGS_API_BASE}/solana/send-transaction`,
    { transaction: signedTx },
    { headers: getHeaders(), timeout: 30000 },
  );

  if (!resp.data.success || !resp.data.response) {
    // Fallback: send via RPC
    log.warn('Bags send failed, trying RPC fallback', { error: resp.data.error });
    const txSig = await conn.sendRawTransaction(tx.serialize(), {
      skipPreflight: true,
      maxRetries: 2,
    });
    log.info('Transaction sent via RPC fallback', { signature: txSig.slice(0, 16) });
    return txSig;
  }

  log.info('Transaction sent via Bags', { signature: resp.data.response.slice(0, 16) });
  return resp.data.response;
}

// ─── High-level buy function ────────────────────────────────
export async function buyTokenViaBags(params: {
  tokenMint: string;
  amountSolLamports: number;
  slippageBps?: number;
}): Promise<{ signature: string; outAmount: string; priceImpact: string }> {
  const { tokenMint, amountSolLamports, slippageBps = 300 } = params;

  log.info('Buying via Bags', {
    token: tokenMint.slice(0, 8),
    solAmount: (amountSolLamports / 1e9).toFixed(4),
    slippage: slippageBps + 'bps',
  });

  // 1. Get quote
  const quote = await getBagsQuote({
    inputMint: WSOL_MINT,
    outputMint: tokenMint,
    amountLamports: amountSolLamports,
    slippageBps,
  });

  // 2. Create swap tx
  const swap = await createBagsSwap(quote);

  // 3. Sign and send
  const signature = await signAndSendBagsSwap(swap);

  return {
    signature,
    outAmount: quote.outAmount,
    priceImpact: quote.priceImpactPct,
  };
}

// ─── High-level sell function ───────────────────────────────
export async function sellTokenViaBags(params: {
  tokenMint: string;
  amountTokenLamports: number;
  slippageBps?: number;
}): Promise<{ signature: string; outAmount: string; priceImpact: string }> {
  const { tokenMint, amountTokenLamports, slippageBps = 500 } = params;

  log.info('Selling via Bags', {
    token: tokenMint.slice(0, 8),
    tokenAmount: amountTokenLamports.toString(),
    slippage: slippageBps + 'bps',
  });

  // 1. Get quote (sell token for SOL)
  const quote = await getBagsQuote({
    inputMint: tokenMint,
    outputMint: WSOL_MINT,
    amountLamports: amountTokenLamports,
    slippageBps,
  });

  // 2. Create swap tx
  const swap = await createBagsSwap(quote);

  // 3. Sign and send
  const signature = await signAndSendBagsSwap(swap);

  return {
    signature,
    outAmount: quote.outAmount,
    priceImpact: quote.priceImpactPct,
  };
}

// ─── TP/SL monitor (runs in background) ────────────────────
export interface StopOrder {
  tokenMint: string;
  entryPriceUsd: number;
  amountTokenLamports: number;
  takeProfitPct: number;
  stopLossPct: number;
  trailingStopPct?: number;
  createdAt: number;
  status: 'ACTIVE' | 'TP_HIT' | 'SL_HIT' | 'TRAILING_HIT' | 'CANCELLED';
  highWaterMark: number; // highest price seen for trailing stop
}

const activeOrders: Map<string, StopOrder> = new Map();

export function createStopOrder(order: Omit<StopOrder, 'status' | 'highWaterMark' | 'createdAt'>): StopOrder {
  const fullOrder: StopOrder = {
    ...order,
    status: 'ACTIVE',
    highWaterMark: order.entryPriceUsd,
    createdAt: Date.now(),
  };
  activeOrders.set(order.tokenMint, fullOrder);
  log.info('Stop order created', {
    token: order.tokenMint.slice(0, 8),
    entry: '$' + order.entryPriceUsd.toFixed(6),
    tp: order.takeProfitPct + '%',
    sl: order.stopLossPct + '%',
    trailing: order.trailingStopPct ? order.trailingStopPct + '%' : 'off',
  });
  return fullOrder;
}

export async function checkStopOrders(
  getCurrentPrice: (mint: string) => Promise<number>,
): Promise<void> {
  for (const [mint, order] of activeOrders) {
    if (order.status !== 'ACTIVE') continue;

    try {
      const currentPrice = await getCurrentPrice(mint);
      const pnlPct = ((currentPrice - order.entryPriceUsd) / order.entryPriceUsd) * 100;

      // Update high water mark
      if (currentPrice > order.highWaterMark) {
        order.highWaterMark = currentPrice;
      }

      // Check take profit
      if (pnlPct >= order.takeProfitPct) {
        log.info('Take profit hit!', { token: mint.slice(0, 8), pnl: pnlPct.toFixed(1) + '%' });
        order.status = 'TP_HIT';
        try {
          await sellTokenViaBags({ tokenMint: mint, amountTokenLamports: order.amountTokenLamports });
        } catch (err) {
          log.error('TP sell failed', { error: (err as Error).message });
          order.status = 'ACTIVE'; // retry next check
        }
        continue;
      }

      // Check stop loss
      if (pnlPct <= -order.stopLossPct) {
        log.info('Stop loss hit!', { token: mint.slice(0, 8), pnl: pnlPct.toFixed(1) + '%' });
        order.status = 'SL_HIT';
        try {
          await sellTokenViaBags({ tokenMint: mint, amountTokenLamports: order.amountTokenLamports });
        } catch (err) {
          log.error('SL sell failed', { error: (err as Error).message });
          order.status = 'ACTIVE';
        }
        continue;
      }

      // Check trailing stop
      if (order.trailingStopPct) {
        const drawdownFromPeak = ((order.highWaterMark - currentPrice) / order.highWaterMark) * 100;
        if (drawdownFromPeak >= order.trailingStopPct && pnlPct > 0) {
          log.info('Trailing stop hit!', {
            token: mint.slice(0, 8),
            pnl: pnlPct.toFixed(1) + '%',
            drawdown: drawdownFromPeak.toFixed(1) + '%',
          });
          order.status = 'TRAILING_HIT';
          try {
            await sellTokenViaBags({ tokenMint: mint, amountTokenLamports: order.amountTokenLamports });
          } catch (err) {
            log.error('Trailing sell failed', { error: (err as Error).message });
            order.status = 'ACTIVE';
          }
        }
      }
    } catch (err) {
      log.warn('Price check failed for stop order', { token: mint.slice(0, 8), error: (err as Error).message });
    }
  }
}

export function getActiveOrders(): StopOrder[] {
  return [...activeOrders.values()].filter(o => o.status === 'ACTIVE');
}

export function cancelOrder(mint: string): boolean {
  const order = activeOrders.get(mint);
  if (order && order.status === 'ACTIVE') {
    order.status = 'CANCELLED';
    return true;
  }
  return false;
}
