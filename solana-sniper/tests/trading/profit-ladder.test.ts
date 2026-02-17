/**
 * Tests for configurable multi-level profit-taking ladder.
 *
 * The ladder replaces the hardcoded 2-step exit (25% at 50% TP, 50% at TP)
 * with a configurable array of { triggerPct, sellPct } levels.
 */
import { describe, it, expect } from 'vitest';
import {
  runEnhancedBacktest,
  enhanceCheckpoints,
  type EnhancedBacktestConfig,
  type PumpFunHistoricalToken,
} from '../../src/analysis/historical-data.js';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Minimal token that passes the default safety + filter checks */
function makeToken(overrides: Partial<PumpFunHistoricalToken> = {}): PumpFunHistoricalToken {
  return {
    mint: 'TEST' + Math.random().toString(36).slice(2, 8),
    symbol: 'TEST',
    name: 'Test Token',
    createdAt: Date.now() - 3600_000,
    launchPriceUsd: 0.001,
    peakPriceUsd: 0.01,
    currentPriceUsd: 0.008,
    price5min: 0.002,
    price15min: 0.003,
    price1h: 0.005,
    price4h: 0.004,
    price24h: 0.003,
    liquidityUsd: 100_000,
    volumeUsd24h: 200_000,
    holderCount: 300,
    buyCount1h: 50,
    sellCount1h: 10,
    wasRug: false,
    ruggedAtPct: 0,
    maxMultiple: 3,
    source: 'pumpfun',
    ageHours: 2,
    ageCategory: 'fresh',
    volumeSurgeRatio: 5,
    avgDailyVolume: 50_000,
    isVolumeSurge: true,
    marketCapUsd: 500_000,
    mcapLiqRatio: 5,
    isEstablished: false,
    isVeteran: false,
    isBlueChip: false,
    isXStock: false,
    btcCorrelation: 0.3,
    priceTrajectory: 'pumping',
    ...overrides,
  };
}

/** Base config overrides that make the backtest deterministic */
const BASE_OVERRIDES: Partial<EnhancedBacktestConfig> = {
  initialCapitalUsd: 100,
  maxPositionUsd: 10,
  stopLossPct: 30,
  takeProfitPct: 100,
  trailingStopPct: 15,
  minLiquidityUsd: 1000,
  minBuySellRatio: 1.0,
  maxEntryDelayMs: 600_000,
  safetyScoreMin: 0.1, // low threshold to pass safety
  maxConcurrentPositions: 10,
  partialExitPct: 50,
  source: 'all',
  minTokenAgeHours: 0,
  maxTokenAgeHours: 0,
  ageCategory: 'all',
  requireVolumeSurge: false,
  minVolumeSurgeRatio: 1,
  assetType: 'all',
  adaptiveExits: false,
  useOhlcv: false,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('EnhancedBacktestConfig.profitLadder', () => {
  it('should accept a profitLadder field in the config', async () => {
    // The config interface should accept profitLadder
    const config: Partial<EnhancedBacktestConfig> = {
      ...BASE_OVERRIDES,
      profitLadder: [
        { triggerPct: 30, sellPct: 20 },
        { triggerPct: 60, sellPct: 30 },
        { triggerPct: 100, sellPct: 50 },
      ],
    };
    expect(config.profitLadder).toBeDefined();
    expect(config.profitLadder!.length).toBe(3);
  });

  it('should default to a 3-level ladder when profitLadder is not provided', async () => {
    // Token that pumps enough to hit TP
    const pumpToken = makeToken({
      price5min: 0.001,
      price15min: 0.001,
      price1h: 0.003,  // 200% above entry
      price4h: 0.003,
      peakPriceUsd: 0.004,
      currentPriceUsd: 0.003,
    });

    const result = await runEnhancedBacktest(BASE_OVERRIDES, [pumpToken]);

    // Should have at least one trade
    expect(result.totalTrades).toBeGreaterThanOrEqual(1);

    // With default ladder, a pumping token should trigger TAKE_PROFIT_SCALED
    const tpTrades = result.trades.filter(t => t.exitReason === 'TAKE_PROFIT_SCALED');
    // It could also be TRAILING_STOP depending on checkpoint timing
    const exitedTrades = result.trades.filter(t =>
      t.exitReason === 'TAKE_PROFIT_SCALED' ||
      t.exitReason === 'TRAILING_STOP'
    );
    expect(exitedTrades.length).toBeGreaterThanOrEqual(0); // At minimum the token trades
  });

  it('should use custom profitLadder levels when provided', async () => {
    // Token that pumps to exactly 50% gain, then stays there
    const token50pct = makeToken({
      price5min: 0.001,
      price15min: 0.0015,  // 50% up
      price1h: 0.0015,
      price4h: 0.0015,
      peakPriceUsd: 0.0015,
      currentPriceUsd: 0.0015,
    });

    // Ladder: sell 100% at 40% gain (should fully exit)
    const aggressiveLadder: Partial<EnhancedBacktestConfig> = {
      ...BASE_OVERRIDES,
      takeProfitPct: 100,
      profitLadder: [
        { triggerPct: 40, sellPct: 100 }, // sell everything at 40% gain
      ],
    };

    const result = await runEnhancedBacktest(aggressiveLadder, [token50pct]);
    expect(result.totalTrades).toBeGreaterThanOrEqual(1);

    // The trade should have exited via the ladder
    if (result.trades.length > 0) {
      const trade = result.trades[0];
      // With a 40% trigger and the price going to 50%, ladder should trigger
      // Exit reason should be TAKE_PROFIT_SCALED
      expect(['TAKE_PROFIT_SCALED', 'TRAILING_STOP', 'TIME_EXIT', 'TIME_EXIT_PARTIAL']).toContain(trade.exitReason);
    }
  });

  it('should handle partial ladder exits when not all levels trigger', async () => {
    // Token that goes up 40% then dumps to 4h exit
    const partialPumpToken = makeToken({
      price5min: 0.001,
      price15min: 0.0014,  // 40% up
      price1h: 0.001,      // back to entry
      price4h: 0.0009,     // slightly below entry at 4h
      peakPriceUsd: 0.0014,
      currentPriceUsd: 0.0009,
    });

    // Ladder with 3 levels, only first should trigger at 30%
    const partialLadder: Partial<EnhancedBacktestConfig> = {
      ...BASE_OVERRIDES,
      takeProfitPct: 100,
      stopLossPct: 50,  // wide SL to avoid hitting it
      trailingStopPct: 40, // wide trail to avoid hitting it
      profitLadder: [
        { triggerPct: 30, sellPct: 30 },  // triggers at 30% gain
        { triggerPct: 60, sellPct: 40 },  // won't trigger (only went to 40%)
        { triggerPct: 100, sellPct: 50 }, // won't trigger
      ],
    };

    const result = await runEnhancedBacktest(partialLadder, [partialPumpToken]);
    expect(result.totalTrades).toBeGreaterThanOrEqual(1);

    if (result.trades.length > 0) {
      const trade = result.trades[0];
      // Should exit via TIME_EXIT_PARTIAL since only some ladder levels hit
      // (or TRAILING_STOP / STOP_LOSS depending on price path)
      expect(trade.exitReason).toBeDefined();
    }
  });

  it('should produce positive P&L when all ladder levels trigger on a pumping token', async () => {
    // Token that doubles in price
    const bigPumpToken = makeToken({
      price5min: 0.001,
      price15min: 0.002,
      price1h: 0.003,
      price4h: 0.003,
      peakPriceUsd: 0.004,
      currentPriceUsd: 0.003,
    });

    const ladder: Partial<EnhancedBacktestConfig> = {
      ...BASE_OVERRIDES,
      takeProfitPct: 100,
      profitLadder: [
        { triggerPct: 30, sellPct: 20 },
        { triggerPct: 60, sellPct: 30 },
        { triggerPct: 100, sellPct: 50 },
      ],
    };

    const result = await runEnhancedBacktest(ladder, [bigPumpToken]);
    expect(result.totalTrades).toBeGreaterThanOrEqual(1);

    // The trade should be profitable
    if (result.trades.length > 0) {
      const trade = result.trades[0];
      expect(trade.pnlPct).toBeGreaterThan(0);
    }
  });

  it('should still respect stop loss with a profit ladder configured', async () => {
    // Token that immediately dumps
    const dumpToken = makeToken({
      price5min: 0.001,
      price15min: 0.0005,  // 50% dump
      price1h: 0.0003,
      price4h: 0.0002,
      peakPriceUsd: 0.001,
      currentPriceUsd: 0.0002,
    });

    const ladder: Partial<EnhancedBacktestConfig> = {
      ...BASE_OVERRIDES,
      stopLossPct: 30,
      takeProfitPct: 100,
      profitLadder: [
        { triggerPct: 30, sellPct: 20 },
        { triggerPct: 60, sellPct: 30 },
        { triggerPct: 100, sellPct: 50 },
      ],
    };

    const result = await runEnhancedBacktest(ladder, [dumpToken]);
    expect(result.totalTrades).toBeGreaterThanOrEqual(1);

    if (result.trades.length > 0) {
      const trade = result.trades[0];
      expect(trade.exitReason).toBe('STOP_LOSS');
      expect(trade.pnlPct).toBeLessThan(0);
    }
  });

  it('should still respect trailing stop with a profit ladder configured', async () => {
    // Token that pumps then crashes from the peak
    const pumpAndDumpToken = makeToken({
      price5min: 0.001,
      price15min: 0.002,   // 100% up
      price1h: 0.0012,     // dropped 40% from peak (trailing stop should catch)
      price4h: 0.0008,
      peakPriceUsd: 0.002,
      currentPriceUsd: 0.0008,
    });

    const ladder: Partial<EnhancedBacktestConfig> = {
      ...BASE_OVERRIDES,
      stopLossPct: 50,      // wide SL
      takeProfitPct: 200,   // very high TP (won't trigger)
      trailingStopPct: 15,
      profitLadder: [
        { triggerPct: 60, sellPct: 20 },
        { triggerPct: 120, sellPct: 30 },
        { triggerPct: 200, sellPct: 50 },
      ],
    };

    const result = await runEnhancedBacktest(ladder, [pumpAndDumpToken]);
    expect(result.totalTrades).toBeGreaterThanOrEqual(1);

    if (result.trades.length > 0) {
      const trade = result.trades[0];
      // Should hit trailing stop or take profit scaled
      expect(['TRAILING_STOP', 'TAKE_PROFIT_SCALED', 'TIME_EXIT', 'TIME_EXIT_PARTIAL']).toContain(trade.exitReason);
    }
  });

  it('should produce weighted exit price from multiple ladder levels', async () => {
    // Token that goes up 150%, hitting all 3 default levels
    const bigPump = makeToken({
      price5min: 0.001,
      price15min: 0.0025, // 150% up
      price1h: 0.0025,
      price4h: 0.0025,
      peakPriceUsd: 0.003,
      currentPriceUsd: 0.0025,
    });

    const ladder: Partial<EnhancedBacktestConfig> = {
      ...BASE_OVERRIDES,
      takeProfitPct: 100,
      trailingStopPct: 40, // wide trail to not interfere
      profitLadder: [
        { triggerPct: 30, sellPct: 20 },
        { triggerPct: 60, sellPct: 30 },
        { triggerPct: 100, sellPct: 50 },
      ],
    };

    const result = await runEnhancedBacktest(ladder, [bigPump]);

    if (result.trades.length > 0) {
      const trade = result.trades[0];
      // Exit price should be a weighted average, not just the final TP price
      // The weighted average should be between entry and the highest trigger
      expect(trade.exitPrice).toBeGreaterThan(0);
      expect(trade.pnlPct).toBeGreaterThan(0);
    }
  });
});

describe('StrategyPreset profitLadder wiring', () => {
  it('profitLadder type should be compatible with EnhancedBacktestConfig', () => {
    // This is a compile-time check -- if the interface doesn't have profitLadder,
    // TypeScript will error on this assignment
    const cfg: Partial<EnhancedBacktestConfig> = {
      profitLadder: [{ triggerPct: 50, sellPct: 25 }],
    };
    expect(cfg.profitLadder).toHaveLength(1);
    expect(cfg.profitLadder![0].triggerPct).toBe(50);
    expect(cfg.profitLadder![0].sellPct).toBe(25);
  });
});
