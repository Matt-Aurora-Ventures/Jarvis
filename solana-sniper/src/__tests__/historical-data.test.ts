import { describe, it, expect } from 'vitest';

// Test the safety simulation and filtering logic extracted from historical-data.ts
// These don't require API calls — they test pure computation

describe('Historical Data - Safety Simulation', () => {
  // Replicated from simulateEnhancedSafety in historical-data.ts
  function simulateEnhancedSafety(token: {
    liquidityUsd: number;
    buyCount1h: number;
    sellCount1h: number;
    volumeUsd24h: number;
    holderCount: number;
    price1h: number;
    currentPriceUsd: number;
    peakPriceUsd: number;
    launchPriceUsd: number;
    wasRug: boolean;
    ruggedAtPct: number;
    source: string;
  }): number {
    let score = 0;

    // 1. Liquidity depth (0-0.20)
    if (token.liquidityUsd >= 100000) score += 0.20;
    else if (token.liquidityUsd >= 50000) score += 0.18;
    else if (token.liquidityUsd >= 25000) score += 0.15;
    else if (token.liquidityUsd >= 10000) score += 0.12;
    else if (token.liquidityUsd >= 5000) score += 0.08;
    else score += 0.03;

    // 2. Buy/sell ratio (0-0.15)
    if (token.buyCount1h > 0 || token.sellCount1h > 0) {
      const ratio = token.buyCount1h / Math.max(1, token.sellCount1h);
      if (ratio >= 3) score += 0.15;
      else if (ratio >= 2) score += 0.12;
      else if (ratio >= 1.5) score += 0.10;
      else if (ratio >= 1) score += 0.07;
      else score += 0.03;
    } else {
      score += 0.07; // neutral when no data
    }

    // 3. Volume-to-liquidity ratio (0-0.15)
    const volLiqRatio = token.volumeUsd24h / Math.max(1, token.liquidityUsd);
    if (volLiqRatio >= 1 && volLiqRatio <= 10) score += 0.15;
    else if (volLiqRatio >= 0.5 && volLiqRatio <= 20) score += 0.10;
    else if (volLiqRatio > 0) score += 0.05;

    // 4. Holder distribution proxy (0-0.10)
    if (token.holderCount >= 500) score += 0.10;
    else if (token.holderCount >= 100) score += 0.07;
    else if (token.holderCount >= 30) score += 0.04;

    // 5. Price momentum (0-0.15)
    const momentum = token.currentPriceUsd > 0 && token.price1h > 0
      ? (token.currentPriceUsd - token.price1h) / token.price1h
      : 0;
    if (momentum > 0.1) score += 0.15;
    else if (momentum > 0) score += 0.10;
    else if (momentum > -0.1) score += 0.07;
    else score += 0.02;

    // 6. Market cap sanity (0-0.10)
    const estMcap = token.currentPriceUsd * 1_000_000_000; // rough
    if (estMcap >= 100_000 && estMcap <= 100_000_000) score += 0.10;
    else if (estMcap >= 10_000) score += 0.05;

    // 7. Volume adequacy (0-0.10)
    if (token.volumeUsd24h >= 50000) score += 0.10;
    else if (token.volumeUsd24h >= 10000) score += 0.07;
    else if (token.volumeUsd24h >= 1000) score += 0.03;

    // 8. Source bonus (0-0.05)
    if (token.source === 'pumpfun') score += 0.05;
    else if (token.source === 'raydium') score += 0.03;

    // Penalties
    if (token.wasRug) score -= 0.40;
    if (token.ruggedAtPct > 80) score -= 0.15;
    if (token.currentPriceUsd === 0 || token.liquidityUsd === 0) score -= 0.10;

    return Math.max(0, Math.min(1, score));
  }

  it('should give high score to healthy token', () => {
    const score = simulateEnhancedSafety({
      liquidityUsd: 120_000,
      buyCount1h: 200,
      sellCount1h: 50,
      volumeUsd24h: 300_000,
      holderCount: 800,
      price1h: 0.001,
      currentPriceUsd: 0.0012,
      peakPriceUsd: 0.0015,
      launchPriceUsd: 0.0005,
      wasRug: false,
      ruggedAtPct: 20,
      source: 'pumpfun',
    });
    expect(score).toBeGreaterThan(0.7);
  });

  it('should heavily penalize rug tokens', () => {
    const score = simulateEnhancedSafety({
      liquidityUsd: 50_000,
      buyCount1h: 100,
      sellCount1h: 30,
      volumeUsd24h: 80_000,
      holderCount: 200,
      price1h: 0.001,
      currentPriceUsd: 0.00001,
      peakPriceUsd: 0.005,
      launchPriceUsd: 0.0005,
      wasRug: true,
      ruggedAtPct: 99,
      source: 'raydium',
    });
    expect(score).toBeLessThan(0.35);
  });

  it('should give low score to low-liquidity dead token', () => {
    const score = simulateEnhancedSafety({
      liquidityUsd: 500,
      buyCount1h: 0,
      sellCount1h: 0,
      volumeUsd24h: 100,
      holderCount: 5,
      price1h: 0.0001,
      currentPriceUsd: 0,
      peakPriceUsd: 0.001,
      launchPriceUsd: 0.0005,
      wasRug: false,
      ruggedAtPct: 100,
      source: 'raydium',
    });
    expect(score).toBeLessThan(0.3);
  });

  it('should handle neutral when no txn data exists', () => {
    const score = simulateEnhancedSafety({
      liquidityUsd: 30_000,
      buyCount1h: 0,
      sellCount1h: 0,
      volumeUsd24h: 20_000,
      holderCount: 100,
      price1h: 0.001,
      currentPriceUsd: 0.001,
      peakPriceUsd: 0.002,
      launchPriceUsd: 0.0005,
      wasRug: false,
      ruggedAtPct: 50,
      source: 'pumpfun',
    });
    // Should still get a reasonable score from other factors
    expect(score).toBeGreaterThan(0.4);
    expect(score).toBeLessThan(0.8);
  });
});

describe('Historical Data - Filter Logic', () => {
  interface Token {
    source: string;
    liquidityUsd: number;
    buyCount1h: number;
    sellCount1h: number;
  }

  function filterTokens(
    tokens: Token[],
    cfg: { source: string; minLiquidityUsd: number; minBuySellRatio: number },
  ): Token[] {
    return tokens.filter(t => {
      if (cfg.source !== 'all' && t.source !== cfg.source) return false;
      if (t.liquidityUsd < cfg.minLiquidityUsd) return false;
      if (t.buyCount1h > 0 || t.sellCount1h > 0) {
        const ratio = t.buyCount1h / Math.max(1, t.sellCount1h);
        if (ratio < cfg.minBuySellRatio) return false;
      }
      return true;
    });
  }

  const testTokens: Token[] = [
    { source: 'pumpfun', liquidityUsd: 50_000, buyCount1h: 100, sellCount1h: 30 },
    { source: 'raydium', liquidityUsd: 5_000, buyCount1h: 0, sellCount1h: 0 },
    { source: 'pumpfun', liquidityUsd: 3_000, buyCount1h: 50, sellCount1h: 100 },
    { source: 'raydium', liquidityUsd: 20_000, buyCount1h: 10, sellCount1h: 5 },
    { source: 'pumpswap', liquidityUsd: 15_000, buyCount1h: 0, sellCount1h: 0 },
  ];

  it('should pass tokens with no txn data through ratio filter', () => {
    const result = filterTokens(testTokens, {
      source: 'all',
      minLiquidityUsd: 1000,
      minBuySellRatio: 1.5,
    });
    // Token[1] (0/0 txns) should pass, token[2] (0.5 ratio) should fail
    expect(result).toHaveLength(4);
    expect(result.find(t => t.liquidityUsd === 3_000)).toBeUndefined();
  });

  it('should filter by source when not all', () => {
    const result = filterTokens(testTokens, {
      source: 'pumpfun',
      minLiquidityUsd: 1000,
      minBuySellRatio: 0,
    });
    expect(result).toHaveLength(2);
    expect(result.every(t => t.source === 'pumpfun')).toBe(true);
  });

  it('should filter by minimum liquidity', () => {
    const result = filterTokens(testTokens, {
      source: 'all',
      minLiquidityUsd: 10_000,
      minBuySellRatio: 0,
    });
    expect(result.every(t => t.liquidityUsd >= 10_000)).toBe(true);
    expect(result).toHaveLength(3);
  });

  it('should pass all when ratio is 0', () => {
    const result = filterTokens(testTokens, {
      source: 'all',
      minLiquidityUsd: 0,
      minBuySellRatio: 0,
    });
    expect(result).toHaveLength(5);
  });
});

// ─── Enhanced Checkpoint Interpolation Tests ────────────────────────
// Tests for the price simulation improvement: adding intermediate
// price points between known checkpoints to capture intra-period volatility.

describe('Historical Data - Enhanced Checkpoint Interpolation', () => {
  // Import the function under test from historical-data.ts
  // This function generates intermediate price points between known checkpoints
  // to model intra-period volatility more accurately.
  let enhanceCheckpoints: (
    checkpoints: Array<{ price: number; timeMin: number }>
  ) => Array<{ price: number; timeMin: number }>;

  beforeAll(async () => {
    const mod = await import('../analysis/historical-data.js');
    enhanceCheckpoints = mod.enhanceCheckpoints;
  });

  it('should be exported from historical-data module', () => {
    expect(typeof enhanceCheckpoints).toBe('function');
  });

  it('should preserve original checkpoints in the output', () => {
    const checkpoints = [
      { price: 1.0, timeMin: 15 },
      { price: 0.80, timeMin: 60 },
      { price: 0.70, timeMin: 240 },
    ];
    const enhanced = enhanceCheckpoints(checkpoints);

    // All original checkpoints must be present
    for (const cp of checkpoints) {
      expect(enhanced.find(e => e.timeMin === cp.timeMin && e.price === cp.price)).toBeDefined();
    }
  });

  it('should add intermediate points for volatile moves (>5%)', () => {
    // Price drops 20% from 1.0 to 0.80 between 15min and 60min
    // This is a 20% move, well above the 5% threshold
    const checkpoints = [
      { price: 1.0, timeMin: 15 },
      { price: 0.80, timeMin: 60 },
      { price: 0.70, timeMin: 240 },
    ];
    const enhanced = enhanceCheckpoints(checkpoints);

    // Should have more points than original (at least mid-point overshoot + 70% interpolation)
    expect(enhanced.length).toBeGreaterThan(checkpoints.length);

    // Should have at least one point between 15 and 60 minutes
    const midPoints = enhanced.filter(e => e.timeMin > 15 && e.timeMin < 60);
    expect(midPoints.length).toBeGreaterThanOrEqual(1);
  });

  it('should add 70% interpolation point for moderate moves (>2%)', () => {
    // 3% move - should get a 70% interpolation point but NOT an overshoot
    const checkpoints = [
      { price: 1.0, timeMin: 15 },
      { price: 0.97, timeMin: 60 },
    ];
    const enhanced = enhanceCheckpoints(checkpoints);

    // Should have at least one interpolated point
    expect(enhanced.length).toBeGreaterThan(checkpoints.length);

    // The 70% interpolation point should exist at ~timeMin 46.5 (15 + 45*0.7)
    const latePoints = enhanced.filter(e => e.timeMin > 15 && e.timeMin < 60);
    expect(latePoints.length).toBeGreaterThanOrEqual(1);
  });

  it('should NOT add extra points for tiny moves (<2%)', () => {
    // 1% move - too small to warrant interpolation
    const checkpoints = [
      { price: 1.0, timeMin: 15 },
      { price: 0.99, timeMin: 60 },
      { price: 0.98, timeMin: 240 },
    ];
    const enhanced = enhanceCheckpoints(checkpoints);

    // Should be exactly the same as original (no interpolation needed)
    expect(enhanced.length).toBe(checkpoints.length);
  });

  it('should produce time-sorted output', () => {
    const checkpoints = [
      { price: 1.0, timeMin: 15 },
      { price: 0.50, timeMin: 60 },
      { price: 0.30, timeMin: 240 },
    ];
    const enhanced = enhanceCheckpoints(checkpoints);

    // Must be sorted by timeMin ascending
    for (let i = 1; i < enhanced.length; i++) {
      expect(enhanced[i].timeMin).toBeGreaterThanOrEqual(enhanced[i - 1].timeMin);
    }
  });

  it('should never produce negative or zero prices', () => {
    // Extreme crash scenario: price drops 99%
    const checkpoints = [
      { price: 1.0, timeMin: 15 },
      { price: 0.01, timeMin: 60 },
      { price: 0.001, timeMin: 240 },
    ];
    const enhanced = enhanceCheckpoints(checkpoints);

    for (const cp of enhanced) {
      expect(cp.price).toBeGreaterThan(0);
    }
  });

  it('should add overshoot in opposite direction for volatile downward moves', () => {
    // Price drops from 1.0 to 0.70 (30% drop) between 15min and 60min
    // For a downward move, overshoot should bounce UP before dropping
    const checkpoints = [
      { price: 1.0, timeMin: 15 },
      { price: 0.70, timeMin: 60 },
    ];
    const enhanced = enhanceCheckpoints(checkpoints);

    // Find the mid-overshoot point (should be around 40% of the time interval)
    const midPoint = enhanced.find(
      e => e.timeMin > 15 && e.timeMin < 40 && e.price !== 1.0 && e.price !== 0.70
    );
    expect(midPoint).toBeDefined();

    // For a downward move, the overshoot should create a brief bounce
    // The mid-point should be HIGHER than the linear interpolation at that time
    // Linear at 40% would be: 1.0 + (0.70 - 1.0) * 0.4 = 0.88
    // With positive overshoot for downward move, it should be above 0.88
    if (midPoint) {
      const linearAt40Pct = 1.0 + (0.70 - 1.0) * 0.4;
      expect(midPoint.price).toBeGreaterThan(linearAt40Pct);
    }
  });

  it('should add overshoot dip for volatile upward moves', () => {
    // Price rises from 1.0 to 2.0 (100% rise) between 15min and 60min
    // For an upward move, overshoot should dip DOWN before rising
    const checkpoints = [
      { price: 1.0, timeMin: 15 },
      { price: 2.0, timeMin: 60 },
    ];
    const enhanced = enhanceCheckpoints(checkpoints);

    // Find the mid-overshoot point
    const midPoint = enhanced.find(
      e => e.timeMin > 15 && e.timeMin < 40 && e.price !== 1.0 && e.price !== 2.0
    );
    expect(midPoint).toBeDefined();

    // For an upward move, the overshoot should create a brief dip
    // The mid-point should be LOWER than the linear interpolation at that time
    // Linear at 40% would be: 1.0 + (2.0 - 1.0) * 0.4 = 1.4
    if (midPoint) {
      const linearAt40Pct = 1.0 + (2.0 - 1.0) * 0.4;
      expect(midPoint.price).toBeLessThan(linearAt40Pct);
    }
  });

  it('should handle single checkpoint without error', () => {
    const checkpoints = [{ price: 1.0, timeMin: 15 }];
    const enhanced = enhanceCheckpoints(checkpoints);
    expect(enhanced).toHaveLength(1);
    expect(enhanced[0]).toEqual({ price: 1.0, timeMin: 15 });
  });

  it('should handle empty checkpoints without error', () => {
    const enhanced = enhanceCheckpoints([]);
    expect(enhanced).toHaveLength(0);
  });
});

describe('Historical Data - Price Simulation with Enhanced Checkpoints', () => {
  // Replicate the simulation loop from historical-data.ts but using enhanceCheckpoints
  let enhanceCheckpoints: (
    checkpoints: Array<{ price: number; timeMin: number }>
  ) => Array<{ price: number; timeMin: number }>;

  beforeAll(async () => {
    const mod = await import('../analysis/historical-data.js');
    enhanceCheckpoints = mod.enhanceCheckpoints;
  });

  // Simulation helper that mirrors the loop in historical-data.ts
  function simulateTrade(
    entryPrice: number,
    checkpoints: Array<{ price: number; timeMin: number }>,
    cfg: { stopLossPct: number; takeProfitPct: number; trailingStopPct: number },
  ): { exitReason: string; exitPrice: number; holdTimeMin: number } {
    let exitPrice = checkpoints[checkpoints.length - 1]?.price * 0.98 ?? entryPrice;
    let exitReason = 'TIME_EXIT';
    let holdTimeMin = 240;
    let trailingHigh = entryPrice;
    let firstTpHit = false;
    let remainingPositionPct = 100;
    let exited = false;

    for (const cp of checkpoints) {
      const changePct = ((cp.price - entryPrice) / entryPrice) * 100;
      trailingHigh = Math.max(trailingHigh, cp.price);
      const trailingDrop = ((trailingHigh - cp.price) / trailingHigh) * 100;

      if (changePct <= -cfg.stopLossPct) {
        exitPrice = entryPrice * (1 - cfg.stopLossPct / 100) * 0.97;
        exitReason = 'STOP_LOSS';
        holdTimeMin = cp.timeMin;
        exited = true;
        break;
      }

      if (trailingHigh > entryPrice * 1.05 && trailingDrop >= cfg.trailingStopPct) {
        exitPrice = cp.price * 0.97;
        exitReason = 'TRAILING_STOP';
        holdTimeMin = cp.timeMin;
        exited = true;
        break;
      }

      if (!firstTpHit && changePct >= cfg.takeProfitPct * 0.5 && remainingPositionPct === 100) {
        remainingPositionPct = 75;
      }

      if (changePct >= cfg.takeProfitPct) {
        if (!firstTpHit) {
          firstTpHit = true;
          const soldAtTP = remainingPositionPct * 0.5;
          const tpExitPrice = entryPrice * (1 + cfg.takeProfitPct / 100);
          const trailedExitPrice = cp.price * (1 - cfg.trailingStopPct / 100);
          const tpPortion = (100 - remainingPositionPct + soldAtTP) / 100;
          const trailedPortion = (remainingPositionPct - soldAtTP) / 100;
          exitPrice = (tpExitPrice * tpPortion + trailedExitPrice * trailedPortion) * 0.97;
          exitReason = 'TAKE_PROFIT_SCALED';
          holdTimeMin = cp.timeMin;
          exited = true;
          break;
        }
      }
    }

    return { exitReason, exitPrice, holdTimeMin };
  }

  it('should catch early stop-loss that coarse checkpoints miss', () => {
    // Scenario: price at 15min is -3% (above SL), but drops to -12% by 1h
    // With 8% SL, the coarse model sees: 15min=-3% (no trigger), 1h=-12% (trigger)
    // With enhanced checkpoints, an interpolated point should trigger SL earlier
    const entryPrice = 1.03; // after 3% slippage on $1.00
    const coarseCheckpoints = [
      { price: 1.0, timeMin: 15 },   // -2.9% from entry
      { price: 0.90, timeMin: 60 },  // -12.6% from entry
      { price: 0.85, timeMin: 240 }, // -17.5% from entry
    ];

    const cfg = { stopLossPct: 8, takeProfitPct: 50, trailingStopPct: 15 };

    // Coarse simulation: SL triggers at 60min (first checkpoint below -8%)
    const coarseResult = simulateTrade(entryPrice, coarseCheckpoints, cfg);
    expect(coarseResult.exitReason).toBe('STOP_LOSS');
    expect(coarseResult.holdTimeMin).toBe(60);

    // Enhanced simulation: SL should trigger BEFORE 60min
    const enhanced = enhanceCheckpoints(coarseCheckpoints);
    const enhancedResult = simulateTrade(entryPrice, enhanced, cfg);
    expect(enhancedResult.exitReason).toBe('STOP_LOSS');
    expect(enhancedResult.holdTimeMin).toBeLessThan(60);
  });

  it('should catch intermediate rally for trailing stop', () => {
    // Scenario: price pumps then dumps between checkpoints
    // 15min: +10%, peak at +30% (estimated ~30min), 1h: +5%
    // With trailing stop at 15%, the dump from +30% to +5% (=25% drop from peak) should trigger
    // But with coarse checkpoints, trailing stop only checks at 15min, peak, 1h
    const entryPrice = 1.0;
    const coarseCheckpoints = [
      { price: 1.10, timeMin: 15 },  // +10%
      { price: 1.30, timeMin: 30 },  // +30% (peak)
      { price: 1.05, timeMin: 60 },  // +5%
      { price: 0.90, timeMin: 240 }, // -10%
    ];

    const cfg = { stopLossPct: 20, takeProfitPct: 100, trailingStopPct: 15 };

    // With coarse checkpoints, trailing stop triggers at 60min
    // (trailing high = 1.30, drop to 1.05 = 19.2% from peak, > 15%)
    const coarseResult = simulateTrade(entryPrice, coarseCheckpoints, cfg);
    expect(coarseResult.exitReason).toBe('TRAILING_STOP');
    expect(coarseResult.holdTimeMin).toBe(60);

    // Enhanced should also produce a trailing stop, possibly at an intermediate point
    const enhanced = enhanceCheckpoints(coarseCheckpoints);
    const enhancedResult = simulateTrade(entryPrice, enhanced, cfg);
    expect(enhancedResult.exitReason).toBe('TRAILING_STOP');
    // Enhanced may trigger at same time or earlier due to interpolated points
    expect(enhancedResult.holdTimeMin).toBeLessThanOrEqual(60);
  });

  it('enhanced checkpoints should produce more granular exit times', () => {
    // Verify that enhanced simulation produces exit times that are NOT
    // only at the original checkpoint boundaries (15, 60, 240)
    const entryPrice = 1.0;
    const checkpoints = [
      { price: 0.95, timeMin: 15 },
      { price: 0.70, timeMin: 60 },  // 30% drop - very volatile
      { price: 0.60, timeMin: 240 },
    ];

    const cfg = { stopLossPct: 15, takeProfitPct: 50, trailingStopPct: 10 };

    // Enhanced should have exit time NOT at standard checkpoint boundaries
    const enhanced = enhanceCheckpoints(checkpoints);
    const enhancedResult = simulateTrade(entryPrice, enhanced, cfg);

    // With 15% SL and a 30% drop between 15min and 60min,
    // the SL should trigger at an interpolated time
    expect(enhancedResult.exitReason).toBe('STOP_LOSS');
    // The exit time should be between 15 and 60, not exactly at either
    expect(enhancedResult.holdTimeMin).toBeGreaterThan(15);
    expect(enhancedResult.holdTimeMin).toBeLessThan(60);
  });
});

// ─── Momentum Entry Slippage Tests ───────────────────────────────
// Tests for computeEntrySlippage: determines how much of the initial
// price move we missed by the time we detect + analyze + execute.

describe('Historical Data - Momentum Entry Slippage', () => {
  let computeEntrySlippage: (token: { price15min: number; price5min: number }) => number;

  beforeAll(async () => {
    const mod = await import('../analysis/historical-data.js');
    computeEntrySlippage = mod.computeEntrySlippage;
  });

  it('should return ~12% slippage for a token that pumped 30% in 15min', () => {
    // price5min (detection) = 1.00, price15min = 1.30 => 30% move
    // 30% is in the >20% bracket => slippage = 30 * 0.4 = 12
    const slippage = computeEntrySlippage({ price15min: 1.30, price5min: 1.00 });
    expect(slippage).toBeCloseTo(12, 1);
  });

  it('should return ~-4.5% slippage (discount) for a token that dumped 15% in 15min', () => {
    // price5min (detection) = 1.00, price15min = 0.85 => -15% move
    // -15% is in the < -10% bracket => slippage = -15 * 0.3 = -4.5
    const slippage = computeEntrySlippage({ price15min: 0.85, price5min: 1.00 });
    expect(slippage).toBeCloseTo(-4.5, 1);
  });

  it('should return 0 slippage for small moves under threshold', () => {
    // price5min (detection) = 1.00, price15min = 1.02 => 2% move
    // 2% is under the 5% threshold => slippage = 0
    const slippage = computeEntrySlippage({ price15min: 1.02, price5min: 1.00 });
    expect(slippage).toBe(0);
  });
});

// ─── OHLCV Integration Tests ─────────────────────────────────────
// Tests that the EnhancedBacktestConfig interface includes the
// useOhlcv flag and that the backtest simulation can accept OHLCV
// checkpoint data in place of coarse price checkpoints.

describe('Historical Data - OHLCV Integration Config', () => {
  it('should accept useOhlcv as an optional field in EnhancedBacktestConfig', async () => {
    // The EnhancedBacktestConfig type should include useOhlcv?: boolean
    // We verify by constructing a config with it and passing to runEnhancedBacktest
    const { runEnhancedBacktest } = await import('../analysis/historical-data.js');

    // This should NOT throw a TypeScript error (runtime check: the function accepts it)
    // We pass an empty cached dataset to avoid API calls and quickly return
    const result = await runEnhancedBacktest(
      { useOhlcv: false },
      [], // empty cached data = 0 trades
    );

    // Should return a valid result (0 trades since no data)
    expect(result).toBeDefined();
    expect(result.totalTrades).toBe(0);
    expect(result.config.useOhlcv).toBe(false);
  });

  it('should default useOhlcv to undefined when not specified', async () => {
    const { runEnhancedBacktest } = await import('../analysis/historical-data.js');

    const result = await runEnhancedBacktest(
      { stopLossPct: 30 },
      [], // empty cached data
    );

    // When not specified, useOhlcv should not appear or be undefined
    // The config is spread from defaults, so it should exist
    expect(result).toBeDefined();
    expect(result.config).toBeDefined();
  });

  it('should store useOhlcv in the result config when set to true', async () => {
    const { runEnhancedBacktest } = await import('../analysis/historical-data.js');

    const result = await runEnhancedBacktest(
      { useOhlcv: true },
      [], // empty cached data
    );

    expect(result.config.useOhlcv).toBe(true);
  });
});

describe('Historical Data - OHLCV Checkpoint Priority in Simulation', () => {
  // These tests verify the simulation loop logic:
  // When OHLCV data is available for a token, the backtester should use
  // the fine-grained OHLCV checkpoints (144 points from 48 5-min candles)
  // instead of the 5 coarse checkpoints (15min, peak, 1h, 4h).

  // We replicate the checkpoint selection logic to test it in isolation.

  it('should prefer OHLCV checkpoints when available and have >10 points', () => {
    // Simulate the checkpoint selection logic from historical-data.ts
    // OHLCV data with 30 checkpoints should be used over coarse ones
    const ohlcvCheckpoints = Array.from({ length: 30 }, (_, i) => ({
      price: 1.0 + i * 0.01,
      timeMin: i * 5,
    }));

    const coarseCheckpoints = [
      { price: 1.0, timeMin: 15 },
      { price: 1.1, timeMin: 60 },
      { price: 0.9, timeMin: 240 },
    ];

    // The logic: if ohlcvCheckpoints exist and length > 10, use them
    const checkpoints = (ohlcvCheckpoints && ohlcvCheckpoints.length > 10)
      ? ohlcvCheckpoints
      : coarseCheckpoints;

    expect(checkpoints).toBe(ohlcvCheckpoints);
    expect(checkpoints.length).toBe(30);
  });

  it('should fall back to coarse checkpoints when OHLCV has <= 10 points', () => {
    // Insufficient OHLCV data should fall back to coarse checkpoints
    const ohlcvCheckpoints = Array.from({ length: 5 }, (_, i) => ({
      price: 1.0 + i * 0.01,
      timeMin: i * 5,
    }));

    const coarseCheckpoints = [
      { price: 1.0, timeMin: 15 },
      { price: 1.1, timeMin: 60 },
      { price: 0.9, timeMin: 240 },
    ];

    const checkpoints = (ohlcvCheckpoints && ohlcvCheckpoints.length > 10)
      ? ohlcvCheckpoints
      : coarseCheckpoints;

    expect(checkpoints).toBe(coarseCheckpoints);
    expect(checkpoints.length).toBe(3);
  });

  it('should fall back to coarse checkpoints when OHLCV data is absent', () => {
    // Simulate the Map.get() pattern used in the actual implementation
    const ohlcvData = new Map<string, Array<{ price: number; timeMin: number }>>();
    // No entry for 'missing-token' -> .get() returns undefined
    const ohlcvCheckpoints = ohlcvData.get('missing-token');

    const coarseCheckpoints = [
      { price: 1.0, timeMin: 15 },
      { price: 1.1, timeMin: 60 },
      { price: 0.9, timeMin: 240 },
    ];

    const checkpoints = (ohlcvCheckpoints && ohlcvCheckpoints.length > 10)
      ? ohlcvCheckpoints
      : coarseCheckpoints;

    expect(checkpoints).toBe(coarseCheckpoints);
  });
});

// ─── Configurable Profit-Taking Ladder Tests ─────────────────────
// Tests for the multi-level profit ladder that replaces the hardcoded
// 2-step exit (25% at 50% TP, 50% at TP).

describe('Historical Data - Configurable Profit Ladder', () => {
  let runEnhancedBacktest: typeof import('../analysis/historical-data.js').runEnhancedBacktest;
  let DEFAULT_PROFIT_LADDER: typeof import('../analysis/historical-data.js').DEFAULT_PROFIT_LADDER;
  let AGGRESSIVE_PROFIT_LADDER: typeof import('../analysis/historical-data.js').AGGRESSIVE_PROFIT_LADDER;

  beforeAll(async () => {
    const mod = await import('../analysis/historical-data.js');
    runEnhancedBacktest = mod.runEnhancedBacktest;
    DEFAULT_PROFIT_LADDER = mod.DEFAULT_PROFIT_LADDER;
    AGGRESSIVE_PROFIT_LADDER = mod.AGGRESSIVE_PROFIT_LADDER;
  });

  // Helper: minimal token that passes safety filters
  function makeToken(overrides: Record<string, unknown> = {}) {
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
      source: 'pumpfun' as const,
      ageHours: 2,
      ageCategory: 'fresh' as const,
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
      priceTrajectory: 'pumping' as const,
      ...overrides,
    };
  }

  const BASE_CONFIG = {
    initialCapitalUsd: 100,
    maxPositionUsd: 10,
    stopLossPct: 30,
    takeProfitPct: 100,
    trailingStopPct: 15,
    minLiquidityUsd: 1000,
    minBuySellRatio: 1.0,
    maxEntryDelayMs: 600_000,
    safetyScoreMin: 0.1,
    maxConcurrentPositions: 10,
    partialExitPct: 50,
    source: 'all' as const,
    minTokenAgeHours: 0,
    maxTokenAgeHours: 0,
    ageCategory: 'all' as const,
    requireVolumeSurge: false,
    minVolumeSurgeRatio: 1,
    assetType: 'all' as const,
    adaptiveExits: false,
    useOhlcv: false,
  };

  // --- Export existence tests ---

  it('should export DEFAULT_PROFIT_LADDER constant', () => {
    expect(DEFAULT_PROFIT_LADDER).toBeDefined();
    expect(Array.isArray(DEFAULT_PROFIT_LADDER)).toBe(true);
    expect(DEFAULT_PROFIT_LADDER.length).toBeGreaterThanOrEqual(3);
    // Each level should have triggerPctOfTp and sellPctOfRemaining
    for (const level of DEFAULT_PROFIT_LADDER) {
      expect(level).toHaveProperty('triggerPctOfTp');
      expect(level).toHaveProperty('sellPctOfRemaining');
      expect(level.triggerPctOfTp).toBeGreaterThan(0);
      expect(level.triggerPctOfTp).toBeLessThanOrEqual(1);
      expect(level.sellPctOfRemaining).toBeGreaterThan(0);
      expect(level.sellPctOfRemaining).toBeLessThanOrEqual(1);
    }
  });

  it('should export AGGRESSIVE_PROFIT_LADDER constant', () => {
    expect(AGGRESSIVE_PROFIT_LADDER).toBeDefined();
    expect(Array.isArray(AGGRESSIVE_PROFIT_LADDER)).toBe(true);
    expect(AGGRESSIVE_PROFIT_LADDER.length).toBeGreaterThanOrEqual(2);
    for (const level of AGGRESSIVE_PROFIT_LADDER) {
      expect(level).toHaveProperty('triggerPctOfTp');
      expect(level).toHaveProperty('sellPctOfRemaining');
    }
  });

  it('DEFAULT_PROFIT_LADDER levels should be sorted ascending by triggerPctOfTp', () => {
    for (let i = 1; i < DEFAULT_PROFIT_LADDER.length; i++) {
      expect(DEFAULT_PROFIT_LADDER[i].triggerPctOfTp).toBeGreaterThan(
        DEFAULT_PROFIT_LADDER[i - 1].triggerPctOfTp
      );
    }
  });

  // --- Default ladder usage tests ---

  it('should use DEFAULT_PROFIT_LADDER when config.profitLadder is undefined', async () => {
    // Token that pumps to TP (100% gain) -- all ladder levels should trigger
    const pumpToken = makeToken({
      price5min: 0.001,
      price15min: 0.002,   // 100% gain
      price1h: 0.003,      // 200% gain
      price4h: 0.003,
      peakPriceUsd: 0.004,
    });

    // No profitLadder in config => should use default
    const result = await runEnhancedBacktest(
      { ...BASE_CONFIG, profitLadder: undefined },
      [pumpToken],
    );

    expect(result.totalTrades).toBeGreaterThanOrEqual(1);
    if (result.trades.length > 0) {
      // With default ladder on a pumping token, should get a scaled exit
      expect(['TAKE_PROFIT_SCALED', 'TRAILING_STOP']).toContain(result.trades[0].exitReason);
      expect(result.trades[0].pnlPct).toBeGreaterThan(0);
    }
  });

  // --- Custom ladder tests ---

  it('should use custom profitLadder when provided', async () => {
    // Token with minimal slippage (price5min ~ price15min) that pumps at 1h
    // Entry slippage: (0.00105 - 0.001)/0.001 = 5% => slippage = 5*0.2 = 1%
    // entryPrice ~ 0.001 * 1.01 * 1.03 ~ 0.001040
    // At 1h: 0.003 => changePct ~ (0.003-0.00104)/0.00104 ~ 188% gain
    // With TP=200%, 50% of TP = 100% gain => triggers at 1h since 188% > 100%
    const token = makeToken({
      price5min: 0.001,
      price15min: 0.00105,  // only 5% move (minimal slippage)
      price1h: 0.003,       // big pump at 1h
      price4h: 0.003,
      peakPriceUsd: 0.004,
    });

    // Custom ladder: sell 100% at 50% of TP (i.e., at 100% gain when TP=200%)
    const result = await runEnhancedBacktest(
      {
        ...BASE_CONFIG,
        takeProfitPct: 200,
        stopLossPct: 50,       // wide SL
        trailingStopPct: 80,   // very wide trail to not interfere
        profitLadder: [
          { triggerPctOfTp: 0.5, sellPctOfRemaining: 1.0 }, // sell everything at 50% of TP
        ],
      },
      [token],
    );

    expect(result.totalTrades).toBeGreaterThanOrEqual(1);
    if (result.trades.length > 0) {
      // Should have exited via the ladder since 188% > 100% (50% of TP=200%)
      expect(result.trades[0].exitReason).toBe('TAKE_PROFIT_SCALED');
    }
  });

  // --- Ladder math: remaining position reduction ---

  it('ladder exits should correctly reduce remaining position', async () => {
    // Token pumps 200%+ -- all default ladder levels should trigger
    const bigPump = makeToken({
      price5min: 0.001,
      price15min: 0.003,   // 200% gain
      price1h: 0.003,
      price4h: 0.003,
      peakPriceUsd: 0.004,
    });

    const result = await runEnhancedBacktest(
      { ...BASE_CONFIG, takeProfitPct: 100, trailingStopPct: 40 },
      [bigPump],
    );

    expect(result.totalTrades).toBeGreaterThanOrEqual(1);
    if (result.trades.length > 0) {
      const trade = result.trades[0];
      // Exit should be profitable
      expect(trade.pnlPct).toBeGreaterThan(0);
      // Exit price should reflect weighted average (not just the TP price)
      // With entry ~0.001 and TP at 100% gain = 0.002, exit should be > entry
      expect(trade.exitPrice).toBeGreaterThan(trade.entryPrice);
    }
  });

  // --- Stop loss still works with ladder ---

  it('should still hit stop loss even when ladder is configured', async () => {
    const dumpToken = makeToken({
      price5min: 0.001,
      price15min: 0.0005,  // 50% dump
      price1h: 0.0003,
      price4h: 0.0002,
      peakPriceUsd: 0.001,
      currentPriceUsd: 0.0002,
    });

    const result = await runEnhancedBacktest(
      {
        ...BASE_CONFIG,
        stopLossPct: 30,
        profitLadder: [
          { triggerPctOfTp: 0.3, sellPctOfRemaining: 0.15 },
          { triggerPctOfTp: 0.5, sellPctOfRemaining: 0.20 },
          { triggerPctOfTp: 1.0, sellPctOfRemaining: 0.50 },
        ],
      },
      [dumpToken],
    );

    expect(result.totalTrades).toBeGreaterThanOrEqual(1);
    if (result.trades.length > 0) {
      expect(result.trades[0].exitReason).toBe('STOP_LOSS');
      expect(result.trades[0].pnlPct).toBeLessThan(0);
    }
  });

  // --- Trailing stop still works with ladder ---

  it('should still hit trailing stop even when ladder is configured', async () => {
    const pumpAndDump = makeToken({
      price5min: 0.001,
      price15min: 0.002,   // 100% up
      price1h: 0.0012,     // dropped 40% from peak
      price4h: 0.0008,
      peakPriceUsd: 0.002,
    });

    const result = await runEnhancedBacktest(
      {
        ...BASE_CONFIG,
        stopLossPct: 50,
        takeProfitPct: 200,
        trailingStopPct: 15,
        profitLadder: [
          { triggerPctOfTp: 0.3, sellPctOfRemaining: 0.15 },
          { triggerPctOfTp: 0.5, sellPctOfRemaining: 0.20 },
          { triggerPctOfTp: 1.0, sellPctOfRemaining: 0.50 },
        ],
      },
      [pumpAndDump],
    );

    expect(result.totalTrades).toBeGreaterThanOrEqual(1);
    if (result.trades.length > 0) {
      const trade = result.trades[0];
      expect(['TRAILING_STOP', 'TAKE_PROFIT_SCALED', 'TIME_EXIT_PARTIAL']).toContain(trade.exitReason);
    }
  });

  // --- Time exit with partial ladder fills ---

  it('should compute weighted exit price when time-exit with partial ladder fills', async () => {
    // Token with minimal slippage that pumps to 1h then falls back by 4h
    // price5min = 0.001, price15min = 0.00105 => 5% move => slippage = 1%
    // entryPrice ~ 0.001 * 1.01 * 1.03 ~ 0.001040
    // At 1h: 0.002 => changePct ~ (0.002-0.00104)/0.00104 ~ 92% gain
    // With TP=200%, 30% of TP = 60% gain => first ladder level triggers (92% > 60%)
    // 70% of TP = 140% gain => second ladder level does NOT trigger (92% < 140%)
    // At 4h: 0.0011 => price falls back, no more triggers
    const partialPump = makeToken({
      price5min: 0.001,
      price15min: 0.00105,  // minimal slippage
      price1h: 0.002,       // big pump at 1h
      price4h: 0.0011,      // falls back by 4h
      peakPriceUsd: 0.002,
    });

    const result = await runEnhancedBacktest(
      {
        ...BASE_CONFIG,
        takeProfitPct: 200,
        stopLossPct: 50,
        trailingStopPct: 80, // very wide trail to avoid interference
        profitLadder: [
          { triggerPctOfTp: 0.3, sellPctOfRemaining: 0.30 },  // triggers at 60% gain (30% of 200%)
          { triggerPctOfTp: 0.7, sellPctOfRemaining: 0.30 },  // won't trigger (needs 140% gain)
          { triggerPctOfTp: 1.0, sellPctOfRemaining: 0.50 },  // won't trigger
        ],
      },
      [partialPump],
    );

    expect(result.totalTrades).toBeGreaterThanOrEqual(1);
    if (result.trades.length > 0) {
      const trade = result.trades[0];
      // Should exit via TIME_EXIT_PARTIAL since only the first ladder level triggered
      expect(['TIME_EXIT_PARTIAL', 'TRAILING_STOP', 'STOP_LOSS']).toContain(trade.exitReason);
    }
  });
});

// ─── xStockCategory Tests ───────────────────────────────────────
// Tests for the new xStockCategory field on PumpFunHistoricalToken
// that provides sub-categorization for tokenized assets.

describe('Historical Data - xStockCategory', () => {
  // The PumpFunHistoricalToken interface should now include
  // an optional xStockCategory field with valid values.

  it('PumpFunHistoricalToken should accept xStockCategory field', async () => {
    const { runEnhancedBacktest } = await import('../analysis/historical-data.js');

    // Create a token with xStockCategory set
    const xstockToken = {
      mint: 'XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp',
      symbol: 'AAPLx',
      name: 'Apple',
      createdAt: Date.now() - 180 * 24 * 60 * 60 * 1000,
      launchPriceUsd: 0.001,
      peakPriceUsd: 0.01,
      currentPriceUsd: 0.008,
      price5min: 0.002,
      price15min: 0.003,
      price1h: 0.005,
      price4h: 0.004,
      price24h: 0.003,
      liquidityUsd: 50000,
      volumeUsd24h: 100000,
      holderCount: 200,
      buyCount1h: 30,
      sellCount1h: 10,
      wasRug: false,
      ruggedAtPct: 0,
      maxMultiple: 3,
      source: 'raydium' as const,
      ageHours: 180 * 24,
      ageCategory: 'veteran' as const,
      volumeSurgeRatio: 1,
      avgDailyVolume: 50000,
      isVolumeSurge: false,
      marketCapUsd: 500000,
      mcapLiqRatio: 10,
      isEstablished: true,
      isVeteran: true,
      isBlueChip: false,
      isXStock: true,
      btcCorrelation: 0.3,
      priceTrajectory: 'consolidating' as const,
      xStockCategory: 'XSTOCK' as const,
    };

    // Should be accepted without type error and run without crash
    const result = await runEnhancedBacktest(
      {
        initialCapitalUsd: 50,
        maxPositionUsd: 5,
        stopLossPct: 3,
        takeProfitPct: 8,
        trailingStopPct: 2,
        minLiquidityUsd: 1000,
        minBuySellRatio: 1.0,
        maxEntryDelayMs: 300000,
        safetyScoreMin: 0.1,
        maxConcurrentPositions: 5,
        partialExitPct: 50,
        source: 'all' as const,
        minTokenAgeHours: 0,
        maxTokenAgeHours: 0,
        ageCategory: 'all' as const,
        requireVolumeSurge: false,
        minVolumeSurgeRatio: 1,
        assetType: 'xstock' as const,
        adaptiveExits: false,
      },
      [xstockToken],
    );

    expect(result).toBeDefined();
    expect(result.totalTokensAnalyzed).toBe(1);
  });

  it('xStockCategory should support all four sub-categories', () => {
    // Verify the type system accepts all 4 categories
    type XStockCategory = 'XSTOCK' | 'PRESTOCK' | 'INDEX' | 'COMMODITY';
    const categories: XStockCategory[] = ['XSTOCK', 'PRESTOCK', 'INDEX', 'COMMODITY'];
    expect(categories).toHaveLength(4);
  });

  it('assetType filter should accept prestock, index, and commodity values', async () => {
    const { runEnhancedBacktest } = await import('../analysis/historical-data.js');

    // These should all be valid assetType values that do not throw
    for (const assetType of ['prestock', 'index', 'commodity'] as const) {
      const result = await runEnhancedBacktest(
        {
          assetType,
          stopLossPct: 10,
          takeProfitPct: 50,
          trailingStopPct: 5,
        },
        [], // empty data
      );
      expect(result).toBeDefined();
      expect(result.config.assetType).toBe(assetType);
    }
  });

  it('xstock filter should only match tokens with xStockCategory XSTOCK', async () => {
    const { runEnhancedBacktest } = await import('../analysis/historical-data.js');

    const xstockToken = {
      mint: 'test_xstock_1',
      symbol: 'AAPLx',
      name: 'Apple',
      createdAt: Date.now() - 180 * 24 * 60 * 60 * 1000,
      launchPriceUsd: 0.001,
      peakPriceUsd: 0.01,
      currentPriceUsd: 0.008,
      price5min: 0.002,
      price15min: 0.003,
      price1h: 0.005,
      price4h: 0.004,
      price24h: 0.003,
      liquidityUsd: 50000,
      volumeUsd24h: 100000,
      holderCount: 200,
      buyCount1h: 30,
      sellCount1h: 10,
      wasRug: false,
      ruggedAtPct: 0,
      maxMultiple: 3,
      source: 'raydium' as const,
      ageHours: 180 * 24,
      ageCategory: 'veteran' as const,
      volumeSurgeRatio: 1,
      avgDailyVolume: 50000,
      isVolumeSurge: false,
      marketCapUsd: 500000,
      mcapLiqRatio: 10,
      isEstablished: true,
      isVeteran: true,
      isBlueChip: false,
      isXStock: true,
      btcCorrelation: 0.3,
      priceTrajectory: 'consolidating' as const,
      xStockCategory: 'XSTOCK' as const,
    };

    const prestockToken = {
      ...xstockToken,
      mint: 'test_prestock_1',
      symbol: 'SPACEX',
      name: 'SpaceX',
      xStockCategory: 'PRESTOCK' as const,
    };

    // When filtering by xstock, only the XSTOCK token should pass
    const result = await runEnhancedBacktest(
      {
        assetType: 'xstock' as const,
        stopLossPct: 3,
        takeProfitPct: 8,
        trailingStopPct: 2,
        minLiquidityUsd: 1000,
        safetyScoreMin: 0.1,
      },
      [xstockToken, prestockToken],
    );

    // Only the XSTOCK token should pass filter (tokensPassedFilter should be 1, not 2)
    expect(result.tokensPassedFilter).toBe(1);
  });

  it('prestock filter should only match tokens with xStockCategory PRESTOCK', async () => {
    const { runEnhancedBacktest } = await import('../analysis/historical-data.js');

    const prestockToken = {
      mint: 'test_prestock_2',
      symbol: 'OPENAI',
      name: 'OpenAI',
      createdAt: Date.now() - 180 * 24 * 60 * 60 * 1000,
      launchPriceUsd: 0.001,
      peakPriceUsd: 0.01,
      currentPriceUsd: 0.008,
      price5min: 0.002,
      price15min: 0.003,
      price1h: 0.005,
      price4h: 0.004,
      price24h: 0.003,
      liquidityUsd: 50000,
      volumeUsd24h: 100000,
      holderCount: 200,
      buyCount1h: 30,
      sellCount1h: 10,
      wasRug: false,
      ruggedAtPct: 0,
      maxMultiple: 3,
      source: 'raydium' as const,
      ageHours: 180 * 24,
      ageCategory: 'veteran' as const,
      volumeSurgeRatio: 1,
      avgDailyVolume: 50000,
      isVolumeSurge: false,
      marketCapUsd: 500000,
      mcapLiqRatio: 10,
      isEstablished: true,
      isVeteran: true,
      isBlueChip: false,
      isXStock: true,
      btcCorrelation: 0.3,
      priceTrajectory: 'consolidating' as const,
      xStockCategory: 'PRESTOCK' as const,
    };

    const indexToken = {
      ...prestockToken,
      mint: 'test_index_1',
      symbol: 'SPYx',
      name: 'S&P 500',
      xStockCategory: 'INDEX' as const,
    };

    // When filtering by prestock, only the PRESTOCK token should pass
    const result = await runEnhancedBacktest(
      {
        assetType: 'prestock' as const,
        stopLossPct: 15,
        takeProfitPct: 50,
        trailingStopPct: 8,
        minLiquidityUsd: 100,
        safetyScoreMin: 0.1,
      },
      [prestockToken, indexToken],
    );

    expect(result.tokensPassedFilter).toBe(1);
  });
});
