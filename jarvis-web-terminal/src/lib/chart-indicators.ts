/**
 * Chart Indicator Overlays
 *
 * Computes technical indicator data in a format ready for
 * lightweight-charts LineSeries (array of {time, value}).
 *
 * Uses the calculation functions from backtest-engine.ts
 * so there is no duplication of math.
 */

import { calculateEMA, calculateBollingerBands } from './backtest-engine';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface IndicatorPoint {
  time: number;
  value: number;
}

export interface BollingerOverlay {
  upper: IndicatorPoint[];
  middle: IndicatorPoint[];
  lower: IndicatorPoint[];
}

export interface ColoredVolume {
  time: number;
  value: number;
  color: string;
}

interface CandleLike {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ---------------------------------------------------------------------------
// EMA Overlay (9 and 21 periods)
// ---------------------------------------------------------------------------

/**
 * Compute EMA 9 and EMA 21 overlay data from candles.
 * Returns arrays of {time, value} with NaN-values filtered out,
 * ready to be fed directly into a LineSeries.setData() call.
 */
export function computeEMAOverlay(candles: CandleLike[]): { ema9: IndicatorPoint[]; ema21: IndicatorPoint[] } {
  const closes = candles.map((c) => c.close);
  const times = candles.map((c) => c.time);

  const raw9 = calculateEMA(closes, 9);
  const raw21 = calculateEMA(closes, 21);

  const ema9: IndicatorPoint[] = [];
  const ema21: IndicatorPoint[] = [];

  for (let i = 0; i < raw9.length; i++) {
    if (!isNaN(raw9[i])) {
      ema9.push({ time: times[i], value: raw9[i] });
    }
  }

  for (let i = 0; i < raw21.length; i++) {
    if (!isNaN(raw21[i])) {
      ema21.push({ time: times[i], value: raw21[i] });
    }
  }

  return { ema9, ema21 };
}

// ---------------------------------------------------------------------------
// Bollinger Bands Overlay (20 period, 2 std dev)
// ---------------------------------------------------------------------------

/**
 * Compute Bollinger Bands (20, 2) overlay data from candles.
 * Returns upper/middle/lower arrays of {time, value} with NaN filtered.
 */
export function computeBollingerOverlay(candles: CandleLike[]): BollingerOverlay {
  const closes = candles.map((c) => c.close);
  const times = candles.map((c) => c.time);

  const raw = calculateBollingerBands(closes, 20, 2);

  const upper: IndicatorPoint[] = [];
  const middle: IndicatorPoint[] = [];
  const lower: IndicatorPoint[] = [];

  for (let i = 0; i < raw.upper.length; i++) {
    if (!isNaN(raw.upper[i])) {
      upper.push({ time: times[i], value: raw.upper[i] });
    }
    if (!isNaN(raw.middle[i])) {
      middle.push({ time: times[i], value: raw.middle[i] });
    }
    if (!isNaN(raw.lower[i])) {
      lower.push({ time: times[i], value: raw.lower[i] });
    }
  }

  return { upper, middle, lower };
}

// ---------------------------------------------------------------------------
// Volume Color-Coding
// ---------------------------------------------------------------------------

/**
 * Color-code volume bars: green for up candles (close >= open),
 * red for down candles (close < open).
 */
export function computeVolumeColors(candles: CandleLike[]): ColoredVolume[] {
  return candles.map((c) => ({
    time: c.time,
    value: c.volume,
    color: c.close >= c.open ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)',
  }));
}
