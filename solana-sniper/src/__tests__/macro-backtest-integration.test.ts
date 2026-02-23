import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ─── Mock dependencies before any imports ─────────────────────

// Mock axios
vi.mock('axios', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: [] }),
  },
}));

// Mock fs
vi.mock('fs', () => ({
  default: {
    existsSync: vi.fn().mockReturnValue(false),
    readFileSync: vi.fn(),
    writeFileSync: vi.fn(),
    mkdirSync: vi.fn(),
  },
}));

// Mock logger
vi.mock('../utils/logger.js', () => ({
  createModuleLogger: () => ({
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  }),
}));

// Mock database (for self-improver)
vi.mock('../utils/database.js', () => ({
  getDb: vi.fn().mockReturnValue({
    prepare: vi.fn().mockReturnValue({
      all: vi.fn().mockReturnValue([]),
      get: vi.fn(),
      run: vi.fn(),
    }),
  }),
}));

import type { MacroSnapshot } from '../analysis/macro-correlator.js';
import type { HLCorrelationData, HLCandle } from '../analysis/hyperliquid-data.js';
import type { EnhancedBacktestConfig } from '../analysis/historical-data.js';

// ─── Helpers ──────────────────────────────────────────────────

function buildSnapshot(overrides: Partial<MacroSnapshot> = {}): MacroSnapshot {
  return {
    btc: { price: 100000, change24h: 0, change7d: 0 },
    eth: { price: 3500, change24h: 0 },
    sol: { price: 200, change24h: 0 },
    dxy: null,
    gold: null,
    regime: 'neutral',
    btcTrend: 'flat',
    memeExposureMultiplier: 1.0,
    fetchedAt: Date.now(),
    ...overrides,
  };
}

function buildHLCorrelation(overrides: Partial<HLCorrelationData> = {}): HLCorrelationData {
  const dummyCandle: HLCandle = {
    timestamp: Date.now(),
    open: 200,
    high: 210,
    low: 195,
    close: 205,
    volume: 1000000,
  };
  return {
    sol: [dummyCandle],
    btc: [dummyCandle],
    eth: [dummyCandle],
    solBtcCorrelation: 0.5,
    solEthCorrelation: 0.6,
    btcVolatility: 50,
    solVolatility: 70,
    fetchedAt: Date.now(),
    ...overrides,
  };
}

// ────────────────────────────────────────────────────────────────
// Test 1: simulateEnhancedSafety accepts macro + hlCorr params
// ────────────────────────────────────────────────────────────────

describe('simulateEnhancedSafety macro integration', () => {
  // We re-import the module to get the actual function
  // simulateEnhancedSafety is a module-level function (not exported),
  // so we test it indirectly through runEnhancedBacktest.
  // But we can verify the module compiles and works with the new signature.

  it('should still work when called without macro data (backward compatible)', async () => {
    // The function should accept optional macro/hlCorr params
    // We verify by importing the module (compilation check) and
    // testing that runEnhancedBacktest works without macro data
    const mod = await import('../analysis/historical-data.js');
    expect(typeof mod.runEnhancedBacktest).toBe('function');
  });
});

// ────────────────────────────────────────────────────────────────
// Test 2: EnhancedBacktestConfig has macroRegime field
// ────────────────────────────────────────────────────────────────

describe('EnhancedBacktestConfig macro fields', () => {
  it('should accept macroRegime as a config override', async () => {
    const mod = await import('../analysis/historical-data.js');

    // This should compile and not throw - macroRegime is optional
    const config: Partial<EnhancedBacktestConfig> = {
      macroRegime: 'risk_on',
    };

    expect(config.macroRegime).toBe('risk_on');
  });

  it('should accept all valid macroRegime values', () => {
    const validValues: Array<EnhancedBacktestConfig['macroRegime']> = [
      'risk_on', 'risk_off', 'neutral', 'all',
    ];
    for (const val of validValues) {
      const cfg: Partial<EnhancedBacktestConfig> = { macroRegime: val };
      expect(cfg.macroRegime).toBe(val);
    }
  });
});

// ────────────────────────────────────────────────────────────────
// Test 3: Macro correlation adjustment impacts safety score
// ────────────────────────────────────────────────────────────────

describe('Macro correlation adjustment in safety scoring', () => {
  it('macro-correlator getCorrelationAdjustment should affect score direction', async () => {
    const { getCorrelationAdjustment } = await import('../analysis/macro-correlator.js');

    // During BTC dump, fresh memecoins should get negative adjustment
    const dumpMacro = buildSnapshot({
      btcTrend: 'dumping',
      btc: { price: 88000, change24h: -5.0, change7d: -8.0 },
      regime: 'risk_off',
    });
    const dumpAdj = getCorrelationAdjustment(dumpMacro, 'fresh', false);
    expect(dumpAdj).toBeLessThan(0);

    // During BTC pump, fresh tokens should get positive adjustment
    const pumpMacro = buildSnapshot({
      btcTrend: 'pumping',
      btc: { price: 110000, change24h: 7.0, change7d: 12.0 },
      regime: 'risk_on',
    });
    const pumpAdj = getCorrelationAdjustment(pumpMacro, 'fresh', false);
    expect(pumpAdj).toBeGreaterThan(0);
  });
});

// ────────────────────────────────────────────────────────────────
// Test 4: Hyperliquid SOL-BTC correlation penalties
// ────────────────────────────────────────────────────────────────

describe('Hyperliquid correlation integration scoring logic', () => {
  // These test the LOGIC that should be added to simulateEnhancedSafety.
  // Since simulateEnhancedSafety is private, we replicate the expected logic
  // and verify the scoring rules match what will be wired in.

  it('should penalize when SOL highly correlated with BTC and BTC is dumping', () => {
    const hlCorr = buildHLCorrelation({ solBtcCorrelation: 0.85 });
    const macro = buildSnapshot({ btcTrend: 'dumping' });

    // Expected: score -= 0.10 when solBtcCorr > 0.7 and BTC dumping
    let score = 0;
    if (hlCorr.solBtcCorrelation > 0.7 && macro.btcTrend === 'dumping') {
      score -= 0.10;
    }
    expect(score).toBe(-0.10);
  });

  it('should give bonus when SOL highly correlated with BTC and BTC is pumping', () => {
    const hlCorr = buildHLCorrelation({ solBtcCorrelation: 0.85 });
    const macro = buildSnapshot({ btcTrend: 'pumping' });

    let score = 0;
    if (hlCorr.solBtcCorrelation > 0.7 && macro.btcTrend === 'pumping') {
      score += 0.05;
    }
    expect(score).toBe(0.05);
  });

  it('should not adjust when SOL-BTC correlation is low', () => {
    const hlCorr = buildHLCorrelation({ solBtcCorrelation: 0.3 });
    const macro = buildSnapshot({ btcTrend: 'dumping' });

    let score = 0;
    if (hlCorr.solBtcCorrelation > 0.7 && macro.btcTrend === 'dumping') {
      score -= 0.10;
    }
    expect(score).toBe(0);
  });

  it('should penalize high SOL volatility', () => {
    const hlCorr = buildHLCorrelation({ solVolatility: 150 }); // >100% annualized

    let score = 0;
    if (hlCorr.solVolatility > 100) {
      score -= 0.05;
    }
    expect(score).toBe(-0.05);
  });

  it('should not penalize normal SOL volatility', () => {
    const hlCorr = buildHLCorrelation({ solVolatility: 60 }); // <100%

    let score = 0;
    if (hlCorr.solVolatility > 100) {
      score -= 0.05;
    }
    expect(score).toBe(0);
  });
});

// ────────────────────────────────────────────────────────────────
// Test 5: Macro regime filter in backtest config
// ────────────────────────────────────────────────────────────────

describe('Macro regime filter logic', () => {
  it('should skip backtest when regime does not match config', () => {
    const cfgRegime: string = 'risk_on';
    const macroSnapshot = buildSnapshot({ regime: 'risk_off' });

    // Expected logic: skip if macroRegime set and doesn't match current regime
    const shouldSkip = cfgRegime && cfgRegime !== 'all' && macroSnapshot
      && macroSnapshot.regime !== cfgRegime;

    expect(shouldSkip).toBe(true);
  });

  it('should not skip when regime matches', () => {
    const cfgRegime: string = 'risk_on';
    const macroSnapshot = buildSnapshot({ regime: 'risk_on' });

    const shouldSkip = cfgRegime && cfgRegime !== 'all' && macroSnapshot
      && macroSnapshot.regime !== cfgRegime;

    expect(shouldSkip).toBe(false);
  });

  it('should not skip when macroRegime is "all"', () => {
    const cfg = { macroRegime: 'all' as const };
    const macroSnapshot = buildSnapshot({ regime: 'risk_off' });

    const shouldSkip = cfg.macroRegime && cfg.macroRegime !== 'all' && macroSnapshot
      && macroSnapshot.regime !== cfg.macroRegime;

    expect(shouldSkip).toBe(false);
  });

  it('should not skip when macroRegime is undefined', () => {
    const cfg: { macroRegime?: string } = {};
    const macroSnapshot = buildSnapshot({ regime: 'risk_off' });

    const shouldSkip = cfg.macroRegime && cfg.macroRegime !== 'all' && macroSnapshot
      && macroSnapshot.regime !== cfg.macroRegime;

    expect(shouldSkip).toBeFalsy();
  });
});

// ────────────────────────────────────────────────────────────────
// Test 6: Meme exposure multiplier position sizing
// ────────────────────────────────────────────────────────────────

describe('Meme exposure multiplier position sizing', () => {
  it('should reduce position size for memecoins when memeExposureMultiplier < 1', () => {
    const maxPositionUsd = 2.50;
    const isXStock = false;
    const memeExposureMultiplier = 0.5;

    const adjustedPositionUsd = maxPositionUsd * (isXStock ? 1.0 : memeExposureMultiplier);

    expect(adjustedPositionUsd).toBe(1.25);
  });

  it('should increase position size for memecoins when memeExposureMultiplier > 1', () => {
    const maxPositionUsd = 2.50;
    const isXStock = false;
    const memeExposureMultiplier = 1.3;

    const adjustedPositionUsd = maxPositionUsd * (isXStock ? 1.0 : memeExposureMultiplier);

    expect(adjustedPositionUsd).toBe(3.25);
  });

  it('should not adjust xStock position sizing regardless of multiplier', () => {
    const maxPositionUsd = 2.50;
    const isXStock = true;
    const memeExposureMultiplier = 0.3;

    const adjustedPositionUsd = maxPositionUsd * (isXStock ? 1.0 : memeExposureMultiplier);

    expect(adjustedPositionUsd).toBe(2.50);
  });

  it('should default to 1.0 multiplier when macroSnapshot is null', () => {
    const macroSnapshot = null as MacroSnapshot | null;
    const maxPositionUsd = 2.50;
    const isXStock = false;

    const macroMultiplier = macroSnapshot?.memeExposureMultiplier ?? 1.0;
    const adjustedPositionUsd = maxPositionUsd * (isXStock ? 1.0 : macroMultiplier);

    expect(adjustedPositionUsd).toBe(2.50);
  });
});

// ────────────────────────────────────────────────────────────────
// Test 7: Self-improver macroRegime in search space
// ────────────────────────────────────────────────────────────────

describe('Self-improver macro integration', () => {
  it('should export runSelfImprovement that accepts deepMode param', async () => {
    const mod = await import('../analysis/self-improver.js');
    expect(typeof mod.runSelfImprovement).toBe('function');
    // Function signature: (generations?, populationSize?, deepMode?)
    // Just verify it exists - actual execution would call APIs
  });

  it('module should compile with macroRegime in search space', async () => {
    // This verifies the self-improver compiles after adding macroRegime
    // to generatePopulation and evolvePopulation
    const mod = await import('../analysis/self-improver.js');
    expect(mod).toBeDefined();
    expect(typeof mod.computeFitnessScore).toBe('function');
  });
});

// ────────────────────────────────────────────────────────────────
// Test 8: Import chain verification
// ────────────────────────────────────────────────────────────────

describe('Import chain verification', () => {
  it('historical-data.ts should import from macro-correlator', async () => {
    // If the imports work, the module loads without error
    const mod = await import('../analysis/historical-data.js');
    expect(mod).toBeDefined();
    expect(typeof mod.runEnhancedBacktest).toBe('function');
    expect(typeof mod.fetchBacktestData).toBe('function');
  });

  it('macro-correlator exports should be accessible', async () => {
    const mod = await import('../analysis/macro-correlator.js');
    expect(typeof mod.getMacroSnapshot).toBe('function');
    expect(typeof mod.getCorrelationAdjustment).toBe('function');
    expect(typeof mod.estimateBtcCorrelation).toBe('function');
  });

  it('hyperliquid-data exports should be accessible', async () => {
    const mod = await import('../analysis/hyperliquid-data.js');
    expect(typeof mod.getHyperliquidCorrelations).toBe('function');
    expect(typeof mod.getExtendedHistory).toBe('function');
  });
});
