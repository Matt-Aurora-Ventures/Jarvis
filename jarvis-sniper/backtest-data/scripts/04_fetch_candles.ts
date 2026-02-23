/**
 * Phase 4: Fetch OHLCV Candle Data
 * 
 * For every qualifying token across all algos (deduplicated),
 * fetches 5m, 15m, and 1h candle data from GeckoTerminal.
 * 
 * Input:  qualified/qualified_{algo_id}.json (all current strategies)
 * Output: candles/{mint}_{timeframe}.json + candles/candles_index.json
 * 
 * Resumable: tracks completed mints in candle_fetch_progress.json.
 * Estimated: 25-50 hours for full fetch (rate-limited to 30 req/min).
 * 
 * Run: npx tsx backtest-data/scripts/04_fetch_candles.ts
 */

import * as fs from 'fs';
import {
  log, logError, fetchJSON, sleep,
  RateLimiter, ProgressTracker, writeJSON, readJSON,
  ensureDir, dataPath, geckoBaseUrl,
} from './shared/utils';
import type { ScoredToken, Candle, CandleIndex, CandleFetchProgress } from './shared/types';
import { CURRENT_ALGO_IDS, type AlgoId } from './shared/algo-ids';

function envInt(name: string, fallback: number): number {
  const raw = process.env[name];
  const n = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(n) ? n : fallback;
}

// GeckoTerminal rate limits vary by plan/key. Default to a conservative value and allow override.
const GECKO_RPM = envInt('GECKO_RPM', 28);
const geckoLimiter = new RateLimiter(GECKO_RPM, 60_000);

// Candle history depth (pagination).
// Default is 2 pages (up to ~2000 candles). For slower-moving assets (indexes/equities/bluechips),
// you typically need more history to evaluate longer holds.
const CANDLE_MAX_PAGES_DEFAULT = Math.max(1, envInt('CANDLE_MAX_PAGES', 2));
const CANDLE_MAX_PAGES_MINUTE = Math.max(1, envInt('CANDLE_MAX_PAGES_MINUTE', CANDLE_MAX_PAGES_DEFAULT));
const CANDLE_MAX_PAGES_HOUR = Math.max(1, envInt('CANDLE_MAX_PAGES_HOUR', CANDLE_MAX_PAGES_DEFAULT));
const CANDLE_MAX_PAGES_DAY = Math.max(1, envInt('CANDLE_MAX_PAGES_DAY', CANDLE_MAX_PAGES_DEFAULT));

// ─── Timeframe Configs ───

interface TimeframeConfig {
  key: '5m' | '15m' | '1h' | '1d';
  endpoint: string; // 'minute' | 'hour' | 'day'
  aggregate: number;
}

const TIMEFRAMES: TimeframeConfig[] = [
  { key: '5m',  endpoint: 'minute', aggregate: 5 },
  { key: '15m', endpoint: 'minute', aggregate: 15 },
  { key: '1h',  endpoint: 'hour',   aggregate: 1 },
  // Slow-moving assets (indexes/equities/bluechips) need higher-timeframe history.
  { key: '1d',  endpoint: 'day',    aggregate: 1 },
];

// ─── GeckoTerminal OHLCV Response ───

interface GeckoOHLCVResponse {
  data?: {
    attributes?: {
      ohlcv_list?: [number, number, number, number, number, number][];
    };
  };
}

// ─── Fetch Candles for One Pool + Timeframe ───

async function fetchCandlesForPool(
  poolAddress: string,
  tf: TimeframeConfig,
  label: string,
): Promise<Candle[]> {
  // GeckoTerminal OHLCV endpoint
  const url = `${geckoBaseUrl()}/networks/solana/pools/${poolAddress}/ohlcv/${tf.endpoint}?aggregate=${tf.aggregate}&limit=1000&currency=usd`;

  const data = await fetchJSON<GeckoOHLCVResponse>(url, {
    rateLimiter: geckoLimiter,
    label: `candles:${label}:${tf.key}`,
    retries: 3,
  });

  if (!data?.data?.attributes?.ohlcv_list) return [];

  // ohlcv_list is [[timestamp, open, high, low, close, volume], ...]
  return data.data.attributes.ohlcv_list
    .map(([ts, o, h, l, c, v]) => ({
      timestamp: ts,
      open: o,
      high: h,
      low: l,
      close: c,
      volume: v,
    }))
    .sort((a, b) => a.timestamp - b.timestamp); // chronological order
}

// Fetch multiple pages of candles to get deeper history
async function fetchDeepCandles(
  poolAddress: string,
  tf: TimeframeConfig,
  label: string,
): Promise<Candle[]> {
  const maxPages =
    tf.endpoint === 'hour' ? CANDLE_MAX_PAGES_HOUR
    : tf.endpoint === 'day' ? CANDLE_MAX_PAGES_DAY
    : CANDLE_MAX_PAGES_MINUTE;

  const merged: Candle[] = [];
  const seen = new Set<number>();
  let beforeTimestamp: number | null = null;

  for (let page = 1; page <= maxPages; page++) {
    const before: string = beforeTimestamp ? `&before_timestamp=${beforeTimestamp}` : '';
    const url: string = `${geckoBaseUrl()}/networks/solana/pools/${poolAddress}/ohlcv/${tf.endpoint}?aggregate=${tf.aggregate}&limit=1000&currency=usd${before}`;

    const data: GeckoOHLCVResponse | null = await fetchJSON<GeckoOHLCVResponse>(url, {
      rateLimiter: geckoLimiter,
      label: `candles:${label}:${tf.key}:p${page}`,
      retries: page === 1 ? 3 : 2,
    });

    const list: [number, number, number, number, number, number][] = data?.data?.attributes?.ohlcv_list || [];
    if (list.length === 0) break;

    const batch: Candle[] = list
      .map(([ts, o, h, l, c, v]: [number, number, number, number, number, number]) => ({ timestamp: ts, open: o, high: h, low: l, close: c, volume: v }))
      .sort((a, b) => a.timestamp - b.timestamp);

    for (const c of batch) {
      if (seen.has(c.timestamp)) continue;
      merged.push(c);
      seen.add(c.timestamp);
    }

    // If this page wasn't full, we've reached the end of history.
    if (batch.length < 990) break;

    // Walk back in time. We use the oldest candle timestamp as the next "before".
    const oldest: number | null = batch[0]?.timestamp ?? null;
    // Use `oldest - 1` to avoid fetching the same oldest candle again if the API is inclusive.
    beforeTimestamp = Number.isFinite(oldest as number) && (oldest as number) > 0 ? (oldest as number) - 1 : null;
    if (!beforeTimestamp) break;
  }

  return merged.sort((a, b) => a.timestamp - b.timestamp);
}

// ─── Collect All Unique Mints + Pool Addresses ───

function parseAlgoList(): AlgoId[] {
  const raw = String(process.env.CANDLE_FETCH_ALGOS || '').trim();
  if (!raw) return [...CURRENT_ALGO_IDS];
  const wanted = raw.split(',').map(s => s.trim()).filter(Boolean);
  const set = new Set(wanted);
  return CURRENT_ALGO_IDS.filter(id => set.has(id));
}

function collectAllQualifiedTokens(): Map<string, { mint: string; pool_address: string; symbol: string }> {
  const algoIds = parseAlgoList();

  const mintMap = new Map<string, { mint: string; pool_address: string; symbol: string }>();

  for (const algoId of algoIds) {
    const tokens = readJSON<ScoredToken[]>(`qualified/qualified_${algoId}.json`);
    if (!tokens) {
      log(`Warning: No qualified file for ${algoId}`);
      continue;
    }
    for (const t of tokens) {
      if (!mintMap.has(t.mint) && t.pool_address && t.pool_address.length >= 20) {
        mintMap.set(t.mint, { mint: t.mint, pool_address: t.pool_address, symbol: t.symbol || 'UNK' });
      }
    }
  }

  return mintMap;
}

// ─── Main ───

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 4: Fetch OHLCV Candle Data');
  log('═══════════════════════════════════════════════════════');

  ensureDir('candles');

  // Collect all unique mints
  const mintMap = collectAllQualifiedTokens();
  const allMints = Array.from(mintMap.values());
  log(`Total unique mints with pool addresses: ${allMints.length}`);

  // Load progress
  const progress = new ProgressTracker<CandleFetchProgress>('candle_fetch_progress.json', {
    total_mints: allMints.length,
    completed_mints: [],
    failed_mints: [],
    last_updated: new Date().toISOString(),
  });

  const p = progress.get();
  const completedSet = new Set(p.completed_mints);
  const failedSet = new Set(p.failed_mints.map(f => f.mint));

  // Load or initialize candle index
  const candleIndex: CandleIndex = readJSON<CandleIndex>('candles/candles_index.json') || {};

  // If a mint's pool address changed since the last fetch, we must refetch candles
  // (files are keyed by mint, so stale candles would silently remain otherwise).
  const forceRefetchMints = new Set<string>();
  for (const m of allMints) {
    const existing = candleIndex[m.mint];
    if (existing?.pool_address && existing.pool_address !== m.pool_address) {
      forceRefetchMints.add(m.mint);
      completedSet.delete(m.mint);
      // If it previously failed, allow a retry against the new pool.
      if (failedSet.has(m.mint)) failedSet.delete(m.mint);
      delete candleIndex[m.mint];
    }
  }
  if (forceRefetchMints.size > 0) {
    log(`Pool changes detected: forcing candle refetch for ${forceRefetchMints.size} mints`);
  }

  // Optional: force refetch even when the pool did not change (useful when increasing CANDLE_MAX_PAGES_*)
  const forceAll = envInt('CANDLE_FORCE_REFETCH', 0) === 1;
  if (forceAll) {
    log('Force refetch enabled (CANDLE_FORCE_REFETCH=1): refetching candles even if files exist');
    const toForce = new Set(allMints.map(m => m.mint));
    for (const mint of toForce) {
      forceRefetchMints.add(mint);
      completedSet.delete(mint);
      if (failedSet.has(mint)) failedSet.delete(mint);
      delete candleIndex[mint];
    }
    // Drop forced mints from the persisted failed list so they can retry cleanly.
    p.failed_mints = p.failed_mints.filter(f => !toForce.has(f.mint));
  }

  const remaining = allMints.filter(m => !completedSet.has(m.mint) && !failedSet.has(m.mint));
  log(`Already completed: ${completedSet.size}`);
  log(`Previously failed: ${failedSet.size}`);
  log(`Remaining to fetch: ${remaining.length}`);

  // Estimate time
  const requestsNeeded = remaining.length * TIMEFRAMES.length;
  const estimatedMinutes = requestsNeeded / 28; // 28 req/min
  log(`Estimated time: ${(estimatedMinutes / 60).toFixed(1)} hours (${requestsNeeded} requests at 28/min)`);
  log('');

  let completed = 0;
  let failed = 0;
  const batchSize = 100; // save progress every 100 mints

  for (let i = 0; i < remaining.length; i++) {
    const { mint, pool_address, symbol } = remaining[i];
    const shortMint = mint.slice(0, 8);

    const entry: CandleIndex[string] = {
      pool_address,
      timeframes: {},
    };

    let hasAnyCandles = false;

    for (const tf of TIMEFRAMES) {
      const filePath = `candles/${mint}_${tf.key}.json`;
      const fullPath = dataPath(filePath);

      // Skip if already fetched
      if (!forceRefetchMints.has(mint) && fs.existsSync(fullPath)) {
        const existing = readJSON<Candle[]>(filePath);
        if (existing && existing.length > 0) {
          entry.timeframes[tf.key] = { count: existing.length, file: filePath };
          hasAnyCandles = true;
          continue;
        }
      }

      const candles = await fetchDeepCandles(pool_address, tf, `${shortMint}`);

      if (candles.length > 0) {
        writeJSON(filePath, candles);
        entry.timeframes[tf.key] = { count: candles.length, file: filePath };
        hasAnyCandles = true;
      }
    }

    if (hasAnyCandles) {
      candleIndex[mint] = entry;
      completedSet.add(mint);
      completed++;
    } else {
      failedSet.add(mint);
      failed++;
      p.failed_mints.push({ mint, error: 'No candle data from any timeframe' });
    }

    // Progress logging
    if ((completed + failed) % 10 === 0) {
      const totalDone = completedSet.size + failedSet.size;
      const pct = ((totalDone / allMints.length) * 100).toFixed(1);
      log(`Progress: ${totalDone}/${allMints.length} (${pct}%) | ✓${completedSet.size} ✗${failedSet.size}`);
    }

    // Save progress periodically
    if ((completed + failed) % batchSize === 0) {
      progress.update({
        completed_mints: Array.from(completedSet),
        failed_mints: p.failed_mints,
      });
      writeJSON('candles/candles_index.json', candleIndex);
      log(`Checkpoint saved: ${completedSet.size} completed, ${failedSet.size} failed`);
    }
  }

  // Final save
  progress.update({
    total_mints: allMints.length,
    completed_mints: Array.from(completedSet),
    failed_mints: p.failed_mints,
  });
  writeJSON('candles/candles_index.json', candleIndex);

  // Stats
  log('');
  log('═══════════════════════════════════════════════════════');
  log(`Total mints: ${allMints.length}`);
  log(`Completed: ${completedSet.size}`);
  log(`Failed: ${failedSet.size}`);

  // Candle count stats
  let total5m = 0, total15m = 0, total1h = 0, total1d = 0;
  for (const entry of Object.values(candleIndex)) {
    total5m += entry.timeframes['5m']?.count || 0;
    total15m += entry.timeframes['15m']?.count || 0;
    total1h += entry.timeframes['1h']?.count || 0;
    total1d += entry.timeframes['1d']?.count || 0;
  }
  log(`Total candles: 5m=${total5m.toLocaleString()}, 15m=${total15m.toLocaleString()}, 1h=${total1h.toLocaleString()}, 1d=${total1d.toLocaleString()}`);

  log(`\n✓ Phase 4 complete: ${completedSet.size} mints with candle data`);
  log(`  → candles/{mint}_{timeframe}.json`);
  log(`  → candles/candles_index.json`);
}

main().catch(err => {
  logError('Fatal error in candle fetching', err);
  process.exit(1);
});
