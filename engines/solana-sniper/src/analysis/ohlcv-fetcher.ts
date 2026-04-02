import axios from 'axios';
import { createModuleLogger } from '../utils/logger.js';

const log = createModuleLogger('ohlcv-fetcher');

export interface OHLCVCandle {
  timestamp: number;  // unix ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TokenOHLCV {
  mint: string;
  poolAddress: string;
  candles: OHLCVCandle[];
  timeframe: string;  // '5m', '15m', '1h'
}

// Rate limit: max 30 requests/min for GeckoTerminal
const RATE_LIMIT_MS = 4200; // ~14 req/min — GeckoTerminal free tier is aggressive with 429s
let lastFetch = 0;

async function rateLimitedFetch<T>(fn: () => Promise<T>): Promise<T> {
  const now = Date.now();
  const elapsed = now - lastFetch;
  if (elapsed < RATE_LIMIT_MS) {
    await new Promise(r => setTimeout(r, RATE_LIMIT_MS - elapsed));
  }
  lastFetch = Date.now();
  return fn();
}

/**
 * Fetch 5-minute OHLCV candles for a token from GeckoTerminal.
 * Returns up to 48 candles (4 hours of data).
 */
export async function fetchOHLCV(poolAddress: string, timeframeMinutes: number = 5): Promise<OHLCVCandle[]> {
  const aggregate = timeframeMinutes;
  const limit = Math.min(Math.floor(240 / timeframeMinutes), 100); // max 4h of data

  try {
    const resp = await rateLimitedFetch(() =>
      axios.get(
        `https://api.geckoterminal.com/api/v2/networks/solana/pools/${poolAddress}/ohlcv/minute?aggregate=${aggregate}&limit=${limit}`,
        { timeout: 8000 }
      )
    );

    const data = resp.data?.data?.attributes?.ohlcv_list ?? [];

    return data.map((c: number[]) => ({
      timestamp: c[0] * 1000,
      open: c[1],
      high: c[2],
      low: c[3],
      close: c[4],
      volume: c[5],
    }));
  } catch (err) {
    log.warn('OHLCV fetch failed', { pool: poolAddress, error: (err as Error).message });
    return [];
  }
}

/**
 * Get pool address for a token from DexScreener.
 * Returns the most liquid Solana pool address.
 */
export async function getPoolAddress(tokenMint: string): Promise<string | null> {
  try {
    const resp = await rateLimitedFetch(() =>
      axios.get(
        `https://api.dexscreener.com/latest/dex/tokens/${tokenMint}`,
        { timeout: 5000 }
      )
    );

    const pairs = (resp.data?.pairs ?? [])
      .filter((p: any) => p.chainId === 'solana')
      .sort((a: any, b: any) => (b.liquidity?.usd ?? 0) - (a.liquidity?.usd ?? 0));

    return pairs[0]?.pairAddress ?? null;
  } catch {
    return null;
  }
}

/**
 * Convert OHLCV candles to checkpoint format used by the backtester.
 * Each candle generates 3 checkpoints based on open-to-close direction:
 *   - Bullish (close >= open): low, high, close
 *   - Bearish (close < open):  high, low, close
 *
 * Offsets within each candle window: +0.5min, +3min, +4.5min
 */
export function ohlcvToCheckpoints(
  candles: OHLCVCandle[],
  startTime: number,  // ms since token creation
): Array<{ price: number; timeMin: number }> {
  const checkpoints: Array<{ price: number; timeMin: number }> = [];

  for (const candle of candles) {
    const timeMin = (candle.timestamp - startTime) / 60000;
    if (timeMin < 0) continue;
    if (timeMin > 240) break;

    // Determine if bullish or bearish candle
    const isBullish = candle.close >= candle.open;

    if (isBullish) {
      // Bullish: open -> low -> high -> close
      checkpoints.push({ price: candle.low, timeMin: timeMin + 0.5 });
      checkpoints.push({ price: candle.high, timeMin: timeMin + 3 });
      checkpoints.push({ price: candle.close, timeMin: timeMin + 4.5 });
    } else {
      // Bearish: open -> high -> low -> close
      checkpoints.push({ price: candle.high, timeMin: timeMin + 0.5 });
      checkpoints.push({ price: candle.low, timeMin: timeMin + 3 });
      checkpoints.push({ price: candle.close, timeMin: timeMin + 4.5 });
    }
  }

  return checkpoints.sort((a, b) => a.timeMin - b.timeMin);
}

/**
 * Fetch OHLCV data for multiple tokens in batch.
 * Respects rate limits and returns a Map of mint -> checkpoints.
 */
export async function fetchBatchOHLCV(
  tokens: Array<{ mint: string; poolAddress?: string; createdAt: number }>,
  maxTokens: number = 50,
): Promise<Map<string, Array<{ price: number; timeMin: number }>>> {
  const results = new Map<string, Array<{ price: number; timeMin: number }>>();
  const toFetch = tokens.slice(0, maxTokens);

  log.info('Fetching OHLCV candles', { tokens: toFetch.length });

  let fetched = 0;
  for (const token of toFetch) {
    let poolAddr = token.poolAddress;

    // Get pool address if not provided
    if (!poolAddr) {
      poolAddr = await getPoolAddress(token.mint) ?? undefined;
      if (!poolAddr) continue;
    }

    const candles = await fetchOHLCV(poolAddr, 5);
    if (candles.length > 0) {
      const checkpoints = ohlcvToCheckpoints(candles, token.createdAt);
      if (checkpoints.length > 0) {
        results.set(token.mint, checkpoints);
        fetched++;
      }
    }
  }

  log.info('OHLCV fetch complete', { fetched, total: toFetch.length });
  return results;
}
