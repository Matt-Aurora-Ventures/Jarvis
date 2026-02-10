/**
 * Historical Data Fetcher — Collect OHLCV candles for backtesting
 *
 * Multi-source OHLCV pipeline:
 *   1. DexScreener chart API (primary)
 *   2. Birdeye public OHLCV API (fallback)
 *   3. Synthetic candles (last resort)
 *
 * Data is cached in localStorage (client-side) for fast repeat backtests.
 * All localStorage access is guarded for server-side (API route) safety.
 *
 * Fulfills: BACK-01 (Historical Data Pipeline)
 */

import type { OHLCVCandle } from './backtest-engine';
import { ALL_BLUECHIPS, type BlueChipToken } from './bluechip-data';

// ─── Types ───

/** Source of OHLCV data: 'dexscreener' | 'birdeye' | 'synthetic' */
export type OHLCVSource = 'dexscreener' | 'birdeye' | 'synthetic';

export interface HistoricalDataSet {
  tokenSymbol: string;
  mintAddress: string;
  pairAddress: string;
  candles: OHLCVCandle[];
  fetchedAt: number;
  source: OHLCVSource;
}

export interface FetchProgress {
  current: number;
  total: number;
  currentToken: string;
  status: 'fetching' | 'cached' | 'error' | 'complete';
}

// ─── DexScreener OHLCV API ───

const DEXSCREENER_PAIRS = 'https://api.dexscreener.com/tokens/v1/solana';
const CACHE_KEY_PREFIX = 'jarvis_ohlcv_';
const CACHE_EXPIRY_MS = 6 * 60 * 60 * 1000; // 6 hours

/**
 * Fetch the best liquidity pair address for a token from DexScreener.
 */
async function fetchBestPair(mintAddress: string): Promise<string | null> {
  try {
    const res = await fetch(`${DEXSCREENER_PAIRS}/${mintAddress}`, {
      headers: { 'Accept': 'application/json' },
    });
    if (!res.ok) return null;

    const pairs: any[] = await res.json();
    if (!pairs || pairs.length === 0) return null;

    // Sort by liquidity, return the best pair
    const sorted = pairs
      .filter((p: any) => p.pairAddress && p.dexId)
      .sort((a: any, b: any) => {
        const aLiq = parseFloat(a.liquidity?.usd || '0');
        const bLiq = parseFloat(b.liquidity?.usd || '0');
        return bLiq - aLiq;
      });

    return sorted[0]?.pairAddress || null;
  } catch {
    return null;
  }
}

/**
 * Fetch OHLCV candles from DexScreener's chart data endpoint.
 *
 * DexScreener provides candlestick data via their chart API.
 * We request 1h candles going back as far as possible.
 */
async function fetchOHLCVFromDexScreener(
  pairAddress: string,
  resolution: string = '60', // 60 = 1 hour
): Promise<OHLCVCandle[]> {
  // DexScreener chart data endpoint
  const url = `https://io.dexscreener.com/dex/chart/amm/v3/solana/${pairAddress}?type=line&tf=${resolution}`;

  try {
    const res = await fetch(url, {
      headers: {
        'Accept': 'application/json',
        'User-Agent': 'Jarvis-Sniper/1.0',
      },
    });

    if (!res.ok) return [];

    const data = await res.json();

    // DexScreener returns bars as arrays: [timestamp, open, high, low, close, volume]
    if (!data?.bars || !Array.isArray(data.bars)) return [];

    return data.bars.map((bar: any) => ({
      timestamp: bar[0] || bar.t || 0,
      open: bar[1] || bar.o || 0,
      high: bar[2] || bar.h || 0,
      low: bar[3] || bar.l || 0,
      close: bar[4] || bar.c || 0,
      volume: bar[5] || bar.v || 0,
    })).filter((c: OHLCVCandle) => c.timestamp > 0 && c.close > 0);
  } catch {
    return [];
  }
}

// ─── Birdeye OHLCV API (Fallback) ───

const BIRDEYE_OHLCV_URL = 'https://public-api.birdeye.so/defi/ohlcv';

/**
 * Fetch OHLCV candles from Birdeye's public API.
 *
 * Works without an API key for basic OHLCV (rate-limited to ~5 req/min).
 * If NEXT_PUBLIC_BIRDEYE_API_KEY is set, uses it for higher rate limits.
 *
 * @returns OHLCVCandle[] — empty array on any error
 */
async function fetchFromBirdeye(
  mintAddress: string,
  timeFrom: number,
  timeTo: number,
): Promise<OHLCVCandle[]> {
  const apiKey =
    (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_BIRDEYE_API_KEY) || '';

  const url =
    `${BIRDEYE_OHLCV_URL}?address=${mintAddress}&type=1H` +
    `&time_from=${timeFrom}&time_to=${timeTo}`;

  const headers: Record<string, string> = {
    Accept: 'application/json',
    'X-API-KEY': apiKey,
  };

  const attempt = async (): Promise<OHLCVCandle[]> => {
    const res = await fetch(url, { headers });

    if (!res.ok) {
      // Surface the status so callers can decide to retry
      const status = res.status;
      console.warn(`[Birdeye] HTTP ${status} for ${mintAddress}`);
      throw new BirdeyeHttpError(status);
    }

    const json = await res.json();
    const items: any[] = json?.data?.items;
    if (!Array.isArray(items) || items.length === 0) return [];

    return items
      .map((item: any) => ({
        timestamp: (item.unixTime ?? 0) * 1000, // Birdeye returns seconds
        open: item.o ?? 0,
        high: item.h ?? 0,
        low: item.l ?? 0,
        close: item.c ?? 0,
        volume: item.v ?? 0,
      }))
      .filter((c: OHLCVCandle) => c.timestamp > 0 && c.close > 0);
  };

  try {
    return await attempt();
  } catch (err) {
    // Retry once on 429 (rate limit) or 5xx after a 3s pause
    if (err instanceof BirdeyeHttpError && (err.status === 429 || err.status >= 500)) {
      await new Promise((r) => setTimeout(r, 3000));
      try {
        return await attempt();
      } catch {
        return [];
      }
    }
    return [];
  }
}

/** Lightweight error class to carry HTTP status through retry logic */
class BirdeyeHttpError extends Error {
  status: number;
  constructor(status: number) {
    super(`Birdeye HTTP ${status}`);
    this.status = status;
  }
}

// ─── Synthetic Data ───

/**
 * Alternative: Generate synthetic OHLCV data from DexScreener's price change data.
 * Used when chart API is unavailable. Creates realistic candles from known statistics.
 */
function generateSyntheticCandles(
  token: BlueChipToken,
  currentPrice: number,
  numCandles: number = 4320, // 6 months of 1h candles
): OHLCVCandle[] {
  const candles: OHLCVCandle[] = [];
  const volatility = token.avgDailyVolatility / 100 / 24; // Per-hour volatility
  const now = Date.now();
  const startTime = now - numCandles * 3600 * 1000;

  let price = currentPrice;

  // Walk backwards to set start price, then forward to generate candles
  for (let i = numCandles; i > 0; i--) {
    // Random walk with mean reversion (Ornstein-Uhlenbeck process)
    const drift = (currentPrice - price) * 0.001; // Mean reversion pull
    const randomReturn = (Math.random() - 0.5) * 2 * volatility;
    price *= (1 + drift + randomReturn);
  }

  // Forward generation
  for (let i = 0; i < numCandles; i++) {
    const timestamp = startTime + i * 3600 * 1000;
    const open = price;

    // Generate realistic intra-candle movement
    const candleVol = volatility * (0.5 + Math.random()); // Variable vol per candle
    const change = (Math.random() - 0.48) * 2 * candleVol; // Slight upward bias
    const close = open * (1 + change);

    // High/low based on volatility
    const range = Math.abs(change) + candleVol * 0.5;
    const high = Math.max(open, close) * (1 + Math.random() * range);
    const low = Math.min(open, close) * (1 - Math.random() * range);

    // Volume: log-normal distribution
    const baseVol = 100000 * (token.mcapTier === 'mega' ? 10 : token.mcapTier === 'large' ? 3 : 1);
    const volume = baseVol * Math.exp((Math.random() - 0.5) * 2);

    candles.push({ timestamp, open, high, low, close, volume });
    price = close;
  }

  return candles;
}

// ─── Cache Management ───

function getCachedData(mintAddress: string): HistoricalDataSet | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    const raw = localStorage.getItem(`${CACHE_KEY_PREFIX}${mintAddress}`);
    if (!raw) return null;
    const data: HistoricalDataSet = JSON.parse(raw);
    if (Date.now() - data.fetchedAt > CACHE_EXPIRY_MS) return null;
    return data;
  } catch {
    return null;
  }
}

function setCachedData(mintAddress: string, data: HistoricalDataSet): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(`${CACHE_KEY_PREFIX}${mintAddress}`, JSON.stringify(data));
  } catch {
    // Storage full — clear old entries
    clearOldCache();
    try {
      localStorage.setItem(`${CACHE_KEY_PREFIX}${mintAddress}`, JSON.stringify(data));
    } catch {
      // Still full, skip caching
    }
  }
}

function clearOldCache(): void {
  if (typeof localStorage === 'undefined') return;
  const keys = Object.keys(localStorage).filter(k => k.startsWith(CACHE_KEY_PREFIX));
  // Remove oldest half
  const toRemove = keys.slice(0, Math.ceil(keys.length / 2));
  for (const key of toRemove) {
    localStorage.removeItem(key);
  }
}

// ─── Public API ───

/**
 * Fetch OHLCV data for a single blue chip token.
 *
 * 3-tier fallback: DexScreener -> Birdeye -> Synthetic
 */
export async function fetchTokenHistory(
  token: BlueChipToken,
  currentPrice?: number,
): Promise<HistoricalDataSet> {
  // Check cache first
  const cached = getCachedData(token.mintAddress);
  if (cached && cached.candles.length > 100) {
    return cached;
  }

  // Tier 1: DexScreener chart API
  const pairAddress = await fetchBestPair(token.mintAddress);
  let candles: OHLCVCandle[] = [];
  let source: OHLCVSource = 'dexscreener';

  if (pairAddress) {
    candles = await fetchOHLCVFromDexScreener(pairAddress);
  }

  // Tier 2: Birdeye OHLCV API (if DexScreener returned insufficient data)
  if (candles.length < 100) {
    const sixMonthsAgo = Math.floor((Date.now() - 180 * 24 * 3600 * 1000) / 1000);
    const nowSec = Math.floor(Date.now() / 1000);
    const birdeyeCandles = await fetchFromBirdeye(token.mintAddress, sixMonthsAgo, nowSec);
    if (birdeyeCandles.length >= 100) {
      candles = birdeyeCandles;
      source = 'birdeye';
    }
  }

  // Tier 3: Synthetic fallback (last resort)
  if (candles.length < 100) {
    const price = currentPrice || (candles.length > 0 ? candles[candles.length - 1].close : 1.0);
    candles = generateSyntheticCandles(token, price);
    source = 'synthetic';
  }

  const dataset: HistoricalDataSet = {
    tokenSymbol: token.ticker,
    mintAddress: token.mintAddress,
    pairAddress: pairAddress || '',
    candles,
    fetchedAt: Date.now(),
    source,
  };

  setCachedData(token.mintAddress, dataset);
  return dataset;
}

/**
 * Fetch OHLCV data for all blue chip tokens.
 * Returns a map of ticker -> HistoricalDataSet.
 *
 * Uses adaptive rate limiting: 500ms between DexScreener-only requests,
 * 1000ms when Birdeye fallback was triggered (respects ~5 req/min limit).
 */
export async function fetchAllBlueChipHistory(
  onProgress?: (progress: FetchProgress) => void,
): Promise<Map<string, HistoricalDataSet>> {
  const results = new Map<string, HistoricalDataSet>();
  const total = ALL_BLUECHIPS.length;
  let lastSourceWasBirdeye = false;

  for (let i = 0; i < total; i++) {
    const token = ALL_BLUECHIPS[i];
    onProgress?.({
      current: i + 1,
      total,
      currentToken: token.ticker,
      status: 'fetching',
    });

    try {
      const data = await fetchTokenHistory(token);
      results.set(token.ticker, data);
      lastSourceWasBirdeye = data.source === 'birdeye';

      onProgress?.({
        current: i + 1,
        total,
        currentToken: token.ticker,
        status: data.source === 'synthetic' ? 'fetching' : 'cached',
      });
    } catch {
      onProgress?.({
        current: i + 1,
        total,
        currentToken: token.ticker,
        status: 'error',
      });
    }

    // Adaptive rate limit: 1s when Birdeye was used (stricter), 500ms otherwise
    if (i < total - 1) {
      const delay = lastSourceWasBirdeye ? 1000 : 500;
      await new Promise((r) => setTimeout(r, delay));
    }
  }

  onProgress?.({
    current: total,
    total,
    currentToken: 'Done',
    status: 'complete',
  });

  return results;
}

/**
 * Clear all cached OHLCV data.
 */
export function clearHistoryCache(): void {
  if (typeof localStorage === 'undefined') return;
  const keys = Object.keys(localStorage).filter(k => k.startsWith(CACHE_KEY_PREFIX));
  for (const key of keys) {
    localStorage.removeItem(key);
  }
}
