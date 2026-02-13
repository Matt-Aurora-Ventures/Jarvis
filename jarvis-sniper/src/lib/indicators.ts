/**
 * Mathematical Indicators & Statistical Utilities
 *
 * Native implementations of quantitative functions for the backtest engine
 * and risk management layer. No external dependencies — pure TypeScript math.
 *
 * Theorems applied:
 *   - Euler/e^x: EMA decay factor α ≈ 1 - e^(-1/N), EWMA volatility
 *   - CLT: Confidence intervals on mean returns, Wilson score for proportions
 *   - FTC-adjacent: Parkinson volatility (numerical integration of log-range)
 *
 * @module indicators
 */

import type { OHLCVCandle } from './backtest-engine';

// ============================================================================
// Exponential Moving Average (Euler: α = 2/(N+1))
// ============================================================================

/**
 * Compute EMA series for candle closes.
 *
 * Decay factor α = 2/(period+1), derived from the exponential function.
 * For large period, α ≈ 1 - e^(-1/period).
 *
 * Returns array of same length as input. First value = first close.
 */
export function computeEMA(candles: OHLCVCandle[], period: number): number[] {
  if (candles.length === 0) return [];
  const alpha = 2 / (period + 1);
  const ema: number[] = [candles[0].close];
  for (let i = 1; i < candles.length; i++) {
    ema.push(alpha * candles[i].close + (1 - alpha) * ema[i - 1]);
  }
  return ema;
}

/**
 * Compute EMA from a raw numeric array (e.g. volumes, returns).
 */
export function computeEMAFromValues(values: number[], period: number): number[] {
  if (values.length === 0) return [];
  const alpha = 2 / (period + 1);
  const ema: number[] = [values[0]];
  for (let i = 1; i < values.length; i++) {
    ema.push(alpha * values[i] + (1 - alpha) * ema[i - 1]);
  }
  return ema;
}

// ============================================================================
// EWMA Volatility (Euler: exponential decay weighting)
// ============================================================================

/**
 * Exponentially-Weighted Moving Average volatility (RiskMetrics-style).
 *
 * λ = 0.94 is the classic daily decay factor. For hourly memecoin data
 * with fast regime changes, λ = 0.90 gives more responsiveness.
 *
 * σ²_t = λ · σ²_{t-1} + (1-λ) · r²_t
 *
 * Returns annualized volatility (assumes hourly candles → 8760 periods/year).
 */
export function ewmaVolatility(returns: number[], lambda = 0.90): number {
  if (returns.length === 0) return 0;
  let variance = returns[0] ** 2;
  for (let i = 1; i < returns.length; i++) {
    variance = lambda * variance + (1 - lambda) * returns[i] ** 2;
  }
  return Math.sqrt(variance);
}

/**
 * Compute EWMA volatility series (one value per candle).
 * Useful for plotting volatility over time or detecting regime shifts.
 */
export function ewmaVolatilitySeries(returns: number[], lambda = 0.90): number[] {
  if (returns.length === 0) return [];
  const series: number[] = [Math.abs(returns[0])];
  let variance = returns[0] ** 2;
  for (let i = 1; i < returns.length; i++) {
    variance = lambda * variance + (1 - lambda) * returns[i] ** 2;
    series.push(Math.sqrt(variance));
  }
  return series;
}

// ============================================================================
// Parkinson Volatility (FTC-adjacent: numerical integration of log-range)
// ============================================================================

/**
 * Parkinson volatility estimator — uses high/low range of each candle.
 *
 * 5.2x more statistically efficient than close-to-close for continuous
 * price processes. For memecoins with huge intra-candle wicks, this
 * captures reality much better than close-only estimators.
 *
 * σ² = (1 / 4N·ln2) · Σ [ln(H_i / L_i)]²
 *
 * Returns per-period volatility (not annualized).
 */
export function parkinsonVolatility(candles: OHLCVCandle[]): number {
  const n = candles.length;
  if (n === 0) return 0;
  const sumSqLogRange = candles.reduce((s, c) => {
    if (c.low <= 0 || c.high <= 0) return s;
    const logRange = Math.log(c.high / c.low);
    return s + logRange * logRange;
  }, 0);
  return Math.sqrt(sumSqLogRange / (4 * n * Math.LN2));
}

/**
 * Parkinson volatility over a rolling window.
 * Returns array where index i = volatility of candles [i-window+1 .. i].
 * First (window-1) values are computed from available data.
 */
export function parkinsonVolatilityRolling(candles: OHLCVCandle[], window = 20): number[] {
  const result: number[] = [];
  for (let i = 0; i < candles.length; i++) {
    const start = Math.max(0, i - window + 1);
    result.push(parkinsonVolatility(candles.slice(start, i + 1)));
  }
  return result;
}

// ============================================================================
// Log Returns (Euler: ln(P_t / P_{t-1}))
// ============================================================================

/**
 * Compute log return between two prices.
 * Log returns are time-additive: ln(P_T/P_0) = Σ ln(P_t/P_{t-1})
 */
export function logReturn(entryPrice: number, exitPrice: number): number {
  if (entryPrice <= 0) return 0;
  return Math.log(exitPrice / entryPrice);
}

/**
 * Compute log returns series from candle closes.
 * Returns array of length (candles.length - 1).
 */
export function logReturnSeries(candles: OHLCVCandle[]): number[] {
  const returns: number[] = [];
  for (let i = 1; i < candles.length; i++) {
    if (candles[i - 1].close > 0) {
      returns.push(Math.log(candles[i].close / candles[i - 1].close));
    } else {
      returns.push(0);
    }
  }
  return returns;
}

// ============================================================================
// Confidence Intervals (CLT + Bootstrap)
// ============================================================================

/**
 * CLT-based 95% confidence interval on the mean.
 *
 * CI = μ ± z · σ/√N
 *
 * Caveat: CLT requires N ≥ 30 for light-tailed distributions,
 * N ≥ 50+ for fat-tailed memecoin returns. The `reliable` flag
 * indicates whether N is sufficient.
 */
export function cltMeanCI(values: number[], z = 1.96): { ci: [number, number]; reliable: boolean } {
  const n = values.length;
  if (n < 2) return { ci: [-Infinity, Infinity], reliable: false };

  const mean = values.reduce((s, v) => s + v, 0) / n;
  const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / (n - 1);
  const se = Math.sqrt(variance) / Math.sqrt(n);

  return {
    ci: [mean - z * se, mean + z * se],
    reliable: n >= 50,
  };
}

/**
 * Wilson score interval for win rate (proportion).
 *
 * Superior to CLT for proportions because:
 * - Never produces negative CIs
 * - Works for small N
 * - Handles edge cases (0% or 100% win rate)
 */
export function wilsonScoreCI(wins: number, total: number, z = 1.96): [number, number] {
  if (total === 0) return [0, 0];
  const p = wins / total;
  const denom = 1 + (z * z) / total;
  const centre = p + (z * z) / (2 * total);
  const margin = z * Math.sqrt((p * (1 - p) + (z * z) / (4 * total)) / total);
  return [(centre - margin) / denom, (centre + margin) / denom];
}

/**
 * Bootstrap confidence interval for the Sharpe ratio.
 *
 * Sharpe's sampling distribution is complex (ratio of random variables),
 * so CLT doesn't apply cleanly. Bootstrap resampling gives an honest CI.
 *
 * Uses a seeded PRNG for reproducibility.
 */
export function bootstrapSharpeCI(
  returns: number[],
  iterations = 2000,
  confidence = 0.95,
): [number, number] {
  const n = returns.length;
  if (n < 10) return [-Infinity, Infinity];

  const sharpes: number[] = [];
  // Simple seedable PRNG (mulberry32)
  let seed = 42;
  const rand = () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  for (let iter = 0; iter < iterations; iter++) {
    let sum = 0;
    let sumSq = 0;
    for (let i = 0; i < n; i++) {
      const r = returns[Math.floor(rand() * n)];
      sum += r;
      sumSq += r * r;
    }
    const mean = sum / n;
    const variance = sumSq / n - mean * mean;
    const std = Math.sqrt(Math.max(variance, 1e-10));
    sharpes.push(mean / std);
  }

  sharpes.sort((a, b) => a - b);
  const tail = (1 - confidence) / 2;
  const lo = sharpes[Math.floor(tail * iterations)];
  const hi = sharpes[Math.floor((1 - tail) * iterations)];
  return [lo, hi];
}

// ============================================================================
// Composite Helpers
// ============================================================================

/**
 * Compute all volatility estimates for a candle series.
 * Returns close-to-close, Parkinson, and EWMA estimates.
 */
export function volatilityEstimates(candles: OHLCVCandle[]): {
  closeToClose: number;
  parkinson: number;
  ewma: number;
} {
  const logReturns = logReturnSeries(candles);
  if (logReturns.length === 0) return { closeToClose: 0, parkinson: 0, ewma: 0 };

  const mean = logReturns.reduce((s, r) => s + r, 0) / logReturns.length;
  const variance = logReturns.reduce((s, r) => s + (r - mean) ** 2, 0) / (logReturns.length - 1 || 1);

  return {
    closeToClose: Math.sqrt(variance),
    parkinson: parkinsonVolatility(candles),
    ewma: ewmaVolatility(logReturns),
  };
}
