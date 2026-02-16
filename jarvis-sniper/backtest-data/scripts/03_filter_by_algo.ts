/**
 * Phase 3: Filter Tokens Through All 25 Algos
 * 
 * For each algo, filter the scored universe by exact acceptance criteria.
 * Produce exactly 5,000 qualifying tokens per algo (most recent first).
 * 
 * Input:  universe/universe_scored.json
 * Output: qualified/qualified_{algo_id}.json + .csv (25 pairs)
 * 
 * Run: npx tsx backtest-data/scripts/03_filter_by_algo.ts
 */

import { log, logError, readJSON, writeJSON, writeCSV, ensureDir } from './shared/utils';
import type { ScoredToken, AlgoFilter } from './shared/types';

const TARGET_PER_ALGO = 5000;

// ─── Algo Filter Definitions (source of truth from prompt) ───

// FILTER PHILOSOPHY:
// - Metadata filters = QUALITY GATES (liquidity, score, age) → prevents rugs & low-quality entries
// - Momentum, vol/liq ratio, breakout signals → detected from CANDLE DATA in Phase 5
// - This gives more tokens per algo for statistical significance while keeping quality high

const ALGO_FILTERS: AlgoFilter[] = [
  // MEMECOIN STRATEGIES (5) — fresh launches, liquidity floor = anti-rug gate
  { algo_id: 'pump_fresh_tight',   category: 'memecoin', min_score: 35, min_liquidity_usd: 5000,   max_age_hours: 48 },
  { algo_id: 'micro_cap_surge',    category: 'memecoin', min_score: 25, min_liquidity_usd: 3000,   max_age_hours: 48 },
  { algo_id: 'elite',              category: 'memecoin', min_liquidity_usd: 50000, max_age_hours: 168 },
  { algo_id: 'momentum',           category: 'memecoin', min_score: 0,  min_liquidity_usd: 25000 },
  { algo_id: 'hybrid_b',           category: 'memecoin', min_liquidity_usd: 25000 },
  { algo_id: 'let_it_ride',        category: 'memecoin', min_liquidity_usd: 25000 },

  // ESTABLISHED TOKEN STRATEGIES (5) — proven tokens with volume + liquidity
  { algo_id: 'sol_veteran',            category: 'established', min_score: 40, min_liquidity_usd: 50000,  min_age_hours: 4380 },
  { algo_id: 'utility_swing',          category: 'established', min_score: 55, min_liquidity_usd: 10000,  min_age_hours: 4380 },
  { algo_id: 'established_breakout',   category: 'established', min_score: 30, min_liquidity_usd: 10000,  min_age_hours: 720 },
  { algo_id: 'meme_classic',           category: 'established', min_score: 40, min_liquidity_usd: 5000,   min_age_hours: 8760 },
  { algo_id: 'volume_spike',           category: 'established', min_score: 40, min_liquidity_usd: 30000,  min_age_hours: 1440, min_vol_liq_ratio: 0.45 },

  // BAGS.FM STRATEGIES (8) — liquidity always 0 for bags (locked by design)
  { algo_id: 'bags_fresh_snipe',   category: 'bags', min_score: 30, max_age_hours: 72 },
  { algo_id: 'bags_momentum',      category: 'bags', min_score: 25, max_age_hours: 336 },
  { algo_id: 'bags_value',         category: 'bags', min_score: 45, max_age_hours: 720 },
  { algo_id: 'bags_dip_buyer',     category: 'bags', min_score: 20, max_age_hours: 720 },
  { algo_id: 'bags_bluechip',      category: 'bags', min_score: 50 },
  { algo_id: 'bags_conservative',  category: 'bags', min_score: 35, max_age_hours: 720 },
  { algo_id: 'bags_aggressive',    category: 'bags', min_score: 10, max_age_hours: 720 },
  { algo_id: 'bags_elite',         category: 'bags', min_score: 55, max_age_hours: 720 },

  // BLUE CHIP STRATEGIES (2) — high liquidity = anti-rug, momentum detected from candles
  { algo_id: 'bluechip_trend_follow', category: 'bluechip', min_score: 50, min_liquidity_usd: 50000 },
  { algo_id: 'bluechip_breakout',     category: 'bluechip', min_score: 50, min_liquidity_usd: 50000 },

  // xSTOCK STRATEGIES (3)
  { algo_id: 'xstock_intraday',      category: 'xstock', min_score: 30 },
  { algo_id: 'xstock_swing',         category: 'xstock', min_score: 45, min_liquidity_usd: 50000, min_age_hours: 168 },
  { algo_id: 'prestock_speculative', category: 'xstock', min_score: 25 },

  // INDEX STRATEGIES (2)
  { algo_id: 'index_intraday',  category: 'index', min_score: 40 },
  { algo_id: 'index_leveraged', category: 'index', min_score: 30 },
];

// ─── Filter Logic ───

function tokenPassesFilter(token: ScoredToken, filter: AlgoFilter): boolean {
  const now = Date.now() / 1000;
  const ageHours = token.creation_timestamp > 0
    ? (now - token.creation_timestamp) / 3600
    : Infinity;

  // Score check
  if (filter.min_score !== undefined && token.score < filter.min_score) return false;

  // Liquidity check (bags tokens skip this — liquidity is always 0 by design)
  if (filter.category !== 'bags') {
    if (filter.min_liquidity_usd !== undefined && token.liquidity_usd < filter.min_liquidity_usd) return false;
  }

  // Momentum check
  if (filter.min_momentum_1h !== undefined && token.price_change_1h < filter.min_momentum_1h) return false;

  // Age check (max)
  if (filter.max_age_hours !== undefined && ageHours > filter.max_age_hours) return false;

  // Age check (min — for established token strategies)
  if (filter.min_age_hours !== undefined && ageHours < filter.min_age_hours) return false;

  // Volume/Liquidity ratio check
  if (filter.min_vol_liq_ratio !== undefined) {
    const ratio = token.liquidity_usd > 0 ? token.volume_24h_usd / token.liquidity_usd : 0;
    if (ratio < filter.min_vol_liq_ratio) return false;
  }

  return true;
}

function isBagsToken(token: ScoredToken): boolean {
  // Bags.fm tokens have 0 liquidity but active trading (locked liquidity by design)
  return token.liquidity_usd === 0 && token.volume_24h_usd > 0 && token.buy_txn_count_24h > 0;
}

// ─── Main ───

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 3: Filter Tokens Through All 25 Algos');
  log('═══════════════════════════════════════════════════════');

  const scored = readJSON<ScoredToken[]>('universe/universe_scored.json');
  if (!scored || scored.length === 0) {
    logError('No scored universe found. Run 02_score_universe.ts first.');
    process.exit(1);
  }

  log(`Universe: ${scored.length} scored tokens`);
  ensureDir('qualified');

  // Pre-sort by creation_timestamp descending (most recent first)
  scored.sort((a, b) => b.creation_timestamp - a.creation_timestamp);

  // Separate bags tokens from non-bags
  const bagsTokens = scored.filter(isBagsToken);
  const nonBagsTokens = scored.filter(t => !isBagsToken(t));
  log(`Bags-style tokens: ${bagsTokens.length}`);
  log(`Non-bags tokens: ${nonBagsTokens.length}`);
  log('');

  const summary: { algo_id: string; qualified: number; lookback_note: string }[] = [];

  for (const filter of ALGO_FILTERS) {
    // Select the right pool of tokens based on category
    const pool = filter.category === 'bags' ? bagsTokens : nonBagsTokens;

    // Filter and take the most recent 5,000
    const qualifying = pool.filter(t => tokenPassesFilter(t, filter));
    const selected = qualifying.slice(0, TARGET_PER_ALGO);

    let lookbackNote = '';
    if (selected.length < TARGET_PER_ALGO) {
      lookbackNote = `Only ${selected.length}/${TARGET_PER_ALGO} qualifying tokens found in ${scored.length}-token universe. ` +
        `Need larger universe or broader lookback.`;
    } else {
      // Calculate actual lookback window used
      const oldestSelected = selected[selected.length - 1];
      const newestSelected = selected[0];
      if (oldestSelected.creation_timestamp > 0 && newestSelected.creation_timestamp > 0) {
        const rangeHours = (newestSelected.creation_timestamp - oldestSelected.creation_timestamp) / 3600;
        lookbackNote = `${rangeHours.toFixed(0)}h lookback window`;
      }
    }

    // Add vol/liq ratio to output for reference
    const enrichedSelected = selected.map(t => ({
      ...t,
      vol_liq_ratio: t.liquidity_usd > 0 ? +(t.volume_24h_usd / t.liquidity_usd).toFixed(3) : 0,
      age_hours: t.creation_timestamp > 0
        ? +((Date.now() / 1000 - t.creation_timestamp) / 3600).toFixed(1)
        : 0,
    }));

    writeJSON(`qualified/qualified_${filter.algo_id}.json`, enrichedSelected);
    writeCSV(`qualified/qualified_${filter.algo_id}.csv`, enrichedSelected as unknown as Record<string, unknown>[]);

    const status = selected.length >= TARGET_PER_ALGO ? '✓' : '⚠';
    log(`${status} ${filter.algo_id}: ${selected.length}/${TARGET_PER_ALGO} qualifying tokens. ${lookbackNote}`);

    summary.push({
      algo_id: filter.algo_id,
      qualified: selected.length,
      lookback_note: lookbackNote,
    });
  }

  // Write summary
  writeJSON('qualified/filter_summary.json', summary);
  writeCSV('qualified/filter_summary.csv', summary as unknown as Record<string, unknown>[]);

  // Final stats
  log('');
  log('═══════════════════════════════════════════════════════');
  const full = summary.filter(s => s.qualified >= TARGET_PER_ALGO).length;
  const partial = summary.filter(s => s.qualified > 0 && s.qualified < TARGET_PER_ALGO).length;
  const empty = summary.filter(s => s.qualified === 0).length;
  log(`Full (5000 tokens): ${full}/${ALGO_FILTERS.length} algos`);
  log(`Partial (<5000):    ${partial}/${ALGO_FILTERS.length} algos`);
  log(`Empty (0 tokens):   ${empty}/${ALGO_FILTERS.length} algos`);

  // Count unique mints across all algos (for candle fetch dedup)
  const allMints = new Set<string>();
  for (const filter of ALGO_FILTERS) {
    const data = readJSON<ScoredToken[]>(`qualified/qualified_${filter.algo_id}.json`);
    if (data) data.forEach(t => allMints.add(t.mint));
  }
  log(`\nUnique mints across all algos: ${allMints.size} (for candle fetch dedup)`);

  log(`\n✓ Phase 3 complete: ${ALGO_FILTERS.length} algos filtered`);
  log(`  → qualified/qualified_{algo_id}.json`);
  log(`  → qualified/qualified_{algo_id}.csv`);
  log(`  → qualified/filter_summary.json`);
}

main().catch(err => {
  logError('Fatal error in filtering', err);
  process.exit(1);
});
