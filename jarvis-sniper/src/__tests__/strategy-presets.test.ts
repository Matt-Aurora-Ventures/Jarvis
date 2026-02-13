import { describe, it, expect } from 'vitest';
import { STRATEGY_PRESETS } from '@/stores/useSniperStore';

// ────────────────────────────────────────────────────────────────
// Test Suite: Strategy Presets — verifies new presets exist and
// the STRATEGY_CATEGORIES grouping is correct.
// ────────────────────────────────────────────────────────────────

describe('STRATEGY_PRESETS', () => {
  it('should have at least the core memecoin presets', () => {
    // Keep this resilient: presets evolve, but we should never regress below core coverage.
    expect(STRATEGY_PRESETS.length).toBeGreaterThanOrEqual(9);
  });

  // ── New presets existence ──
  it('should include genetic_v2 preset', () => {
    const preset = STRATEGY_PRESETS.find(p => p.id === 'genetic_v2');
    expect(preset).toBeDefined();
    expect(preset!.name).toBe('GENETIC V2');
    expect(preset!.config.stopLossPct).toBe(28);
    expect(preset!.config.takeProfitPct).toBe(140);
    expect(preset!.config.trailingStopPct).toBe(8);
    expect(preset!.config.minLiquidityUsd).toBe(5000);
    expect(preset!.config.strategyMode).toBe('aggressive');
  });

  it('should include xstock presets', () => {
    const intraday = STRATEGY_PRESETS.find(p => p.id === 'xstock_intraday');
    const swing = STRATEGY_PRESETS.find(p => p.id === 'xstock_swing');
    expect(intraday).toBeDefined();
    expect(swing).toBeDefined();
    expect(intraday!.assetType).toBe('xstock');
    expect(swing!.assetType).toBe('xstock');

    expect(intraday!.config.stopLossPct).toBe(3);
    expect(intraday!.config.takeProfitPct).toBe(10);
    expect(intraday!.config.trailingStopPct).toBe(2.2);

    expect(swing!.config.stopLossPct).toBe(6);
    expect(swing!.config.takeProfitPct).toBe(18);
    expect(swing!.config.trailingStopPct).toBe(4);
  });

  it('should include prestock_speculative preset', () => {
    const preset = STRATEGY_PRESETS.find(p => p.id === 'prestock_speculative');
    expect(preset).toBeDefined();
    expect(preset!.name).toBe('PRESTOCK SPEC');
    expect(preset!.assetType).toBe('prestock');
    expect(preset!.config.stopLossPct).toBe(8);
    expect(preset!.config.takeProfitPct).toBe(24);
    expect(preset!.config.trailingStopPct).toBe(5);
    expect(preset!.config.minLiquidityUsd).toBe(0); // Liquidity removed as factor for prestocks
  });

  it('should include index presets', () => {
    const intraday = STRATEGY_PRESETS.find(p => p.id === 'index_intraday');
    const leveraged = STRATEGY_PRESETS.find(p => p.id === 'index_leveraged');
    expect(intraday).toBeDefined();
    expect(leveraged).toBeDefined();
    expect(intraday!.assetType).toBe('index');
    expect(leveraged!.assetType).toBe('index');

    expect(intraday!.config.stopLossPct).toBe(2.8);
    expect(intraday!.config.takeProfitPct).toBe(9);
    expect(intraday!.config.trailingStopPct).toBe(2);

    expect(leveraged!.config.stopLossPct).toBe(7);
    expect(leveraged!.config.takeProfitPct).toBe(20);
    expect(leveraged!.config.trailingStopPct).toBe(4.5);
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

  it('should have 6 categories', async () => {
    const { STRATEGY_CATEGORIES } = await import('@/components/strategy-categories');
    expect(STRATEGY_CATEGORIES.length).toBe(6);
  });

  it('should have correct category labels', async () => {
    const { STRATEGY_CATEGORIES } = await import('@/components/strategy-categories');
    const labels = STRATEGY_CATEGORIES.map((c: any) => c.label);
    expect(labels).toContain('TOP PERFORMERS');
    expect(labels).toContain('BALANCED');
    expect(labels).toContain('AGGRESSIVE');
    expect(labels).toContain('DEGEN');
    expect(labels).toContain('BLUE CHIP SOLANA');
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
  it('should have STRATEGY_INFO entries for every preset', async () => {
    const { STRATEGY_INFO } = await import('@/components/strategy-info');
    for (const preset of STRATEGY_PRESETS) {
      const id = preset.id;
      expect(STRATEGY_INFO[id]).toBeDefined();
      expect(STRATEGY_INFO[id].summary).toBeTruthy();
      expect(STRATEGY_INFO[id].optimal).toBeTruthy();
      expect(STRATEGY_INFO[id].risk).toBeTruthy();
      expect(STRATEGY_INFO[id].params).toBeTruthy();
    }
  });

  it('should still have STRATEGY_INFO for key presets', async () => {
    const { STRATEGY_INFO } = await import('@/components/strategy-info');
    const origIds = ['momentum', 'insight_j', 'hybrid_b', 'let_it_ride', 'pump_fresh_tight'];
    for (const id of origIds) {
      expect(STRATEGY_INFO[id]).toBeDefined();
    }
  });
});
