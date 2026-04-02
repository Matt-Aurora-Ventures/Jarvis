import { describe, it, expect } from 'vitest';

// We import only the pure function — no network calls needed
import { ohlcvToCheckpoints, type OHLCVCandle } from '../analysis/ohlcv-fetcher.js';

describe('ohlcvToCheckpoints', () => {
  const BASE_TIME = 1700000000000; // arbitrary start time in ms

  it('returns empty array for empty candles', () => {
    const result = ohlcvToCheckpoints([], BASE_TIME);
    expect(result).toEqual([]);
  });

  it('generates 3 checkpoints per bullish candle (low, high, close)', () => {
    const candle: OHLCVCandle = {
      timestamp: BASE_TIME + 5 * 60000, // 5 min after start
      open: 1.0,
      high: 1.5,
      low: 0.8,
      close: 1.3, // close > open = bullish
      volume: 10000,
    };

    const result = ohlcvToCheckpoints([candle], BASE_TIME);

    expect(result).toHaveLength(3);

    // Bullish order: low first, then high, then close
    expect(result[0].price).toBe(0.8);  // low
    expect(result[1].price).toBe(1.5);  // high
    expect(result[2].price).toBe(1.3);  // close
  });

  it('generates 3 checkpoints per bearish candle (high, low, close)', () => {
    const candle: OHLCVCandle = {
      timestamp: BASE_TIME + 10 * 60000, // 10 min after start
      open: 1.5,
      high: 1.7,
      low: 0.9,
      close: 1.0, // close < open = bearish
      volume: 8000,
    };

    const result = ohlcvToCheckpoints([candle], BASE_TIME);

    expect(result).toHaveLength(3);

    // Bearish order: high first, then low, then close
    expect(result[0].price).toBe(1.7);  // high
    expect(result[1].price).toBe(0.9);  // low
    expect(result[2].price).toBe(1.0);  // close
  });

  it('sorts all checkpoints chronologically across multiple candles', () => {
    const candles: OHLCVCandle[] = [
      {
        timestamp: BASE_TIME + 5 * 60000,
        open: 1.0, high: 1.5, low: 0.8, close: 1.3,
        volume: 10000,
      },
      {
        timestamp: BASE_TIME + 10 * 60000,
        open: 1.3, high: 1.8, low: 1.1, close: 1.6,
        volume: 12000,
      },
    ];

    const result = ohlcvToCheckpoints(candles, BASE_TIME);

    expect(result).toHaveLength(6); // 3 per candle

    // Verify monotonically increasing timeMin
    for (let i = 1; i < result.length; i++) {
      expect(result[i].timeMin).toBeGreaterThanOrEqual(result[i - 1].timeMin);
    }
  });

  it('excludes candles with negative time (before startTime)', () => {
    const candle: OHLCVCandle = {
      timestamp: BASE_TIME - 60000, // 1 min BEFORE start
      open: 1.0, high: 1.5, low: 0.8, close: 1.3,
      volume: 5000,
    };

    const result = ohlcvToCheckpoints([candle], BASE_TIME);
    expect(result).toEqual([]);
  });

  it('excludes candles beyond 240 minutes', () => {
    const candle: OHLCVCandle = {
      timestamp: BASE_TIME + 250 * 60000, // 250 min after start (>240)
      open: 1.0, high: 1.5, low: 0.8, close: 1.3,
      volume: 5000,
    };

    const result = ohlcvToCheckpoints([candle], BASE_TIME);
    expect(result).toEqual([]);
  });

  it('includes candle at exactly 240 minutes', () => {
    const candle: OHLCVCandle = {
      timestamp: BASE_TIME + 239 * 60000, // 239 min — just under 240
      open: 1.0, high: 1.5, low: 0.8, close: 1.3,
      volume: 5000,
    };

    const result = ohlcvToCheckpoints([candle], BASE_TIME);
    expect(result).toHaveLength(3);
  });

  it('treats flat candle (close === open) as bullish', () => {
    const candle: OHLCVCandle = {
      timestamp: BASE_TIME + 5 * 60000,
      open: 1.0, high: 1.2, low: 0.9, close: 1.0, // close === open
      volume: 3000,
    };

    const result = ohlcvToCheckpoints([candle], BASE_TIME);

    expect(result).toHaveLength(3);
    // Bullish path: low first, then high, then close
    expect(result[0].price).toBe(0.9);  // low
    expect(result[1].price).toBe(1.2);  // high
    expect(result[2].price).toBe(1.0);  // close
  });

  it('handles many candles and produces correctly ordered output', () => {
    // Create 48 candles (simulating 4h of 5min candles)
    const candles: OHLCVCandle[] = [];
    for (let i = 0; i < 48; i++) {
      const t = BASE_TIME + i * 5 * 60000;
      candles.push({
        timestamp: t,
        open: 1.0 + i * 0.01,
        high: 1.0 + i * 0.01 + 0.05,
        low: 1.0 + i * 0.01 - 0.03,
        close: 1.0 + i * 0.01 + 0.02,
        volume: 1000 + i * 100,
      });
    }

    const result = ohlcvToCheckpoints(candles, BASE_TIME);

    // 48 candles x 3 checkpoints each = 144
    expect(result).toHaveLength(144);

    // All timeMin values must be non-decreasing
    for (let i = 1; i < result.length; i++) {
      expect(result[i].timeMin).toBeGreaterThanOrEqual(result[i - 1].timeMin);
    }

    // All prices must be positive
    for (const cp of result) {
      expect(cp.price).toBeGreaterThan(0);
    }
  });

  it('correctly computes timeMin relative to startTime', () => {
    const candle: OHLCVCandle = {
      timestamp: BASE_TIME + 60 * 60000, // exactly 60 min after start
      open: 2.0, high: 2.5, low: 1.8, close: 2.3,
      volume: 20000,
    };

    const result = ohlcvToCheckpoints([candle], BASE_TIME);

    // Base timeMin = 60, offsets are +0.5, +3, +4.5
    expect(result[0].timeMin).toBeCloseTo(60.5, 1);
    expect(result[1].timeMin).toBeCloseTo(63, 1);
    expect(result[2].timeMin).toBeCloseTo(64.5, 1);
  });

  it('mixed bullish and bearish candles interleave correctly', () => {
    const candles: OHLCVCandle[] = [
      {
        // Bullish at t=5min
        timestamp: BASE_TIME + 5 * 60000,
        open: 1.0, high: 1.5, low: 0.8, close: 1.3,
        volume: 10000,
      },
      {
        // Bearish at t=10min
        timestamp: BASE_TIME + 10 * 60000,
        open: 1.3, high: 1.4, low: 0.7, close: 0.9,
        volume: 8000,
      },
    ];

    const result = ohlcvToCheckpoints(candles, BASE_TIME);
    expect(result).toHaveLength(6);

    // First 3 from bullish candle (low, high, close at t=5 + offsets)
    expect(result[0].price).toBe(0.8);  // bullish low at 5.5
    expect(result[1].price).toBe(1.5);  // bullish high at 8
    expect(result[2].price).toBe(1.3);  // bullish close at 9.5

    // Next 3 from bearish candle (high, low, close at t=10 + offsets)
    expect(result[3].price).toBe(1.4);  // bearish high at 10.5
    expect(result[4].price).toBe(0.7);  // bearish low at 13
    expect(result[5].price).toBe(0.9);  // bearish close at 14.5
  });
});
