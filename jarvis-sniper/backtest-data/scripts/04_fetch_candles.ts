/**
 * Phase 4: Fetch OHLCV Candle Data
 * 
 * For every qualifying token across all algos (deduplicated),
 * fetches 5m, 15m, and 1h candle data from GeckoTerminal.
 * 
 * Input:  qualified/qualified_{algo_id}.json (all active algos)
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

// GeckoTerminal paid tier: 250 req/min (use 200 with buffer)
const geckoLimiter = new RateLimiter(200, 60_000, 300);

// ─── Timeframe Configs ───

interface TimeframeConfig {
  key: '5m' | '15m' | '1h';
  endpoint: string; // 'minute' or 'hour'
  aggregate: number;
}

const TIMEFRAMES: TimeframeConfig[] = [
  { key: '5m',  endpoint: 'minute', aggregate: 5 },
  { key: '15m', endpoint: 'minute', aggregate: 15 },
  { key: '1h',  endpoint: 'hour',   aggregate: 1 },
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
  // First fetch (most recent 1000 candles)
  const candles = await fetchCandlesForPool(poolAddress, tf, label);
  if (candles.length === 0) return [];

  // If we got 1000 candles, try to fetch more history by using before_timestamp
  if (candles.length >= 990) {
    const oldestTs = candles[0].timestamp;
    const url2 = `${geckoBaseUrl()}/networks/solana/pools/${poolAddress}/ohlcv/${tf.endpoint}?aggregate=${tf.aggregate}&limit=1000&currency=usd&before_timestamp=${oldestTs}`;
    const data2 = await fetchJSON<GeckoOHLCVResponse>(url2, {
      rateLimiter: geckoLimiter,
      label: `candles:${label}:${tf.key}:p2`,
      retries: 2,
    });

    if (data2?.data?.attributes?.ohlcv_list) {
      const olderCandles = data2.data.attributes.ohlcv_list
        .map(([ts, o, h, l, c, v]) => ({ timestamp: ts, open: o, high: h, low: l, close: c, volume: v }))
        .sort((a, b) => a.timestamp - b.timestamp);

      // Merge, dedup by timestamp
      const seen = new Set(candles.map(c => c.timestamp));
      for (const c of olderCandles) {
        if (!seen.has(c.timestamp)) {
          candles.unshift(c);
          seen.add(c.timestamp);
        }
      }
    }
  }

  return candles.sort((a, b) => a.timestamp - b.timestamp);
}

// ─── Collect All Unique Mints + Pool Addresses ───

function collectAllQualifiedTokens(): Map<string, { mint: string; pool_address: string; symbol: string }> {
  const filterSummary = readJSON<Array<{ algo_id: string }>>('qualified/filter_summary.json');
  const algoIds = filterSummary?.map(s => s.algo_id) || [];
  if (algoIds.length === 0) {
    log('Warning: qualified/filter_summary.json missing or empty; no algo files will be scanned.');
  }

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
  const MAX_CANDLE_MINTS = (() => {
    const raw = process.env.MAX_CANDLE_MINTS;
    const n = raw ? parseInt(raw, 10) : NaN;
    return Number.isFinite(n) && n > 0 ? n : 0;
  })();
  const targetMints = MAX_CANDLE_MINTS > 0 ? allMints.slice(0, MAX_CANDLE_MINTS) : allMints;
  log(`Total unique mints with pool addresses: ${allMints.length}`);
  if (MAX_CANDLE_MINTS > 0) {
    log(`MAX_CANDLE_MINTS active: processing ${targetMints.length}/${allMints.length}`);
  }

  // Load progress
  const progress = new ProgressTracker<CandleFetchProgress>('candle_fetch_progress.json', {
    total_mints: targetMints.length,
    completed_mints: [],
    failed_mints: [],
    last_updated: new Date().toISOString(),
  });

  const p = progress.get();
  const completedSet = new Set(p.completed_mints);
  const failedSet = new Set(p.failed_mints.map(f => f.mint));

  // Load or initialize candle index
  const candleIndex: CandleIndex = readJSON<CandleIndex>('candles/candles_index.json') || {};

  const remaining = targetMints.filter(m => !completedSet.has(m.mint) && !failedSet.has(m.mint));
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
      if (fs.existsSync(fullPath)) {
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
      const pct = targetMints.length > 0 ? ((totalDone / targetMints.length) * 100).toFixed(1) : '0.0';
      log(`Progress: ${totalDone}/${targetMints.length} (${pct}%) | ✓${completedSet.size} ✗${failedSet.size}`);
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
    total_mints: targetMints.length,
    completed_mints: Array.from(completedSet),
    failed_mints: p.failed_mints,
  });
  writeJSON('candles/candles_index.json', candleIndex);

  // Stats
  log('');
  log('═══════════════════════════════════════════════════════');
  log(`Total mints (target set): ${targetMints.length}`);
  log(`Universe mints available: ${allMints.length}`);
  log(`Completed: ${completedSet.size}`);
  log(`Failed: ${failedSet.size}`);

  // Candle count stats
  let total5m = 0, total15m = 0, total1h = 0;
  for (const entry of Object.values(candleIndex)) {
    total5m += entry.timeframes['5m']?.count || 0;
    total15m += entry.timeframes['15m']?.count || 0;
    total1h += entry.timeframes['1h']?.count || 0;
  }
  log(`Total candles: 5m=${total5m.toLocaleString()}, 15m=${total15m.toLocaleString()}, 1h=${total1h.toLocaleString()}`);

  log(`\n✓ Phase 4 complete: ${completedSet.size} mints with candle data`);
  log(`  → candles/{mint}_{timeframe}.json`);
  log(`  → candles/candles_index.json`);
}

main().catch(err => {
  logError('Fatal error in candle fetching', err);
  process.exit(1);
});
