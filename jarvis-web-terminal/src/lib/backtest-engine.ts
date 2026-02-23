/**
 * Backtest Engine -- Tests trading strategies against historical OHLCV data
 *
 * Uses GeckoTerminal free API for historical candlestick data.
 * Runs strategies entirely in the browser (no server required).
 *
 * Exports:
 *  - Technical indicator helpers (EMA, RSI, Bollinger)
 *  - 4 built-in strategies
 *  - simulateTrades() for trade simulation with TP/SL
 *  - runBacktest() for end-to-end backtesting
 */

import {
  fetchOHLCV,
  type OHLCVCandle as GeckoCandle,
  type TimeInterval,
} from './gecko-terminal';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface OHLCVCandle {
  time: number;   // Unix timestamp in seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TradeSignal {
  timestamp: number;
  type: 'BUY' | 'SELL';
  price: number;
  reason: string;
}

export interface BacktestTrade {
  entryTime: number;
  exitTime: number;
  entryPrice: number;
  exitPrice: number;
  returnPct: number;
  holdingPeriod: number; // minutes
}

export interface BacktestResult {
  strategyName: string;
  totalTrades: number;
  winRate: number;       // 0-100
  avgReturn: number;     // percentage
  maxDrawdown: number;   // percentage (negative or zero)
  sharpeRatio: number;
  profitFactor: number;
  trades: BacktestTrade[];
}

export interface BacktestStrategy {
  name: string;
  description: string;
  evaluate: (candles: OHLCVCandle[]) => TradeSignal[];
}

// ---------------------------------------------------------------------------
// Technical Indicator Helpers
// ---------------------------------------------------------------------------

/**
 * Calculate Exponential Moving Average.
 *
 * Returns an array of the same length as `values`.
 * Indices before `period - 1` are NaN.
 * The first valid EMA value (at index `period - 1`) is the SMA of the first
 * `period` values.  Subsequent values use the standard EMA formula:
 *   EMA_t = close_t * k + EMA_{t-1} * (1 - k)
 * where k = 2 / (period + 1).
 */
export function calculateEMA(values: number[], period: number): number[] {
  const result: number[] = new Array(values.length).fill(NaN);

  if (values.length < period || period < 1) {
    return result;
  }

  // Seed with SMA of first `period` values
  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += values[i];
  }
  result[period - 1] = sum / period;

  const k = 2 / (period + 1);

  for (let i = period; i < values.length; i++) {
    result[i] = values[i] * k + result[i - 1] * (1 - k);
  }

  return result;
}

/**
 * Calculate Relative Strength Index (Wilder's smoothing).
 *
 * Returns an array of the same length as `closes`.
 * Indices 0 through `period - 1` are NaN.
 * Index `period` is the first valid RSI value.
 */
export function calculateRSI(closes: number[], period: number = 14): number[] {
  const result: number[] = new Array(closes.length).fill(NaN);

  if (closes.length <= period) {
    return result;
  }

  // Calculate price changes
  const changes: number[] = [];
  for (let i = 1; i < closes.length; i++) {
    changes.push(closes[i] - closes[i - 1]);
  }

  // First average gain/loss from the initial `period` changes
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 0; i < period; i++) {
    if (changes[i] > 0) avgGain += changes[i];
    else avgLoss += Math.abs(changes[i]);
  }
  avgGain /= period;
  avgLoss /= period;

  // First RSI value at index `period` (uses changes[0..period-1])
  if (avgLoss === 0) {
    result[period] = 100;
  } else {
    const rs = avgGain / avgLoss;
    result[period] = 100 - 100 / (1 + rs);
  }

  // Wilder's smoothing for the rest
  for (let i = period; i < changes.length; i++) {
    const change = changes[i];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? Math.abs(change) : 0;

    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;

    if (avgLoss === 0) {
      result[i + 1] = 100;
    } else {
      const rs = avgGain / avgLoss;
      result[i + 1] = 100 - 100 / (1 + rs);
    }
  }

  return result;
}

/**
 * Calculate Bollinger Bands (SMA +/- N standard deviations).
 *
 * Returns { upper, middle, lower } arrays of the same length as `closes`.
 * Indices before `period - 1` are NaN.
 */
export function calculateBollingerBands(
  closes: number[],
  period: number = 20,
  stdDev: number = 2,
): { upper: number[]; middle: number[]; lower: number[] } {
  const upper: number[] = new Array(closes.length).fill(NaN);
  const middle: number[] = new Array(closes.length).fill(NaN);
  const lower: number[] = new Array(closes.length).fill(NaN);

  if (closes.length < period) {
    return { upper, middle, lower };
  }

  for (let i = period - 1; i < closes.length; i++) {
    // SMA
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sum += closes[j];
    }
    const sma = sum / period;

    // Standard deviation
    let sqSum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sqSum += (closes[j] - sma) ** 2;
    }
    const sd = Math.sqrt(sqSum / period); // population std dev

    middle[i] = sma;
    upper[i] = sma + stdDev * sd;
    lower[i] = sma - stdDev * sd;
  }

  return { upper, middle, lower };
}

// ---------------------------------------------------------------------------
// Built-in Strategies
// ---------------------------------------------------------------------------

/**
 * 1. EMA Crossover 9/21
 *
 * When the 9-period EMA crosses above the 21-period EMA => BUY
 * When the 9-period EMA crosses below the 21-period EMA => SELL
 */
function emaCrossover(candles: OHLCVCandle[]): TradeSignal[] {
  const closes = candles.map(c => c.close);
  const ema9 = calculateEMA(closes, 9);
  const ema21 = calculateEMA(closes, 21);
  const signals: TradeSignal[] = [];

  // We need both EMAs to be valid (from index 20 onward)
  for (let i = 21; i < candles.length; i++) {
    if (isNaN(ema9[i]) || isNaN(ema21[i]) || isNaN(ema9[i - 1]) || isNaN(ema21[i - 1])) {
      continue;
    }

    const prevDiff = ema9[i - 1] - ema21[i - 1];
    const currDiff = ema9[i] - ema21[i];

    // Crossover: prev was below/equal, current is above
    if (prevDiff <= 0 && currDiff > 0) {
      signals.push({
        timestamp: candles[i].time,
        type: 'BUY',
        price: candles[i].close,
        reason: `EMA9 (${ema9[i].toFixed(4)}) crossed above EMA21 (${ema21[i].toFixed(4)})`,
      });
    }

    // Crossunder: prev was above/equal, current is below
    if (prevDiff >= 0 && currDiff < 0) {
      signals.push({
        timestamp: candles[i].time,
        type: 'SELL',
        price: candles[i].close,
        reason: `EMA9 (${ema9[i].toFixed(4)}) crossed below EMA21 (${ema21[i].toFixed(4)})`,
      });
    }
  }

  return signals;
}

/**
 * 2. RSI Reversal
 *
 * RSI < 30 => BUY (oversold)
 * RSI > 70 => SELL (overbought)
 *
 * Only signals on the transition (i.e., first candle where RSI crosses threshold).
 */
function rsiReversal(candles: OHLCVCandle[]): TradeSignal[] {
  const closes = candles.map(c => c.close);
  const rsi = calculateRSI(closes, 14);
  const signals: TradeSignal[] = [];

  for (let i = 1; i < candles.length; i++) {
    if (isNaN(rsi[i]) || isNaN(rsi[i - 1])) continue;

    // Transition into oversold
    if (rsi[i - 1] >= 30 && rsi[i] < 30) {
      signals.push({
        timestamp: candles[i].time,
        type: 'BUY',
        price: candles[i].close,
        reason: `RSI dropped to ${rsi[i].toFixed(1)} (oversold <30)`,
      });
    }

    // Transition into overbought
    if (rsi[i - 1] <= 70 && rsi[i] > 70) {
      signals.push({
        timestamp: candles[i].time,
        type: 'SELL',
        price: candles[i].close,
        reason: `RSI rose to ${rsi[i].toFixed(1)} (overbought >70)`,
      });
    }
  }

  return signals;
}

/**
 * 3. Momentum Breakout
 *
 * Volume > 2x the 20-period average AND close > 20-period high => BUY
 * Volume > 2x the 20-period average AND close < 20-period low  => SELL
 */
function momentumBreakout(candles: OHLCVCandle[]): TradeSignal[] {
  const signals: TradeSignal[] = [];
  const lookback = 20;

  if (candles.length <= lookback) return signals;

  for (let i = lookback; i < candles.length; i++) {
    // Calculate 20-period average volume, high, and low
    let volumeSum = 0;
    let periodHigh = -Infinity;
    let periodLow = Infinity;

    for (let j = i - lookback; j < i; j++) {
      volumeSum += candles[j].volume;
      periodHigh = Math.max(periodHigh, candles[j].high);
      periodLow = Math.min(periodLow, candles[j].low);
    }
    const avgVolume = volumeSum / lookback;

    const c = candles[i];

    if (c.volume > 2 * avgVolume) {
      if (c.close > periodHigh) {
        signals.push({
          timestamp: c.time,
          type: 'BUY',
          price: c.close,
          reason: `Breakout: close ${c.close.toFixed(4)} > 20p high ${periodHigh.toFixed(4)}, vol ${c.volume.toFixed(0)} > 2x avg ${avgVolume.toFixed(0)}`,
        });
      }

      if (c.close < periodLow) {
        signals.push({
          timestamp: c.time,
          type: 'SELL',
          price: c.close,
          reason: `Breakdown: close ${c.close.toFixed(4)} < 20p low ${periodLow.toFixed(4)}, vol ${c.volume.toFixed(0)} > 2x avg ${avgVolume.toFixed(0)}`,
        });
      }
    }
  }

  return signals;
}

/**
 * 4. Mean Reversion (Bollinger Bands)
 *
 * Price closes below the lower band => BUY (expect reversion to mean)
 * Price closes above the upper band => SELL (expect reversion to mean)
 */
function meanReversion(candles: OHLCVCandle[]): TradeSignal[] {
  const closes = candles.map(c => c.close);
  const bb = calculateBollingerBands(closes, 20, 2);
  const signals: TradeSignal[] = [];

  for (let i = 0; i < candles.length; i++) {
    if (isNaN(bb.upper[i]) || isNaN(bb.lower[i])) continue;

    const c = candles[i];

    if (c.close <= bb.lower[i]) {
      signals.push({
        timestamp: c.time,
        type: 'BUY',
        price: c.close,
        reason: `Price ${c.close.toFixed(4)} touched lower BB ${bb.lower[i].toFixed(4)}`,
      });
    }

    if (c.close >= bb.upper[i]) {
      signals.push({
        timestamp: c.time,
        type: 'SELL',
        price: c.close,
        reason: `Price ${c.close.toFixed(4)} touched upper BB ${bb.upper[i].toFixed(4)}`,
      });
    }
  }

  return signals;
}

// ---------------------------------------------------------------------------
// Strategy Registry
// ---------------------------------------------------------------------------

export const BUILTIN_STRATEGIES: BacktestStrategy[] = [
  {
    name: 'EMA Crossover 9/21',
    description: 'Trend following with 9 and 21 period EMAs',
    evaluate: emaCrossover,
  },
  {
    name: 'RSI Reversal',
    description: 'Buy oversold (RSI<30), sell overbought (RSI>70)',
    evaluate: rsiReversal,
  },
  {
    name: 'Momentum Breakout',
    description: 'Volume spike + price breakout above 20-period high',
    evaluate: momentumBreakout,
  },
  {
    name: 'Mean Reversion',
    description: 'Bollinger Band mean reversion — buy lower band, sell upper band',
    evaluate: meanReversion,
  },
];

// ---------------------------------------------------------------------------
// Trade Simulation
// ---------------------------------------------------------------------------

interface SimulationOptions {
  takeProfitPct: number; // e.g. 20 means +20%
  stopLossPct: number;   // e.g. 10 means -10%
}

/**
 * Simulate trades from a set of signals against candle data.
 *
 * Rules:
 * - Only BUY signals open long positions.
 * - A position is closed when TP or SL is hit, or at the end of data.
 * - Only one position at a time (no overlapping).
 * - SELL signals close the current position (if any).
 */
export function simulateTrades(
  signals: TradeSignal[],
  candles: OHLCVCandle[],
  options: SimulationOptions,
): Omit<BacktestResult, 'strategyName'> {
  const trades: BacktestTrade[] = [];

  if (signals.length === 0 || candles.length === 0) {
    return {
      totalTrades: 0,
      winRate: 0,
      avgReturn: 0,
      maxDrawdown: 0,
      sharpeRatio: 0,
      profitFactor: 0,
      trades: [],
    };
  }

  // Build a signal lookup by timestamp for efficient scanning
  const buySignals = signals
    .filter(s => s.type === 'BUY')
    .sort((a, b) => a.timestamp - b.timestamp);

  const sellSignals = new Set(
    signals.filter(s => s.type === 'SELL').map(s => s.timestamp),
  );

  // Walk through candles and simulate
  let inPosition = false;
  let entryPrice = 0;
  let entryTime = 0;
  let tpPrice = 0;
  let slPrice = 0;
  let signalIdx = 0;

  for (let i = 0; i < candles.length; i++) {
    const c = candles[i];

    if (!inPosition) {
      // Look for next BUY signal at or before this candle
      while (signalIdx < buySignals.length && buySignals[signalIdx].timestamp <= c.time) {
        // Open position
        entryPrice = buySignals[signalIdx].price;
        entryTime = buySignals[signalIdx].timestamp;
        tpPrice = entryPrice * (1 + options.takeProfitPct / 100);
        slPrice = entryPrice * (1 - options.stopLossPct / 100);
        inPosition = true;
        signalIdx++;
        break;
      }
    }

    if (inPosition) {
      let exitPrice: number | null = null;
      let exitTime: number | null = null;

      // Check SL hit (low touches or goes below SL)
      if (c.low <= slPrice) {
        exitPrice = slPrice;
        exitTime = c.time;
      }
      // Check TP hit (high touches or goes above TP)
      else if (c.high >= tpPrice) {
        exitPrice = tpPrice;
        exitTime = c.time;
      }
      // Check SELL signal
      else if (sellSignals.has(c.time)) {
        exitPrice = c.close;
        exitTime = c.time;
      }

      if (exitPrice !== null && exitTime !== null) {
        const returnPct = ((exitPrice - entryPrice) / entryPrice) * 100;
        const holdingPeriod = Math.max(0, (exitTime - entryTime) / 60); // seconds -> minutes
        trades.push({
          entryTime,
          exitTime,
          entryPrice,
          exitPrice,
          returnPct,
          holdingPeriod,
        });
        inPosition = false;
      }
    }
  }

  // Close any remaining position at last candle
  if (inPosition && candles.length > 0) {
    const lastCandle = candles[candles.length - 1];
    const returnPct = ((lastCandle.close - entryPrice) / entryPrice) * 100;
    const holdingPeriod = Math.max(0, (lastCandle.time - entryTime) / 60);
    trades.push({
      entryTime,
      exitTime: lastCandle.time,
      entryPrice,
      exitPrice: lastCandle.close,
      returnPct,
      holdingPeriod,
    });
  }

  // Calculate statistics
  const totalTrades = trades.length;
  const wins = trades.filter(t => t.returnPct > 0);
  const losses = trades.filter(t => t.returnPct <= 0);
  const winRate = totalTrades > 0 ? (wins.length / totalTrades) * 100 : 0;
  const avgReturn =
    totalTrades > 0
      ? trades.reduce((sum, t) => sum + t.returnPct, 0) / totalTrades
      : 0;

  // Max drawdown (cumulative equity curve)
  let peak = 0;
  let maxDrawdown = 0;
  let cumReturn = 0;
  for (const t of trades) {
    cumReturn += t.returnPct;
    if (cumReturn > peak) peak = cumReturn;
    const dd = cumReturn - peak;
    if (dd < maxDrawdown) maxDrawdown = dd;
  }

  // Sharpe ratio (annualized, assuming daily returns)
  const returns = trades.map(t => t.returnPct);
  const meanReturn = returns.length > 0 ? returns.reduce((a, b) => a + b, 0) / returns.length : 0;
  const variance =
    returns.length > 1
      ? returns.reduce((s, r) => s + (r - meanReturn) ** 2, 0) / (returns.length - 1)
      : 0;
  const stdDevReturns = Math.sqrt(variance);
  const sharpeRatio = stdDevReturns > 0 ? (meanReturn / stdDevReturns) * Math.sqrt(252) : 0;

  // Profit factor = gross profit / gross loss
  const grossProfit = wins.reduce((s, t) => s + t.returnPct, 0);
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.returnPct, 0));
  const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? Infinity : 0;

  return {
    totalTrades,
    winRate,
    avgReturn,
    maxDrawdown,
    sharpeRatio,
    profitFactor,
    trades,
  };
}

// ---------------------------------------------------------------------------
// Main Backtest Runner
// ---------------------------------------------------------------------------

export interface BacktestOptions {
  timeframe?: TimeInterval;
  lookbackCandles?: number;
  takeProfitPct?: number;
  stopLossPct?: number;
}

/**
 * Run a full backtest for a pool address with a given strategy.
 *
 * 1. Fetches OHLCV data from GeckoTerminal.
 * 2. Runs strategy.evaluate() to generate signals.
 * 3. Simulates trades with TP/SL.
 * 4. Returns BacktestResult with full statistics.
 */
export async function runBacktest(
  poolAddress: string,
  strategy: BacktestStrategy,
  options?: BacktestOptions,
): Promise<BacktestResult> {
  const timeframe = options?.timeframe ?? '1h';
  const lookbackCandles = options?.lookbackCandles ?? 300;
  const takeProfitPct = options?.takeProfitPct ?? 20;
  const stopLossPct = options?.stopLossPct ?? 10;

  // Fetch OHLCV data from GeckoTerminal
  const geckoCandles = await fetchOHLCV(poolAddress, timeframe, lookbackCandles);

  // Transform GeckoTerminal candles to our format (they share the same shape)
  const candles: OHLCVCandle[] = geckoCandles.map(c => ({
    time: c.time,
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
    volume: c.volume,
  }));

  if (candles.length < 30) {
    return {
      strategyName: strategy.name,
      totalTrades: 0,
      winRate: 0,
      avgReturn: 0,
      maxDrawdown: 0,
      sharpeRatio: 0,
      profitFactor: 0,
      trades: [],
    };
  }

  // Generate signals
  const signals = strategy.evaluate(candles);

  // Simulate trades
  const sim = simulateTrades(signals, candles, { takeProfitPct, stopLossPct });

  return {
    strategyName: strategy.name,
    ...sim,
  };
}

/**
 * Get the current signal (latest) from a strategy for a set of candles.
 * Returns 'BUY', 'SELL', or 'HOLD' plus any relevant data.
 */
export function getCurrentSignal(
  strategy: BacktestStrategy,
  candles: OHLCVCandle[],
): { signal: 'BUY' | 'SELL' | 'HOLD'; price: number; reason: string; indicatorValue?: number } {
  if (candles.length < 22) {
    return { signal: 'HOLD', price: 0, reason: 'Insufficient data' };
  }

  const signals = strategy.evaluate(candles);
  const lastPrice = candles[candles.length - 1].close;

  if (signals.length === 0) {
    return { signal: 'HOLD', price: lastPrice, reason: 'No recent signals' };
  }

  // Return the most recent signal
  const latest = signals[signals.length - 1];

  // Check if the signal is from the last 3 candles (recent enough to be actionable)
  const recentThreshold = candles[Math.max(0, candles.length - 4)].time;
  if (latest.timestamp >= recentThreshold) {
    return {
      signal: latest.type,
      price: latest.price,
      reason: latest.reason,
    };
  }

  return { signal: 'HOLD', price: lastPrice, reason: 'Last signal too old' };
}

/**
 * Determine consensus signal across all strategies.
 */
export function getConsensus(
  results: Array<{ signal: 'BUY' | 'SELL' | 'HOLD' }>,
): { consensus: 'BUY' | 'SELL' | 'HOLD'; buyCount: number; sellCount: number; holdCount: number; total: number } {
  const buyCount = results.filter(r => r.signal === 'BUY').length;
  const sellCount = results.filter(r => r.signal === 'SELL').length;
  const holdCount = results.filter(r => r.signal === 'HOLD').length;
  const total = results.length;

  let consensus: 'BUY' | 'SELL' | 'HOLD' = 'HOLD';
  if (buyCount > sellCount && buyCount > holdCount) consensus = 'BUY';
  else if (sellCount > buyCount && sellCount > holdCount) consensus = 'SELL';

  return { consensus, buyCount, sellCount, holdCount, total };
}
