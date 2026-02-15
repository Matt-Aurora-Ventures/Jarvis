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
    presetIds: ['pump_fresh_tight', 'genetic_best'],
  },
  {
    label: 'MEMECOIN',
    icon: 'Zap',
    presetIds: ['micro_cap_surge', 'elite'],
  },
  {
    label: 'BAGS.FM',
    icon: 'Package',
    presetIds: [
      'bags_elite',
      'bags_bluechip',
      'bags_conservative',
      'bags_value',
      'bags_dip_buyer',
      'bags_fresh_snipe',
      'bags_momentum',
      'bags_aggressive',
    ],
  },
];
