import { describe, expect, it } from 'vitest';

import { BacktestEngine, type BacktestConfig, type OHLCVCandle } from '@/lib/backtest-engine';

function buildCandles(prices: number[]): OHLCVCandle[] {
  const baseTs = 1_700_000_000_000;
  return prices.map((price, idx) => ({
    timestamp: baseTs + (idx * 60 * 60 * 1000),
    open: price,
    high: price,
    low: price,
    close: price,
    volume: 1_000 + idx,
  }));
}

function buildConfig(overrides: Partial<BacktestConfig> = {}): BacktestConfig {
  return {
    strategyId: 'cost-accounting-check',
    stopLossPct: 50,
    takeProfitPct: 50,
    trailingStopPct: 0,
    minScore: 0,
    minLiquidityUsd: 0,
    slippagePct: 1,
    feePct: 0,
    maxHoldCandles: 1,
    entrySignal: (_c, idx) => idx === 0,
    ...overrides,
  };
}

describe('backtest cost accounting contract', () => {
  it('does not subtract slippage twice from pnlNet', () => {
    const engine = new BacktestEngine(buildCandles([100, 100, 100]), buildConfig({ slippagePct: 1, feePct: 0 }));
    const result = engine.run('TEST');

    expect(result.totalTrades).toBe(1);
    const trade = result.trades[0];

    // Entry/exit slippage is already embedded in execution prices:
    // entry = 100 * 1.01 = 101, exit = 100 * 0.99 = 99
    const expectedGross = ((99 - 101) / 101) * 100;
    expect(trade.pnlPct).toBeCloseTo(expectedGross, 10);
    expect(trade.pnlNet).toBeCloseTo(expectedGross, 10);
  });

  it('reports explicit gross/fee/slippage/net components on each trade', () => {
    const cfg = buildConfig({ slippagePct: 0.5, feePct: 0.2 });
    const engine = new BacktestEngine(buildCandles([100, 101, 102]), cfg);
    const result = engine.run('TEST');

    expect(result.totalTrades).toBe(1);
    const trade = result.trades[0] as unknown as {
      pnlPct: number;
      pnlNet: number;
      grossPnlPct: number;
      feesPct: number;
      slippagePct: number;
      netPnlPct: number;
    };

    const expectedFeesPct = cfg.feePct * 2;
    const expectedNet = trade.pnlPct - expectedFeesPct;

    expect(trade.pnlNet).toBeCloseTo(expectedNet, 10);
    expect(trade.grossPnlPct).toBeCloseTo(trade.pnlPct, 10);
    expect(trade.feesPct).toBeCloseTo(expectedFeesPct, 10);
    expect(trade.slippagePct).toBeCloseTo(cfg.slippagePct, 10);
    expect(trade.netPnlPct).toBeCloseTo(trade.pnlNet, 10);
  });
});
