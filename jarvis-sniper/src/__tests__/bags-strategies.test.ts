import { describe, it, expect } from 'vitest';
import type { BagsStrategy } from '@/lib/bags-strategies';

// ────────────────────────────────────────────────────────────────
// Test Suite: Bags Strategy Presets
//
// Validates:
// 1. All 8 required presets exist
// 2. Each preset has correct shape and reasonable defaults
// 3. Parameter ranges are sane (TP > SL for profitable R:R)
// 4. getStrategiesByRisk returns correct tiers
// 5. Presets are exportable for UI consumption
// ────────────────────────────────────────────────────────────────

describe('BAGS_STRATEGY_PRESETS', () => {
  it('should export BAGS_STRATEGY_PRESETS array', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    expect(Array.isArray(BAGS_STRATEGY_PRESETS)).toBe(true);
    expect(BAGS_STRATEGY_PRESETS.length).toBe(8);
  });

  it('should contain the 8 required preset IDs', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const ids = BAGS_STRATEGY_PRESETS.map((p: BagsStrategy) => p.id);
    expect(ids).toContain('bags_fresh_snipe');
    expect(ids).toContain('bags_momentum');
    expect(ids).toContain('bags_value');
    expect(ids).toContain('bags_dip_buyer');
    expect(ids).toContain('bags_bluechip');
    expect(ids).toContain('bags_conservative');
    expect(ids).toContain('bags_aggressive');
    expect(ids).toContain('bags_elite');
  });

  it('every preset should have all required fields', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    for (const preset of BAGS_STRATEGY_PRESETS) {
      expect(preset.id).toBeTruthy();
      expect(preset.name).toBeTruthy();
      expect(preset.description).toBeTruthy();
      expect(preset.backtestWinRate).toBeTruthy();
      expect(typeof preset.backtestTrades).toBe('number');
      expect(preset.params).toBeDefined();
      expect(typeof preset.params.stopLossPct).toBe('number');
      expect(typeof preset.params.takeProfitPct).toBe('number');
      expect(typeof preset.params.trailingStopPct).toBe('number');
      expect(typeof preset.params.entryDelayMinutes).toBe('number');
      expect(typeof preset.params.minScore).toBe('number');
    }
  });

  it('all preset IDs should be unique', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const ids = BAGS_STRATEGY_PRESETS.map((p: BagsStrategy) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe('preset parameter sanity', () => {
  it('takeProfitPct should always be greater than stopLossPct (TP > SL for profitable R:R)', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    for (const preset of BAGS_STRATEGY_PRESETS) {
      expect(preset.params.takeProfitPct).toBeGreaterThan(preset.params.stopLossPct);
    }
  });

  it('stopLossPct should be between 1 and 60', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    for (const preset of BAGS_STRATEGY_PRESETS) {
      expect(preset.params.stopLossPct).toBeGreaterThanOrEqual(1);
      expect(preset.params.stopLossPct).toBeLessThanOrEqual(60);
    }
  });

  it('takeProfitPct should be between 9 and 100', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    for (const preset of BAGS_STRATEGY_PRESETS) {
      expect(preset.params.takeProfitPct).toBeGreaterThanOrEqual(9);
      expect(preset.params.takeProfitPct).toBeLessThanOrEqual(100);
    }
  });

  it('trailingStopPct should be 99 (disabled) for all R4 presets', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    for (const preset of BAGS_STRATEGY_PRESETS) {
      expect(preset.params.trailingStopPct).toBe(99);
    }
  });

  it('entryDelayMinutes should be between 0 and 15', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    for (const preset of BAGS_STRATEGY_PRESETS) {
      expect(preset.params.entryDelayMinutes).toBeGreaterThanOrEqual(0);
      expect(preset.params.entryDelayMinutes).toBeLessThanOrEqual(15);
    }
  });

  it('minScore should be between 0 and 100', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    for (const preset of BAGS_STRATEGY_PRESETS) {
      expect(preset.params.minScore).toBeGreaterThanOrEqual(0);
      expect(preset.params.minScore).toBeLessThanOrEqual(100);
    }
  });
});

describe('individual preset defaults', () => {
  it('BAGS CONSERVATIVE should have sweep-optimized params', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const p = BAGS_STRATEGY_PRESETS.find((s: BagsStrategy) => s.id === 'bags_conservative')!;
    expect(p.params.takeProfitPct).toBeGreaterThan(p.params.stopLossPct);
    expect(p.backtestWinRate).toBe('51.3%');
    expect(p.backtestTrades).toBe(78);
  });

  it('BAGS MOMENTUM should have sweep-optimized params', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const p = BAGS_STRATEGY_PRESETS.find((s: BagsStrategy) => s.id === 'bags_momentum')!;
    expect(p.params.takeProfitPct).toBeGreaterThan(p.params.stopLossPct);
    expect(p.backtestWinRate).toBe('29.5%');
    expect(p.backtestTrades).toBe(61);
  });

  it('BAGS VALUE should require high score', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const p = BAGS_STRATEGY_PRESETS.find((s: BagsStrategy) => s.id === 'bags_value')!;
    expect(p.params.minScore).toBeGreaterThanOrEqual(50);
    expect(p.backtestWinRate).toBe('50.7%');
    expect(p.backtestTrades).toBe(71);
  });

  it('BAGS AGGRESSIVE should have wide TP', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const p = BAGS_STRATEGY_PRESETS.find((s: BagsStrategy) => s.id === 'bags_aggressive')!;
    expect(p.params.takeProfitPct).toBeGreaterThanOrEqual(20);
    expect(p.params.takeProfitPct).toBeGreaterThan(p.params.stopLossPct);
    expect(p.backtestWinRate).toBe('33.3%');
    expect(p.backtestTrades).toBe(105);
  });

  it('BAGS ELITE should require score > 70 and tight risk', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const p = BAGS_STRATEGY_PRESETS.find((s: BagsStrategy) => s.id === 'bags_elite')!;
    expect(p.params.minScore).toBeGreaterThanOrEqual(70);
    expect(p.params.stopLossPct).toBeLessThanOrEqual(10);
    expect(p.backtestWinRate).toBe('55.0%');
    expect(p.backtestTrades).toBe(40);
  });

  it('BAGS FRESH SNIPE should target fresh launches', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const p = BAGS_STRATEGY_PRESETS.find((s: BagsStrategy) => s.id === 'bags_fresh_snipe')!;
    expect(p.params.takeProfitPct).toBeGreaterThan(p.params.stopLossPct);
    expect(p.backtestWinRate).toBe('37.5%');
    expect(p.backtestTrades).toBe(48);
  });

  it('BAGS DIP BUYER should have moderate risk', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const p = BAGS_STRATEGY_PRESETS.find((s: BagsStrategy) => s.id === 'bags_dip_buyer')!;
    expect(p.params.takeProfitPct).toBeGreaterThan(p.params.stopLossPct);
    expect(p.backtestWinRate).toBe('36.4%');
    expect(p.backtestTrades).toBe(110);
  });

  it('BAGS BLUECHIP should have highest win rate', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const p = BAGS_STRATEGY_PRESETS.find((s: BagsStrategy) => s.id === 'bags_bluechip')!;
    expect(p.params.minScore).toBeGreaterThanOrEqual(60);
    expect(p.backtestWinRate).toBe('54.5%');
    expect(p.backtestTrades).toBe(66);
  });
});

describe('getStrategiesByRisk', () => {
  it('should export getStrategiesByRisk function', async () => {
    const { getStrategiesByRisk } = await import('@/lib/bags-strategies');
    expect(typeof getStrategiesByRisk).toBe('function');
  });

  it('should return strategies filtered by risk level', async () => {
    const { getStrategiesByRisk } = await import('@/lib/bags-strategies');

    const low = getStrategiesByRisk('low');
    const medium = getStrategiesByRisk('medium');
    const high = getStrategiesByRisk('high');

    expect(low.length).toBeGreaterThan(0);
    expect(medium.length).toBeGreaterThan(0);
    expect(high.length).toBeGreaterThan(0);

    // Low risk strategies should have tighter SL
    for (const s of low) {
      expect(s.params.stopLossPct).toBeLessThanOrEqual(20);
    }
  });
});

describe('getBagsStrategyById', () => {
  it('should export getBagsStrategyById function', async () => {
    const { getBagsStrategyById } = await import('@/lib/bags-strategies');
    expect(typeof getBagsStrategyById).toBe('function');
  });

  it('should return correct strategy by ID', async () => {
    const { getBagsStrategyById } = await import('@/lib/bags-strategies');
    const elite = getBagsStrategyById('bags_elite');
    expect(elite).toBeDefined();
    expect(elite!.id).toBe('bags_elite');
  });

  it('should return undefined for unknown ID', async () => {
    const { getBagsStrategyById } = await import('@/lib/bags-strategies');
    const unknown = getBagsStrategyById('does_not_exist');
    expect(unknown).toBeUndefined();
  });
});
