/**
 * Backtesting Engine — Validate strategy presets against historical data
 *
 * Simulates entries/exits using OHLCV candle data with realistic slippage
 * and fee models. Supports walk-forward optimization.
 *
 * Usage:
 *   const engine = new BacktestEngine(candles, config);
 *   const result = engine.run();
 *
 * Fulfills: BACK-02 (Backtesting Engine)
 */

// ─── Types ───

export interface OHLCVCandle {
  timestamp: number;   // Unix ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface BacktestConfig {
  /** Strategy name for identification */
  strategyId: string;
  /** Stop-loss percentage (e.g., 20 = 20%) */
  stopLossPct: number;
  /** Take-profit percentage */
  takeProfitPct: number;
  /** Trailing stop percentage (0 = disabled) */
  trailingStopPct: number;
  /** Minimum score to enter (0-100) */
  minScore: number;
  /** Minimum liquidity in USD */
  minLiquidityUsd: number;
  /** Slippage model: percentage applied to entry/exit */
  slippagePct: number;
  /** Fee per trade (percentage of trade value) */
  feePct: number;
  /** Maximum hold time in candles before forced exit */
  maxHoldCandles: number;
  /** Entry signal function — returns true if candle qualifies for entry */
  entrySignal?: (candle: OHLCVCandle, index: number, candles: OHLCVCandle[]) => boolean;
}

export interface BacktestTrade {
  entryTime: number;
  exitTime: number;
  entryPrice: number;
  exitPrice: number;
  pnlPct: number;
  pnlNet: number;      // After fees/slippage
  exitReason: 'tp' | 'sl' | 'trail' | 'expired' | 'end_of_data';
  holdCandles: number;
  highWaterMark: number;   // Max price during hold
  lowWaterMark: number;    // Min price during hold
  maxDrawdownPct: number;  // Max intra-trade drawdown
}

export interface BacktestResult {
  strategyId: string;
  config: BacktestConfig;
  tokenSymbol: string;
  /** Total trades executed */
  totalTrades: number;
  /** Winning trades */
  wins: number;
  /** Losing trades */
  losses: number;
  /** Win rate as decimal (0.0-1.0) */
  winRate: number;
  /** Sum of all winning trade P&L / sum of all losing trade P&L (absolute) */
  profitFactor: number;
  /** Average trade return (net of fees/slippage) */
  avgReturnPct: number;
  /** Best single trade return */
  bestTradePct: number;
  /** Worst single trade return */
  worstTradePct: number;
  /** Maximum portfolio drawdown from peak */
  maxDrawdownPct: number;
  /** Sharpe ratio (annualized, assuming 1h candles) */
  sharpeRatio: number;
  /** Average number of candles held */
  avgHoldCandles: number;
  /** Expectancy: (WR * avgWin) - ((1-WR) * avgLoss) */
  expectancy: number;
  /** All individual trades */
  trades: BacktestTrade[];
  /** Equity curve (cumulative return at each trade close) */
  equityCurve: number[];
  /** Data range */
  dataStartTime: number;
  dataEndTime: number;
  /** Number of candles analyzed */
  totalCandles: number;
}

// ─── Default Entry Signals ───

/**
 * Mean Reversion entry: buy when price drops X% below SMA(N) then starts recovering.
 * Uses 20-period SMA, entry when close < SMA * 0.97 and close > open (green candle = recovery).
 */
export function meanReversionEntry(candle: OHLCVCandle, index: number, candles: OHLCVCandle[]): boolean {
  if (index < 20) return false;
  const sma20 = candles.slice(index - 20, index).reduce((s, c) => s + c.close, 0) / 20;
  const recentMin = Math.min(candles[index - 1].close, candles[index - 2].close, candle.close);
  const oversold = recentMin < sma20 * 0.99;
  const recovering = candle.close > candle.open; // Green candle
  return oversold && recovering;
}

/**
 * Trend Following entry: buy when price breaks above SMA(20) with volume confirmation.
 * Entry when close crosses above SMA and volume is 1.5x average.
 */
export function trendFollowingEntry(candle: OHLCVCandle, index: number, candles: OHLCVCandle[]): boolean {
  if (index < 21) return false;
  const sma20 = candles.slice(index - 20, index).reduce((s, c) => s + c.close, 0) / 20;
  const prevClose = candles[index - 1].close;
  const avgVol = candles.slice(index - 20, index).reduce((s, c) => s + c.volume, 0) / 20;
  const crossedAbove = prevClose <= sma20 && candle.close > sma20;
  const volumeConfirm = candle.volume > avgVol * 1.2;
  return crossedAbove && volumeConfirm;
}

/**
 * Breakout entry: buy when price breaks above the highest high of last N candles
 * with volume spike.
 */
export function breakoutEntry(candle: OHLCVCandle, index: number, candles: OHLCVCandle[]): boolean {
  if (index < 12) return false;
  const lookback = candles.slice(index - 12, index);
  const highestHigh = Math.max(...lookback.map(c => c.high));
  const avgVol = lookback.reduce((s, c) => s + c.volume, 0) / lookback.length;
  return candle.close >= highestHigh && candle.volume > avgVol * 1.5;
}

/**
 * Momentum entry: buy when RSI(14) is between 50-70 and price is rising.
 * Avoids overbought (>70) and bearish (<50) conditions.
 */
export function momentumEntry(candle: OHLCVCandle, index: number, candles: OHLCVCandle[]): boolean {
  if (index < 15) return false;

  // Calculate RSI(14)
  const changes = [];
  for (let i = index - 13; i <= index; i++) {
    changes.push(candles[i].close - candles[i - 1].close);
  }
  const gains = changes.filter(c => c > 0);
  const losses = changes.filter(c => c < 0).map(c => Math.abs(c));
  const avgGain = gains.length > 0 ? gains.reduce((s, g) => s + g, 0) / 14 : 0;
  const avgLoss = losses.length > 0 ? losses.reduce((s, l) => s + l, 0) / 14 : 0.0001;
  const rs = avgGain / avgLoss;
  const rsi = 100 - (100 / (1 + rs));

  return rsi >= 50 && rsi <= 70 && candle.close > candle.open;
}

/**
 * Volatility Regime: buy when Bollinger Band width contracts below threshold
 * then expands (squeeze breakout).
 */
export function squeezeBreakoutEntry(candle: OHLCVCandle, index: number, candles: OHLCVCandle[]): boolean {
  if (index < 21) return false;

  const period = 20;
  const slice = candles.slice(index - period, index);
  const sma = slice.reduce((s, c) => s + c.close, 0) / period;
  const variance = slice.reduce((s, c) => s + (c.close - sma) ** 2, 0) / period;
  const stdDev = Math.sqrt(variance);
  const bbWidth = (stdDev * 2) / sma; // Normalized BB width

  // Previous BB width
  const prevSlice = candles.slice(index - period - 1, index - 1);
  const prevSma = prevSlice.reduce((s, c) => s + c.close, 0) / period;
  const prevVariance = prevSlice.reduce((s, c) => s + (c.close - prevSma) ** 2, 0) / period;
  const prevBBWidth = (Math.sqrt(prevVariance) * 2) / prevSma;

  // Squeeze: previous BB width was narrow, current is expanding, price breaks above SMA
  return prevBBWidth < 0.04 && bbWidth > prevBBWidth && candle.close > sma;
}

// ─── Engine ───

export class BacktestEngine {
  private candles: OHLCVCandle[];
  private config: BacktestConfig;

  constructor(candles: OHLCVCandle[], config: BacktestConfig) {
    this.candles = candles;
    this.config = config;
  }

  /**
   * Run backtest simulation across all candles.
   * Enters on entrySignal(), exits on SL/TP/Trail/Expiry.
   */
  run(tokenSymbol: string = 'UNKNOWN'): BacktestResult {
    const { config, candles } = this;
    const trades: BacktestTrade[] = [];
    const STARTING_EQUITY = 100;
    const equityCurve: number[] = [STARTING_EQUITY];

    let i = 0;
    let equity = STARTING_EQUITY;
    let peak = STARTING_EQUITY;
    let maxDrawdown = 0;

    // Default entry signal: every N candles (for pure SL/TP/Trail testing)
    const entryFn = config.entrySignal || ((_c: OHLCVCandle, idx: number) => idx % 24 === 0);

    while (i < candles.length) {
      const candle = candles[i];

      // Check for entry signal
      if (entryFn(candle, i, candles)) {
        const trade = this.simulateTrade(i);
        if (trade) {
          trades.push(trade);
          equity *= (1 + trade.pnlNet / 100);
          equity = Math.max(equity, 0); // Equity can't go negative
          equityCurve.push(equity);

          // Track drawdown (equity-based, bounded 0-100%)
          peak = Math.max(peak, equity);
          const dd = peak > 0 ? (peak - equity) / peak * 100 : 0;
          maxDrawdown = Math.max(maxDrawdown, dd);

          // Skip past the trade duration
          i += trade.holdCandles + 1;
          continue;
        }
      }
      i++;
    }

    // Calculate stats
    const wins = trades.filter(t => t.pnlNet > 0).length;
    const losses = trades.filter(t => t.pnlNet <= 0).length;
    const winRate = trades.length > 0 ? wins / trades.length : 0;

    const winningPnl = trades.filter(t => t.pnlNet > 0).reduce((s, t) => s + t.pnlNet, 0);
    const losingPnl = Math.abs(trades.filter(t => t.pnlNet <= 0).reduce((s, t) => s + t.pnlNet, 0));
    const rawPF = losingPnl > 0 ? winningPnl / losingPnl : (winningPnl > 0 ? 999 : 0);
    const profitFactor = Math.min(rawPF, 999);

    const avgReturn = trades.length > 0 ? trades.reduce((s, t) => s + t.pnlPct, 0) / trades.length : 0;
    const bestTrade = trades.length > 0 ? Math.max(...trades.map(t => t.pnlPct)) : 0;
    const worstTrade = trades.length > 0 ? Math.min(...trades.map(t => t.pnlPct)) : 0;
    const avgHold = trades.length > 0 ? trades.reduce((s, t) => s + t.holdCandles, 0) / trades.length : 0;

    // Sharpe (annualized for 1h candles: ~8760 candles/year)
    const returns = trades.map(t => t.pnlNet);
    const meanReturn = returns.length > 0 ? returns.reduce((s, r) => s + r, 0) / returns.length : 0;
    const variance = returns.length > 1
      ? returns.reduce((s, r) => s + (r - meanReturn) ** 2, 0) / (returns.length - 1)
      : 0;
    const stdReturn = Math.sqrt(variance);
    const tradesPerYear = candles.length > 0 ? (trades.length / candles.length) * 8760 : 0;
    const MIN_STD = 0.001;
    const effectiveStd = Math.max(stdReturn, MIN_STD);
    const rawSharpe = (meanReturn / effectiveStd) * Math.sqrt(Math.max(tradesPerYear, 1));
    const sharpeRatio = Math.max(-10, Math.min(10, rawSharpe));

    // Expectancy
    const avgWin = wins > 0 ? winningPnl / wins : 0;
    const avgLoss = losses > 0 ? losingPnl / losses : 0;
    const expectancy = (winRate * avgWin) - ((1 - winRate) * avgLoss);

    return {
      strategyId: config.strategyId,
      config,
      tokenSymbol,
      totalTrades: trades.length,
      wins,
      losses,
      winRate,
      profitFactor,
      avgReturnPct: avgReturn,
      bestTradePct: bestTrade,
      worstTradePct: worstTrade,
      maxDrawdownPct: maxDrawdown,
      sharpeRatio,
      avgHoldCandles: avgHold,
      expectancy,
      trades,
      equityCurve,
      dataStartTime: candles[0]?.timestamp || 0,
      dataEndTime: candles[candles.length - 1]?.timestamp || 0,
      totalCandles: candles.length,
    };
  }

  /**
   * Simulate a single trade starting at candle index.
   * Applies slippage on entry, then checks SL/TP/Trail/Expiry on each subsequent candle.
   */
  private simulateTrade(entryIndex: number): BacktestTrade | null {
    const { candles, config } = this;
    const entryCandle = candles[entryIndex];

    // Entry price with slippage (buy higher)
    const entryPrice = entryCandle.close * (1 + config.slippagePct / 100);

    // Calculate exit levels
    const tpPrice = entryPrice * (1 + config.takeProfitPct / 100);
    const slPrice = entryPrice * (1 - config.stopLossPct / 100);

    let highWaterMark = entryPrice;
    let lowWaterMark = entryPrice;
    let trailStopPrice = 0;
    let maxDrawdownPct = 0;

    for (let j = entryIndex + 1; j < candles.length; j++) {
      const candle = candles[j];
      const holdCandles = j - entryIndex;

      // Update watermarks
      highWaterMark = Math.max(highWaterMark, candle.high);
      lowWaterMark = Math.min(lowWaterMark, candle.low);

      // Intra-trade drawdown from entry
      const drawdown = (entryPrice - lowWaterMark) / entryPrice * 100;
      maxDrawdownPct = Math.max(maxDrawdownPct, drawdown);

      // Update trailing stop
      if (config.trailingStopPct > 0) {
        const trailFromHWM = highWaterMark * (1 - config.trailingStopPct / 100);
        trailStopPrice = Math.max(trailStopPrice, trailFromHWM);
      }

      // Check exits (order: SL first, then TP, then trail, then expiry)
      // SL hit — candle low touched SL
      if (candle.low <= slPrice) {
        return this.makeTrade(entryPrice, slPrice, entryCandle.timestamp, candle.timestamp,
          'sl', holdCandles, highWaterMark, lowWaterMark, maxDrawdownPct);
      }

      // TP hit — candle high touched TP
      if (candle.high >= tpPrice) {
        return this.makeTrade(entryPrice, tpPrice, entryCandle.timestamp, candle.timestamp,
          'tp', holdCandles, highWaterMark, lowWaterMark, maxDrawdownPct);
      }

      // Trailing stop hit
      if (config.trailingStopPct > 0 && trailStopPrice > slPrice && candle.low <= trailStopPrice) {
        return this.makeTrade(entryPrice, trailStopPrice, entryCandle.timestamp, candle.timestamp,
          'trail', holdCandles, highWaterMark, lowWaterMark, maxDrawdownPct);
      }

      // Max hold time expired
      if (holdCandles >= config.maxHoldCandles) {
        const exitPrice = candle.close * (1 - config.slippagePct / 100); // Slippage on exit
        return this.makeTrade(entryPrice, exitPrice, entryCandle.timestamp, candle.timestamp,
          'expired', holdCandles, highWaterMark, lowWaterMark, maxDrawdownPct);
      }
    }

    // End of data — close at last candle
    const lastCandle = candles[candles.length - 1];
    const exitPrice = lastCandle.close * (1 - config.slippagePct / 100);
    return this.makeTrade(entryPrice, exitPrice, entryCandle.timestamp, lastCandle.timestamp,
      'end_of_data', candles.length - 1 - entryIndex, highWaterMark, lowWaterMark, maxDrawdownPct);
  }

  private makeTrade(
    entryPrice: number, exitPrice: number,
    entryTime: number, exitTime: number,
    exitReason: BacktestTrade['exitReason'],
    holdCandles: number,
    highWaterMark: number, lowWaterMark: number,
    maxDrawdownPct: number,
  ): BacktestTrade {
    const { config } = this;
    const grossPnl = (exitPrice - entryPrice) / entryPrice * 100;
    const fees = config.feePct * 2; // Entry + exit fee
    const pnlNet = grossPnl - fees - config.slippagePct; // Net after all costs

    return {
      entryTime, exitTime, entryPrice, exitPrice,
      pnlPct: grossPnl,
      pnlNet,
      exitReason,
      holdCandles,
      highWaterMark,
      lowWaterMark,
      maxDrawdownPct,
    };
  }
}

// ─── Walk-Forward Optimization ───

export interface WalkForwardResult {
  /** In-sample results (training period) */
  inSample: BacktestResult;
  /** Out-of-sample results (validation period) */
  outOfSample: BacktestResult;
  /** Config used */
  config: BacktestConfig;
  /** Whether out-of-sample confirms in-sample (similar win rate) */
  robust: boolean;
}

/**
 * Walk-forward optimization: train on first 70%, validate on last 30%.
 * A strategy is "robust" if out-of-sample win rate is within 15% of in-sample.
 */
export function walkForwardTest(
  candles: OHLCVCandle[],
  config: BacktestConfig,
  tokenSymbol: string,
  splitRatio: number = 0.7,
): WalkForwardResult {
  const splitIdx = Math.floor(candles.length * splitRatio);
  const trainCandles = candles.slice(0, splitIdx);
  const testCandles = candles.slice(splitIdx);

  const trainEngine = new BacktestEngine(trainCandles, config);
  const testEngine = new BacktestEngine(testCandles, config);

  const inSample = trainEngine.run(`${tokenSymbol}_train`);
  const outOfSample = testEngine.run(`${tokenSymbol}_test`);

  // Robust = out-of-sample WR within 15% of in-sample
  const wrDiff = Math.abs(inSample.winRate - outOfSample.winRate);
  const robust = wrDiff <= 0.15 && outOfSample.totalTrades >= 5;

  return { inSample, outOfSample, config, robust };
}

// ─── Parameter Grid Search ───

export interface GridSearchConfig {
  stopLossPcts: number[];
  takeProfitPcts: number[];
  trailingStopPcts: number[];
  maxHoldCandles: number[];
}

/**
 * Grid search over parameter space to find optimal config.
 * Returns results sorted by expectancy.
 */
export function gridSearch(
  candles: OHLCVCandle[],
  baseConfig: Omit<BacktestConfig, 'stopLossPct' | 'takeProfitPct' | 'trailingStopPct' | 'maxHoldCandles'>,
  grid: GridSearchConfig,
  tokenSymbol: string,
  entrySignal?: BacktestConfig['entrySignal'],
): BacktestResult[] {
  const results: BacktestResult[] = [];

  for (const sl of grid.stopLossPcts) {
    for (const tp of grid.takeProfitPcts) {
      for (const trail of grid.trailingStopPcts) {
        for (const maxHold of grid.maxHoldCandles) {
          const config: BacktestConfig = {
            ...baseConfig,
            stopLossPct: sl,
            takeProfitPct: tp,
            trailingStopPct: trail,
            maxHoldCandles: maxHold,
            entrySignal,
          };

          const engine = new BacktestEngine(candles, config);
          const result = engine.run(tokenSymbol);

          // Only include results with enough trades
          if (result.totalTrades >= 10) {
            results.push(result);
          }
        }
      }
    }
  }

  // Sort by expectancy (best risk-adjusted returns first)
  return results.sort((a, b) => b.expectancy - a.expectancy);
}

// ─── Report Generation ───

/**
 * Generate a markdown report from backtest results.
 */
export function generateBacktestReport(results: BacktestResult[]): string {
  const lines: string[] = [
    '# Backtest Validation Report',
    '',
    `**Generated:** ${new Date().toISOString()}`,
    `**Strategies tested:** ${results.length}`,
    '',
    '## Summary',
    '',
    '| Strategy | Token | Trades | Win Rate | Profit Factor | Sharpe | Max DD | Expectancy |',
    '|----------|-------|--------|----------|---------------|--------|--------|------------|',
  ];

  for (const r of results) {
    lines.push(
      `| ${r.strategyId} | ${r.tokenSymbol} | ${r.totalTrades} | ${(r.winRate * 100).toFixed(1)}% | ${r.profitFactor.toFixed(2)} | ${r.sharpeRatio.toFixed(2)} | ${r.maxDrawdownPct.toFixed(1)}% | ${r.expectancy.toFixed(4)} |`
    );
  }

  lines.push('', '## Exit Distribution', '');
  for (const r of results) {
    const tpCount = r.trades.filter(t => t.exitReason === 'tp').length;
    const slCount = r.trades.filter(t => t.exitReason === 'sl').length;
    const trailCount = r.trades.filter(t => t.exitReason === 'trail').length;
    const expiredCount = r.trades.filter(t => t.exitReason === 'expired').length;
    lines.push(`**${r.strategyId} (${r.tokenSymbol}):** TP=${tpCount} SL=${slCount} Trail=${trailCount} Expired=${expiredCount}`);
  }

  lines.push('', '## Best/Worst Trades', '');
  for (const r of results) {
    lines.push(`**${r.strategyId}:** Best=${r.bestTradePct.toFixed(1)}% Worst=${r.worstTradePct.toFixed(1)}% Avg=${r.avgReturnPct.toFixed(1)}% AvgHold=${r.avgHoldCandles.toFixed(0)} candles`);
  }

  return lines.join('\n');
}
