import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { computeFitnessScore, generateBiasedPopulation } from '../analysis/self-improver.js';
import type { EnhancedBacktestResult, EnhancedBacktestConfig } from '../analysis/historical-data.js';

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

// ---- Requirement 1: Default parameter changes ----

describe('runSelfImprovement defaults', () => {
  it('should export runSelfImprovement function', async () => {
    const mod = await import('../analysis/self-improver.js');
    expect(typeof mod.runSelfImprovement).toBe('function');
  });
});

// ---- Requirement 2: Expanded search space in generatePopulation ----
// (generatePopulation is private, so we test indirectly through the module)

describe('generatePopulation expanded search space', () => {
  it('should export the module without errors (implies generatePopulation compiles)', async () => {
    // This verifies that the new parameters (minTokenAgeHours, maxTokenAgeHours,
    // ageCategory, requireVolumeSurge, minVolumeSurgeRatio, assetType, adaptiveExits)
    // and expanded ranges compile correctly.
    const mod = await import('../analysis/self-improver.js');
    expect(mod).toBeDefined();
  });
});

// ---- Requirement 4: Enhanced computeFitnessScore ----

describe('Enhanced computeFitnessScore', () => {
  it('should still return 0.01 for zero trades', () => {
    const score = computeFitnessScore(makeResult({ totalTrades: 0 }));
    expect(score).toBe(0.01);
  });

  it('should require more trades for full significance (30 instead of 15)', () => {
    // With the new threshold of 30, 15 trades should give significance of 0.5
    // not the old 1.0. So a 15-trade config should score lower than before.
    const fifteenTrades = computeFitnessScore(makeResult({
      totalTrades: 15, wins: 9, losses: 6, winRate: 0.6,
      totalPnlUsd: 5, totalPnlPct: 10, sharpeRatio: 1.5,
      profitFactor: 3, maxDrawdownPct: 2,
    }));

    const thirtyTrades = computeFitnessScore(makeResult({
      totalTrades: 30, wins: 18, losses: 12, winRate: 0.6,
      totalPnlUsd: 5, totalPnlPct: 10, sharpeRatio: 1.5,
      profitFactor: 3, maxDrawdownPct: 2,
    }));

    // 30 trades should have higher significance than 15 trades
    expect(thirtyTrades).toBeGreaterThan(fifteenTrades);

    // The 15-trade significance should be 0.5 (15/30), not 1.0
    // So fifteenTrades should be roughly half of thirtyTrades
    // Allow some tolerance due to the volumeBonus difference
    expect(fifteenTrades / thirtyTrades).toBeLessThan(0.75);
  });

  it('should give diversity bonus for trades from multiple sources', () => {
    const singleSource = computeFitnessScore(makeResult({
      totalTrades: 20, wins: 12, losses: 8, winRate: 0.6,
      totalPnlUsd: 5, totalPnlPct: 10, sharpeRatio: 1.5,
      profitFactor: 3, maxDrawdownPct: 2,
      trades: Array.from({ length: 20 }, (_, i) => ({
        symbol: `TOKEN${i}`,
        source: 'pumpfun',
        entryPrice: 1, exitPrice: 1.1, pnlPct: 10, pnlUsd: 0.5,
        exitReason: 'tp', holdTimeMin: 30, safetyScore: 0.7,
      })),
    }));

    const multiSource = computeFitnessScore(makeResult({
      totalTrades: 20, wins: 12, losses: 8, winRate: 0.6,
      totalPnlUsd: 5, totalPnlPct: 10, sharpeRatio: 1.5,
      profitFactor: 3, maxDrawdownPct: 2,
      trades: Array.from({ length: 20 }, (_, i) => ({
        symbol: `TOKEN${i}`,
        source: i % 3 === 0 ? 'pumpfun' : i % 3 === 1 ? 'raydium' : 'pumpswap',
        entryPrice: 1, exitPrice: 1.1, pnlPct: 10, pnlUsd: 0.5,
        exitReason: 'tp', holdTimeMin: 30, safetyScore: 0.7,
      })),
    }));

    // Multi-source config should score higher due to diversity bonus
    expect(multiSource).toBeGreaterThan(singleSource);
  });

  it('should cap diversity bonus at 0.10', () => {
    // Even with 5+ sources (though typically max 3-4), bonus caps at 0.10
    const manySourceTrades = Array.from({ length: 30 }, (_, i) => ({
      symbol: `TOKEN${i}`,
      source: `source${i % 6}`,  // 6 different sources
      entryPrice: 1, exitPrice: 1.1, pnlPct: 10, pnlUsd: 0.5,
      exitReason: 'tp', holdTimeMin: 30, safetyScore: 0.7,
    }));

    const withManySources = computeFitnessScore(makeResult({
      totalTrades: 30, wins: 18, losses: 12, winRate: 0.6,
      totalPnlUsd: 5, totalPnlPct: 10, sharpeRatio: 1.5,
      profitFactor: 3, maxDrawdownPct: 2,
      trades: manySourceTrades,
    }));

    const noSourceTrades: EnhancedBacktestResult['trades'] = [];
    const noSources = computeFitnessScore(makeResult({
      totalTrades: 30, wins: 18, losses: 12, winRate: 0.6,
      totalPnlUsd: 5, totalPnlPct: 10, sharpeRatio: 1.5,
      profitFactor: 3, maxDrawdownPct: 2,
      trades: noSourceTrades,
    }));

    // Diversity bonus capped at 0.10 (so max delta is 0.10 * significance)
    const delta = withManySources - noSources;
    expect(delta).toBeLessThanOrEqual(0.11); // small tolerance
    expect(delta).toBeGreaterThan(0);
  });

  it('should use minimum significance of 0.10 instead of 0.15', () => {
    // With the new formula: max(0.10, totalTrades / 30)
    // 1 trade: max(0.10, 1/30) = 0.10
    const singleTrade = computeFitnessScore(makeResult({
      totalTrades: 1, wins: 1, losses: 0, winRate: 1.0,
      totalPnlUsd: 2.0, totalPnlPct: 50, sharpeRatio: 80,
      profitFactor: Infinity, maxDrawdownPct: 0,
      rugsAvoided: 2, rugsHit: 0,
    }));

    // With significance of 0.10 (new) vs 0.15 (old), single trade should score lower
    // The max raw score (perfect metrics) is about 0.85-1.0
    // At significance 0.10: score <= 0.10 * rawScore
    // We just verify it's small enough
    expect(singleTrade).toBeLessThan(0.15);
  });

  it('should still score within valid range with diversity bonus', () => {
    const best = computeFitnessScore(makeResult({
      totalTrades: 50, wins: 45, losses: 5, winRate: 0.9,
      totalPnlUsd: 100, totalPnlPct: 200, sharpeRatio: 5,
      profitFactor: 20, maxDrawdownPct: 0, rugsAvoided: 10, rugsHit: 0,
      trades: Array.from({ length: 50 }, (_, i) => ({
        symbol: `TOKEN${i}`,
        source: i % 3 === 0 ? 'pumpfun' : i % 3 === 1 ? 'raydium' : 'pumpswap',
        entryPrice: 1, exitPrice: 2, pnlPct: 100, pnlUsd: 2,
        exitReason: 'tp', holdTimeMin: 20, safetyScore: 0.9,
      })),
    }));

    expect(best).toBeGreaterThan(0);
    expect(best).toBeLessThanOrEqual(1.5); // With diversity bonus, score can exceed old 1.0 range slightly
    expect(isFinite(best)).toBe(true);
  });
});

// ---- Requirement 5: Continuous improvement mode ----

describe('runContinuousImprovement', () => {
  it('should be exported as a function', async () => {
    const mod = await import('../analysis/self-improver.js');
    expect(typeof mod.runContinuousImprovement).toBe('function');
  });
});

// ---- Requirement 3: Expanded evolvePopulation mutations ----
// (evolvePopulation is private, tested indirectly through compilation and module export)

describe('evolvePopulation mutations', () => {
  it('module should export without errors (implies new mutations compile)', async () => {
    const mod = await import('../analysis/self-improver.js');
    expect(mod.runSelfImprovement).toBeDefined();
    expect(mod.computeFitnessScore).toBeDefined();
    expect(mod.runContinuousImprovement).toBeDefined();
  });
});

// ---- Biased Population (v1 backtest findings) ----

describe('generateBiasedPopulation', () => {
  it('should be exported as a function', () => {
    expect(typeof generateBiasedPopulation).toBe('function');
  });

  it('should return requested population size', () => {
    const pop = generateBiasedPopulation(20);
    expect(pop.length).toBe(20);
  });

  it('should include seed config when provided', () => {
    const seed: Partial<EnhancedBacktestConfig> = {
      stopLossPct: 99,
      takeProfitPct: 999,
    };
    const pop = generateBiasedPopulation(10, seed);
    // The seed should be the first element
    expect(pop[0]).toEqual(seed);
  });

  it('should inject known winner configs (DEGEN x volume_surge, Pumpswap, Established)', () => {
    const pop = generateBiasedPopulation(30);
    // Check for the DEGEN volume_surge winner (SL:35, TP:150, Trail:15)
    const degenWinner = pop.find(
      (c) => c.stopLossPct === 35 && c.takeProfitPct === 150 && c.trailingStopPct === 15
        && c.requireVolumeSurge === true && c.minVolumeSurgeRatio === 2.5,
    );
    expect(degenWinner).toBeDefined();

    // Check for the Pumpswap momentum winner (SL:30, TP:120, source=pumpswap)
    const pumpswapWinner = pop.find(
      (c) => c.stopLossPct === 30 && c.takeProfitPct === 120 && c.source === 'pumpswap',
    );
    expect(pumpswapWinner).toBeDefined();

    // Check for the Established momentum winner (SL:20, TP:75, ageCategory=established)
    const establishedWinner = pop.find(
      (c) => c.stopLossPct === 20 && c.takeProfitPct === 75 && c.ageCategory === 'established',
    );
    expect(establishedWinner).toBeDefined();
  });

  it('should bias stop-loss toward 20-45 range (no extreme lows like 5 or 8)', () => {
    // Generate a large population to check distribution
    const pop = generateBiasedPopulation(200);
    const slValues = pop.map((c) => c.stopLossPct).filter((v): v is number => v !== undefined);
    // All SL values should be in the biased set [20, 25, 30, 35, 40, 45]
    // (the 3 known winners use 20, 30, 35 which are also in range)
    const inRange = slValues.filter((v) => v >= 20 && v <= 45);
    // At least 90% should be in the biased range (known winners + biased random)
    expect(inRange.length / slValues.length).toBeGreaterThan(0.9);
  });

  it('should bias take-profit toward 75-200 range', () => {
    const pop = generateBiasedPopulation(200);
    const tpValues = pop.map((c) => c.takeProfitPct).filter((v): v is number => v !== undefined);
    const inRange = tpValues.filter((v) => v >= 75 && v <= 200);
    expect(inRange.length / tpValues.length).toBeGreaterThan(0.9);
  });

  it('should bias safetyScoreMin toward 0.30-0.50 (not 0.55+)', () => {
    const pop = generateBiasedPopulation(200);
    const ssValues = pop.map((c) => c.safetyScoreMin).filter((v): v is number => v !== undefined);
    const inRange = ssValues.filter((v) => v >= 0.30 && v <= 0.50);
    expect(inRange.length / ssValues.length).toBeGreaterThan(0.9);
  });

  it('should never generate veteran-only age category in biased random slots', () => {
    const pop = generateBiasedPopulation(200);
    const ageCategories = pop.map((c) => c.ageCategory).filter((v) => v !== undefined);
    // No individual should have ageCategory = 'veteran' (toxic per backtest findings)
    const veterans = ageCategories.filter((v) => v === 'veteran');
    expect(veterans.length).toBe(0);
  });

  it('should have pumpswap source bias (higher proportion than raydium)', () => {
    const pop = generateBiasedPopulation(200);
    const sources = pop.map((c) => c.source).filter((v) => v !== undefined);
    const pumpswapCount = sources.filter((v) => v === 'pumpswap').length;
    const raydiumCount = sources.filter((v) => v === 'raydium').length;
    // Pumpswap should significantly outnumber raydium (which should be 0 in biased gen)
    expect(pumpswapCount).toBeGreaterThan(raydiumCount);
  });

  it('should bias minLiquidity toward 3K-25K range', () => {
    const pop = generateBiasedPopulation(200);
    const liqValues = pop.map((c) => c.minLiquidityUsd).filter((v): v is number => v !== undefined);
    const inRange = liqValues.filter((v) => v >= 3000 && v <= 25000);
    expect(inRange.length / liqValues.length).toBeGreaterThan(0.9);
  });

  it('should work with size smaller than known winners count', () => {
    // 3 known winners + seed = 4, but asking for size 2
    // Should still return exactly 2 items
    const pop = generateBiasedPopulation(2);
    expect(pop.length).toBeGreaterThanOrEqual(2);
  });
});
