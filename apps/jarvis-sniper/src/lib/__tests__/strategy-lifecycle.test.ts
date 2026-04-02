import { describe, expect, it } from 'vitest';
import { resolveStrategyLifecycle, type StrategyLiveEvidence } from '@/lib/strategy-lifecycle';
import { STRATEGY_PRESETS, type BacktestMetaEntry } from '@/stores/useSniperStore';

function makeMeta(overrides: Partial<BacktestMetaEntry> = {}): BacktestMetaEntry {
  return {
    winRate: '43.0%',
    trades: 240,
    totalTrades: 240,
    backtested: true,
    dataSource: 'mixed',
    underperformer: false,
    winRatePct: 43,
    winRateLower95Pct: 31.2,
    winRateUpper95Pct: 48.8,
    netPnlPct: 8.4,
    profitFactorValue: 1.14,
    stage: 'sanity',
    promotionEligible: false,
    ...overrides,
  };
}

function makeLiveEvidence(overrides: Partial<StrategyLiveEvidence> = {}): StrategyLiveEvidence {
  return {
    confirmedLiveTrades: 0,
    confirmedWins: 0,
    confirmedLosses: 0,
    consecutiveConfirmedLosses: 0,
    liveProfitFactor: 0,
    liveMaxDrawdownPct: 0,
    fillRatePct: 100,
    liveWinRatePct: 0,
    paperWinRateDeltaPct: 0,
    failedExits: 0,
    unresolvedExits: 0,
    ...overrides,
  };
}

describe('strategy-lifecycle', () => {
  it('keeps seeded profitable presets at paper without confirmed live evidence', () => {
    const preset = STRATEGY_PRESETS.find((entry) => entry.id === 'pump_fresh_tight');
    expect(preset).toBeDefined();

    const resolved = resolveStrategyLifecycle({
      preset: preset!,
      meta: makeMeta({
        totalTrades: 1800,
        trades: 1800,
        stage: 'stability',
        winRateLower95Pct: 35.4,
        netPnlPct: 14.2,
        profitFactorValue: 1.22,
      }),
    });

    expect(resolved.lifecycle).toBe('paper');
    expect(resolved.paperEligible).toBe(true);
    expect(resolved.autoEligible).toBe(false);
  });

  it('does not allow seeded presets to become production from backtest data alone', () => {
    const preset = STRATEGY_PRESETS.find((entry) => entry.id === 'utility_swing');
    expect(preset).toBeDefined();

    const resolved = resolveStrategyLifecycle({
      preset: preset!,
      meta: makeMeta({
        totalTrades: 6400,
        trades: 6400,
        stage: 'promotion',
        winRateLower95Pct: 41.8,
        netPnlPct: 26.7,
        profitFactorValue: 1.58,
      }),
    });

    expect(resolved.lifecycle).toBe('paper');
    expect(resolved.sampleStage).toBe('promotion');
    expect(resolved.autoEligible).toBe(false);
  });

  it('promotes paper strategies to micro-live and production only after confirmed reliable trades', () => {
    const preset = STRATEGY_PRESETS.find((entry) => entry.id === 'pump_fresh_tight');
    expect(preset).toBeDefined();

    const microLive = resolveStrategyLifecycle({
      preset: preset!,
      meta: makeMeta({
        totalTrades: 1800,
        trades: 1800,
        stage: 'stability',
        winRateLower95Pct: 34.5,
      }),
      liveEvidence: makeLiveEvidence({
        confirmedLiveTrades: 12,
        confirmedWins: 7,
        confirmedLosses: 5,
        liveProfitFactor: 0.97,
        liveMaxDrawdownPct: 7.1,
        fillRatePct: 90,
        liveWinRatePct: 58.3,
        paperWinRateDeltaPct: 14.8,
      }),
    });

    const production = resolveStrategyLifecycle({
      preset: preset!,
      meta: makeMeta({
        totalTrades: 1800,
        trades: 1800,
        stage: 'stability',
        winRatePct: 49,
        winRateLower95Pct: 34.5,
      }),
      liveEvidence: makeLiveEvidence({
        confirmedLiveTrades: 34,
        confirmedWins: 18,
        confirmedLosses: 16,
        liveProfitFactor: 1.08,
        liveMaxDrawdownPct: 8.9,
        fillRatePct: 92,
        liveWinRatePct: 52.9,
        paperWinRateDeltaPct: 3.9,
      }),
    });

    expect(microLive.lifecycle).toBe('micro_live');
    expect(microLive.autoEligible).toBe(true);
    expect(production.lifecycle).toBe('production');
    expect(production.autoEligible).toBe(true);
  });

  it('quarantines strategies on regime floor failures or repeated confirmed losses', () => {
    const established = STRATEGY_PRESETS.find((entry) => entry.id === 'utility_swing');
    const momentum = STRATEGY_PRESETS.find((entry) => entry.id === 'momentum');
    expect(established).toBeDefined();
    expect(momentum).toBeDefined();

    const floorFailure = resolveStrategyLifecycle({
      preset: established!,
      meta: makeMeta({
        winRatePct: 47,
        winRateLower95Pct: 37.2,
        profitFactorValue: 1.24,
        netPnlPct: 9.7,
      }),
    });

    const repeatedLosses = resolveStrategyLifecycle({
      preset: momentum!,
      meta: makeMeta({
        winRatePct: 33,
        winRateLower95Pct: 31.1,
        profitFactorValue: 1.08,
        netPnlPct: 4.2,
      }),
      liveEvidence: makeLiveEvidence({
        confirmedLiveTrades: 5,
        confirmedWins: 1,
        confirmedLosses: 4,
        consecutiveConfirmedLosses: 3,
        liveProfitFactor: 0.82,
        liveMaxDrawdownPct: 17,
        fillRatePct: 88,
        liveWinRatePct: 20,
        paperWinRateDeltaPct: 13,
      }),
    });

    expect(floorFailure.lifecycle).toBe('quarantined');
    expect(repeatedLosses.lifecycle).toBe('quarantined');
    expect(repeatedLosses.reason).toMatch(/confirmed losses/i);
  });

  it('keeps xstock and index presets disabled from the live catalog', () => {
    const preset = STRATEGY_PRESETS.find((entry) => entry.id === 'xstock_intraday');
    expect(preset).toBeDefined();

    const resolved = resolveStrategyLifecycle({
      preset: preset!,
      meta: makeMeta({
        totalTrades: 3200,
        trades: 3200,
        winRateLower95Pct: 32,
        netPnlPct: -12,
        profitFactorValue: 0.75,
      }),
    });

    expect(resolved.lifecycle).toBe('disabled');
    expect(resolved.autoEligible).toBe(false);
  });
});
