import { describe, it, expect } from 'vitest';
import type { EnhancedBacktestResult, EnhancedBacktestConfig } from '../analysis/historical-data.js';
import {
  STRATEGY_PRESETS,
  buildFullConfig,
  extractStrategyResult,
  computeRankings,
  generateRecommendations,
  analyzeTimeOfDay,
  type StrategyPreset,
  type StrategyResultEntry,
  type MassiveBacktestReport,
} from '../scripts/massive-backtest.js';
import type { PumpFunHistoricalToken } from '../analysis/historical-data.js';

// ─── Helpers ─────────────────────────────────────────────────
function makeMockResult(overrides: Partial<EnhancedBacktestResult> = {}): EnhancedBacktestResult {
  return {
    config: {} as EnhancedBacktestConfig,
    totalTokensAnalyzed: 100,
    tokensPassedFilter: 50,
    totalTrades: 20,
    wins: 12,
    losses: 8,
    winRate: 0.6,
    totalPnlUsd: 5.0,
    totalPnlPct: 10,
    maxDrawdownPct: 3,
    sharpeRatio: 1.2,
    profitFactor: 2.5,
    avgWinPct: 25,
    avgLossPct: -12,
    expectancy: 0.25,
    rugsAvoided: 5,
    rugsHit: 1,
    bestTrade: { symbol: 'BEST', pnlPct: 80 },
    worstTrade: { symbol: 'WORST', pnlPct: -20 },
    avgHoldTimeMin: 45,
    trades: [
      {
        symbol: 'TOKEN1',
        source: 'pumpfun',
        entryPrice: 0.001,
        exitPrice: 0.002,
        pnlPct: 80,
        pnlUsd: 2.0,
        exitReason: 'TAKE_PROFIT_SCALED',
        holdTimeMin: 30,
        safetyScore: 0.7,
      },
      {
        symbol: 'TOKEN2',
        source: 'raydium',
        entryPrice: 0.005,
        exitPrice: 0.003,
        pnlPct: -20,
        pnlUsd: -0.5,
        exitReason: 'STOP_LOSS',
        holdTimeMin: 60,
        safetyScore: 0.6,
      },
    ],
    ...overrides,
  };
}

// ─── Tests ───────────────────────────────────────────────────

describe('STRATEGY_PRESETS', () => {
  it('should define exactly 22 strategy presets', () => {
    expect(STRATEGY_PRESETS).toHaveLength(22);
  });

  it('should have unique names for all presets', () => {
    const names = STRATEGY_PRESETS.map(p => p.name);
    const unique = new Set(names);
    expect(unique.size).toBe(22);
  });

  it('should include all expected preset names', () => {
    const names = STRATEGY_PRESETS.map(p => p.name);
    expect(names).toContain('TRAIL_8');
    expect(names).toContain('MOMENTUM');
    expect(names).toContain('SCALP');
    expect(names).toContain('DEGEN');
    expect(names).toContain('VETERAN_SURGE');
    expect(names).toContain('SMART_FLOW');
    // Data-driven strategies from backtest v1 findings
    expect(names).toContain('SURGE_HUNTER');
    expect(names).toContain('PUMPSWAP_ALPHA');
    expect(names).toContain('ESTABLISHED_MOMENTUM');
    expect(names).toContain('FRESH_DEGEN');
    expect(names).toContain('GENETIC_BEST');
    expect(names).toContain('NO_VETERANS');
    // Experimental strategies replacing XSTOCKS, TIGHT, SAFE
    expect(names).toContain('MICRO_CAP_SURGE');
    expect(names).toContain('PUMP_FRESH_TIGHT');
    expect(names).toContain('WIDE_NET');
    // Confirm removed strategies are gone
    expect(names).not.toContain('XSTOCKS');
    expect(names).not.toContain('TIGHT');
    expect(names).not.toContain('SAFE');
  });

  it('should have valid SL/TP/Trail values for each preset', () => {
    for (const preset of STRATEGY_PRESETS) {
      expect(preset.stopLossPct).toBeGreaterThan(0);
      expect(preset.takeProfitPct).toBeGreaterThan(0);
      expect(preset.trailingStopPct).toBeGreaterThan(0);
      expect(preset.minLiquidityUsd).toBeGreaterThanOrEqual(0);
      expect(preset.safetyScoreMin).toBeGreaterThanOrEqual(0);
      expect(preset.safetyScoreMin).toBeLessThanOrEqual(1);
    }
  });

  it('DEGEN should have the loosest parameters', () => {
    const degen = STRATEGY_PRESETS.find(p => p.name === 'DEGEN')!;
    expect(degen.stopLossPct).toBe(40);
    expect(degen.takeProfitPct).toBe(200);
    expect(degen.minLiquidityUsd).toBe(10000);
    expect(degen.safetyScoreMin).toBe(0.40);
  });

  it('MICRO_CAP_SURGE should target micro-cap tokens with volume surge', () => {
    const mcs = STRATEGY_PRESETS.find(p => p.name === 'MICRO_CAP_SURGE')!;
    expect(mcs).toBeDefined();
    expect(mcs.stopLossPct).toBe(45);
    expect(mcs.takeProfitPct).toBe(250);
    expect(mcs.trailingStopPct).toBe(20);
    expect(mcs.minLiquidityUsd).toBe(3000);
    expect(mcs.safetyScoreMin).toBe(0.30);
    expect(mcs.requireVolumeSurge).toBe(true);
    expect(mcs.minVolumeSurgeRatio).toBe(3.0);
    expect(mcs.ageCategory).toBe('fresh');
    expect(mcs.adaptiveExits).toBe(false);
  });

  it('VETERAN_SURGE should require volume surge', () => {
    const vs = STRATEGY_PRESETS.find(p => p.name === 'VETERAN_SURGE')!;
    expect(vs.requireVolumeSurge).toBe(true);
    expect(vs.minVolumeSurgeRatio).toBe(2.0);
    expect(vs.ageCategory).toBe('veteran');
  });

  it('PUMP_FRESH_TIGHT should target pumpswap fresh tokens with tight exits', () => {
    const pft = STRATEGY_PRESETS.find(p => p.name === 'PUMP_FRESH_TIGHT')!;
    expect(pft).toBeDefined();
    expect(pft.stopLossPct).toBe(20);
    expect(pft.takeProfitPct).toBe(80);
    expect(pft.trailingStopPct).toBe(8);
    expect(pft.minLiquidityUsd).toBe(5000);
    expect(pft.safetyScoreMin).toBe(0.40);
    expect(pft.ageCategory).toBe('fresh');
    expect(pft.sourceFilter).toBe('pumpswap');
    expect(pft.adaptiveExits).toBe(false);
  });

  it('WIDE_NET should use very relaxed filters with wide exits', () => {
    const wn = STRATEGY_PRESETS.find(p => p.name === 'WIDE_NET')!;
    expect(wn).toBeDefined();
    expect(wn.stopLossPct).toBe(50);
    expect(wn.takeProfitPct).toBe(300);
    expect(wn.trailingStopPct).toBe(25);
    expect(wn.minLiquidityUsd).toBe(1000);
    expect(wn.safetyScoreMin).toBe(0.20);
    expect(wn.adaptiveExits).toBe(false);
  });

  // ─── Data-Driven Strategy Tests ──────────────────────────────

  it('SURGE_HUNTER should require volume surge with wide exits', () => {
    const sh = STRATEGY_PRESETS.find(p => p.name === 'SURGE_HUNTER')!;
    expect(sh.requireVolumeSurge).toBe(true);
    expect(sh.minVolumeSurgeRatio).toBe(2.5);
    expect(sh.stopLossPct).toBe(35);
    expect(sh.takeProfitPct).toBe(150);
    expect(sh.trailingStopPct).toBe(15);
    expect(sh.minLiquidityUsd).toBe(5000);
    expect(sh.safetyScoreMin).toBe(0.40);
    expect(sh.adaptiveExits).toBe(false);
  });

  it('PUMPSWAP_ALPHA should filter to pumpswap source', () => {
    const pa = STRATEGY_PRESETS.find(p => p.name === 'PUMPSWAP_ALPHA')!;
    expect(pa.sourceFilter).toBe('pumpswap');
    expect(pa.stopLossPct).toBe(30);
    expect(pa.takeProfitPct).toBe(120);
    expect(pa.trailingStopPct).toBe(12);
    expect(pa.minLiquidityUsd).toBe(10000);
    expect(pa.safetyScoreMin).toBe(0.45);
    expect(pa.adaptiveExits).toBe(false);
  });

  it('ESTABLISHED_MOMENTUM should target established tokens with adaptive exits', () => {
    const em = STRATEGY_PRESETS.find(p => p.name === 'ESTABLISHED_MOMENTUM')!;
    expect(em.ageCategory).toBe('established');
    expect(em.adaptiveExits).toBe(true);
    expect(em.stopLossPct).toBe(20);
    expect(em.takeProfitPct).toBe(75);
    expect(em.trailingStopPct).toBe(10);
    expect(em.minLiquidityUsd).toBe(25000);
    expect(em.safetyScoreMin).toBe(0.50);
  });

  it('FRESH_DEGEN should target fresh tokens with aggressive parameters', () => {
    const fd = STRATEGY_PRESETS.find(p => p.name === 'FRESH_DEGEN')!;
    expect(fd.ageCategory).toBe('fresh');
    expect(fd.stopLossPct).toBe(40);
    expect(fd.takeProfitPct).toBe(200);
    expect(fd.trailingStopPct).toBe(18);
    expect(fd.minLiquidityUsd).toBe(3000);
    expect(fd.safetyScoreMin).toBe(0.35);
    expect(fd.adaptiveExits).toBe(false);
  });

  it('GENETIC_BEST should use genetic optimizer champion parameters', () => {
    const gb = STRATEGY_PRESETS.find(p => p.name === 'GENETIC_BEST')!;
    expect(gb).toBeDefined();
    expect(gb.stopLossPct).toBe(35);
    expect(gb.takeProfitPct).toBe(200);
    expect(gb.trailingStopPct).toBe(12);
    expect(gb.minLiquidityUsd).toBe(3000);
    expect(gb.safetyScoreMin).toBe(0.43);
    expect(gb.ageCategory).toBe('fresh');
    expect(gb.adaptiveExits).toBe(false);
  });

  it('NO_VETERANS should exclude veteran age category', () => {
    const nv = STRATEGY_PRESETS.find(p => p.name === 'NO_VETERANS')!;
    expect(nv.excludeAge).toEqual(['veteran']);
    expect(nv.stopLossPct).toBe(30);
    expect(nv.takeProfitPct).toBe(150);
    expect(nv.trailingStopPct).toBe(12);
    expect(nv.minLiquidityUsd).toBe(15000);
    expect(nv.safetyScoreMin).toBe(0.45);
    expect(nv.adaptiveExits).toBe(true);
  });

  // ─── Time-Filtered Strategy Tests ──────────────────────────────

  it('PUMP_FRESH_PEAK_HOURS should filter to UTC peak hours 12-18', () => {
    const pfph = STRATEGY_PRESETS.find(p => p.name === 'PUMP_FRESH_PEAK_HOURS')!;
    expect(pfph).toBeDefined();
    expect(pfph.stopLossPct).toBe(20);
    expect(pfph.takeProfitPct).toBe(80);
    expect(pfph.trailingStopPct).toBe(8);
    expect(pfph.minLiquidityUsd).toBe(5000);
    expect(pfph.safetyScoreMin).toBe(0.40);
    expect(pfph.ageCategory).toBe('fresh');
    expect(pfph.sourceFilter).toBe('pumpswap');
    expect(pfph.adaptiveExits).toBe(false);
    expect(pfph.allowedEntryHoursUtc).toEqual([12, 13, 14, 15, 16, 17, 18]);
  });

  it('SURGE_NIGHT_OWL should filter to Asian session hours 0-8', () => {
    const sno = STRATEGY_PRESETS.find(p => p.name === 'SURGE_NIGHT_OWL')!;
    expect(sno).toBeDefined();
    expect(sno.stopLossPct).toBe(35);
    expect(sno.takeProfitPct).toBe(150);
    expect(sno.trailingStopPct).toBe(15);
    expect(sno.minLiquidityUsd).toBe(5000);
    expect(sno.safetyScoreMin).toBe(0.40);
    expect(sno.requireVolumeSurge).toBe(true);
    expect(sno.minVolumeSurgeRatio).toBe(2.5);
    expect(sno.adaptiveExits).toBe(false);
    expect(sno.allowedEntryHoursUtc).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8]);
  });

  it('should include time-filtered preset names', () => {
    const names = STRATEGY_PRESETS.map(p => p.name);
    expect(names).toContain('PUMP_FRESH_PEAK_HOURS');
    expect(names).toContain('SURGE_NIGHT_OWL');
  });

  // ─── Asset Class Strategy Tests ──────────────────────────────

  it('should include all 4 asset class strategy preset names', () => {
    const names = STRATEGY_PRESETS.map(p => p.name);
    expect(names).toContain('XSTOCK_MOMENTUM');
    expect(names).toContain('PRESTOCK_SPECULATIVE');
    expect(names).toContain('INDEX_MEAN_REVERT');
    expect(names).toContain('COMMODITY_TREND');
  });

  it('XSTOCK_MOMENTUM should target xstock asset type with tight exits and US hours', () => {
    const xm = STRATEGY_PRESETS.find(p => p.name === 'XSTOCK_MOMENTUM')!;
    expect(xm).toBeDefined();
    expect(xm.stopLossPct).toBe(3);
    expect(xm.takeProfitPct).toBe(8);
    expect(xm.trailingStopPct).toBe(2);
    expect(xm.minLiquidityUsd).toBe(1000);
    expect(xm.safetyScoreMin).toBe(0.20);
    expect(xm.assetType).toBe('xstock');
    expect(xm.adaptiveExits).toBe(false);
    expect(xm.allowedEntryHoursUtc).toEqual([14, 15, 16, 17, 18, 19, 20]);
  });

  it('PRESTOCK_SPECULATIVE should target prestock asset type with wide exits', () => {
    const ps = STRATEGY_PRESETS.find(p => p.name === 'PRESTOCK_SPECULATIVE')!;
    expect(ps).toBeDefined();
    expect(ps.stopLossPct).toBe(15);
    expect(ps.takeProfitPct).toBe(50);
    expect(ps.trailingStopPct).toBe(8);
    expect(ps.minLiquidityUsd).toBe(500);
    expect(ps.safetyScoreMin).toBe(0.15);
    expect(ps.assetType).toBe('prestock');
    expect(ps.adaptiveExits).toBe(false);
    expect(ps.allowedEntryHoursUtc).toBeUndefined();
  });

  it('INDEX_MEAN_REVERT should target index asset type with very tight exits and US hours', () => {
    const imr = STRATEGY_PRESETS.find(p => p.name === 'INDEX_MEAN_REVERT')!;
    expect(imr).toBeDefined();
    expect(imr.stopLossPct).toBe(2);
    expect(imr.takeProfitPct).toBe(5);
    expect(imr.trailingStopPct).toBe(1.5);
    expect(imr.minLiquidityUsd).toBe(1000);
    expect(imr.safetyScoreMin).toBe(0.20);
    expect(imr.assetType).toBe('index');
    expect(imr.adaptiveExits).toBe(false);
    expect(imr.allowedEntryHoursUtc).toEqual([14, 15, 16, 17, 18, 19, 20]);
  });

  it('COMMODITY_TREND should target commodity asset type with trend-following exits', () => {
    const ct = STRATEGY_PRESETS.find(p => p.name === 'COMMODITY_TREND')!;
    expect(ct).toBeDefined();
    expect(ct.stopLossPct).toBe(4);
    expect(ct.takeProfitPct).toBe(12);
    expect(ct.trailingStopPct).toBe(3);
    expect(ct.minLiquidityUsd).toBe(500);
    expect(ct.safetyScoreMin).toBe(0.20);
    expect(ct.assetType).toBe('commodity');
    expect(ct.adaptiveExits).toBe(false);
    expect(ct.allowedEntryHoursUtc).toBeUndefined();
  });
});

describe('buildFullConfig', () => {
  it('should produce a complete EnhancedBacktestConfig from a preset', () => {
    const preset = STRATEGY_PRESETS[0]; // TRAIL_8
    const config = buildFullConfig(preset);

    // Check all required fields of EnhancedBacktestConfig exist
    expect(config.initialCapitalUsd).toBeDefined();
    expect(config.maxPositionUsd).toBeDefined();
    expect(config.stopLossPct).toBe(preset.stopLossPct);
    expect(config.takeProfitPct).toBe(preset.takeProfitPct);
    expect(config.trailingStopPct).toBe(preset.trailingStopPct);
    expect(config.minLiquidityUsd).toBe(preset.minLiquidityUsd);
    expect(config.safetyScoreMin).toBe(preset.safetyScoreMin);
    expect(config.source).toBe('all');
    expect(config.maxConcurrentPositions).toBeGreaterThan(0);
  });

  it('should carry over optional preset fields like ageCategory', () => {
    const veteran = STRATEGY_PRESETS.find(p => p.name === 'VETERAN_SURGE')!;
    const config = buildFullConfig(veteran);
    expect(config.ageCategory).toBe('veteran');
    expect(config.requireVolumeSurge).toBe(true);
    expect(config.adaptiveExits).toBe(false);  // Fixed params, not adaptive
  });

  it('should set defaults for fields not specified in preset', () => {
    const scalp = STRATEGY_PRESETS.find(p => p.name === 'SCALP')!;
    const config = buildFullConfig(scalp);
    // SCALP does not set ageCategory, should default to 'all'
    expect(config.ageCategory).toBe('all');
    expect(config.requireVolumeSurge).toBe(false);
    expect(config.assetType).toBe('all');
  });

  it('should wire sourceFilter to config.source for PUMPSWAP_ALPHA', () => {
    const pa = STRATEGY_PRESETS.find(p => p.name === 'PUMPSWAP_ALPHA')!;
    const config = buildFullConfig(pa);
    expect(config.source).toBe('pumpswap');
  });

  it('should default source to all when sourceFilter is not set', () => {
    const degen = STRATEGY_PRESETS.find(p => p.name === 'DEGEN')!;
    const config = buildFullConfig(degen);
    expect(config.source).toBe('all');
  });

  it('should wire SURGE_HUNTER volume surge fields correctly', () => {
    const sh = STRATEGY_PRESETS.find(p => p.name === 'SURGE_HUNTER')!;
    const config = buildFullConfig(sh);
    expect(config.requireVolumeSurge).toBe(true);
    expect(config.minVolumeSurgeRatio).toBe(2.5);
    expect(config.adaptiveExits).toBe(false);
  });

  it('should default useOhlcv to false for speed in massive backtest', () => {
    // All presets should produce configs with useOhlcv: false by default
    // OHLCV adds 50+ API calls and ~2 minutes per run
    for (const preset of STRATEGY_PRESETS) {
      const config = buildFullConfig(preset);
      expect(config.useOhlcv).toBe(false);
    }
  });

  it('should pass through allowedEntryHoursUtc from preset', () => {
    const pfph = STRATEGY_PRESETS.find(p => p.name === 'PUMP_FRESH_PEAK_HOURS')!;
    const config = buildFullConfig(pfph);
    expect(config.allowedEntryHoursUtc).toEqual([12, 13, 14, 15, 16, 17, 18]);
  });

  it('should default allowedEntryHoursUtc to undefined when preset has none', () => {
    const scalp = STRATEGY_PRESETS.find(p => p.name === 'SCALP')!;
    const config = buildFullConfig(scalp);
    expect(config.allowedEntryHoursUtc).toBeUndefined();
  });

  it('should pass through xstock assetType for XSTOCK_MOMENTUM', () => {
    const xm = STRATEGY_PRESETS.find(p => p.name === 'XSTOCK_MOMENTUM')!;
    const config = buildFullConfig(xm);
    expect(config.assetType).toBe('xstock');
  });

  it('should pass through prestock assetType for PRESTOCK_SPECULATIVE', () => {
    const ps = STRATEGY_PRESETS.find(p => p.name === 'PRESTOCK_SPECULATIVE')!;
    const config = buildFullConfig(ps);
    expect(config.assetType).toBe('prestock');
  });

  it('should pass through index assetType for INDEX_MEAN_REVERT', () => {
    const imr = STRATEGY_PRESETS.find(p => p.name === 'INDEX_MEAN_REVERT')!;
    const config = buildFullConfig(imr);
    expect(config.assetType).toBe('index');
  });

  it('should pass through commodity assetType for COMMODITY_TREND', () => {
    const ct = STRATEGY_PRESETS.find(p => p.name === 'COMMODITY_TREND')!;
    const config = buildFullConfig(ct);
    expect(config.assetType).toBe('commodity');
  });
});

describe('extractStrategyResult', () => {
  it('should extract relevant fields from EnhancedBacktestResult', () => {
    const result = makeMockResult();
    const entry = extractStrategyResult('TEST_STRATEGY', result, 0.55);

    expect(entry.name).toBe('TEST_STRATEGY');
    expect(entry.winRate).toBe(0.6);
    expect(entry.totalTrades).toBe(20);
    expect(entry.pnlUsd).toBe(5.0);
    expect(entry.pnlPct).toBe(10);
    expect(entry.sharpe).toBe(1.2);
    expect(entry.profitFactor).toBe(2.5);
    expect(entry.maxDrawdown).toBe(3);
    expect(entry.avgWin).toBe(25);
    expect(entry.avgLoss).toBe(-12);
    expect(entry.bestTrade).toEqual({ symbol: 'BEST', pnlPct: 80 });
    expect(entry.worstTrade).toEqual({ symbol: 'WORST', pnlPct: -20 });
    expect(entry.rugsAvoided).toBe(5);
    expect(entry.rugsHit).toBe(1);
    expect(entry.fitnessScore).toBe(0.55);
    expect(entry.avgHoldTime).toBe(45);
  });

  it('should handle zero-trade results gracefully', () => {
    const result = makeMockResult({
      totalTrades: 0,
      wins: 0,
      losses: 0,
      winRate: 0,
      totalPnlUsd: 0,
      totalPnlPct: 0,
      avgHoldTimeMin: 0,
      bestTrade: { symbol: 'N/A', pnlPct: 0 },
      worstTrade: { symbol: 'N/A', pnlPct: 0 },
    });
    const entry = extractStrategyResult('EMPTY', result, 0.01);

    expect(entry.totalTrades).toBe(0);
    expect(entry.winRate).toBe(0);
    expect(entry.fitnessScore).toBe(0.01);
  });
});

describe('computeRankings', () => {
  it('should rank strategies by win rate descending', () => {
    const entries: StrategyResultEntry[] = [
      { name: 'A', winRate: 0.5, totalTrades: 10, pnlUsd: 3, pnlPct: 6, sharpe: 0.8, profitFactor: 2, maxDrawdown: 5, avgWin: 20, avgLoss: -10, bestTrade: { symbol: 'X', pnlPct: 30 }, worstTrade: { symbol: 'Y', pnlPct: -10 }, rugsAvoided: 2, rugsHit: 0, fitnessScore: 0.4, avgHoldTime: 30 },
      { name: 'B', winRate: 0.7, totalTrades: 15, pnlUsd: 8, pnlPct: 16, sharpe: 1.5, profitFactor: 3, maxDrawdown: 2, avgWin: 25, avgLoss: -8, bestTrade: { symbol: 'X', pnlPct: 50 }, worstTrade: { symbol: 'Y', pnlPct: -5 }, rugsAvoided: 3, rugsHit: 1, fitnessScore: 0.6, avgHoldTime: 40 },
      { name: 'C', winRate: 0.6, totalTrades: 8, pnlUsd: 1, pnlPct: 2, sharpe: 2.0, profitFactor: 4, maxDrawdown: 1, avgWin: 15, avgLoss: -7, bestTrade: { symbol: 'X', pnlPct: 20 }, worstTrade: { symbol: 'Y', pnlPct: -3 }, rugsAvoided: 1, rugsHit: 0, fitnessScore: 0.5, avgHoldTime: 20 },
    ];

    const rankings = computeRankings(entries);

    expect(rankings.byWinRate).toEqual(['B', 'C', 'A']);
    expect(rankings.byPnl).toEqual(['B', 'A', 'C']);
    expect(rankings.bySharpe).toEqual(['C', 'B', 'A']);
    expect(rankings.byFitness).toEqual(['B', 'C', 'A']);
  });

  it('should handle empty entries', () => {
    const rankings = computeRankings([]);
    expect(rankings.byWinRate).toEqual([]);
    expect(rankings.byPnl).toEqual([]);
    expect(rankings.bySharpe).toEqual([]);
    expect(rankings.byFitness).toEqual([]);
  });

  it('should handle single entry', () => {
    const entries: StrategyResultEntry[] = [
      { name: 'ONLY', winRate: 0.5, totalTrades: 10, pnlUsd: 3, pnlPct: 6, sharpe: 0.8, profitFactor: 2, maxDrawdown: 5, avgWin: 20, avgLoss: -10, bestTrade: { symbol: 'X', pnlPct: 30 }, worstTrade: { symbol: 'Y', pnlPct: -10 }, rugsAvoided: 2, rugsHit: 0, fitnessScore: 0.4, avgHoldTime: 30 },
    ];
    const rankings = computeRankings(entries);
    expect(rankings.byWinRate).toEqual(['ONLY']);
  });
});

describe('generateRecommendations', () => {
  it('should produce at least one recommendation', () => {
    const entries: StrategyResultEntry[] = [
      { name: 'TRAIL_8', winRate: 0.65, totalTrades: 20, pnlUsd: 7, pnlPct: 14, sharpe: 1.5, profitFactor: 3, maxDrawdown: 3, avgWin: 25, avgLoss: -10, bestTrade: { symbol: 'X', pnlPct: 50 }, worstTrade: { symbol: 'Y', pnlPct: -15 }, rugsAvoided: 4, rugsHit: 1, fitnessScore: 0.55, avgHoldTime: 40 },
    ];

    const recs = generateRecommendations(entries, []);
    expect(recs.length).toBeGreaterThan(0);
  });

  it('should mention the highest win rate strategy', () => {
    const entries: StrategyResultEntry[] = [
      { name: 'ALPHA', winRate: 0.8, totalTrades: 20, pnlUsd: 10, pnlPct: 20, sharpe: 2.0, profitFactor: 5, maxDrawdown: 2, avgWin: 30, avgLoss: -8, bestTrade: { symbol: 'X', pnlPct: 60 }, worstTrade: { symbol: 'Y', pnlPct: -5 }, rugsAvoided: 5, rugsHit: 0, fitnessScore: 0.7, avgHoldTime: 35 },
      { name: 'BETA', winRate: 0.4, totalTrades: 15, pnlUsd: -2, pnlPct: -4, sharpe: 0.3, profitFactor: 0.8, maxDrawdown: 8, avgWin: 15, avgLoss: -12, bestTrade: { symbol: 'X', pnlPct: 20 }, worstTrade: { symbol: 'Y', pnlPct: -15 }, rugsAvoided: 1, rugsHit: 3, fitnessScore: 0.2, avgHoldTime: 50 },
    ];

    const recs = generateRecommendations(entries, []);
    const hasWinRateRec = recs.some(r => r.includes('ALPHA') && r.includes('win rate'));
    expect(hasWinRateRec).toBe(true);
  });

  it('should mention best Sharpe ratio strategy', () => {
    const entries: StrategyResultEntry[] = [
      { name: 'LOW_SHARPE', winRate: 0.7, totalTrades: 20, pnlUsd: 5, pnlPct: 10, sharpe: 0.5, profitFactor: 2, maxDrawdown: 5, avgWin: 20, avgLoss: -10, bestTrade: { symbol: 'X', pnlPct: 30 }, worstTrade: { symbol: 'Y', pnlPct: -10 }, rugsAvoided: 3, rugsHit: 0, fitnessScore: 0.5, avgHoldTime: 40 },
      { name: 'HIGH_SHARPE', winRate: 0.6, totalTrades: 18, pnlUsd: 4, pnlPct: 8, sharpe: 2.5, profitFactor: 3, maxDrawdown: 2, avgWin: 18, avgLoss: -8, bestTrade: { symbol: 'X', pnlPct: 25 }, worstTrade: { symbol: 'Y', pnlPct: -5 }, rugsAvoided: 4, rugsHit: 0, fitnessScore: 0.55, avgHoldTime: 35 },
    ];

    const recs = generateRecommendations(entries, []);
    const hasSharpeRec = recs.some(r => r.includes('HIGH_SHARPE') && (r.includes('Sharpe') || r.includes('risk-adjusted')));
    expect(hasSharpeRec).toBe(true);
  });

  it('should include cross-category insight when data is present', () => {
    const entries: StrategyResultEntry[] = [
      { name: 'TRAIL_8', winRate: 0.6, totalTrades: 20, pnlUsd: 5, pnlPct: 10, sharpe: 1.0, profitFactor: 2, maxDrawdown: 3, avgWin: 20, avgLoss: -10, bestTrade: { symbol: 'X', pnlPct: 30 }, worstTrade: { symbol: 'Y', pnlPct: -10 }, rugsAvoided: 3, rugsHit: 0, fitnessScore: 0.5, avgHoldTime: 40 },
    ];

    const crossCat = [
      { strategy: 'TRAIL_8', category: 'veteran', winRate: 0.75, trades: 10, pnlUsd: 5, sharpe: 1.5 },
      { strategy: 'TRAIL_8', category: 'fresh', winRate: 0.45, trades: 8, pnlUsd: -1, sharpe: 0.3 },
    ];

    const recs = generateRecommendations(entries, crossCat);
    // Should have a recommendation about category performance
    expect(recs.length).toBeGreaterThan(0);
  });

  it('should handle all-zero strategies gracefully', () => {
    const entries: StrategyResultEntry[] = [
      { name: 'ZERO', winRate: 0, totalTrades: 0, pnlUsd: 0, pnlPct: 0, sharpe: 0, profitFactor: 0, maxDrawdown: 0, avgWin: 0, avgLoss: 0, bestTrade: { symbol: 'N/A', pnlPct: 0 }, worstTrade: { symbol: 'N/A', pnlPct: 0 }, rugsAvoided: 0, rugsHit: 0, fitnessScore: 0, avgHoldTime: 0 },
    ];

    const recs = generateRecommendations(entries, []);
    // Should not crash, may produce minimal recommendations
    expect(Array.isArray(recs)).toBe(true);
  });
});

// ─── Helper: mock token ─────────────────────────────────────
function makeMockToken(overrides: Partial<PumpFunHistoricalToken> = {}): PumpFunHistoricalToken {
  return {
    mint: 'mock_mint_' + Math.random().toString(36).slice(2),
    symbol: 'MOCK',
    name: 'Mock Token',
    createdAt: Date.now() / 1000,
    launchPriceUsd: 0.001,
    peakPriceUsd: 0.01,
    currentPriceUsd: 0.005,
    price5min: 0.002,
    price15min: 0.003,
    price1h: 0.004,
    price4h: 0.005,
    price24h: 0.005,
    liquidityUsd: 50000,
    volumeUsd24h: 100000,
    holderCount: 500,
    buyCount1h: 100,
    sellCount1h: 50,
    wasRug: false,
    ruggedAtPct: 0,
    maxMultiple: 10,
    source: 'pumpfun',
    ageHours: 24,
    ageCategory: 'fresh',
    volumeSurgeRatio: 1.0,
    avgDailyVolume: 50000,
    isVolumeSurge: false,
    marketCapUsd: 500000,
    mcapLiqRatio: 10,
    isEstablished: false,
    isVeteran: false,
    isBlueChip: false,
    isXStock: false,
    btcCorrelation: 0.5,
    priceTrajectory: 'pumping',
    ...overrides,
  };
}

describe('analyzeTimeOfDay', () => {
  it('should return empty stats for empty trades', () => {
    const result = makeMockResult({ trades: [] });
    const tokens: PumpFunHistoricalToken[] = [];

    const analysis = analyzeTimeOfDay(result, tokens);

    expect(analysis.hourlyStats).toEqual([]);
    expect(analysis.bestHours).toEqual([]);
    expect(analysis.worstHours).toEqual([]);
  });

  it('should group trades by UTC hour of token creation', () => {
    // Token created at 2026-01-15 03:00 UTC (hour 3)
    const token3am = makeMockToken({
      symbol: 'ALPHA',
      createdAt: new Date('2026-01-15T03:30:00Z').getTime() / 1000,
      source: 'pumpfun',
    });
    // Token created at 2026-01-15 14:00 UTC (hour 14)
    const token2pm = makeMockToken({
      symbol: 'BETA',
      createdAt: new Date('2026-01-15T14:45:00Z').getTime() / 1000,
      source: 'raydium',
    });
    // Another token at hour 3
    const token3amB = makeMockToken({
      symbol: 'GAMMA',
      createdAt: new Date('2026-01-16T03:10:00Z').getTime() / 1000,
      source: 'pumpswap',
    });

    const result = makeMockResult({
      trades: [
        { symbol: 'ALPHA', source: 'pumpfun', entryPrice: 0.001, exitPrice: 0.002, pnlPct: 100, pnlUsd: 2.0, exitReason: 'TAKE_PROFIT', holdTimeMin: 30, safetyScore: 0.7 },
        { symbol: 'BETA', source: 'raydium', entryPrice: 0.005, exitPrice: 0.003, pnlPct: -40, pnlUsd: -1.0, exitReason: 'STOP_LOSS', holdTimeMin: 60, safetyScore: 0.6 },
        { symbol: 'GAMMA', source: 'pumpswap', entryPrice: 0.002, exitPrice: 0.003, pnlPct: 50, pnlUsd: 1.0, exitReason: 'TRAILING_STOP', holdTimeMin: 45, safetyScore: 0.65 },
      ],
    });

    const tokens = [token3am, token2pm, token3amB];
    const analysis = analyzeTimeOfDay(result, tokens);

    // Should have stats for hours 3 and 14
    const hour3 = analysis.hourlyStats.find(s => s.hour === 3);
    const hour14 = analysis.hourlyStats.find(s => s.hour === 14);

    expect(hour3).toBeDefined();
    expect(hour3!.trades).toBe(2);
    expect(hour3!.winRate).toBe(1.0); // Both ALPHA (+100%) and GAMMA (+50%) are wins
    expect(hour3!.avgPnlPct).toBe(75); // (100 + 50) / 2

    expect(hour14).toBeDefined();
    expect(hour14!.trades).toBe(1);
    expect(hour14!.winRate).toBe(0); // BETA is a loss
    expect(hour14!.avgPnlPct).toBe(-40);
  });

  it('should identify best and worst hours correctly', () => {
    // Create tokens at different hours with different outcomes
    // Hour 9: two winning trades
    const tokenH9a = makeMockToken({
      symbol: 'WIN1',
      createdAt: new Date('2026-01-15T09:00:00Z').getTime() / 1000,
    });
    const tokenH9b = makeMockToken({
      symbol: 'WIN2',
      createdAt: new Date('2026-01-16T09:30:00Z').getTime() / 1000,
    });
    // Hour 15: two losing trades
    const tokenH15a = makeMockToken({
      symbol: 'LOSE1',
      createdAt: new Date('2026-01-15T15:00:00Z').getTime() / 1000,
    });
    const tokenH15b = makeMockToken({
      symbol: 'LOSE2',
      createdAt: new Date('2026-01-16T15:30:00Z').getTime() / 1000,
    });
    // Hour 21: mixed (one win, one loss)
    const tokenH21a = makeMockToken({
      symbol: 'MIX1',
      createdAt: new Date('2026-01-15T21:00:00Z').getTime() / 1000,
    });
    const tokenH21b = makeMockToken({
      symbol: 'MIX2',
      createdAt: new Date('2026-01-16T21:30:00Z').getTime() / 1000,
    });

    const result = makeMockResult({
      trades: [
        { symbol: 'WIN1', source: 'pumpfun', entryPrice: 0.001, exitPrice: 0.002, pnlPct: 100, pnlUsd: 2.0, exitReason: 'TAKE_PROFIT', holdTimeMin: 30, safetyScore: 0.7 },
        { symbol: 'WIN2', source: 'pumpfun', entryPrice: 0.001, exitPrice: 0.003, pnlPct: 200, pnlUsd: 4.0, exitReason: 'TAKE_PROFIT', holdTimeMin: 40, safetyScore: 0.8 },
        { symbol: 'LOSE1', source: 'raydium', entryPrice: 0.005, exitPrice: 0.002, pnlPct: -60, pnlUsd: -1.5, exitReason: 'STOP_LOSS', holdTimeMin: 20, safetyScore: 0.5 },
        { symbol: 'LOSE2', source: 'raydium', entryPrice: 0.005, exitPrice: 0.001, pnlPct: -80, pnlUsd: -2.0, exitReason: 'STOP_LOSS', holdTimeMin: 15, safetyScore: 0.4 },
        { symbol: 'MIX1', source: 'pumpswap', entryPrice: 0.002, exitPrice: 0.003, pnlPct: 50, pnlUsd: 1.0, exitReason: 'TRAILING_STOP', holdTimeMin: 45, safetyScore: 0.65 },
        { symbol: 'MIX2', source: 'pumpswap', entryPrice: 0.002, exitPrice: 0.001, pnlPct: -50, pnlUsd: -1.0, exitReason: 'STOP_LOSS', holdTimeMin: 25, safetyScore: 0.55 },
      ],
    });

    const tokens = [tokenH9a, tokenH9b, tokenH15a, tokenH15b, tokenH21a, tokenH21b];
    const analysis = analyzeTimeOfDay(result, tokens);

    // Best hours: hour 9 has 100% WR and highest avgPnL
    expect(analysis.bestHours).toContain(9);
    // Worst hours: hour 15 has 0% WR and worst avgPnL
    expect(analysis.worstHours).toContain(15);
    // Hour 9 should NOT be in worst, hour 15 should NOT be in best
    expect(analysis.bestHours).not.toContain(15);
    expect(analysis.worstHours).not.toContain(9);
  });
});
