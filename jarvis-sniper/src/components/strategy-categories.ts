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
    presetIds: ['elite', 'micro_cap_surge', 'pump_fresh_tight'],
  },
  {
    label: 'MEMECOIN',
    icon: 'Zap',
    presetIds: ['momentum', 'hybrid_b', 'let_it_ride'],
  },
  {
    label: 'ESTABLISHED TOKENS',
    icon: 'Landmark',
    presetIds: ['sol_veteran', 'utility_swing', 'meme_classic'],
  },
  {
    label: 'BAGS.FM',
    icon: 'Package',
    presetIds: ['bags_dip_buyer', 'bags_aggressive', 'bags_bluechip'],
  },
  {
    label: 'EXPERIMENTAL',
    icon: 'FlaskConical',
    presetIds: [
      'volume_spike', 'established_breakout',
      'bags_fresh_snipe', 'bags_momentum', 'bags_value', 'bags_conservative', 'bags_elite',
      'bluechip_trend_follow', 'bluechip_breakout',
      'xstock_intraday', 'xstock_swing', 'prestock_speculative', 'index_intraday', 'index_leveraged',
    ],
  },
];
