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
    presetIds: ['pump_fresh_tight', 'insight_j', 'genetic_best', 'genetic_v2'],
  },
  {
    label: 'BALANCED',
    icon: 'Shield',
    presetIds: ['hybrid_b', 'momentum', 'let_it_ride'],
  },
  {
    label: 'AGGRESSIVE',
    icon: 'Zap',
    presetIds: ['micro_cap_surge', 'elite', 'loose'],
  },
  {
    label: 'DEGEN',
    icon: 'Package',
    presetIds: [
      'bags_fresh_snipe',
      'bags_momentum',
      'bags_value',
      'bags_dip_buyer',
      'bags_bluechip',
      'bags_conservative',
      'bags_aggressive',
      'bags_elite',
    ],
  },
  {
    label: 'BLUE CHIP SOLANA',
    icon: 'Gem',
    presetIds: ['bluechip_mean_revert', 'bluechip_trend_follow', 'bluechip_breakout'],
  },
  {
    label: 'XSTOCK & INDEX',
    icon: 'BarChart3',
    presetIds: ['xstock_intraday', 'xstock_swing', 'prestock_speculative', 'index_intraday', 'index_leveraged'],
  },
];
