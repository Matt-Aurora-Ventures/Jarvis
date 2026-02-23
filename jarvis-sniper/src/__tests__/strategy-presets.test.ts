import { describe, it, expect } from 'vitest';
import { STRATEGY_PRESETS } from '@/stores/useSniperStore';

// ────────────────────────────────────────────────────────────────
// Test Suite: Strategy Presets — R4 params (realistic TP, trailing disabled)
// NOTE: Not all presets are profitable; underperformers remain available but flagged.
// ────────────────────────────────────────────────────────────────

describe('STRATEGY_PRESETS', () => {
  it('should have exactly 26 sweep-optimized strategies', () => {
    expect(STRATEGY_PRESETS.length).toBe(26);
  });

  // ── All 26 presets exist ──
  const allIds = [
    'pump_fresh_tight', 'micro_cap_surge', 'elite',
    'momentum', 'hybrid_b', 'let_it_ride',
    'sol_veteran', 'utility_swing', 'established_breakout', 'meme_classic', 'volume_spike',
    'bags_fresh_snipe', 'bags_momentum', 'bags_value', 'bags_dip_buyer',
    'bags_bluechip', 'bags_conservative', 'bags_aggressive', 'bags_elite',
    'bluechip_trend_follow', 'bluechip_breakout',
    'xstock_intraday', 'xstock_swing', 'prestock_speculative',
    'index_intraday', 'index_leveraged',
  ];
  for (const id of allIds) {
    it(`should include sweep-optimized preset: ${id}`, () => {
      expect(STRATEGY_PRESETS.find(p => p.id === id)).toBeDefined();
    });
  }

  // ── TP > SL for ALL strategies ──
  it('every preset should have TP > SL (positive R:R)', () => {
    for (const preset of STRATEGY_PRESETS) {
      expect(preset.config.takeProfitPct!).toBeGreaterThan(preset.config.stopLossPct!);
    }
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
});

describe('STRATEGY_CATEGORIES', () => {
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
    expect(labels).toContain('MEMECOIN');
    expect(labels).toContain('ESTABLISHED TOKENS');
    expect(labels).toContain('BAGS.FM');
    expect(labels).toContain('BLUE CHIP SOLANA');
    expect(labels).toContain('xSTOCK & INDEX');
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
    for (const preset of STRATEGY_PRESETS) {
      expect(allCategoryIds).toContain(preset.id);
    }
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

describe('STRATEGY_INFO entries for presets', () => {
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
});
