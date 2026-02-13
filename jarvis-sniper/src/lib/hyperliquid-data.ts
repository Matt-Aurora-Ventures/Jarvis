import type { OHLCVCandle } from './backtest-engine';
import { fetchWithRetry } from './fetch-utils';
import { createHash } from 'crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';

/**
 * Hyperliquid market data (public) -> normalized OHLCV candles for backtesting.
 *
 * Notes:
 * - Hyperliquid's `candleSnapshot` endpoint frequently returns `text/plain` with JSON content.
 *   We therefore parse via `res.text()` then `JSON.parse(...)`.
 * - This module does NOT generate synthetic candles.
 */

export type HyperliquidInterval = '1m' | '5m' | '15m' | '30m' | '1h' | '4h' | '1d';

type HyperliquidCandle = {
  t: number; // start time (ms)
  T: number; // end time (ms)
  s: string; // symbol (e.g. BTC)
  i: HyperliquidInterval; // interval
  o: string;
  c: string;
  h: string;
  l: string;
  v: string;
  n?: number; // trade count
};

const HL_INFO_URL = process.env.HYPERLIQUID_DATA_API || 'https://api.hyperliquid.xyz/info';
const DEFAULT_TIMEOUT_MS = 25_000;
const DEFAULT_TTL_MS = 15 * 60_000; // 15 minutes

const CACHE_DIR = join(process.cwd(), '.jarvis-cache', 'hyperliquid');

function ensureCacheDir(): void {
  try {
    if (!existsSync(CACHE_DIR)) mkdirSync(CACHE_DIR, { recursive: true });
  } catch {
    // best-effort
  }
}

function sha256Hex(input: string): string {
  return createHash('sha256').update(input).digest('hex');
}

function cachePath(key: string): string {
  return join(CACHE_DIR, `${key}.json`);
}

function parseHyperliquidJson(text: string): unknown {
  // Some environments may return already-parsed JSON, but in Node fetch we'll call `.text()`.
  // Keep this strict and fail loudly: upstream responses are our "source of truth".
  return JSON.parse(text);
}

async function postInfo(payload: Record<string, unknown>, timeoutMs: number): Promise<string> {
  const res = await fetchWithRetry(HL_INFO_URL, {
    timeoutMs,
    maxRetries: 2,
    baseDelayMs: 800,
    fetchOptions: {
      method: 'POST',
      headers: {
        Accept: 'application/json,text/plain;q=0.9,*/*;q=0.8',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Hyperliquid info failed (${res.status}): ${body.slice(0, 200)}`);
  }

  return await res.text();
}

function normalizeCandles(raw: HyperliquidCandle[]): OHLCVCandle[] {
  const out: OHLCVCandle[] = [];
  for (const c of raw) {
    const ts = Number(c.t);
    const open = Number(c.o);
    const high = Number(c.h);
    const low = Number(c.l);
    const close = Number(c.c);
    const volume = Number(c.v);
    if (!Number.isFinite(ts) || ts <= 0) continue;
    if (![open, high, low, close, volume].every(Number.isFinite)) continue;
    out.push({ timestamp: ts, open, high, low, close, volume });
  }

  // Sort + dedupe on timestamp.
  out.sort((a, b) => a.timestamp - b.timestamp);
  const deduped: OHLCVCandle[] = [];
  for (const c of out) {
    if (deduped.length > 0 && deduped[deduped.length - 1].timestamp === c.timestamp) continue;
    deduped.push(c);
  }
  return deduped;
}

export type FetchHyperliquidCandlesArgs = {
  coin: string;
  interval: HyperliquidInterval;
  startTime: number;
  endTime: number;
  /** Best-effort cache TTL. Default: 15 minutes. */
  ttlMs?: number;
  /** Per-request timeout. Default: 25s. */
  timeoutMs?: number;
  /** Chunk window in ms (reduces response size). Default: 7 days. */
  chunkMs?: number;
};

export async function fetchHyperliquidCandles(args: FetchHyperliquidCandlesArgs): Promise<OHLCVCandle[]> {
  const {
    coin,
    interval,
    startTime,
    endTime,
    ttlMs = DEFAULT_TTL_MS,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    chunkMs = 7 * 24 * 60 * 60 * 1000,
  } = args;

  const coinUpper = coin.toUpperCase().trim();
  if (!coinUpper) throw new Error('Missing coin');
  if (!Number.isFinite(startTime) || !Number.isFinite(endTime) || startTime <= 0 || endTime <= startTime) {
    throw new Error('Invalid startTime/endTime');
  }

  const key = sha256Hex(JSON.stringify({ v: 1, coin: coinUpper, interval, startTime, endTime }));

  // Disk cache (best-effort; useful for repeated tuning runs).
  try {
    ensureCacheDir();
    const p = cachePath(key);
    if (existsSync(p)) {
      const cached = JSON.parse(readFileSync(p, 'utf8'));
      const expiresAt = Number(cached?.expiresAt ?? 0);
      const candles = cached?.candles as OHLCVCandle[] | undefined;
      if (candles && Number.isFinite(expiresAt) && Date.now() < expiresAt) {
        return candles;
      }
    }
  } catch {
    // ignore
  }

  // Fetch chunked windows to avoid huge responses.
  const all: OHLCVCandle[] = [];
  for (let cursor = startTime; cursor < endTime; cursor += chunkMs) {
    const chunkEnd = Math.min(endTime, cursor + chunkMs);
    const payload = {
      type: 'candleSnapshot',
      req: {
        coin: coinUpper,
        interval,
        startTime: Math.floor(cursor),
        endTime: Math.floor(chunkEnd),
      },
    };

    const text = await postInfo(payload, timeoutMs);
    const json = parseHyperliquidJson(text);
    if (!Array.isArray(json)) {
      throw new Error('Hyperliquid candleSnapshot returned non-array JSON');
    }

    const candles = normalizeCandles(json as HyperliquidCandle[]);
    all.push(...candles);
  }

  // Final sort + dedupe.
  all.sort((a, b) => a.timestamp - b.timestamp);
  const deduped: OHLCVCandle[] = [];
  for (const c of all) {
    if (deduped.length > 0 && deduped[deduped.length - 1].timestamp === c.timestamp) continue;
    deduped.push(c);
  }

  // Write cache (best-effort).
  try {
    ensureCacheDir();
    writeFileSync(
      cachePath(key),
      JSON.stringify({ expiresAt: Date.now() + Math.max(1, ttlMs), candles: deduped }),
      'utf8',
    );
  } catch {
    // ignore
  }

  return deduped;
}

