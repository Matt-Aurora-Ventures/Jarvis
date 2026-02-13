import { describe, expect, it } from 'vitest';
import {
  qualifiesByWrGate,
  resolveAdaptiveThreshold,
  selectBestWrGateStrategy,
  type WrGateCandidate,
} from '@/lib/auto-wr-gate';
import type { BacktestMetaEntry, SniperConfig } from '@/stores/useSniperStore';

const BASE_CONFIG: Pick<
  SniperConfig,
  'autoWrPrimaryPct' | 'autoWrFallbackPct' | 'autoWrMinTrades' | 'autoWrMethod'
> = {
  autoWrPrimaryPct: 70,
  autoWrFallbackPct: 50,
  autoWrMinTrades: 1000,
  autoWrMethod: 'wilson95_lower',
};

function makeMeta(overrides: Partial<BacktestMetaEntry> = {}): BacktestMetaEntry {
  return {
    winRate: '72.0%',
    trades: 1200,
    totalTrades: 1200,
    backtested: true,
    dataSource: 'gecko',
    underperformer: false,
    winRatePct: 72,
    winRateLower95Pct: 70.2,
    winRateUpper95Pct: 73.8,
    netPnlPct: 12.5,
    profitFactorValue: 1.8,
    ...overrides,
  };
}

describe('auto-wr-gate', () => {
  it('passes/fails on Wilson 95% lower bound at threshold edge', () => {
    const pass = qualifiesByWrGate(makeMeta({ winRateLower95Pct: 70 }), BASE_CONFIG, 70);
    const fail = qualifiesByWrGate(makeMeta({ winRateLower95Pct: 69.99 }), BASE_CONFIG, 70);

    expect(pass.ok).toBe(true);
    expect(pass.metric).toBe('winRateLower95Pct');
    expect(fail.ok).toBe(false);
    expect(fail.reason).toBe('below_threshold');
  });

  it('rejects when sample size is below minimum', () => {
    const res = qualifiesByWrGate(
      makeMeta({ trades: 999, totalTrades: 999, winRateLower95Pct: 90 }),
      BASE_CONFIG,
      70,
    );
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('insufficient_sample');
    expect(res.totalTrades).toBe(999);
  });

  it('falls back from 70 to 50 and selects best net PnL among eligible', () => {
    const candidates: WrGateCandidate[] = [
      {
        strategyId: 'a',
        meta: makeMeta({ winRateLower95Pct: 68.5, netPnlPct: 8 }),
      },
      {
        strategyId: 'b',
        meta: makeMeta({ winRateLower95Pct: 52.1, netPnlPct: 14 }),
      },
      {
        strategyId: 'c',
        meta: makeMeta({ winRateLower95Pct: 49.9, netPnlPct: 22 }),
      },
    ];

    const resolution = resolveAdaptiveThreshold(candidates, BASE_CONFIG);
    expect(resolution.mode).toBe('fallback');
    expect(resolution.usedThreshold).toBe(50);
    expect(resolution.eligibleCount).toBe(2);

    const selection = selectBestWrGateStrategy(candidates, BASE_CONFIG);
    expect(selection.selected?.strategyId).toBe('b');
    expect(selection.selectedThresholdSource).toBe('fallback');
    expect(selection.selectedThresholdPct).toBe(50);
  });

  it('supports per-strategy primary override (pump_fresh_tight @50) while global primary remains 70', () => {
    const candidates: WrGateCandidate[] = [
      {
        strategyId: 'pump_fresh_tight',
        primaryThresholdOverridePct: 50,
        meta: makeMeta({ winRateLower95Pct: 54, netPnlPct: 7 }),
      },
      {
        strategyId: 'bags_momentum',
        meta: makeMeta({ winRateLower95Pct: 64, netPnlPct: 20 }),
      },
    ];

    const resolution = resolveAdaptiveThreshold(candidates, BASE_CONFIG);
    expect(resolution.mode).toBe('primary');
    expect(resolution.usedThreshold).toBe(70);
    expect(resolution.eligibleCount).toBe(1);
    expect(resolution.eligible[0]?.strategyId).toBe('pump_fresh_tight');

    const selection = selectBestWrGateStrategy(candidates, BASE_CONFIG);
    expect(selection.selected?.strategyId).toBe('pump_fresh_tight');
    expect(selection.selectedThresholdSource).toBe('primary_override');
    expect(selection.selectedThresholdPct).toBe(50);
  });
});
