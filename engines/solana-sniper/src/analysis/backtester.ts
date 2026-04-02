import axios from 'axios';
import { createModuleLogger } from '../utils/logger.js';
import { getDb } from '../utils/database.js';
import { SAFETY_PASS_THRESHOLD } from '../config/constants.js';

const log = createModuleLogger('backtester');

// ─── Historical data types ───────────────────────────────────
interface HistoricalToken {
  mint: string;
  symbol: string;
  launchPrice: number;
  peakPrice: number;
  price1h: number;
  price4h: number;
  price24h: number;
  liquidityAtLaunch: number;
  volumeFirst1h: number;
  wasRug: boolean;
  holderCountAtLaunch: number;
  marketCapAtLaunch: number;
}

interface BacktestConfig {
  startDate: string;
  endDate: string;
  initialCapitalUsd: number;
  maxPositionUsd: number;
  stopLossPct: number;
  takeProfitPct: number;
  minSafetyScore: number;
  minLiquidityUsd: number;
  maxConcurrentPositions: number;
  entryDelaySec: number; // seconds after launch to enter
}

interface BacktestResult {
  config: BacktestConfig;
  totalTrades: number;
  wins: number;
  losses: number;
  winRate: number;
  totalPnlUsd: number;
  totalPnlPct: number;
  maxDrawdownPct: number;
  sharpeRatio: number;
  avgWinPct: number;
  avgLossPct: number;
  profitFactor: number;
  bestTradeUsd: number;
  worstTradeUsd: number;
  avgHoldTimeSec: number;
  rugsAvoided: number;
  rugsHit: number;
  trades: BacktestTrade[];
}

interface BacktestTrade {
  mint: string;
  symbol: string;
  entryPrice: number;
  exitPrice: number;
  pnlPct: number;
  pnlUsd: number;
  exitReason: 'TAKE_PROFIT' | 'STOP_LOSS' | 'TIME_EXIT' | 'RUG';
  holdTimeSec: number;
}

// ─── Fetch historical data from DexScreener ──────────────────
async function fetchHistoricalTokens(limit: number = 100): Promise<HistoricalToken[]> {
  const tokens: HistoricalToken[] = [];

  try {
    // Fetch recently created pairs on Solana
    const resp = await axios.get(
      'https://api.dexscreener.com/token-profiles/latest/v1',
      { timeout: 10000 }
    );

    const profiles = (resp.data ?? []).slice(0, limit);

    for (const profile of profiles) {
      if (profile.chainId !== 'solana') continue;

      try {
        const pairResp = await axios.get(
          `https://api.dexscreener.com/latest/dex/tokens/${profile.tokenAddress}`,
          { timeout: 5000 }
        );

        const pair = pairResp.data?.pairs?.[0];
        if (!pair) continue;

        const priceUsd = parseFloat(pair.priceUsd ?? '0');
        const h1Change = pair.priceChange?.h1 ?? 0;
        const h24Change = pair.priceChange?.h24 ?? 0;
        const liquidity = parseFloat(pair.liquidity?.usd ?? '0');
        const volume = parseFloat(pair.volume?.h24 ?? '0');

        // Estimate launch price from price changes
        const launchPrice = priceUsd / (1 + (h24Change / 100));
        const peakPrice = priceUsd * (1 + Math.max(h1Change, h24Change) / 100);

        tokens.push({
          mint: profile.tokenAddress,
          symbol: pair.baseToken?.symbol ?? 'UNKNOWN',
          launchPrice: Math.max(0.0000001, launchPrice),
          peakPrice: Math.max(priceUsd, peakPrice),
          price1h: priceUsd / (1 + (h1Change / 100)),
          price4h: priceUsd,
          price24h: priceUsd,
          liquidityAtLaunch: liquidity * 0.3, // estimate
          volumeFirst1h: volume * 0.2, // estimate
          wasRug: h24Change < -90 || liquidity < 1000,
          holderCountAtLaunch: 20, // estimate
          marketCapAtLaunch: parseFloat(pair.fdv ?? '0') * 0.1,
        });
      } catch {
        continue;
      }
    }
  } catch (err) {
    log.error('Failed to fetch historical data', { error: (err as Error).message });
  }

  log.info('Fetched historical tokens', { count: tokens.length });
  return tokens;
}

// ─── Run backtest ────────────────────────────────────────────
export async function runBacktest(overrides?: Partial<BacktestConfig>): Promise<BacktestResult> {
  const cfg: BacktestConfig = {
    startDate: '2025-01-01',
    endDate: '2026-02-08',
    initialCapitalUsd: 50,
    maxPositionUsd: 2.50,
    stopLossPct: 30,
    takeProfitPct: 100,
    minSafetyScore: SAFETY_PASS_THRESHOLD,
    minLiquidityUsd: 10000,
    maxConcurrentPositions: 3,
    entryDelaySec: 30,
    ...overrides,
  };

  log.info('Starting backtest', cfg);

  const historicalTokens = await fetchHistoricalTokens(200);
  const trades: BacktestTrade[] = [];
  let capital = cfg.initialCapitalUsd;
  let peakCapital = capital;
  let maxDrawdown = 0;
  let openPositions = 0;
  const dailyReturns: number[] = [];

  for (const token of historicalTokens) {
    // Skip if max positions reached
    if (openPositions >= cfg.maxConcurrentPositions) continue;

    // Skip rugs that our safety pipeline would catch
    const wouldPassSafety = simulateSafetyCheck(token, cfg);
    if (!wouldPassSafety) {
      if (token.wasRug) {
        // Good — we avoided a rug
      }
      continue;
    }

    // If it was actually a rug and we didn't catch it
    if (token.wasRug) {
      const pnlPct = -90; // Assume 90% loss on rug
      const pnlUsd = cfg.maxPositionUsd * (pnlPct / 100);
      capital += pnlUsd;

      trades.push({
        mint: token.mint,
        symbol: token.symbol,
        entryPrice: token.launchPrice,
        exitPrice: token.launchPrice * 0.1,
        pnlPct,
        pnlUsd,
        exitReason: 'RUG',
        holdTimeSec: 300,
      });

      continue;
    }

    // Simulate trade execution
    openPositions++;
    const entryPrice = token.launchPrice * 1.05; // 5% slippage on entry

    // Determine exit based on price action
    let exitPrice: number;
    let exitReason: BacktestTrade['exitReason'];
    let holdTimeSec: number;

    const maxGain = ((token.peakPrice - entryPrice) / entryPrice) * 100;
    const loss1h = ((token.price1h - entryPrice) / entryPrice) * 100;

    if (maxGain >= cfg.takeProfitPct) {
      // Take profit hit
      exitPrice = entryPrice * (1 + cfg.takeProfitPct / 100) * 0.97; // 3% slippage
      exitReason = 'TAKE_PROFIT';
      holdTimeSec = 3600; // estimate 1h
    } else if (loss1h <= -cfg.stopLossPct) {
      // Stop loss hit
      exitPrice = entryPrice * (1 - cfg.stopLossPct / 100) * 0.97;
      exitReason = 'STOP_LOSS';
      holdTimeSec = 1800;
    } else {
      // Time-based exit at 4h
      exitPrice = token.price4h * 0.98;
      exitReason = 'TIME_EXIT';
      holdTimeSec = 14400;
    }

    const pnlPct = ((exitPrice - entryPrice) / entryPrice) * 100;
    const pnlUsd = cfg.maxPositionUsd * (pnlPct / 100);
    capital += pnlUsd;
    openPositions--;

    // Track drawdown
    peakCapital = Math.max(peakCapital, capital);
    const drawdown = ((peakCapital - capital) / peakCapital) * 100;
    maxDrawdown = Math.max(maxDrawdown, drawdown);

    dailyReturns.push(pnlPct);

    trades.push({
      mint: token.mint,
      symbol: token.symbol,
      entryPrice,
      exitPrice,
      pnlPct,
      pnlUsd,
      exitReason,
      holdTimeSec,
    });
  }

  // Calculate statistics
  const wins = trades.filter(t => t.pnlUsd > 0);
  const losses = trades.filter(t => t.pnlUsd <= 0);
  const rugsAvoided = historicalTokens.filter(t => t.wasRug && !simulateSafetyCheck(t, cfg)).length;
  const rugsHit = trades.filter(t => t.exitReason === 'RUG').length;

  const avgReturn = dailyReturns.length > 0 ? dailyReturns.reduce((a, b) => a + b, 0) / dailyReturns.length : 0;
  const stdDev = dailyReturns.length > 1
    ? Math.sqrt(dailyReturns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / (dailyReturns.length - 1))
    : 1;
  const sharpe = stdDev > 0 ? avgReturn / stdDev : 0;

  const grossProfit = wins.reduce((s, t) => s + t.pnlUsd, 0);
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.pnlUsd, 0));

  const result: BacktestResult = {
    config: cfg,
    totalTrades: trades.length,
    wins: wins.length,
    losses: losses.length,
    winRate: trades.length > 0 ? wins.length / trades.length : 0,
    totalPnlUsd: capital - cfg.initialCapitalUsd,
    totalPnlPct: ((capital - cfg.initialCapitalUsd) / cfg.initialCapitalUsd) * 100,
    maxDrawdownPct: maxDrawdown,
    sharpeRatio: sharpe,
    avgWinPct: wins.length > 0 ? wins.reduce((s, t) => s + t.pnlPct, 0) / wins.length : 0,
    avgLossPct: losses.length > 0 ? losses.reduce((s, t) => s + t.pnlPct, 0) / losses.length : 0,
    profitFactor: grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? Infinity : 0,
    bestTradeUsd: trades.length > 0 ? Math.max(...trades.map(t => t.pnlUsd)) : 0,
    worstTradeUsd: trades.length > 0 ? Math.min(...trades.map(t => t.pnlUsd)) : 0,
    avgHoldTimeSec: trades.length > 0 ? trades.reduce((s, t) => s + t.holdTimeSec, 0) / trades.length : 0,
    rugsAvoided,
    rugsHit,
    trades,
  };

  log.info('Backtest complete', {
    trades: result.totalTrades,
    winRate: (result.winRate * 100).toFixed(1) + '%',
    pnl: '$' + result.totalPnlUsd.toFixed(2),
    maxDrawdown: result.maxDrawdownPct.toFixed(1) + '%',
    sharpe: result.sharpeRatio.toFixed(2),
    rugsAvoided,
    rugsHit,
  });

  // Store results in DB
  storeBacktestResults(result);

  return result;
}

function simulateSafetyCheck(token: HistoricalToken, cfg: BacktestConfig): boolean {
  // Simulate our safety pipeline's decision
  let score = 0;

  // Higher liquidity = safer
  if (token.liquidityAtLaunch >= cfg.minLiquidityUsd) score += 0.3;
  else return false;

  // More holders = safer
  if (token.holderCountAtLaunch >= 20) score += 0.2;

  // Volume indicates real interest
  if (token.volumeFirst1h > 5000) score += 0.2;

  // Market cap sanity
  if (token.marketCapAtLaunch > 1000 && token.marketCapAtLaunch < 10_000_000) score += 0.15;

  // Not already pumped too much
  if (token.peakPrice / token.launchPrice < 50) score += 0.15;

  return score >= cfg.minSafetyScore;
}

function storeBacktestResults(result: BacktestResult): void {
  try {
    const db = getDb();
    db.prepare(`
      INSERT OR REPLACE INTO strategy_performance
      (strategy, signal_source, trades_count, win_rate, avg_pnl_pct, total_pnl_usd, sharpe_ratio, max_drawdown_pct, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      `backtest_sl${result.config.stopLossPct}_tp${result.config.takeProfitPct}`,
      'historical',
      result.totalTrades,
      result.winRate,
      result.totalPnlPct / Math.max(1, result.totalTrades),
      result.totalPnlUsd,
      result.sharpeRatio,
      result.maxDrawdownPct,
      Date.now(),
    );
  } catch (err) {
    log.warn('Failed to store backtest results', { error: (err as Error).message });
  }
}

// ─── Strategy optimizer (self-improving) ─────────────────────
export async function optimizeStrategy(): Promise<{
  bestConfig: Partial<BacktestConfig>;
  bestWinRate: number;
  bestPnl: number;
  iterations: number;
}> {
  log.info('Starting strategy optimization...');

  const paramGrid = {
    stopLossPct: [20, 25, 30, 35, 40, 50],
    takeProfitPct: [50, 75, 100, 150, 200, 300],
    minSafetyScore: [0.5, 0.6, 0.7, 0.8],
    minLiquidityUsd: [5000, 10000, 25000, 50000],
    maxConcurrentPositions: [2, 3, 5],
    maxPositionUsd: [1, 2, 2.5, 3, 5],
  };

  let bestResult: BacktestResult | null = null;
  let bestConfig: Partial<BacktestConfig> = {};
  let iterations = 0;

  // Grid search over key parameters
  for (const sl of paramGrid.stopLossPct) {
    for (const tp of paramGrid.takeProfitPct) {
      for (const safety of paramGrid.minSafetyScore) {
        // Skip invalid combos
        if (tp <= sl) continue;

        iterations++;
        const result = await runBacktest({
          stopLossPct: sl,
          takeProfitPct: tp,
          minSafetyScore: safety,
        });

        // Score: weighted combination of win rate, PnL, and drawdown
        const score = result.winRate * 0.4 +
                     (result.totalPnlPct / 100) * 0.3 +
                     (1 - result.maxDrawdownPct / 100) * 0.3;

        if (!bestResult || score > (bestResult.winRate * 0.4 + (bestResult.totalPnlPct / 100) * 0.3 + (1 - bestResult.maxDrawdownPct / 100) * 0.3)) {
          bestResult = result;
          bestConfig = { stopLossPct: sl, takeProfitPct: tp, minSafetyScore: safety };
        }
      }
    }
  }

  log.info('Strategy optimization complete', {
    iterations,
    bestWinRate: ((bestResult?.winRate ?? 0) * 100).toFixed(1) + '%',
    bestPnl: '$' + (bestResult?.totalPnlUsd ?? 0).toFixed(2),
    bestConfig,
  });

  return {
    bestConfig,
    bestWinRate: bestResult?.winRate ?? 0,
    bestPnl: bestResult?.totalPnlUsd ?? 0,
    iterations,
  };
}
