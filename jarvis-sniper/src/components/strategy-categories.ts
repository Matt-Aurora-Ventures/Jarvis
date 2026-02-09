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
    label: 'XSTOCK & INDEX',
    icon: 'BarChart3',
    presetIds: ['xstock_momentum', 'prestock_speculative', 'index_revert'],
  },
];
