import { describe, it, expect } from 'vitest';
import type { BagsStrategy } from '@/lib/bags-strategies';

// ────────────────────────────────────────────────────────────────
// Test Suite: Bags Strategy Presets
//
// Validates:
// 1. All 5 required presets exist
// 2. Each preset has correct shape and reasonable defaults
// 3. Parameter ranges are sane (TP > SL for profitable R:R)
// 4. getStrategiesByRisk returns correct tiers
// 5. Presets are exportable for UI consumption
// ────────────────────────────────────────────────────────────────

describe('BAGS_STRATEGY_PRESETS', () => {
  it('should export BAGS_STRATEGY_PRESETS array', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    expect(Array.isArray(BAGS_STRATEGY_PRESETS)).toBe(true);
    expect(BAGS_STRATEGY_PRESETS.length).toBeGreaterThanOrEqual(5);
  });

  it('should contain the 5 required preset IDs', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const ids = BAGS_STRATEGY_PRESETS.map((p: BagsStrategy) => p.id);
    expect(ids).toContain('bags_conservative');
    expect(ids).toContain('bags_momentum');
    expect(ids).toContain('bags_value');
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

  it('takeProfitPct should be between 10 and 25', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    for (const preset of BAGS_STRATEGY_PRESETS) {
      expect(preset.params.takeProfitPct).toBeGreaterThanOrEqual(10);
      expect(preset.params.takeProfitPct).toBeLessThanOrEqual(25);
    }
  });

  it('trailingStopPct should be between 0 and 30', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    for (const preset of BAGS_STRATEGY_PRESETS) {
      expect(preset.params.trailingStopPct).toBeGreaterThanOrEqual(0);
      expect(preset.params.trailingStopPct).toBeLessThanOrEqual(30);
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
  it('BAGS CONSERVATIVE should have TP > SL (proven profitable)', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const p = BAGS_STRATEGY_PRESETS.find((s: BagsStrategy) => s.id === 'bags_conservative')!;
    expect(p.params.takeProfitPct).toBeGreaterThan(p.params.stopLossPct);
    expect(p.params.stopLossPct).toBeLessThanOrEqual(12);
    expect(p.backtestWinRate).toBe('49.3%');
    expect(p.backtestTrades).toBe(75);
  });

  it('BAGS MOMENTUM should have TP > SL (proven profitable)', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const p = BAGS_STRATEGY_PRESETS.find((s: BagsStrategy) => s.id === 'bags_momentum')!;
    expect(p.params.takeProfitPct).toBeGreaterThan(p.params.stopLossPct);
    expect(p.params.takeProfitPct).toBeGreaterThanOrEqual(12);
    expect(p.backtestWinRate).toBe('42.0%');
    expect(p.backtestTrades).toBe(69);
  });

  it('BAGS VALUE should require high score, patient entry', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const p = BAGS_STRATEGY_PRESETS.find((s: BagsStrategy) => s.id === 'bags_value')!;
    expect(p.params.minScore).toBeGreaterThanOrEqual(50);
    expect(p.backtestWinRate).toBe('47.8%');
    expect(p.backtestTrades).toBe(69);
  });

  it('BAGS AGGRESSIVE should have widest TP for maximum upside', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const p = BAGS_STRATEGY_PRESETS.find((s: BagsStrategy) => s.id === 'bags_aggressive')!;
    expect(p.params.takeProfitPct).toBeGreaterThanOrEqual(18);
    expect(p.params.takeProfitPct).toBeGreaterThan(p.params.stopLossPct);
    expect(p.backtestWinRate).toBe('42.7%');
    expect(p.backtestTrades).toBe(110);
  });

  it('BAGS ELITE should require score > 70 and tight risk', async () => {
    const { BAGS_STRATEGY_PRESETS } = await import('@/lib/bags-strategies');
    const p = BAGS_STRATEGY_PRESETS.find((s: BagsStrategy) => s.id === 'bags_elite')!;
    expect(p.params.minScore).toBeGreaterThanOrEqual(70);
    expect(p.params.stopLossPct).toBeLessThanOrEqual(10);
    expect(p.backtestWinRate).toBe('48.6%');
    expect(p.backtestTrades).toBe(37);
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
