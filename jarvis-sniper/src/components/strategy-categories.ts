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
    presetIds: ['utility_swing', 'sol_veteran', 'meme_classic'],
  },
  {
    label: 'MEMECOIN',
    icon: 'Zap',
    presetIds: ['elite', 'micro_cap_surge', 'pump_fresh_tight', 'momentum', 'hybrid_b', 'let_it_ride'],
  },
  {
    label: 'ESTABLISHED TOKENS',
    icon: 'Landmark',
    presetIds: ['established_breakout', 'volume_spike'],
  },
  {
    label: 'BAGS.FM',
    icon: 'Package',
    presetIds: [
      'bags_dip_buyer', 'bags_aggressive', 'bags_bluechip',
      'bags_fresh_snipe', 'bags_momentum', 'bags_value', 'bags_conservative', 'bags_elite',
    ],
  },
  {
    label: 'EXPERIMENTAL',
    icon: 'FlaskConical',
    presetIds: [
      'bluechip_trend_follow', 'bluechip_breakout',
      'xstock_intraday', 'xstock_swing', 'prestock_speculative', 'index_intraday', 'index_leveraged',
    ],
  },
];
