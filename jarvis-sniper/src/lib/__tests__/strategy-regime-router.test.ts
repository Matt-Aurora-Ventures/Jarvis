import { describe, expect, it } from 'vitest';
import {
  deriveStrategyEventContext,
  selectStrategiesForRegime,
} from '@/lib/strategy-regime-router';
import { STRATEGY_PRESETS } from '@/stores/useSniperStore';
import type { ResolvedStrategyLifecycle } from '@/lib/strategy-lifecycle';
import type { BagsGraduation } from '@/lib/bags-api';

function makeGraduation(overrides: Partial<BagsGraduation> = {}): BagsGraduation {
  return {
    mint: 'mint-1',
    symbol: 'TEST',
    name: 'Test Token',
    score: 62,
    graduation_time: Math.floor(Date.now() / 1000) - 60 * 60,
    bonding_curve_score: 78,
    holder_distribution_score: 61,
    liquidity_score: 54,
    social_score: 40,
    market_cap: 125000,
    price_usd: 0.0042,
    liquidity: 18000,
    volume_24h: 94000,
    price_change_1h: 28,
    txn_buys_1h: 122,
    txn_sells_1h: 34,
    buy_sell_ratio: 3.6,
    age_hours: 4,
    holderCount: 210,
    organicScore: 68,
    ...overrides,
  };
}

function lifecycle(
  lifecycleValue: ResolvedStrategyLifecycle['lifecycle'],
  regime: ResolvedStrategyLifecycle['regime'],
  autoEligible: boolean,
): ResolvedStrategyLifecycle {
  return {
    lifecycle: lifecycleValue,
    regime,
    reason: lifecycleValue,
    sampleStage: 'stability',
    paperEligible: lifecycleValue === 'paper' || autoEligible,
    autoEligible,
    confirmedLiveTrades: autoEligible ? 10 : 0,
    liveProfitFactor: autoEligible ? 1.05 : 0,
    liveMaxDrawdownPct: autoEligible ? 6 : 0,
    fillRatePct: autoEligible ? 90 : 0,
  };
}

describe('strategy-regime-router', () => {
  it('classifies fresh memecoin launches as launch_memecoin event flow', () => {
    const context = deriveStrategyEventContext({
      assetType: 'memecoin',
      graduations: [makeGraduation()],
    });

    expect(context.regime).toBe('launch_memecoin');
    expect(context.primarySignalType).toBe('event');
    expect(context.eventBias).toBe('launch_freshness');
  });

  it('routes bags feeds to the bags_launch regime', () => {
    const context = deriveStrategyEventContext({
      assetType: 'bags',
      graduations: [makeGraduation({ score: 71, age_hours: 10, liquidity: 42000 })],
    });

    expect(context.regime).toBe('bags_launch');
    expect(context.primarySignalType).toBe('event');
  });

  it('routes established and bluechip assets to confirmation-first regimes', () => {
    const established = deriveStrategyEventContext({
      assetType: 'established',
      graduations: [makeGraduation({ age_hours: 720, liquidity: 140000, price_change_1h: 2 })],
    });
    const bluechip = deriveStrategyEventContext({
      assetType: 'bluechip',
      graduations: [makeGraduation({ age_hours: 1800, liquidity: 650000, price_change_1h: 1.5 })],
    });

    expect(established.regime).toBe('established_sol');
    expect(established.primarySignalType).toBe('confirmation');
    expect(bluechip.regime).toBe('bluechip_sol');
    expect(bluechip.primarySignalType).toBe('confirmation');
  });

  it('filters candidates by regime and auto eligibility before WR gate ranking', () => {
    const lifecycleById: Record<string, ResolvedStrategyLifecycle> = {
      pump_fresh_tight: lifecycle('micro_live', 'launch_memecoin', true),
      utility_swing: lifecycle('production', 'established_sol', true),
      bags_value: lifecycle('paper', 'bags_launch', false),
      xstock_intraday: lifecycle('disabled', 'xstock', false),
    };

    const selected = selectStrategiesForRegime({
      presets: STRATEGY_PRESETS,
      assetType: 'memecoin',
      graduations: [makeGraduation()],
      lifecycleById,
      requireAutoEligible: true,
    });

    expect(selected.map((preset) => preset.id)).toEqual(['pump_fresh_tight']);
  });
});
