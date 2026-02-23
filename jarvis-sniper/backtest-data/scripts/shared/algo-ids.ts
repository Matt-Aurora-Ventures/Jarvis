/**
 * Backtest strategy IDs (source of truth).
 *
 * Keep this list in sync with:
 * - backtest-data/scripts/03_filter_by_algo.ts (filters)
 * - backtest-data/scripts/05_simulate_trades.ts (exit params)
 * - jarvis-sniper runtime STRATEGY_PRESETS (live presets)
 *
 * NOTE: The backtest pipeline leaves old `qualified_*` / `results_*` files around.
 * Scripts must use this list to avoid accidentally processing stale strategy IDs.
 */

export const CURRENT_ALGO_IDS = [
  // Memecoin core + wide
  'pump_fresh_tight',
  'micro_cap_surge',
  'elite',
  'momentum',
  'hybrid_b',
  'let_it_ride',

  // Established tokens
  'sol_veteran',
  'utility_swing',
  'established_breakout',
  'meme_classic',
  'volume_spike',

  // Bags.fm
  'bags_fresh_snipe',
  'bags_momentum',
  'bags_value',
  'bags_dip_buyer',
  'bags_bluechip',
  'bags_conservative',
  'bags_aggressive',
  'bags_elite',

  // Blue chips
  'bluechip_trend_follow',
  'bluechip_breakout',

  // Tokenized equities (xStocks / PreStocks / Indexes)
  'xstock_intraday',
  'xstock_swing',
  'prestock_speculative',
  'index_intraday',
  'index_leveraged',
] as const;

export type AlgoId = (typeof CURRENT_ALGO_IDS)[number];

