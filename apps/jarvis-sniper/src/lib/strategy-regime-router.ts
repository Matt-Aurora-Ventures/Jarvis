import type { BagsGraduation } from '@/lib/bags-api';
import type { ResolvedStrategyLifecycle } from '@/lib/strategy-lifecycle';
import type {
  AssetType,
  StrategyPreset,
  StrategyPrimarySignalType,
  StrategyRegime,
} from '@/stores/useSniperStore';

export interface StrategyEventContext {
  assetType: AssetType;
  regime: StrategyRegime;
  primarySignalType: StrategyPrimarySignalType;
  eventBias:
    | 'launch_freshness'
    | 'bags_launch'
    | 'liquidity_migration'
    | 'established_confirmation'
    | 'bluechip_confirmation'
    | 'disabled_market';
  freshLaunchCount: number;
  averageLiquidityUsd: number;
  averageBuySellRatio: number;
  volumeImpulse: number;
}

function toFiniteNumber(value: unknown, fallback = 0): number {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function regimeForAssetType(assetType: AssetType): StrategyRegime {
  switch (assetType) {
    case 'bags':
      return 'bags_launch';
    case 'established':
      return 'established_sol';
    case 'bluechip':
      return 'bluechip_sol';
    case 'xstock':
    case 'prestock':
      return 'xstock';
    case 'index':
      return 'index';
    case 'memecoin':
    default:
      return 'launch_memecoin';
  }
}

function primarySignalTypeForRegime(regime: StrategyRegime): StrategyPrimarySignalType {
  return regime === 'launch_memecoin' || regime === 'bags_launch' ? 'event' : 'confirmation';
}

export function deriveStrategyEventContext(args: {
  assetType: AssetType;
  graduations?: BagsGraduation[];
}): StrategyEventContext {
  const assetType = args.assetType || 'memecoin';
  const graduations = Array.isArray(args.graduations) ? args.graduations : [];
  const regime = regimeForAssetType(assetType);
  const primarySignalType = primarySignalTypeForRegime(regime);

  const freshLaunchCount = graduations.filter((entry) => toFiniteNumber(entry?.age_hours, 9999) <= 24).length;
  const averageLiquidityUsd = graduations.length > 0
    ? graduations.reduce((sum, entry) => sum + toFiniteNumber(entry?.liquidity, 0), 0) / graduations.length
    : 0;
  const averageBuySellRatio = graduations.length > 0
    ? graduations.reduce((sum, entry) => sum + toFiniteNumber(entry?.buy_sell_ratio, 1), 0) / graduations.length
    : 1;
  const volumeImpulse = graduations.length > 0
    ? graduations.reduce((sum, entry) => {
        const volume = toFiniteNumber(entry?.volume_24h, 0);
        const liquidity = Math.max(1, toFiniteNumber(entry?.liquidity, 0));
        return sum + (volume / liquidity);
      }, 0) / graduations.length
    : 0;

  let eventBias: StrategyEventContext['eventBias'] = 'launch_freshness';
  if (regime === 'bags_launch') eventBias = 'bags_launch';
  else if (regime === 'established_sol') eventBias = 'established_confirmation';
  else if (regime === 'bluechip_sol') eventBias = 'bluechip_confirmation';
  else if (regime === 'xstock' || regime === 'index') eventBias = 'disabled_market';
  else if (freshLaunchCount <= 0 && averageLiquidityUsd >= 100000) eventBias = 'liquidity_migration';

  return {
    assetType,
    regime,
    primarySignalType,
    eventBias,
    freshLaunchCount,
    averageLiquidityUsd: Number(averageLiquidityUsd.toFixed(4)),
    averageBuySellRatio: Number(averageBuySellRatio.toFixed(4)),
    volumeImpulse: Number(volumeImpulse.toFixed(4)),
  };
}

export function selectStrategiesForRegime(args: {
  presets: StrategyPreset[];
  assetType: AssetType;
  graduations?: BagsGraduation[];
  lifecycleById?: Record<string, ResolvedStrategyLifecycle>;
  requireAutoEligible?: boolean;
}): StrategyPreset[] {
  const context = deriveStrategyEventContext({
    assetType: args.assetType,
    graduations: args.graduations,
  });

  return args.presets
    .filter((preset) => preset.regime === context.regime)
    .filter((preset) => {
      const lifecycle = args.lifecycleById?.[preset.id];
      if (!lifecycle) return !args.requireAutoEligible && preset.productionVisible;
      if (args.requireAutoEligible) return lifecycle.autoEligible;
      return lifecycle.lifecycle !== 'disabled' && lifecycle.lifecycle !== 'quarantined';
    })
    .filter((preset) => preset.researchVisible || preset.productionVisible);
}

