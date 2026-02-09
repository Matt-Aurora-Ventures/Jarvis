import { describe, it, expect } from 'vitest';
import { STRATEGY_PRESETS } from '@/stores/useSniperStore';

// ────────────────────────────────────────────────────────────────
// Test Suite: Strategy Presets — verifies new presets exist and
// the STRATEGY_CATEGORIES grouping is correct.
// ────────────────────────────────────────────────────────────────

describe('STRATEGY_PRESETS', () => {
  // Original 9 presets + 4 new = 13 total
  it('should have 13 total strategy presets', () => {
    expect(STRATEGY_PRESETS.length).toBe(13);
  });

  // ── New presets existence ──
  it('should include genetic_v2 preset', () => {
    const preset = STRATEGY_PRESETS.find(p => p.id === 'genetic_v2');
    expect(preset).toBeDefined();
    expect(preset!.name).toBe('GENETIC V2 (71% WR)');
    expect(preset!.config.stopLossPct).toBe(45);
    expect(preset!.config.takeProfitPct).toBe(207);
    expect(preset!.config.trailingStopPct).toBe(10);
    expect(preset!.config.minLiquidityUsd).toBe(5000);
    expect(preset!.config.strategyMode).toBe('aggressive');
  });

  it('should include xstock_momentum preset', () => {
    const preset = STRATEGY_PRESETS.find(p => p.id === 'xstock_momentum');
    expect(preset).toBeDefined();
    expect(preset!.name).toBe('XSTOCK MOMENTUM');
    expect(preset!.config.stopLossPct).toBe(3);
    expect(preset!.config.takeProfitPct).toBe(8);
    expect(preset!.config.trailingStopPct).toBe(2);
    expect(preset!.config.minLiquidityUsd).toBe(10000);
    expect(preset!.config.strategyMode).toBe('conservative');
  });

  it('should include prestock_speculative preset', () => {
    const preset = STRATEGY_PRESETS.find(p => p.id === 'prestock_speculative');
    expect(preset).toBeDefined();
    expect(preset!.name).toBe('PRESTOCK SPEC');
    expect(preset!.config.stopLossPct).toBe(15);
    expect(preset!.config.takeProfitPct).toBe(50);
    expect(preset!.config.trailingStopPct).toBe(8);
    expect(preset!.config.minLiquidityUsd).toBe(5000);
    expect(preset!.config.strategyMode).toBe('aggressive');
  });

  it('should include index_revert preset', () => {
    const preset = STRATEGY_PRESETS.find(p => p.id === 'index_revert');
    expect(preset).toBeDefined();
    expect(preset!.name).toBe('INDEX MEAN REVERT');
    expect(preset!.config.stopLossPct).toBe(2);
    expect(preset!.config.takeProfitPct).toBe(5);
    expect(preset!.config.trailingStopPct).toBe(1.5);
    expect(preset!.config.minLiquidityUsd).toBe(20000);
    expect(preset!.config.strategyMode).toBe('conservative');
  });

  // ── All presets have required fields ──
  it('every preset should have id, name, description, winRate, trades, and config', () => {
    for (const preset of STRATEGY_PRESETS) {
      expect(preset.id).toBeTruthy();
      expect(preset.name).toBeTruthy();
      expect(preset.description).toBeTruthy();
      expect(preset.winRate).toBeTruthy();
      expect(typeof preset.trades).toBe('number');
      expect(preset.config).toBeDefined();
      expect(typeof preset.config.stopLossPct).toBe('number');
      expect(typeof preset.config.takeProfitPct).toBe('number');
      expect(typeof preset.config.trailingStopPct).toBe('number');
    }
  });

  // ── Unique IDs ──
  it('all preset IDs should be unique', () => {
    const ids = STRATEGY_PRESETS.map(p => p.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  // ── Original presets still exist ──
  const originalIds = [
    'pump_fresh_tight', 'micro_cap_surge', 'elite', 'momentum',
    'insight_j', 'hybrid_b', 'let_it_ride', 'loose', 'genetic_best',
  ];
  for (const id of originalIds) {
    it(`should still include original preset: ${id}`, () => {
      expect(STRATEGY_PRESETS.find(p => p.id === id)).toBeDefined();
    });
  }
});

describe('STRATEGY_CATEGORIES', () => {
  // We import from the controls module where categories are defined
  // Since STRATEGY_CATEGORIES will be exported from SniperControls or a shared location,
  // we test the structure expectations here.

  it('should be importable from the strategy-categories module', async () => {
    const mod = await import('@/components/strategy-categories');
    expect(mod.STRATEGY_CATEGORIES).toBeDefined();
    expect(Array.isArray(mod.STRATEGY_CATEGORIES)).toBe(true);
  });

  it('should have 4 categories', async () => {
    const { STRATEGY_CATEGORIES } = await import('@/components/strategy-categories');
    expect(STRATEGY_CATEGORIES.length).toBe(4);
  });

  it('should have correct category labels', async () => {
    const { STRATEGY_CATEGORIES } = await import('@/components/strategy-categories');
    const labels = STRATEGY_CATEGORIES.map((c: any) => c.label);
    expect(labels).toContain('TOP PERFORMERS');
    expect(labels).toContain('BALANCED');
    expect(labels).toContain('AGGRESSIVE');
    expect(labels).toContain('XSTOCK & INDEX');
  });

  it('every preset ID in categories should exist in STRATEGY_PRESETS', async () => {
    const { STRATEGY_CATEGORIES } = await import('@/components/strategy-categories');
    const allCategoryIds = STRATEGY_CATEGORIES.flatMap((c: any) => c.presetIds);
    for (const id of allCategoryIds) {
      expect(STRATEGY_PRESETS.find(p => p.id === id)).toBeDefined();
    }
  });

  it('every STRATEGY_PRESET should appear in exactly one category', async () => {
    const { STRATEGY_CATEGORIES } = await import('@/components/strategy-categories');
    const allCategoryIds = STRATEGY_CATEGORIES.flatMap((c: any) => c.presetIds);
    // Every preset should be in at least one category
    for (const preset of STRATEGY_PRESETS) {
      expect(allCategoryIds).toContain(preset.id);
    }
    // No duplicates
    expect(new Set(allCategoryIds).size).toBe(allCategoryIds.length);
  });

  it('each category should have label, icon, and presetIds', async () => {
    const { STRATEGY_CATEGORIES } = await import('@/components/strategy-categories');
    for (const cat of STRATEGY_CATEGORIES) {
      expect(cat.label).toBeTruthy();
      expect(cat.icon).toBeTruthy();
      expect(Array.isArray(cat.presetIds)).toBe(true);
      expect(cat.presetIds.length).toBeGreaterThan(0);
    }
  });
});

describe('STRATEGY_INFO entries for new presets', () => {
  it('should have STRATEGY_INFO entries for all 4 new presets', async () => {
    // STRATEGY_INFO is defined inside SniperControls.tsx as a local const.
    // We'll extract it to a shared module so it can be tested.
    const { STRATEGY_INFO } = await import('@/components/strategy-info');
    const newIds = ['genetic_v2', 'xstock_momentum', 'prestock_speculative', 'index_revert'];
    for (const id of newIds) {
      expect(STRATEGY_INFO[id]).toBeDefined();
      expect(STRATEGY_INFO[id].summary).toBeTruthy();
      expect(STRATEGY_INFO[id].optimal).toBeTruthy();
      expect(STRATEGY_INFO[id].risk).toBeTruthy();
      expect(STRATEGY_INFO[id].params).toBeTruthy();
    }
  });

  it('should still have STRATEGY_INFO for original presets', async () => {
    const { STRATEGY_INFO } = await import('@/components/strategy-info');
    const origIds = ['momentum', 'insight_j', 'hot', 'hybrid_b', 'let_it_ride', 'insight_i'];
    for (const id of origIds) {
      expect(STRATEGY_INFO[id]).toBeDefined();
    }
  });
});
