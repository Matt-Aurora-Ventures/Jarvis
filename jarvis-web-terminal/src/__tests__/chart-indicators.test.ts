/**
 * Chart Indicator Overlay Tests
 *
 * Tests the indicator computation helpers used by PriceChart
 * to produce data suitable for lightweight-charts LineSeries.
 */
import { describe, it, expect } from 'vitest';

import {
  computeEMAOverlay,
  computeBollingerOverlay,
  computeVolumeColors,
  type IndicatorPoint,
  type BollingerOverlay,
  type ColoredVolume,
} from '@/lib/chart-indicators';

// ---------------------------------------------------------------------------
// Test Data
// ---------------------------------------------------------------------------

interface TestCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

function makeCandles(closes: number[]): TestCandle[] {
  return closes.map((close, i) => ({
    time: 1000 + i * 60,
    open: close - 0.5,
    high: close + 1,
    low: close - 1,
    close,
    volume: 1000 + i * 10,
  }));
}

function makeUpDownCandles(): TestCandle[] {
  // Alternating up and down candles for volume color testing
  return [
    { time: 1000, open: 10, high: 12, low: 9, close: 11, volume: 500 },   // up
    { time: 1060, open: 11, high: 13, low: 10, close: 10, volume: 600 },  // down
    { time: 1120, open: 10, high: 11, low: 9, close: 10, volume: 700 },   // flat (close == open)
    { time: 1180, open: 10, high: 14, low: 9, close: 13, volume: 800 },   // up
    { time: 1240, open: 13, high: 14, low: 8, close: 9, volume: 900 },    // down
  ];
}

// ---------------------------------------------------------------------------
// EMA Overlay
// ---------------------------------------------------------------------------

describe('computeEMAOverlay', () => {
  it('returns arrays of {time, value} points with NaN values filtered out', () => {
    // Need at least 21 candles for EMA 21 to produce a value
    const candles = makeCandles(Array.from({ length: 30 }, (_, i) => 100 + i));
    const { ema9, ema21 } = computeEMAOverlay(candles);

    // EMA9 first valid at index 8 (period-1), so should have 30 - 8 = 22 points
    expect(ema9.length).toBe(22);
    // EMA21 first valid at index 20 (period-1), so should have 30 - 20 = 10 points
    expect(ema21.length).toBe(10);

    // All returned points should have valid numeric values
    for (const pt of ema9) {
      expect(typeof pt.time).toBe('number');
      expect(typeof pt.value).toBe('number');
      expect(isNaN(pt.value)).toBe(false);
    }
    for (const pt of ema21) {
      expect(typeof pt.time).toBe('number');
      expect(typeof pt.value).toBe('number');
      expect(isNaN(pt.value)).toBe(false);
    }
  });

  it('returns empty arrays when not enough data', () => {
    const candles = makeCandles([100, 101, 102]);
    const { ema9, ema21 } = computeEMAOverlay(candles);
    expect(ema9).toEqual([]);
    expect(ema21).toEqual([]);
  });

  it('preserves candle timestamps in output', () => {
    const candles = makeCandles(Array.from({ length: 30 }, (_, i) => 100 + i));
    const { ema9 } = computeEMAOverlay(candles);
    // First EMA9 point corresponds to candle index 8
    expect(ema9[0].time).toBe(candles[8].time);
    // Last EMA9 point corresponds to last candle
    expect(ema9[ema9.length - 1].time).toBe(candles[candles.length - 1].time);
  });

  it('EMA tracks the trend direction', () => {
    // Linear uptrend: EMA should be below the closing prices (lagging)
    const candles = makeCandles(Array.from({ length: 30 }, (_, i) => 100 + i * 2));
    const { ema9 } = computeEMAOverlay(candles);
    const lastEma = ema9[ema9.length - 1];
    const lastClose = candles[candles.length - 1].close;
    // In an uptrend, EMA lags below current price
    expect(lastEma.value).toBeLessThan(lastClose);
  });
});

// ---------------------------------------------------------------------------
// Bollinger Bands Overlay
// ---------------------------------------------------------------------------

describe('computeBollingerOverlay', () => {
  it('returns upper, middle, lower arrays with NaN filtered', () => {
    // BB(20,2) needs at least 20 candles
    const candles = makeCandles(Array.from({ length: 30 }, (_, i) => 100 + Math.sin(i) * 5));
    const bb = computeBollingerOverlay(candles);

    // 30 candles, BB(20) first valid at index 19 => 11 points
    expect(bb.upper.length).toBe(11);
    expect(bb.middle.length).toBe(11);
    expect(bb.lower.length).toBe(11);

    // Upper should be above middle, middle above lower
    for (let i = 0; i < bb.upper.length; i++) {
      expect(bb.upper[i].value).toBeGreaterThan(bb.middle[i].value);
      expect(bb.middle[i].value).toBeGreaterThan(bb.lower[i].value);
    }
  });

  it('returns empty arrays when not enough data', () => {
    const candles = makeCandles([100, 101, 102, 103, 104]);
    const bb = computeBollingerOverlay(candles);
    expect(bb.upper).toEqual([]);
    expect(bb.middle).toEqual([]);
    expect(bb.lower).toEqual([]);
  });

  it('timestamps align between all three bands', () => {
    const candles = makeCandles(Array.from({ length: 25 }, (_, i) => 50 + i));
    const bb = computeBollingerOverlay(candles);

    for (let i = 0; i < bb.upper.length; i++) {
      expect(bb.upper[i].time).toBe(bb.middle[i].time);
      expect(bb.middle[i].time).toBe(bb.lower[i].time);
    }
  });

  it('bands widen with higher volatility', () => {
    // Low volatility: constant prices
    const lowVol = makeCandles(Array.from({ length: 25 }, () => 100));
    const bbLow = computeBollingerOverlay(lowVol);

    // High volatility: big swings
    const highVol = makeCandles(Array.from({ length: 25 }, (_, i) => 100 + (i % 2 === 0 ? 20 : -20)));
    const bbHigh = computeBollingerOverlay(highVol);

    // Compare bandwidth at the last point
    const bwLow = bbLow.upper[bbLow.upper.length - 1].value - bbLow.lower[bbLow.lower.length - 1].value;
    const bwHigh = bbHigh.upper[bbHigh.upper.length - 1].value - bbHigh.lower[bbHigh.lower.length - 1].value;
    expect(bwHigh).toBeGreaterThan(bwLow);
  });
});

// ---------------------------------------------------------------------------
// Volume Color-Coding
// ---------------------------------------------------------------------------

describe('computeVolumeColors', () => {
  it('returns green for up candles and red for down candles', () => {
    const candles = makeUpDownCandles();
    const result = computeVolumeColors(candles);

    expect(result).toHaveLength(5);

    // Up candle (close > open)
    expect(result[0].color).toContain('34,197,94');  // green channel
    // Down candle (close < open)
    expect(result[1].color).toContain('239,68,68');   // red channel
    // Flat candle (close == open) should be green (>= logic)
    expect(result[2].color).toContain('34,197,94');
    // Up candle
    expect(result[3].color).toContain('34,197,94');
    // Down candle
    expect(result[4].color).toContain('239,68,68');
  });

  it('preserves time and volume values', () => {
    const candles = makeUpDownCandles();
    const result = computeVolumeColors(candles);

    for (let i = 0; i < candles.length; i++) {
      expect(result[i].time).toBe(candles[i].time);
      expect(result[i].value).toBe(candles[i].volume);
    }
  });

  it('handles empty array', () => {
    expect(computeVolumeColors([])).toEqual([]);
  });
});
