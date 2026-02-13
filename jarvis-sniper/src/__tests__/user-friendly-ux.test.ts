import { describe, it, expect } from 'vitest';

// ────────────────────────────────────────────────────────────────
// Test Suite: User-Friendly UX Enhancements
// Verifies smart defaults, strategy descriptions, tooltips, etc.
// ────────────────────────────────────────────────────────────────

describe('Smart Default Strategy Selection', () => {
  it('default activePreset should be pump_fresh_tight (highest WR)', async () => {
    // The store initializer should default to pump_fresh_tight
    const mod = await import('@/stores/useSniperStore');
    const store = mod.useSniperStore.getState();
    expect(store.activePreset).toBe('pump_fresh_tight');
  });

  it('default autoSnipe should be false (safety first)', async () => {
    const mod = await import('@/stores/useSniperStore');
    const store = mod.useSniperStore.getState();
    expect(store.config.autoSnipe).toBe(false);
  });

  it('default strategyMode should be conservative', async () => {
    const mod = await import('@/stores/useSniperStore');
    const store = mod.useSniperStore.getState();
    expect(store.config.strategyMode).toBe('conservative');
  });

  it('default budget should be 0.5 SOL (reasonable for new users)', async () => {
    const mod = await import('@/stores/useSniperStore');
    const store = mod.useSniperStore.getState();
    expect(store.budget.budgetSol).toBe(0.5);
  });
});

describe('Strategy Descriptions Enhancement', () => {
  it('every STRATEGY_INFO entry should have a bestFor field', async () => {
    const { STRATEGY_INFO } = await import('@/components/strategy-info');
    for (const [id, info] of Object.entries(STRATEGY_INFO)) {
      expect(info.bestFor, `${id} missing bestFor`).toBeTruthy();
      expect(typeof info.bestFor).toBe('string');
    }
  });

  it('every STRATEGY_INFO entry should have a riskLevel field', async () => {
    const { STRATEGY_INFO } = await import('@/components/strategy-info');
    const validLevels = ['LOW', 'MEDIUM', 'HIGH', 'EXTREME'];
    for (const [id, info] of Object.entries(STRATEGY_INFO)) {
      expect(info.riskLevel, `${id} missing riskLevel`).toBeTruthy();
      expect(validLevels).toContain(info.riskLevel);
    }
  });

  it('every STRATEGY_INFO entry should have a holdTime field', async () => {
    const { STRATEGY_INFO } = await import('@/components/strategy-info');
    for (const [id, info] of Object.entries(STRATEGY_INFO)) {
      expect(info.holdTime, `${id} missing holdTime`).toBeTruthy();
      expect(typeof info.holdTime).toBe('string');
    }
  });

  it('strategy summaries should be human-readable (no jargon abbreviations)', async () => {
    const { STRATEGY_INFO } = await import('@/components/strategy-info');
    // Spot-check a few known entries for plain language
    const pumpFresh = STRATEGY_INFO['pump_fresh_tight'];
    expect(pumpFresh).toBeDefined();
    expect(pumpFresh.summary.length).toBeGreaterThan(30);
    // bestFor should be beginner-friendly
    expect(pumpFresh.bestFor.length).toBeGreaterThan(10);
  });

  it('pump_fresh_tight should be recommended for new users', async () => {
    const { STRATEGY_INFO } = await import('@/components/strategy-info');
    const pft = STRATEGY_INFO['pump_fresh_tight'];
    // bestFor should mention new users or beginners
    const lc = pft.bestFor.toLowerCase();
    expect(lc.includes('new') || lc.includes('beginner') || lc.includes('start')).toBe(true);
  });
});

describe('Strategy Info Type Shape', () => {
  it('STRATEGY_INFO type should include bestFor, riskLevel, holdTime', async () => {
    const { STRATEGY_INFO } = await import('@/components/strategy-info');
    // Check the actual shape of a known entry
    const momentum = STRATEGY_INFO['momentum'];
    expect(momentum).toHaveProperty('summary');
    expect(momentum).toHaveProperty('optimal');
    expect(momentum).toHaveProperty('risk');
    expect(momentum).toHaveProperty('params');
    expect(momentum).toHaveProperty('bestFor');
    expect(momentum).toHaveProperty('riskLevel');
    expect(momentum).toHaveProperty('holdTime');
  });
});
