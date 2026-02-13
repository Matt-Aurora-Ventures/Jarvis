import { describe, it, expect } from 'vitest';
import type { TVStockData } from '@/lib/tv-screener';
import type { TokenizedEquity } from '@/lib/xstocks-data';
import {
  calcMomentumScore,
  calcVolumeConfirmation,
  calcTVEnhancedScore,
  calcTVEnhancedScoreDetailed,
  type TVEnhancedScore,
} from '@/lib/tv-scoring';

// ============================================================================
// Test Helpers — Mock TVStockData
// ============================================================================

/** Returns a minimal TVStockData with all nullable fields set to null */
function makeTVData(overrides: Partial<TVStockData> = {}): TVStockData {
  return {
    symbol: 'NASDAQ:TEST',
    name: 'Test Stock',
    price: 100,
    changePercent: 0,
    change: 0,
    open: 100,
    high: 101,
    low: 99,
    gap: null,
    volume: 1_000_000,
    avgVolume10d: 1_000_000,
    relativeVolume: 1.0,
    rsi14: null,
    macdLevel: null,
    macdSignal: null,
    stochK: null,
    williamsR: null,
    cci: null,
    adx: null,
    momentum: null,
    moneyFlow: null,
    technicalRating: null,
    oscillatorsRating: null,
    maRating: null,
    sma20: null,
    sma50: null,
    sma200: null,
    ema20: null,
    ema50: null,
    bollingerLower: null,
    bollingerUpper: null,
    atr: null,
    volatility: null,
    perfWeek: null,
    perfMonth: null,
    perf3M: null,
    perfYTD: null,
    marketCap: null,
    sector: null,
    premarketChange: null,
    premarketVolume: null,
    postmarketChange: null,
    vwap: null,
    beta: null,
    updateMode: null,
    ...overrides,
  };
}

/** Returns a minimal TokenizedEquity for testing */
function makeToken(overrides: Partial<TokenizedEquity> = {}): TokenizedEquity {
  return {
    ticker: 'TESTx',
    name: 'Test',
    company: 'Test Corp',
    category: 'XSTOCK',
    sector: 'Technology',
    mintAddress: '0x123',
    description: 'Test token',
    ...overrides,
  };
}

/** Returns a minimal DexScreener pair object */
function makeDexPair(overrides: Record<string, any> = {}): any {
  return {
    liquidity: { usd: '500000' },
    volume: { h24: '100000' },
    priceChange: { h1: 1.5, h24: 3.0 },
    txns: { h1: { buys: 50, sells: 30 } },
    priceUsd: '100',
    fdv: 5_000_000,
    ...overrides,
  };
}

// ============================================================================
// calcMomentumScore Tests
// ============================================================================

describe('calcMomentumScore', () => {
  it('returns score > 70 for a bullish setup', () => {
    const tv = makeTVData({
      rsi14: 60,
      macdLevel: 1.5,
      macdSignal: 0.5,        // MACD above signal -> bullish
      technicalRating: 0.7,    // Positive technical rating
      price: 150,
      sma20: 145,              // Price > SMA20 > SMA50 > SMA200 -> uptrend
      sma50: 140,
      sma200: 130,
    });
    const score = calcMomentumScore(tv);
    expect(score).toBeGreaterThan(70);
  });

  it('returns score < 35 for a bearish setup', () => {
    const tv = makeTVData({
      rsi14: 35,               // Weak zone (30-45) -> -5
      macdLevel: -2.0,
      macdSignal: -0.5,        // MACD below signal -> bearish
      technicalRating: -0.8,   // Negative technical rating
      price: 80,
      sma20: 90,               // Price < SMA20 < SMA50 -> downtrend
      sma50: 95,
      sma200: 100,
    });
    const score = calcMomentumScore(tv);
    expect(score).toBeLessThan(35);
  });

  it('returns score between 40-60 for a neutral setup', () => {
    const tv = makeTVData({
      rsi14: 50,               // Neutral zone (45-55) -> 0
      macdLevel: -0.01,
      macdSignal: 0.01,        // MACD slightly below signal -> -8
      technicalRating: 0.05,   // Near-zero rating -> +0.75
      price: 100,
      sma20: 101,              // Price < SMA20 but SMA20 > SMA50 -> mixed -> 0
      sma50: 99,
      sma200: 95,
    });
    const score = calcMomentumScore(tv);
    expect(score).toBeGreaterThanOrEqual(40);
    expect(score).toBeLessThanOrEqual(60);
  });

  it('returns 50 (neutral baseline) when all indicators are null', () => {
    const tv = makeTVData({
      rsi14: null,
      macdLevel: null,
      macdSignal: null,
      technicalRating: null,
      sma20: null,
      sma50: null,
      sma200: null,
    });
    const score = calcMomentumScore(tv);
    expect(score).toBe(50);
  });

  it('applies overbought penalty when RSI > 70', () => {
    const tv = makeTVData({
      rsi14: 78,                // Overbought -> -15
      macdLevel: 0.5,
      macdSignal: 0.3,         // MACD slightly bullish -> +12
      technicalRating: 0.2,    // Mild positive -> +3
      price: 150,
      sma20: 145,
      sma50: 140,
      sma200: 130,             // Uptrend -> +10
    });
    const score = calcMomentumScore(tv);
    // RSI overbought penalty (-15) should meaningfully drag the score down
    // compared to a non-overbought RSI with the same other indicators.
    // Score should be well below a fully bullish setup (>70)
    expect(score).toBeLessThanOrEqual(60);
  });
});

// ============================================================================
// calcVolumeConfirmation Tests
// ============================================================================

describe('calcVolumeConfirmation', () => {
  it('returns score > 65 for a volume surge', () => {
    const tv = makeTVData({
      relativeVolume: 2.5,
      volume: 2_500_000,
      price: 100,
    });
    const result = calcVolumeConfirmation(tv, 200_000);
    expect(result.score).toBeGreaterThan(65);
    expect(result.volumeRatio).toBeGreaterThan(0);
  });

  it('returns score < 40 for low volume', () => {
    const tv = makeTVData({
      relativeVolume: 0.3,
      volume: 200_000,
      price: 100,
    });
    const result = calcVolumeConfirmation(tv, 50);
    expect(result.score).toBeLessThan(40);
  });

  it('applies bonus for high tokenized interest', () => {
    const tv = makeTVData({
      relativeVolume: 1.0,
      volume: 1_000_000,
      price: 50,
    });
    // dexVolume / (tv.volume * tv.price) = 800_000 / (1_000_000 * 50) = 0.016 > 0.01 -> bonus
    const result = calcVolumeConfirmation(tv, 800_000);
    expect(result.score).toBeGreaterThan(60);
  });

  it('returns neutral 50 when TV volume is zero', () => {
    const tv = makeTVData({
      relativeVolume: 0,
      volume: 0,
      price: 0,
    });
    const result = calcVolumeConfirmation(tv, 100_000);
    expect(result.score).toBe(50);
    expect(result.volumeRatio).toBe(0);
  });
});

// ============================================================================
// calcTVEnhancedScore Tests
// ============================================================================

describe('calcTVEnhancedScore', () => {
  it('returns a different score with TV data than without', () => {
    const tv = makeTVData({
      rsi14: 65,
      macdLevel: 2.0,
      macdSignal: 1.0,
      technicalRating: 0.5,
      price: 150,
      sma20: 145,
      sma50: 140,
      sma200: 130,
      relativeVolume: 2.0,
      volume: 2_000_000,
    });
    const pair = makeDexPair();
    const token = makeToken();

    const withTV = calcTVEnhancedScore(tv, pair, token);
    const withoutTV = calcTVEnhancedScore(null, pair, token);
    expect(withTV).not.toBe(withoutTV);
  });

  it('falls back to DexScreener-only scoring when tv is null', () => {
    const pair = makeDexPair();
    const token = makeToken();

    const score = calcTVEnhancedScore(null, pair, token);
    // Should return a valid number in the 10-100 range (clamped)
    expect(score).toBeGreaterThanOrEqual(10);
    expect(score).toBeLessThanOrEqual(100);
  });

  it('blends 40% DexScreener + 35% momentum + 25% volume confirmation', () => {
    const tv = makeTVData({
      rsi14: 50,
      macdLevel: 0,
      macdSignal: 0,
      technicalRating: 0,
      price: 100,
      sma20: 100,
      sma50: 100,
      sma200: 100,
      relativeVolume: 1.0,
      volume: 1_000_000,
    });
    const pair = makeDexPair();
    const token = makeToken();

    const result = calcTVEnhancedScoreDetailed(tv, pair, token);
    expect(result.hasTVData).toBe(true);

    // Verify the composite is a weighted blend
    const expected = Math.round(
      result.baseEquityScore * 0.4 +
      result.momentum * 0.35 +
      result.volumeConfirmation * 0.25
    );
    // Allow 1-point rounding tolerance
    expect(Math.abs(result.composite - Math.max(10, Math.min(100, expected)))).toBeLessThanOrEqual(1);
  });
});

// ============================================================================
// calcTVEnhancedScoreDetailed Tests
// ============================================================================

describe('calcTVEnhancedScoreDetailed', () => {
  it('returns full TVEnhancedScore object with hasTVData=true when TV data present', () => {
    const tv = makeTVData({ rsi14: 55 });
    const pair = makeDexPair();
    const token = makeToken();

    const result = calcTVEnhancedScoreDetailed(tv, pair, token);
    expect(result).toHaveProperty('composite');
    expect(result).toHaveProperty('momentum');
    expect(result).toHaveProperty('volumeConfirmation');
    expect(result).toHaveProperty('baseEquityScore');
    expect(result.hasTVData).toBe(true);
  });

  it('returns hasTVData=false when TV data is null', () => {
    const pair = makeDexPair();
    const token = makeToken();

    const result = calcTVEnhancedScoreDetailed(null, pair, token);
    expect(result.hasTVData).toBe(false);
    expect(result.composite).toBeGreaterThanOrEqual(10);
  });

  it('clamps composite to 10-100 range', () => {
    // Edge case: all indicators maximally bearish
    const tv = makeTVData({
      rsi14: 10,
      macdLevel: -5,
      macdSignal: 0,
      technicalRating: -1.0,
      price: 50,
      sma20: 80,
      sma50: 90,
      sma200: 100,
      relativeVolume: 0.1,
      volume: 100,
    });
    const pair = makeDexPair({
      liquidity: { usd: '1000' },
      volume: { h24: '10' },
      priceChange: { h1: -5, h24: -10 },
      txns: { h1: { buys: 1, sells: 20 } },
    });
    const token = makeToken();

    const result = calcTVEnhancedScoreDetailed(tv, pair, token);
    expect(result.composite).toBeGreaterThanOrEqual(10);
    expect(result.composite).toBeLessThanOrEqual(100);
  });
});
