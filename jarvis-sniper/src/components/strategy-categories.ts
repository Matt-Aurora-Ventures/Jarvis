/** Strategy categories for the grouped dropdown selector */
export interface StrategyCategory {
  label: string;
  icon: string;
  presetIds: string[];
}

export const STRATEGY_CATEGORIES: StrategyCategory[] = [
  {
    label: 'TOP PERFORMERS',
    icon: 'Trophy',
    // Profitable presets only (default recommendations).
    presetIds: ['pump_fresh_tight', 'utility_swing', 'meme_classic'],
  },
  {
    label: 'MEMECOIN',
    icon: 'Zap',
    presetIds: ['elite', 'micro_cap_surge', 'momentum', 'hybrid_b', 'let_it_ride'],
  },
  {
    label: 'ESTABLISHED TOKENS',
    icon: 'Landmark',
    presetIds: ['sol_veteran', 'volume_spike', 'established_breakout'],
  },
  {
    label: 'BAGS.FM',
    icon: 'Package',
    presetIds: [
      'bags_elite', 'bags_bluechip', 'bags_conservative', 'bags_value',
      'bags_dip_buyer', 'bags_fresh_snipe', 'bags_momentum', 'bags_aggressive',
    ],
  },
  {
    label: 'BLUE CHIP SOLANA',
    icon: 'Shield',
    presetIds: ['bluechip_trend_follow', 'bluechip_breakout'],
  },
  {
    label: 'xSTOCK & INDEX',
    icon: 'TrendingUp',
    presetIds: ['xstock_intraday', 'xstock_swing', 'prestock_speculative', 'index_intraday', 'index_leveraged'],
  },
];
