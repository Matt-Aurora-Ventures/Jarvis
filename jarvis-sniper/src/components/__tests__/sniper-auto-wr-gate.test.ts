import { describe, expect, it } from 'vitest';
import {
  buildWrGateCandidates,
  selectBestWrGateStrategy,
} from '@/lib/auto-wr-gate';
import { STRATEGY_PRESETS, type SniperConfig } from '@/stores/useSniperStore';

const GATE_CONFIG: Pick<
  SniperConfig,
  | 'autoWrPrimaryPct'
  | 'autoWrFallbackPct'
  | 'autoWrMinTrades'
  | 'autoWrMethod'
  | 'autoWrScope'
> = {
  autoWrPrimaryPct: 70,
  autoWrFallbackPct: 50,
  autoWrMinTrades: 1000,
  autoWrMethod: 'wilson95_lower',
  autoWrScope: 'memecoin_bags',
};

describe('sniper auto WR gate strategy selection', () => {
  it('chooses highest net PnL among gate-eligible strategies', () => {
    const meta = {
      pump_fresh_tight: {
        winRate: '78%',
        trades: 1800,
        totalTrades: 1800,
        backtested: true,
        dataSource: 'gecko',
        underperformer: false,
        winRatePct: 78,
        winRateLower95Pct: 72.5,
        winRateUpper95Pct: 81.5,
        netPnlPct: 14.2,
        profitFactorValue: 1.7,
      },
      bags_momentum: {
        winRate: '74%',
        trades: 1600,
        totalTrades: 1600,
        backtested: true,
        dataSource: 'gecko',
        underperformer: false,
        winRatePct: 74,
        winRateLower95Pct: 71.2,
        winRateUpper95Pct: 76.8,
        netPnlPct: 21.9,
        profitFactorValue: 1.6,
      },
    } as const;

    const candidates = buildWrGateCandidates(STRATEGY_PRESETS, meta as any, GATE_CONFIG.autoWrScope);
    const selection = selectBestWrGateStrategy(candidates, GATE_CONFIG);

    expect(selection.resolution.mode).toBe('primary');
    expect(selection.selected?.strategyId).toBe('bags_momentum');
    expect(selection.selectedThresholdSource).toBe('global_primary');
    expect(selection.selectedThresholdPct).toBe(70);
  });

  it('falls back from 70 to 50 when primary threshold has no candidates', () => {
    const meta = {
      bags_momentum: {
        winRate: '65%',
        trades: 1200,
        totalTrades: 1200,
        backtested: true,
        dataSource: 'gecko',
        underperformer: false,
        winRatePct: 65,
        winRateLower95Pct: 64.1,
        winRateUpper95Pct: 68.9,
        netPnlPct: 8.5,
        profitFactorValue: 1.3,
      },
    } as const;

    const candidates = buildWrGateCandidates(STRATEGY_PRESETS, meta as any, GATE_CONFIG.autoWrScope);
    const selection = selectBestWrGateStrategy(candidates, GATE_CONFIG);

    expect(selection.resolution.mode).toBe('fallback');
    expect(selection.resolution.usedThreshold).toBe(50);
    expect(selection.selected?.strategyId).toBe('bags_momentum');
    expect(selection.selectedThresholdSource).toBe('fallback');
  });

  it('marks pump_fresh_tight as primary override when selected at 50', () => {
    const meta = {
      pump_fresh_tight: {
        winRate: '55%',
        trades: 1500,
        totalTrades: 1500,
        backtested: true,
        dataSource: 'gecko',
        underperformer: false,
        winRatePct: 55,
        winRateLower95Pct: 53.7,
        winRateUpper95Pct: 57.9,
        netPnlPct: 9.2,
        profitFactorValue: 1.2,
      },
    } as const;

    const candidates = buildWrGateCandidates(STRATEGY_PRESETS, meta as any, GATE_CONFIG.autoWrScope);
    const selection = selectBestWrGateStrategy(candidates, GATE_CONFIG);

    expect(selection.resolution.mode).toBe('primary');
    expect(selection.selected?.strategyId).toBe('pump_fresh_tight');
    expect(selection.selectedThresholdSource).toBe('primary_override');
    expect(selection.selectedThresholdPct).toBe(50);
  });

  it('returns no eligible strategy when none pass fallback threshold', () => {
    const meta = {
      pump_fresh_tight: {
        winRate: '45%',
        trades: 1200,
        totalTrades: 1200,
        backtested: true,
        dataSource: 'gecko',
        underperformer: false,
        winRatePct: 45,
        winRateLower95Pct: 44.1,
        winRateUpper95Pct: 47.8,
        netPnlPct: 3.1,
        profitFactorValue: 0.9,
      },
    } as const;

    const candidates = buildWrGateCandidates(STRATEGY_PRESETS, meta as any, GATE_CONFIG.autoWrScope);
    const selection = selectBestWrGateStrategy(candidates, GATE_CONFIG);

    expect(selection.resolution.mode).toBe('none');
    expect(selection.selected).toBeNull();
  });
});
