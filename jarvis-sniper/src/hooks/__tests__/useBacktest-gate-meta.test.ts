import { describe, expect, it } from 'vitest';
import { buildPresetBacktestUpdates, type BacktestSummary } from '@/hooks/useBacktest';

describe('useBacktest gate metadata mapping', () => {
  it('persists numeric WR CI/sample/PnL fields for store gate usage', () => {
    const rows: BacktestSummary[] = [
      {
        strategyId: 'pump_fresh_tight',
        token: 'A',
        trades: 600,
        winRate: '74.0%',
        winRatePct: 74,
        winRateLower95Pct: 70.5,
        winRateUpper95Pct: 77.2,
        netPnlPct: 6.2,
        profitFactor: '1.80',
        profitFactorValue: 1.8,
        sharpe: '1.2',
        maxDD: '-12%',
        expectancy: '0.01',
        avgHold: '4h',
        dataSource: 'gecko',
        validated: true,
      },
      {
        strategyId: 'pump_fresh_tight',
        token: 'B',
        trades: 400,
        winRate: '70.0%',
        winRatePct: 70,
        winRateLower95Pct: 66.2,
        winRateUpper95Pct: 73.1,
        netPnlPct: 3.4,
        profitFactor: '1.30',
        profitFactorValue: 1.3,
        sharpe: '0.9',
        maxDD: '-15%',
        expectancy: '0.01',
        avgHold: '5h',
        dataSource: 'gecko',
        validated: true,
      },
    ];

    const updates = buildPresetBacktestUpdates(rows);
    expect(updates).toHaveLength(1);
    const row = updates[0];

    expect(row.strategyId).toBe('pump_fresh_tight');
    expect(row.totalTrades).toBe(1000);
    expect(row.winRatePct).toBeCloseTo(72.4, 4);
    expect(row.winRateLower95Pct).toBeCloseTo(68.78, 2);
    expect(row.winRateUpper95Pct).toBeCloseTo(75.56, 2);
    expect(row.netPnlPct).toBeCloseTo(9.6, 6);
    expect(row.profitFactorValue).toBeCloseTo(1.6, 6);
    expect(row.backtested).toBe(true);
    expect(row.stage).toBe('stability');
  });
});

