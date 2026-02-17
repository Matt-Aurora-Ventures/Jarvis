// ─── Token Universe Types ───

export interface TokenRecord {
  mint: string;
  symbol: string;
  name: string;
  pool_address: string;
  creation_timestamp: number; // unix epoch seconds
  liquidity_usd: number;
  volume_24h_usd: number;
  price_change_1h: number;
  price_usd: number;
  buy_txn_count_24h: number;
  sell_txn_count_24h: number;
  holder_count: number;
  has_twitter: boolean;
  has_website: boolean;
  has_telegram: boolean;
  source: 'geckoterminal' | 'dexscreener' | 'jupiter_gems' | 'birdeye' | 'pumpfun' | 'helius';
  /**
   * Confidence score for this record's source data in [0,1].
   * Optional to keep compatibility with old cached datasets.
   */
  source_confidence?: number;
  /**
   * Free-form source metadata useful for provenance (endpoint, flags, etc).
   */
  source_details?: Record<string, unknown>;
}

export interface ScoredToken extends TokenRecord {
  score: number;
  score_bonding: number;
  score_holders: number;
  score_social: number;
  score_liquidity: number;
}

// ─── Algo Filter Definitions ───

export interface AlgoFilter {
  algo_id: string;
  category: 'memecoin' | 'bags' | 'bluechip' | 'xstock' | 'index' | 'established';
  min_score?: number;
  min_liquidity_usd?: number;
  min_momentum_1h?: number;
  max_age_hours?: number;
  min_age_hours?: number;
  min_vol_liq_ratio?: number;
}

export interface AlgoExitParams {
  algo_id: string;
  stopLossPct: number;
  takeProfitPct: number;
  trailingStopPct: number;
  maxPositionAgeHours?: number;
}

// ─── OHLCV Candle Types ───

export interface Candle {
  timestamp: number; // unix epoch seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface CandleIndex {
  [mint: string]: {
    pool_address: string;
    timeframes: {
      '5m'?: { count: number; file: string };
      '15m'?: { count: number; file: string };
      '1h'?: { count: number; file: string };
      '1d'?: { count: number; file: string };
    };
  };
}

// ─── Trade Simulation Types ───

export type ExitReason = 'sl_hit' | 'tp_hit' | 'trail_stop' | 'expired' | 'end_of_data';

export interface TradeResult {
  algo_id: string;
  mint: string;
  symbol: string;
  name: string;
  entry_timestamp: number;
  entry_price_usd: number;
  exit_timestamp: number;
  exit_price_usd: number;
  pnl_percent: number;
  pnl_usd: number; // normalized to $100 position
  exit_reason: ExitReason;
  /** True when both SL and TP were hit in the same candle (counted as SL). */
  dual_trigger_bar?: boolean;
  high_water_mark_price: number;
  high_water_mark_percent: number;
  trade_duration_hours: number;
  candles_in_trade: number;
  score_at_entry: number;
  liquidity_at_entry: number;
  momentum_1h_at_entry: number;
  vol_liq_ratio_at_entry: number;
}

// ─── Summary Types ───

export interface AlgoSummary {
  algo_id: string;
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  max_win_pct: number;
  max_loss_pct: number;
  avg_trade_duration_hours: number;
  median_trade_duration_hours: number;
  profit_factor: number;
  expectancy_per_trade_pct: number;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  dual_trigger_bars: number;
  expiry_exits_below_entry: number;
  exit_distribution: Record<ExitReason, number>;
  monthly_breakdown: { month: string; trades: number; pnl_pct: number; win_rate: number }[];
  best_day: string;
  worst_day: string;
}

// ─── Progress Tracking ───

export interface DiscoveryProgress {
  phase: string;
  geckoterminal_new_pools_page: number;
  geckoterminal_top_pools_page: number;
  dexscreener_profiles_done: boolean;
  dexscreener_boosts_done: boolean;
  jupiter_gems_done: boolean;
  birdeye_done?: boolean;
  pumpfun_done?: boolean;
  helius_enrichment_done?: boolean;
  total_tokens_discovered: number;
  last_updated: string;
}

export interface CandleFetchProgress {
  total_mints: number;
  completed_mints: string[];
  failed_mints: { mint: string; error: string }[];
  last_updated: string;
}

// ─── Data Manifest ───

export interface DataManifest {
  created_at: string;
  pipeline_version: string;
  phases: {
    [phase: string]: {
      completed_at: string;
      files: { path: string; rows?: number; sha256: string }[];
    };
  };
}

export type SampleBand = 'ROBUST' | 'MEDIUM' | 'THIN';
export type StrategyStatusLabel = 'PROVEN' | 'EXPERIMENTAL' | 'EXPERIMENTAL_DISABLED';

export interface ConsistencyReportRow {
  algo_id: string;
  trades: number;
  win_rate: number;
  profit_factor: number;
  expectancy_pct: number;
  total_return_pct: number;
  min_pos_frac: number;
  avg_pos_frac: number;
  sample_band: SampleBand;
  status_label: StrategyStatusLabel;
  pos10?: number;
  pos25?: number;
  pos50?: number;
  pos100?: number;
  pos250?: number;
  pos500?: number;
  pos1000?: number;
}

export interface WalkforwardFoldMetrics {
  fold: number;
  train_trades: number;
  validate_trades: number;
  validate_win_rate: number;
  validate_profit_factor: number;
  validate_expectancy_pct: number;
  validate_total_return_pct: number;
}

export interface WalkforwardSummary {
  algo_id: string;
  folds: number;
  total_trades: number;
  validated_trades: number;
  pass_folds: number;
  fail_folds: number;
  pass_rate: number;
  sample_band: SampleBand;
  status_label: StrategyStatusLabel;
  fold_metrics: WalkforwardFoldMetrics[];
}
