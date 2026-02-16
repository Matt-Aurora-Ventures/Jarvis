import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

// ─── Load .env for API keys ───
function loadEnvFile(filePath: string): void {
  if (!fs.existsSync(filePath)) return;
  const envContent = fs.readFileSync(filePath, 'utf-8');
  for (const line of envContent.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx <= 0) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    const val = trimmed.slice(eqIdx + 1).trim();
    if (!process.env[key]) process.env[key] = val;
  }
}

// Priority: backtest-data/.env (documented), then project root .env fallback.
loadEnvFile(path.resolve(__dirname, '..', '..', 'backtest-data', '.env'));
loadEnvFile(path.resolve(__dirname, '..', '..', '.env'));

export function getCoinGeckoApiKey(): string | undefined {
  return process.env.COINGECKO_API_KEY;
}

// Use CoinGecko pro onchain endpoints when API key is available (250 req/min)
// Falls back to GeckoTerminal free endpoints (30 req/min)
export function geckoBaseUrl(): string {
  return getCoinGeckoApiKey()
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
  const headers = Object.keys(rows[0]);
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
        await sleep(backoff);
        if (rateLimiter) await rateLimiter.wait(); // re-enter rate limiter queue
        continue;
      }

      if (!res.ok) {
        log(`HTTP ${res.status} on ${label || url} (attempt ${attempt}/${retries})`);
        if (attempt < retries) {
          await sleep(2000 * Math.pow(2, attempt - 1));
          continue;
        }
        return null;
      }

      return (await res.json()) as T;
    } catch (err) {
      logError(`Fetch failed ${label || url} (attempt ${attempt}/${retries})`, err);
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
        await sleep(backoff);
        continue;
      }

      if (!res.ok) {
        log(`HTTP ${res.status} on ${label || url} (attempt ${attempt}/${retries})`);
        if (attempt < retries) {
          await sleep(2000 * Math.pow(2, attempt - 1));
          continue;
        }
        return null;
      }

      return (await res.json()) as T;
    } catch (err) {
      logError(`POST failed ${label || url} (attempt ${attempt}/${retries})`, err);
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
  const seen = new Set<string>();
  const result: T[] = [];
  for (const t of tokens) {
    if (!seen.has(t.mint)) {
      seen.add(t.mint);
      result.push(t);
    }
  }
  return result;
}
