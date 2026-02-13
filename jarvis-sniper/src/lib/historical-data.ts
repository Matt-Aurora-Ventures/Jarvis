/**
 * Historical Data Fetcher — Collect OHLCV candles for backtesting
 *
 * Multi-source OHLCV pipeline:
 *   1. DexScreener pair discovery (pool address)
 *   2. GeckoTerminal OHLCV API (primary candles)
 *   3. Birdeye OHLCV API (fallback, requires API key)
 *
 * Data is cached in localStorage (client-side) and in-memory (server-side)
 * for fast repeat backtests. All caching is guarded for server-side safety.
 *
 * Fulfills: BACK-01 (Historical Data Pipeline)
 */

import type { OHLCVCandle } from './backtest-engine';
import { ALL_BLUECHIPS, type BlueChipToken } from './bluechip-data';
import { geckoFetchPaced as geckoFetchPacedShared } from './gecko-fetch';
import { ServerCache } from './server-cache';
import { createHash } from 'crypto';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, unlinkSync, writeFileSync } from 'fs';
import { join } from 'path';

// ─── Types ───

/** Source of OHLCV candle data */
export type OHLCVSource = 'geckoterminal' | 'birdeye';

export interface HistoricalDataSet {
  tokenSymbol: string;
  mintAddress: string;
  pairAddress: string;
  candles: OHLCVCandle[];
  fetchedAt: number;
  source: OHLCVSource;
}

export interface FetchMintHistoryOptions {
  /** Minimum candles required or the fetch fails. */
  minCandles?: number;
  /** Override DexScreener pair discovery and use this pool/pair address directly (GeckoTerminal OHLCV). */
  pairAddressOverride?: string;
  /**
   * Attempt Birdeye fallback if GeckoTerminal returns fewer than this many candles.
   * Defaults to 100. Set to `minCandles` to minimize Birdeye usage.
   */
  attemptBirdeyeIfCandlesBelow?: number;
  /** Disable Birdeye fallback entirely (useful for large batch runs to avoid strict rate limits). */
  allowBirdeyeFallback?: boolean;
  /** Candle resolution in minutes for GeckoTerminal OHLCV (default: '60' = 1h). */
  resolution?: string;
  /** Limit number of candles pulled from GeckoTerminal. Lower values reduce rate-limit pressure. */
  maxCandles?: number;
  /** Birdeye lookback window in days (default: 180). */
  birdeyeLookbackDays?: number;
}

export interface FetchProgress {
  current: number;
  total: number;
  currentToken: string;
  status: 'fetching' | 'cached' | 'error' | 'complete';
}

// ─── Pair Discovery (DexScreener) ───

const DEXSCREENER_PAIRS = 'https://api.dexscreener.com/tokens/v1/solana';
const CACHE_KEY_PREFIX = 'jarvis_ohlcv_';
const CACHE_EXPIRY_MS = 6 * 60 * 60 * 1000; // 6 hours
const MIN_REAL_CANDLES = 50;

// Server-side cache for Next API routes (localStorage is unavailable on server).
const serverOhlcvCache = new ServerCache<HistoricalDataSet>();

// Disk-backed server cache for larger universes / long-running tuning.
// Best-effort: no-ops if fs is unavailable.
const DISK_CACHE_DIR = join(process.cwd(), '.jarvis-cache', 'ohlcv');
const DISK_CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days
let lastDiskCleanupAt = 0;

function sha256Hex(input: string): string {
  return createHash('sha256').update(input).digest('hex');
}

function ensureDiskCacheDir(): void {
  try {
    if (!existsSync(DISK_CACHE_DIR)) mkdirSync(DISK_CACHE_DIR, { recursive: true });
  } catch {
    // ignore
  }
}

function diskCachePath(cacheKey: string): string {
  return join(DISK_CACHE_DIR, `${cacheKey}.json`);
}

function maybeCleanupDiskCache(now: number): void {
  if (now - lastDiskCleanupAt < 60_000) return;
  lastDiskCleanupAt = now;

  try {
    if (!existsSync(DISK_CACHE_DIR)) return;
    const files = readdirSync(DISK_CACHE_DIR);
    for (const f of files) {
      if (!f.endsWith('.json')) continue;
      const full = join(DISK_CACHE_DIR, f);
      try {
        const st = statSync(full);
        if (now - st.mtimeMs > DISK_CACHE_TTL_MS + 5 * 60_000) {
          unlinkSync(full);
        }
      } catch {
        // ignore
      }
    }
  } catch {
    // ignore
  }
}

type OhlcvCacheKeyArgs = {
  mintAddress: string;
  pairAddressOverride?: string;
  resolution?: string;
  maxCandles?: number;
  allowBirdeyeFallback?: boolean;
  birdeyeLookbackDays?: number;
};

function makeOhlcvCacheKey(args: OhlcvCacheKeyArgs): string {
  return sha256Hex(
    JSON.stringify({
      v: 1,
      mintAddress: args.mintAddress,
      pairAddressOverride: (args.pairAddressOverride || '').trim() || null,
      resolution: args.resolution || '60',
      maxCandles: args.maxCandles ?? 2000,
      allowBirdeyeFallback: args.allowBirdeyeFallback ?? true,
      birdeyeLookbackDays: args.birdeyeLookbackDays ?? 180,
    }),
  );
}

/**
 * Fetch the best liquidity pair address for a token from DexScreener.
 */
const DEXSCREENER_TIMEOUT_MS = 12_000;

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function fetchBestPair(mintAddress: string): Promise<string | null> {
  try {
    const res = await fetchWithTimeout(
      `${DEXSCREENER_PAIRS}/${mintAddress}`,
      { headers: { Accept: 'application/json' } },
      DEXSCREENER_TIMEOUT_MS,
    );
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

// ─── OHLCV (GeckoTerminal) ───

const GECKO_BASE = 'https://api.geckoterminal.com/api/v2/networks/solana/pools';
const GECKO_MIN_INTERVAL_MS = 2200; // GeckoTerminal free API: ~30 req/min

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

// Server-side pacing so batched backtests don't instantly 429 GeckoTerminal.
// Client-side isn't heavily used for this module (API routes call it).
let geckoChain: Promise<Response> = Promise.resolve(null as unknown as Response);
let geckoLastAt = 0;

async function geckoFetchPaced(url: string): Promise<Response> {
  const run = async (): Promise<Response> => {
    const waitMs = Math.max(0, geckoLastAt + GECKO_MIN_INTERVAL_MS - Date.now());
    if (waitMs > 0) await sleep(waitMs);
    geckoLastAt = Date.now();

    // Simple 429 retry with backoff (rare if pacing works, but helps under load).
    for (let attempt = 0; attempt < 3; attempt++) {
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (res.status !== 429) return res;
      await sleep(1500 + attempt * 1500);
      geckoLastAt = Date.now();
    }
    return fetch(url, { headers: { Accept: 'application/json' } });
  };

  // On server: serialize all GeckoTerminal requests with pacing.
  if (typeof window === 'undefined') {
    geckoChain = geckoChain.then(run, run);
    return geckoChain;
  }

  // On client: don't globally serialize (avoid UX stalls if ever used).
  return run();
}

type GeckoTimeframe = 'minute' | 'hour' | 'day';

function geckoParamsForResolution(resolutionMins: string): { timeframe: GeckoTimeframe; aggregate: number } {
  const mins = Number.parseInt(resolutionMins, 10);
  if (!Number.isFinite(mins) || mins <= 0) return { timeframe: 'hour', aggregate: 1 };

  if (mins < 60) return { timeframe: 'minute', aggregate: Math.max(1, mins) };

  if (mins % 1440 === 0) return { timeframe: 'day', aggregate: Math.max(1, Math.floor(mins / 1440)) };

  if (mins % 60 === 0) return { timeframe: 'hour', aggregate: Math.max(1, Math.floor(mins / 60)) };

  return { timeframe: 'minute', aggregate: Math.max(1, mins) };
}

/**
 * Fetch OHLCV candles from GeckoTerminal for a given pool (DexScreener pairAddress).
 *
 * Gecko returns most-recent-first; we normalize to ascending timestamps.
 */
async function fetchOHLCVFromGeckoTerminal(
  poolAddress: string,
  resolutionMins: string = '60',
  maxCandles: number = 2000,
): Promise<OHLCVCandle[]> {
  const { timeframe, aggregate } = geckoParamsForResolution(resolutionMins);

  const all: OHLCVCandle[] = [];
  let beforeTimestamp: number | null = null; // unix seconds

  // GeckoTerminal supports paging via before_timestamp. Limit is capped server-side (commonly 1000).
  while (all.length < maxCandles) {
    const remaining = maxCandles - all.length;
    const limit = Math.min(1000, Math.max(1, remaining));

    const url =
      `${GECKO_BASE}/${poolAddress}/ohlcv/${timeframe}` +
      `?aggregate=${aggregate}&limit=${limit}&currency=usd` +
      (beforeTimestamp ? `&before_timestamp=${beforeTimestamp}` : '');

    try {
      const res = await geckoFetchPacedShared(url);
      if (!res.ok) break;

      const json = await res.json();
      const list: any[] = json?.data?.attributes?.ohlcv_list;
      if (!Array.isArray(list) || list.length === 0) break;

      // list items: [timestamp_sec, open, high, low, close, volume]
      const page = list
        .map((row: any) => ({
          tsSec: Number(row?.[0] ?? 0),
          open: Number(row?.[1] ?? 0),
          high: Number(row?.[2] ?? 0),
          low: Number(row?.[3] ?? 0),
          close: Number(row?.[4] ?? 0),
          volume: Number(row?.[5] ?? 0),
        }))
        .filter((r: any) => Number.isFinite(r.tsSec) && r.tsSec > 0 && r.close > 0);

      if (page.length === 0) break;

      for (const r of page) {
        all.push({
          timestamp: r.tsSec * 1000,
          open: r.open,
          high: r.high,
          low: r.low,
          close: r.close,
          volume: r.volume,
        });
      }

      // Page further back in time using the oldest candle timestamp minus 1 second.
      const oldest = Math.min(...page.map((p: any) => p.tsSec));
      beforeTimestamp = oldest > 1 ? oldest - 1 : null;

      // If we received fewer than requested, assume end of history.
      if (list.length < limit || beforeTimestamp == null) break;
    } catch {
      break;
    }
  }

  // Gecko returns newest-first; our paging appends in that order. Normalize to ascending and dedupe.
  const dedup = new Map<number, OHLCVCandle>();
  for (const c of all) dedup.set(c.timestamp, c);

  return [...dedup.values()].sort((a, b) => a.timestamp - b.timestamp);
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
    const res = await fetchWithTimeout(url, { headers }, 12_000);

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

// ─── Cache Management ───

function getCachedData(cacheKey: string, legacyMintKey?: string): HistoricalDataSet | null {
  // Client-side cache
  if (typeof localStorage !== 'undefined') {
    try {
      const raw = localStorage.getItem(`${CACHE_KEY_PREFIX}${cacheKey}`)
        ?? (legacyMintKey ? localStorage.getItem(`${CACHE_KEY_PREFIX}${legacyMintKey}`) : null);
      if (!raw) return null;
      const data: HistoricalDataSet = JSON.parse(raw);
      if (Date.now() - data.fetchedAt > CACHE_EXPIRY_MS) return null;

      // Forward-compat: older caches may contain deprecated source labels.
      const source: OHLCVSource =
        data.source === 'birdeye' ? 'birdeye' : 'geckoterminal';

      return { ...data, source };
    } catch {
      return null;
    }
  }

  // Server-side cache (memory)
  const mem = serverOhlcvCache.get(cacheKey) || (legacyMintKey ? serverOhlcvCache.get(legacyMintKey) : null);
  if (mem) return mem;

  // Server-side cache (disk fallback)
  try {
    ensureDiskCacheDir();
    const p = diskCachePath(cacheKey);
    if (!existsSync(p) && legacyMintKey) {
      const legacyPath = diskCachePath(legacyMintKey);
      if (existsSync(legacyPath)) {
        const rawLegacy = JSON.parse(readFileSync(legacyPath, 'utf8'));
        const expiresAtLegacy = Number(rawLegacy?.expiresAt ?? 0);
        const dataLegacy = rawLegacy?.data as HistoricalDataSet | undefined;
        if (dataLegacy && Number.isFinite(expiresAtLegacy) && Date.now() < expiresAtLegacy) {
          serverOhlcvCache.set(cacheKey, dataLegacy, Math.max(1, expiresAtLegacy - Date.now()));
          return dataLegacy;
        }
      }
    }

    if (!existsSync(p)) return null;

    const raw = JSON.parse(readFileSync(p, 'utf8'));
    const expiresAt = Number(raw?.expiresAt ?? 0);
    const data = raw?.data as HistoricalDataSet | undefined;
    if (!data || !Number.isFinite(expiresAt) || Date.now() >= expiresAt) return null;

    serverOhlcvCache.set(cacheKey, data, Math.max(1, expiresAt - Date.now()));
    return data;
  } catch {
    return null;
  }
}

function setCachedData(cacheKey: string, data: HistoricalDataSet): void {
  // Client-side cache
  if (typeof localStorage !== 'undefined') {
    try {
      localStorage.setItem(`${CACHE_KEY_PREFIX}${cacheKey}`, JSON.stringify(data));
    } catch {
      // Storage full — clear old entries
      clearOldCache();
      try {
        localStorage.setItem(`${CACHE_KEY_PREFIX}${cacheKey}`, JSON.stringify(data));
      } catch {
        // Still full, skip caching
      }
    }
    return;
  }

  // Server-side cache (Next API routes)
  serverOhlcvCache.set(cacheKey, data, CACHE_EXPIRY_MS);

  // Disk-backed fallback so big universes don't need to refetch every run.
  try {
    const now = Date.now();
    ensureDiskCacheDir();
    maybeCleanupDiskCache(now);
    writeFileSync(
      diskCachePath(cacheKey),
      JSON.stringify({ expiresAt: now + DISK_CACHE_TTL_MS, data }),
      'utf8',
    );
  } catch {
    // ignore
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
 * 2-tier fallback: GeckoTerminal (via DexScreener pair discovery) -> Birdeye
 */
export async function fetchTokenHistory(
  token: BlueChipToken,
  currentPrice?: number,
): Promise<HistoricalDataSet> {
  void currentPrice;
  // Check cache first
  const cacheKey = makeOhlcvCacheKey({
    mintAddress: token.mintAddress,
    resolution: '60',
    maxCandles: 3000,
    allowBirdeyeFallback: true,
    birdeyeLookbackDays: 180,
  });

  const cached = getCachedData(cacheKey, token.mintAddress);
  if (cached && cached.candles.length >= MIN_REAL_CANDLES) {
    return cached;
  }

  // Tier 1: GeckoTerminal OHLCV via DexScreener pair discovery
  const pairAddress = await fetchBestPair(token.mintAddress);
  let candles: OHLCVCandle[] = [];
  let source: OHLCVSource = 'geckoterminal';

  if (pairAddress) {
    candles = await fetchOHLCVFromGeckoTerminal(pairAddress, '60', 3000);
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

  // No synthetic fallback: require real candles.
  if (candles.length < MIN_REAL_CANDLES) {
    throw new Error(`Insufficient real OHLCV for ${token.ticker} (${candles.length} candles)`);
  }

  const dataset: HistoricalDataSet = {
    tokenSymbol: token.ticker,
    mintAddress: token.mintAddress,
    pairAddress: pairAddress || '',
    candles,
    fetchedAt: Date.now(),
    source,
  };

  setCachedData(cacheKey, dataset);
  return dataset;
}

/**
 * Fetch OHLCV data for any Solana SPL token mint address.
 *
 * Real-data only: GeckoTerminal OHLCV (via DexScreener pair discovery) with optional Birdeye fallback.
 * Throws if insufficient candles (no synthetic generation).
 */
export async function fetchMintHistory(
  mintAddress: string,
  tokenSymbol: string = mintAddress.slice(0, 6),
  options: FetchMintHistoryOptions = {},
): Promise<HistoricalDataSet> {
  const minCandles = options.minCandles ?? MIN_REAL_CANDLES;
  const pairAddressOverride = (options.pairAddressOverride || '').trim();
  const attemptBirdeyeIfCandlesBelow = options.attemptBirdeyeIfCandlesBelow ?? 100;
  const allowBirdeyeFallback = options.allowBirdeyeFallback ?? true;
  const resolution = options.resolution ?? '60';
  const maxCandles = options.maxCandles ?? 2000;
  const birdeyeLookbackDays = options.birdeyeLookbackDays ?? 180;

  const cacheKey = makeOhlcvCacheKey({
    mintAddress,
    pairAddressOverride,
    resolution,
    maxCandles,
    allowBirdeyeFallback,
    birdeyeLookbackDays,
  });

  const cached = getCachedData(cacheKey, mintAddress);
  if (cached && cached.candles.length >= minCandles) {
    return cached;
  }

  const pairAddress = pairAddressOverride || (await fetchBestPair(mintAddress));
  let candles: OHLCVCandle[] = [];
  let source: OHLCVSource = 'geckoterminal';

  if (pairAddress) {
    // Use a smaller cap for batch universes; callers can raise if they need deeper history.
    candles = await fetchOHLCVFromGeckoTerminal(pairAddress, resolution, maxCandles);
  }

  // Optional Birdeye fallback (use sparingly; public endpoint is heavily rate limited).
  if (allowBirdeyeFallback && candles.length < Math.max(minCandles, attemptBirdeyeIfCandlesBelow)) {
    const lookbackSec = Math.floor((Date.now() - birdeyeLookbackDays * 24 * 3600 * 1000) / 1000);
    const nowSec = Math.floor(Date.now() / 1000);
    const birdeyeCandles = await fetchFromBirdeye(mintAddress, lookbackSec, nowSec);
    if (birdeyeCandles.length >= minCandles) {
      candles = birdeyeCandles;
      source = 'birdeye';
    }
  }

  if (candles.length < minCandles) {
    throw new Error(`Insufficient real OHLCV for ${tokenSymbol} (${candles.length} candles)`);
  }

  const dataset: HistoricalDataSet = {
    tokenSymbol,
    mintAddress,
    pairAddress: pairAddress || '',
    candles,
    fetchedAt: Date.now(),
    source,
  };

  setCachedData(cacheKey, dataset);
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
        status: 'cached',
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
