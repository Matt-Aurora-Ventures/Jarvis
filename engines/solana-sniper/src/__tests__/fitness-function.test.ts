import { describe, it, expect } from 'vitest';
import { computeFitnessScore } from '../analysis/self-improver.js';
import type { EnhancedBacktestResult } from '../analysis/historical-data.js';

function makeResult(overrides: Partial<EnhancedBacktestResult>): EnhancedBacktestResult {
  return {
    config: {} as EnhancedBacktestResult['config'],
    totalTokensAnalyzed: 50,
    tokensPassedFilter: 20,
    totalTrades: 10,
    wins: 6,
    losses: 4,
    winRate: 0.6,
    totalPnlUsd: 5.0,
    totalPnlPct: 10,
    maxDrawdownPct: 2,
    sharpeRatio: 1.5,
    profitFactor: 3.0,
    avgWinPct: 20,
    avgLossPct: -10,
    expectancy: 0.5,
    rugsAvoided: 3,
    rugsHit: 0,
    bestTrade: { symbol: 'BEST', pnlPct: 50 },
    worstTrade: { symbol: 'WORST', pnlPct: -15 },
    avgHoldTimeMin: 30,
    trades: [],
    ...overrides,
  };
}

describe('Fitness Function', () => {
  it('should return near-zero for zero trades', () => {
    const score = computeFitnessScore(makeResult({ totalTrades: 0 }));
    expect(score).toBe(0.01);
  });

  it('should heavily penalize single-trade 100% WR configs', () => {
    const singleTrade = computeFitnessScore(makeResult({
      totalTrades: 1, wins: 1, losses: 0, winRate: 1.0,
      totalPnlUsd: 2.0, totalPnlPct: 50, sharpeRatio: 80,
      profitFactor: Infinity, maxDrawdownPct: 0,
      rugsAvoided: 2, rugsHit: 0,
    }));

    const multiTrade = computeFitnessScore(makeResult({
      totalTrades: 15, wins: 9, losses: 6, winRate: 0.6,
      totalPnlUsd: 7.0, totalPnlPct: 14, sharpeRatio: 0.7,
      profitFactor: 3.5, maxDrawdownPct: 3,
      rugsAvoided: 2, rugsHit: 0,
    }));

    // Multi-trade config should score HIGHER than single-trade 100% WR
    expect(multiTrade).toBeGreaterThan(singleTrade);
  });

  it('should reward more trades (statistical significance)', () => {
    const fewTrades = computeFitnessScore(makeResult({
      totalTrades: 3, wins: 2, losses: 1, winRate: 0.67,
      totalPnlUsd: 1.0, totalPnlPct: 2,
    }));

    const manyTrades = computeFitnessScore(makeResult({
      totalTrades: 20, wins: 13, losses: 7, winRate: 0.65,
      totalPnlUsd: 8.0, totalPnlPct: 16,
    }));

    expect(manyTrades).toBeGreaterThan(fewTrades);
  });

  it('should penalize high drawdown', () => {
    const lowDD = computeFitnessScore(makeResult({ maxDrawdownPct: 1 }));
    const highDD = computeFitnessScore(makeResult({ maxDrawdownPct: 30 }));

    expect(lowDD).toBeGreaterThan(highDD);
  });

  it('should reward rug avoidance', () => {
    const avoidsRugs = computeFitnessScore(makeResult({
      rugsAvoided: 5, rugsHit: 0,
    }));
    const hitsRugs = computeFitnessScore(makeResult({
      rugsAvoided: 0, rugsHit: 5,
    }));

    expect(avoidsRugs).toBeGreaterThan(hitsRugs);
  });

  it('should score within valid range', () => {
    const best = computeFitnessScore(makeResult({
      totalTrades: 50, wins: 45, losses: 5, winRate: 0.9,
      totalPnlUsd: 100, totalPnlPct: 200, sharpeRatio: 5,
      profitFactor: 20, maxDrawdownPct: 0, rugsAvoided: 10, rugsHit: 0,
    }));

    expect(best).toBeGreaterThan(0);
    expect(best).toBeLessThanOrEqual(1);
  });

  it('should prefer profitable over unprofitable at same WR', () => {
    const profitable = computeFitnessScore(makeResult({
      totalPnlUsd: 10, totalPnlPct: 20, profitFactor: 5,
    }));
    const unprofitable = computeFitnessScore(makeResult({
      totalPnlUsd: -5, totalPnlPct: -10, profitFactor: 0.5,
    }));

    expect(profitable).toBeGreaterThan(unprofitable);
  });

  it('should strongly prefer higher Sharpe ratios', () => {
    const highSharpe = computeFitnessScore(makeResult({
      totalTrades: 15, winRate: 0.6, sharpeRatio: 2.5,
    }));
    const lowSharpe = computeFitnessScore(makeResult({
      totalTrades: 15, winRate: 0.6, sharpeRatio: 0.3,
    }));

    expect(highSharpe).toBeGreaterThan(lowSharpe);
  });

  it('should handle Infinity profitFactor gracefully', () => {
    const score = computeFitnessScore(makeResult({
      totalTrades: 5, wins: 5, losses: 0, winRate: 1.0,
      profitFactor: Infinity,
    }));

    expect(score).toBeGreaterThan(0);
    expect(score).toBeLessThanOrEqual(1);
    expect(isFinite(score)).toBe(true);
  });

  it('should give consistent scores for same input', () => {
    const result = makeResult({ totalTrades: 20, winRate: 0.65, totalPnlUsd: 8 });
    const score1 = computeFitnessScore(result);
    const score2 = computeFitnessScore(result);

    expect(score1).toBe(score2);
  });
});
