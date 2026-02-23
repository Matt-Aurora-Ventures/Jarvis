import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

// ─── Load .env for API keys ───
function loadEnvFromFile(envPath: string): void {
  if (!fs.existsSync(envPath)) return;
  const envContent = fs.readFileSync(envPath, 'utf-8');
  for (const line of envContent.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx > 0) {
      const key = trimmed.slice(0, eqIdx).trim();
      const val = trimmed.slice(eqIdx + 1).trim();
      if (!process.env[key]) process.env[key] = val;
    }
  }
}

const BACKTEST_ENV_PATH = path.resolve(__dirname, '..', '..', '.env');
const ROOT_ENV_PATH = path.resolve(__dirname, '..', '..', '..', '.env');
// Priority: backtest-data/.env first, then root .env fallback.
loadEnvFromFile(BACKTEST_ENV_PATH);
loadEnvFromFile(ROOT_ENV_PATH);

export function getCoinGeckoApiKey(): string | undefined {
  return process.env.COINGECKO_API_KEY;
}

// Base URL for GeckoTerminal-style endpoints.
//
// IMPORTANT:
// - Many teams use a "CG-..." key that upgrades GeckoTerminal limits via `x-cg-pro-api-key`,
//   but does NOT grant access to CoinGecko "pro-api.coingecko.com/api/v3/onchain".
// - Default to GeckoTerminal and only opt into CoinGecko Pro Onchain with an explicit flag.
export function geckoBaseUrl(): string {
  const useProOnchain = String(process.env.GECKO_USE_COINGECKO_PRO_ONCHAIN || '')
    .trim()
    .toLowerCase() === 'true';
  return useProOnchain
    ? 'https://pro-api.coingecko.com/api/v3/onchain'
    : 'https://api.geckoterminal.com/api/v2';
}

// ─── Directory Helpers ───

const ROOT = path.resolve(__dirname, '..', '..');

export function ensureDir(relativePath: string): string {
  const full = path.join(ROOT, relativePath);
  fs.mkdirSync(full, { recursive: true });
  return full;
}

export function dataPath(relativePath: string): string {
  return path.join(ROOT, relativePath);
}

// ─── JSON / CSV File IO ───

export function writeJSON(relativePath: string, data: unknown): void {
  const full = dataPath(relativePath);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, JSON.stringify(data, null, 2), 'utf-8');
  log(`Wrote ${full} (${(fs.statSync(full).size / 1024).toFixed(1)} KB)`);
}

export function readJSON<T>(relativePath: string): T | null {
  const full = dataPath(relativePath);
  if (!fs.existsSync(full)) return null;
  return JSON.parse(fs.readFileSync(full, 'utf-8'));
}

export function writeCSV(relativePath: string, rows: Record<string, unknown>[]): void {
  if (rows.length === 0) return;
  const full = dataPath(relativePath);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  // Use a stable union of keys across all rows (first-seen order) so we don't
  // accidentally drop sparse columns (e.g., rolling-window pos50/pos1000).
  const headers: string[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    for (const k of Object.keys(row)) {
      if (!seen.has(k)) {
        seen.add(k);
        headers.push(k);
      }
    }
  }
  const lines = [headers.join(',')];
  for (const row of rows) {
    const vals = headers.map(h => {
      const v = row[h];
      if (v === null || v === undefined) return '';
      if (typeof v === 'string') return `"${v.replace(/"/g, '""')}"`;
      return String(v);
    });
    lines.push(vals.join(','));
  }
  fs.writeFileSync(full, lines.join('\n'), 'utf-8');
  log(`Wrote ${full} (${rows.length} rows, ${(fs.statSync(full).size / 1024).toFixed(1)} KB)`);
}

// ─── SHA256 ───

export function sha256File(relativePath: string): string {
  const full = dataPath(relativePath);
  const content = fs.readFileSync(full);
  return crypto.createHash('sha256').update(content).digest('hex');
}

// ─── Logging ───

const LOG_FILE = path.join(ROOT, 'pipeline.log');
const SOURCE_REQUEST_LOG_FILE = path.join(ROOT, 'results', 'source_request_log.csv');

type SourceRequestRow = {
  ts: string;
  method: 'GET' | 'POST';
  provider: string;
  label: string;
  url: string;
  status: string;
  attempt: number;
  retries: number;
  duration_ms: number;
  error: string;
};

function csvEscape(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function inferProvider(url: string): string {
  if (url.includes('geckoterminal.com') || url.includes('/api/v3/onchain')) return 'gecko';
  if (url.includes('dexscreener.com')) return 'dexscreener';
  if (url.includes('jup.ag')) return 'jupiter';
  if (url.includes('birdeye.so')) return 'birdeye';
  if (url.includes('pump.fun')) return 'pumpfun';
  if (url.includes('helius-rpc.com')) return 'helius';
  return 'other';
}

function appendSourceRequest(row: SourceRequestRow): void {
  try {
    fs.mkdirSync(path.dirname(SOURCE_REQUEST_LOG_FILE), { recursive: true });
    if (!fs.existsSync(SOURCE_REQUEST_LOG_FILE)) {
      const header = [
        'ts',
        'method',
        'provider',
        'label',
        'url',
        'status',
        'attempt',
        'retries',
        'duration_ms',
        'error',
      ].join(',');
      fs.writeFileSync(SOURCE_REQUEST_LOG_FILE, header + '\n', 'utf-8');
    }

    const line = [
      csvEscape(row.ts),
      csvEscape(row.method),
      csvEscape(row.provider),
      csvEscape(row.label),
      csvEscape(row.url),
      csvEscape(row.status),
      String(row.attempt),
      String(row.retries),
      String(row.duration_ms),
      csvEscape(row.error),
    ].join(',');
    fs.appendFileSync(SOURCE_REQUEST_LOG_FILE, line + '\n');
  } catch {
    // Never break fetch pipeline because of request logging I/O.
  }
}

export function log(msg: string): void {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}`;
  console.log(line);
  fs.appendFileSync(LOG_FILE, line + '\n');
}

export function logError(msg: string, err?: unknown): void {
  const detail = err instanceof Error ? err.message : String(err ?? '');
  log(`ERROR: ${msg} ${detail}`);
}

// ─── Rate Limiter ───

export class RateLimiter {
  private queue: number[] = [];
  private minDelayMs: number;
  constructor(
    private maxRequests: number,
    private windowMs: number,
    minDelayMs?: number,
  ) {
    // Default minimum delay: spread requests evenly across the window + 20% buffer
    this.minDelayMs = minDelayMs ?? Math.ceil((windowMs / maxRequests) * 1.2);
  }

  async wait(): Promise<void> {
    // Enforce minimum delay since last request
    if (this.queue.length > 0) {
      const last = this.queue[this.queue.length - 1];
      const elapsed = Date.now() - last;
      if (elapsed < this.minDelayMs) {
        await sleep(this.minDelayMs - elapsed);
      }
    }

    const now = Date.now();
    this.queue = this.queue.filter(t => now - t < this.windowMs);
    if (this.queue.length >= this.maxRequests) {
      const oldest = this.queue[0];
      const waitMs = this.windowMs - (now - oldest) + 100;
      log(`Rate limiter: window full (${this.queue.length}/${this.maxRequests}), waiting ${waitMs}ms`);
      await sleep(waitMs);
      return this.wait();
    }
    this.queue.push(Date.now());
  }
}

// ─── HTTP Fetch with Retry ───

export interface FetchOptions {
  retries?: number;
  rateLimiter?: RateLimiter;
  label?: string;
  extraHeaders?: Record<string, string>;
}

export async function fetchJSON<T>(url: string, opts: FetchOptions = {}): Promise<T | null> {
  const { retries = 3, rateLimiter, label } = opts;
  if (rateLimiter) await rateLimiter.wait();

  for (let attempt = 1; attempt <= retries; attempt++) {
    const started = Date.now();
    try {
      const headers: Record<string, string> = { 'Accept': 'application/json' };
      headers['User-Agent'] = 'JarvisSniperBacktest/1.0';
      const cgKey = getCoinGeckoApiKey();
      if (cgKey && url.includes('coingecko.com')) headers['x-cg-pro-api-key'] = cgKey;
      if (cgKey && url.includes('geckoterminal.com')) headers['x-cg-pro-api-key'] = cgKey;
      if (opts.extraHeaders) Object.assign(headers, opts.extraHeaders);
      const res = await fetch(url, {
        headers,
        signal: AbortSignal.timeout(30_000),
      });

      if (res.status === 429) {
        const retryAfterRaw = parseInt(res.headers.get('retry-after') || '0', 10);
        // Always wait at least 5s on 429, scale up with attempts
        const backoff = Math.max(retryAfterRaw * 1000, 5000) * attempt;
        log(`429 rate limited on ${label || url} — waiting ${backoff}ms (attempt ${attempt}/${retries})`);
        appendSourceRequest({
          ts: new Date().toISOString(),
          method: 'GET',
          provider: inferProvider(url),
          label: label || url,
          url,
          status: '429',
          attempt,
          retries,
          duration_ms: Date.now() - started,
          error: '',
        });
        await sleep(backoff);
        if (rateLimiter) await rateLimiter.wait(); // re-enter rate limiter queue
        continue;
      }

      if (!res.ok) {
        log(`HTTP ${res.status} on ${label || url} (attempt ${attempt}/${retries})`);
        appendSourceRequest({
          ts: new Date().toISOString(),
          method: 'GET',
          provider: inferProvider(url),
          label: label || url,
          url,
          status: String(res.status),
          attempt,
          retries,
          duration_ms: Date.now() - started,
          error: '',
        });
        // Non-transient statuses: don't waste retries.
        if (res.status === 404 || res.status === 401 || res.status === 403) {
          return null;
        }
        if (attempt < retries) {
          await sleep(2000 * Math.pow(2, attempt - 1));
          continue;
        }
        return null;
      }

      appendSourceRequest({
        ts: new Date().toISOString(),
        method: 'GET',
        provider: inferProvider(url),
        label: label || url,
        url,
        status: String(res.status),
        attempt,
        retries,
        duration_ms: Date.now() - started,
        error: '',
      });
      return (await res.json()) as T;
    } catch (err) {
      logError(`Fetch failed ${label || url} (attempt ${attempt}/${retries})`, err);
      appendSourceRequest({
        ts: new Date().toISOString(),
        method: 'GET',
        provider: inferProvider(url),
        label: label || url,
        url,
        status: 'ERR',
        attempt,
        retries,
        duration_ms: Date.now() - started,
        error: err instanceof Error ? err.message : String(err ?? ''),
      });
      if (attempt < retries) {
        await sleep(2000 * Math.pow(2, attempt - 1));
      }
    }
  }
  return null;
}

export async function fetchJSONPost<T>(url: string, body: unknown, opts: FetchOptions = {}): Promise<T | null> {
  const { retries = 3, rateLimiter, label } = opts;
  if (rateLimiter) await rateLimiter.wait();

  for (let attempt = 1; attempt <= retries; attempt++) {
    const started = Date.now();
    try {
      const headers: Record<string, string> = { 'Accept': 'application/json', 'Content-Type': 'application/json' };
      headers['User-Agent'] = 'JarvisSniperBacktest/1.0';
      const cgKey = getCoinGeckoApiKey();
      if (cgKey && url.includes('coingecko.com')) headers['x-cg-pro-api-key'] = cgKey;
      if (cgKey && url.includes('geckoterminal.com')) headers['x-cg-pro-api-key'] = cgKey;
      if (opts.extraHeaders) Object.assign(headers, opts.extraHeaders);
      const res = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(30_000),
      });

      if (res.status === 429) {
        const backoff = Math.min(5000, 60_000) * attempt;
        log(`429 rate limited on ${label || url} — waiting ${backoff}ms (attempt ${attempt}/${retries})`);
        appendSourceRequest({
          ts: new Date().toISOString(),
          method: 'POST',
          provider: inferProvider(url),
          label: label || url,
          url,
          status: '429',
          attempt,
          retries,
          duration_ms: Date.now() - started,
          error: '',
        });
        await sleep(backoff);
        continue;
      }

      if (!res.ok) {
        log(`HTTP ${res.status} on ${label || url} (attempt ${attempt}/${retries})`);
        appendSourceRequest({
          ts: new Date().toISOString(),
          method: 'POST',
          provider: inferProvider(url),
          label: label || url,
          url,
          status: String(res.status),
          attempt,
          retries,
          duration_ms: Date.now() - started,
          error: '',
        });
        if (res.status === 404 || res.status === 401 || res.status === 403) {
          return null;
        }
        if (attempt < retries) {
          await sleep(2000 * Math.pow(2, attempt - 1));
          continue;
        }
        return null;
      }

      appendSourceRequest({
        ts: new Date().toISOString(),
        method: 'POST',
        provider: inferProvider(url),
        label: label || url,
        url,
        status: String(res.status),
        attempt,
        retries,
        duration_ms: Date.now() - started,
        error: '',
      });
      return (await res.json()) as T;
    } catch (err) {
      logError(`POST failed ${label || url} (attempt ${attempt}/${retries})`, err);
      appendSourceRequest({
        ts: new Date().toISOString(),
        method: 'POST',
        provider: inferProvider(url),
        label: label || url,
        url,
        status: 'ERR',
        attempt,
        retries,
        duration_ms: Date.now() - started,
        error: err instanceof Error ? err.message : String(err ?? ''),
      });
      if (attempt < retries) {
        await sleep(2000 * Math.pow(2, attempt - 1));
      }
    }
  }
  return null;
}

// ─── Sleep ───

export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ─── Progress Tracker ───

export class ProgressTracker<T extends object> {
  private filePath: string;
  private data: T;

  constructor(relativePath: string, defaults: T) {
    this.filePath = dataPath(relativePath);
    if (fs.existsSync(this.filePath)) {
      this.data = { ...defaults, ...JSON.parse(fs.readFileSync(this.filePath, 'utf-8')) };
      log(`Resumed progress from ${this.filePath}`);
    } else {
      this.data = { ...defaults };
      fs.mkdirSync(path.dirname(this.filePath), { recursive: true });
    }
  }

  get(): T { return this.data; }

  update(partial: Partial<T>): void {
    this.data = { ...this.data, ...partial, last_updated: new Date().toISOString() } as T;
    fs.writeFileSync(this.filePath, JSON.stringify(this.data, null, 2), 'utf-8');
  }
}

// ─── Deduplication ───

export function deduplicateByMint<T extends { mint: string }>(tokens: T[]): T[] {
  // NOTE:
  // Universe discovery frequently returns the same mint multiple times (different pools).
  // Keeping the "first seen" entry can lock us onto tiny/illiquid pools (bad candles, bad slippage,
  // misleading backtests). Prefer the record with the *best pool* (highest liquidity, then volume),
  // while merging non-pool metadata (social flags, earliest creation timestamp, etc).
  const byMint = new Map<string, T>();

  const num = (v: unknown): number => {
    const n = typeof v === 'number' ? v : Number(v);
    return Number.isFinite(n) ? n : 0;
  };

  const isValidPool = (v: unknown): boolean => typeof v === 'string' && v.length >= 20;

  for (const t of tokens) {
    const mint = t.mint;
    const existing = byMint.get(mint);
    if (!existing) {
      byMint.set(mint, t);
      continue;
    }

    const eAny = existing as any;
    const tAny = t as any;

    const eLiq = num(eAny.liquidity_usd);
    const tLiq = num(tAny.liquidity_usd);
    const eVol = num(eAny.volume_24h_usd);
    const tVol = num(tAny.volume_24h_usd);
    const eHasPool = isValidPool(eAny.pool_address);
    const tHasPool = isValidPool(tAny.pool_address);

    // Choose the better pool snapshot for pricing/liquidity/volume fields.
    let best: any = eAny;
    let other: any = tAny;
    if (tLiq > eLiq) {
      best = tAny;
      other = eAny;
    } else if (tLiq === eLiq) {
      if (tVol > eVol) {
        best = tAny;
        other = eAny;
      } else if (tVol === eVol) {
        // If all else equal, prefer the one that actually has a pool address.
        if (tHasPool && !eHasPool) {
          best = tAny;
          other = eAny;
        }
      }
    }

    // Merge non-pool metadata into the chosen best record.
    const merged: any = { ...best };

    // Preserve earliest known creation timestamp (pool created at varies by pool).
    const bt = num(best.creation_timestamp);
    const ot = num(other.creation_timestamp);
    if (bt > 0 && ot > 0) merged.creation_timestamp = Math.min(bt, ot);
    else merged.creation_timestamp = bt || ot || 0;

    // If best lacks a valid pool address but the other has one, take it.
    if (!isValidPool(merged.pool_address) && isValidPool(other.pool_address)) merged.pool_address = other.pool_address;

    // Merge socials/metadata as OR.
    merged.has_twitter = Boolean(best.has_twitter || other.has_twitter);
    merged.has_website = Boolean(best.has_website || other.has_website);
    merged.has_telegram = Boolean(best.has_telegram || other.has_telegram);

    // Prefer non-empty strings for symbol/name.
    if (!merged.symbol && other.symbol) merged.symbol = other.symbol;
    if (!merged.name && other.name) merged.name = other.name;

    // Holder count: keep max if present.
    if (typeof merged.holder_count !== 'undefined') {
      merged.holder_count = Math.max(num(best.holder_count), num(other.holder_count));
    }

    byMint.set(mint, merged as T);
  }

  return Array.from(byMint.values());
}
