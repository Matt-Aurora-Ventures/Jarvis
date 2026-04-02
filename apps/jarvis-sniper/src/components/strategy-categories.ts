import { buildStrategyLifecycleMap, type ResolvedStrategyLifecycle } from '@/lib/strategy-lifecycle';
import { regimeForAssetType } from '@/lib/strategy-regime-router';
import type {
  AssetType,
  BacktestMetaEntry,
  Position,
  StrategyLifecycle,
  StrategyPreset,
} from '@/stores/useSniperStore';
import { STRATEGY_PRESETS } from '@/stores/useSniperStore';

export interface StrategyCategory {
  key: 'live' | 'paper' | 'research' | 'disabled';
  label: string;
  icon: string;
  defaultVisible: boolean;
  collapsed?: boolean;
  presetIds: string[];
  emptyMessage?: string;
}

function seedMatchesLifecycle(preset: StrategyPreset, lifecycles: StrategyLifecycle[]): boolean {
  return lifecycles.includes(preset.lifecycleSeed);
}

const STRATEGY_CATEGORY_TEMPLATES: StrategyCategory[] = [
  {
    key: 'live',
    label: 'Live Eligible',
    icon: 'ShieldCheck',
    defaultVisible: true,
    presetIds: [],
    emptyMessage: 'No live-eligible strategy for this regime yet.',
  },
  {
    key: 'paper',
    label: 'Paper Validated',
    icon: 'FlaskConical',
    defaultVisible: true,
    presetIds: [],
  },
  {
    key: 'research',
    label: 'Research Lab',
    icon: 'Rocket',
    defaultVisible: false,
    collapsed: true,
    presetIds: [],
  },
  {
    key: 'disabled',
    label: 'Disabled',
    icon: 'Ban',
    defaultVisible: false,
    collapsed: true,
    presetIds: [],
  },
];

export const STRATEGY_CATEGORIES: StrategyCategory[] = STRATEGY_CATEGORY_TEMPLATES.map((category) => {
  const acceptedLifecycles =
    category.key === 'live'
      ? ([] as StrategyLifecycle[])
      : category.key === 'paper'
        ? (['paper'] as StrategyLifecycle[])
        : category.key === 'research'
          ? (['research'] as StrategyLifecycle[])
          : (['quarantined', 'disabled'] as StrategyLifecycle[]);

  return {
    ...category,
    presetIds: STRATEGY_PRESETS
      .filter((preset) => seedMatchesLifecycle(preset, acceptedLifecycles))
      .map((preset) => preset.id),
  };
});

export interface StrategyCategorySection extends StrategyCategory {
  lifecyclesById: Record<string, ResolvedStrategyLifecycle>;
}

export function buildStrategyCategorySections(args: {
  presets: StrategyPreset[];
  assetType: AssetType;
  backtestMeta?: Record<string, BacktestMetaEntry>;
  positions?: Position[];
  lifecycleById?: Record<string, ResolvedStrategyLifecycle>;
}): StrategyCategorySection[] {
  const lifecycleById = args.lifecycleById || buildStrategyLifecycleMap({
    presets: args.presets,
    backtestMeta: args.backtestMeta,
    positions: args.positions,
  });
  const activeRegime = regimeForAssetType(args.assetType);
  const presetsForRegime = args.presets.filter((preset) => preset.regime === activeRegime);

  const byLifecycle = (accepted: StrategyLifecycle[]) =>
    presetsForRegime
      .filter((preset) => accepted.includes(lifecycleById[preset.id]?.lifecycle || preset.lifecycleSeed))
      .map((preset) => preset.id);

  return [
    {
      ...STRATEGY_CATEGORIES[0],
      presetIds: byLifecycle(['micro_live', 'production']),
      lifecyclesById: lifecycleById,
    },
    {
      ...STRATEGY_CATEGORIES[1],
      presetIds: byLifecycle(['paper']),
      lifecyclesById: lifecycleById,
    },
    {
      ...STRATEGY_CATEGORIES[2],
      presetIds: byLifecycle(['research']),
      lifecyclesById: lifecycleById,
    },
    {
      ...STRATEGY_CATEGORIES[3],
      presetIds: byLifecycle(['quarantined', 'disabled']),
      lifecyclesById: lifecycleById,
    },
  ];
}
