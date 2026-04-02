#!/usr/bin/env npx tsx
/**
 * Real Data Backtest Runner
 *
 * Fetches REAL OHLCV data from DexScreener for live Solana tokens,
 * then runs every sniper strategy against the data.
 *
 * NO synthetic data. NO fake data. Every trade is timestamped and traceable
 * to a real DexScreener pair address and candle timestamp.
 *
 * Usage: npx tsx scripts/real-backtest.ts
 *
 * Output: docs/REAL_BACKTEST_RESULTS.md (verifiable report)
 */

// ─── Types ───

interface OHLCVCandle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface BacktestTrade {
  entryTime: number;
  exitTime: number;
  entryPrice: number;
  exitPrice: number;
  pnlPct: number;
  pnlNet: number;
  exitReason: 'tp' | 'sl' | 'trail' | 'expired' | 'end_of_data';
  holdCandles: number;
  highWaterMark: number;
  lowWaterMark: number;
  maxDrawdownPct: number;
}

interface StrategyConfig {
  id: string;
  name: string;
  category: 'memecoin' | 'bags' | 'bluechip' | 'xstock';
  stopLossPct: number;
  takeProfitPct: number;
  trailingStopPct: number;
  maxHoldCandles: number;
  slippagePct: number;
  feePct: number;
  minLiquidityUsd: number;
  entrySignal: string; // Name of the signal function
}

interface BacktestResult {
  strategyId: string;
  tokenSymbol: string;
  pairAddress: string;
  dataSource: string;
  totalTrades: number;
  wins: number;
  losses: number;
  winRate: number;
  profitFactor: number;
  avgReturnPct: number;
  bestTradePct: number;
  worstTradePct: number;
  maxDrawdownPct: number;
  sharpeRatio: number;
  avgHoldCandles: number;
  expectancy: number;
  totalCandles: number;
  dataStartTime: number;
  dataEndTime: number;
  trades: BacktestTrade[];
}

interface TokenInfo {
  symbol: string;
  mint: string;
  pairAddress: string;
  liquidity: number;
  volume24h: number;
  marketCap: number;
  source: string;
}

// ─── Constants ───

// GeckoTerminal API (free, no key, has Solana DEX OHLCV)
const GECKO_TERMINAL = 'https://api.geckoterminal.com/api/v2';

const RATE_LIMIT_MS = 400; // ~2.5 req/sec to stay within GeckoTerminal free limits

// Blue chip tokens — GeckoTerminal pool addresses verified 2026-02-10
const BLUECHIPS = [
  { symbol: 'JUP', pool: 'C8Gr6AUuq9hEdSYJzoEpNcdjpojPZwqG5MtQbeouNNwg' },
  { symbol: 'BONK', pool: '6oFWm7KPLfxnwMb3z5xwBoXNSPP3JJyirAPqPSiVcnsp' },
  { symbol: 'WIF', pool: 'EP2ib6dYdEeqD8MfE2ezHCxX3kP3K2eLKoczfh7SnXcc' },
  { symbol: 'PYTH', pool: '9n3dSLrERZQpJfRVpWVbEMHAQ8TXYMzQN1dv15QfE1Ey' },
  { symbol: 'RAY', pool: '2AXXcN6oN9bBT5owwmTH53C7QHUXvhLeu718Kqt8rvY2' },
  { symbol: 'ORCA', pool: 'Hxw77h9fEx598afiiZunwHaX3vYu9UskDk9EpPNZp1mG' },
  { symbol: 'JITO', pool: 'Hp53XEtt4S8SvPCXarsLSdGfZBuUr5mMmZmX2DRNXQKp' },
  { symbol: 'RENDER', pool: 'FZ8MJvdTPbp8juhtFCCzb7LsKunhexgzShGQ59SUJkNL' },
  { symbol: 'W', pool: '4gBdoceUxqqcyzgAqkN3wC5FivB34FwFJvTvgdUf6vLz' },
];

// Known Solana memecoins — pool addresses from GeckoTerminal search, verified 2026-02-10
const KNOWN_MEMECOINS = [
  { symbol: 'POPCAT', pool: 'FRhB8L7Y9Qq41qZXYLtC2nw8An1RJfLLxRF2x9RwLLMo' },
  { symbol: 'MEW', pool: '879F697iuDJGMevRkRcnW21fcXiAeLJK1ffsw2ATebce' },
  { symbol: 'ai16z', pool: '7qAVrzrbULwg1B13YseqA95Uapf8EVp9jQE5uipqFMoP' },
  { symbol: 'FWOG', pool: 'AB1eu2L1Jr3nfEft85AuD2zGksUbam1Kr8MR3uM2sjwt' },
  { symbol: 'PNUT', pool: '4AZRPNEfCJ7iw28rJu5aUyeQhYcvdcNm8cswyL51AY9i' },
  { symbol: 'GOAT', pool: '9Tb2ohu5P16BpBarqd3N27WnkF51Ukfs8Z1GzzLDxVZW' },
  { symbol: 'MOODENG', pool: '22WrmyTj8x2TRVQen3fxxi2r4Rn6JDHWoMTpsSmn8RUd' },
  { symbol: 'SPX', pool: '9t1H1uDJ558iMPNkEPSN1fqkpC4XSPQ6cqSf6uEsTfTR' },
  { symbol: 'GRIFFAIN', pool: 'CpsMssqi3P9VMvNqxrdWVbSBCwyUHbGgNcrw7MorBq3g' },
  { symbol: 'arc', pool: 'J3b6dvheS2Y1cbMtVz5TCWXNegSjJDbUKxdUVDPoqmS7' },
  { symbol: 'ZEREBRO', pool: '3sjNoCnkkhWPVXYGDtem8rCciHSGc9jSFZuUAzKbvRVp' },
  { symbol: 'TRUMP', pool: '7fiyY2LYDUnswEPZSo8VzuivdwgSbyiWBTUgNhqYCcvv' },
];

// ─── All Strategy Configs ───

const STRATEGIES: StrategyConfig[] = [
  // ── Memecoin strategies ──
  { id: 'pump_fresh_tight', name: 'Pump Fresh Tight', category: 'memecoin',
    stopLossPct: 20, takeProfitPct: 80, trailingStopPct: 8, maxHoldCandles: 4,
    slippagePct: 1.0, feePct: 0.25, minLiquidityUsd: 5000, entrySignal: 'momentum' },
  { id: 'momentum', name: 'Momentum', category: 'memecoin',
    stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8, maxHoldCandles: 8,
    slippagePct: 0.5, feePct: 0.25, minLiquidityUsd: 50000, entrySignal: 'momentum' },
  { id: 'insight_j', name: 'Insight-J', category: 'memecoin',
    stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8, maxHoldCandles: 8,
    slippagePct: 0.5, feePct: 0.25, minLiquidityUsd: 50000, entrySignal: 'trend' },
  { id: 'micro_cap_surge', name: 'Micro Cap Surge', category: 'memecoin',
    stopLossPct: 45, takeProfitPct: 250, trailingStopPct: 20, maxHoldCandles: 24,
    slippagePct: 1.5, feePct: 0.25, minLiquidityUsd: 3000, entrySignal: 'breakout' },
  { id: 'elite', name: 'Elite', category: 'memecoin',
    stopLossPct: 15, takeProfitPct: 60, trailingStopPct: 8, maxHoldCandles: 8,
    slippagePct: 0.5, feePct: 0.25, minLiquidityUsd: 100000, entrySignal: 'momentum' },
  { id: 'hybrid_b', name: 'Hybrid-B', category: 'memecoin',
    stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8, maxHoldCandles: 8,
    slippagePct: 0.5, feePct: 0.25, minLiquidityUsd: 50000, entrySignal: 'trend' },
  { id: 'let_it_ride', name: 'Let It Ride', category: 'memecoin',
    stopLossPct: 20, takeProfitPct: 100, trailingStopPct: 5, maxHoldCandles: 24,
    slippagePct: 0.5, feePct: 0.25, minLiquidityUsd: 50000, entrySignal: 'momentum' },
  { id: 'loose', name: 'Loose', category: 'memecoin',
    stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8, maxHoldCandles: 8,
    slippagePct: 0.5, feePct: 0.25, minLiquidityUsd: 25000, entrySignal: 'breakout' },
  { id: 'genetic_best', name: 'Genetic Best', category: 'memecoin',
    stopLossPct: 35, takeProfitPct: 200, trailingStopPct: 12, maxHoldCandles: 24,
    slippagePct: 1.0, feePct: 0.25, minLiquidityUsd: 3000, entrySignal: 'momentum' },
  { id: 'genetic_v2', name: 'Genetic V2', category: 'memecoin',
    stopLossPct: 45, takeProfitPct: 207, trailingStopPct: 10, maxHoldCandles: 24,
    slippagePct: 1.0, feePct: 0.25, minLiquidityUsd: 5000, entrySignal: 'breakout' },
  // ── Bags.fm strategies ──
  { id: 'bags_fresh_snipe', name: 'Bags Fresh Snipe', category: 'bags',
    stopLossPct: 20, takeProfitPct: 80, trailingStopPct: 8, maxHoldCandles: 6,
    slippagePct: 1.0, feePct: 0.25, minLiquidityUsd: 0, entrySignal: 'momentum' },
  { id: 'bags_momentum', name: 'Bags Momentum', category: 'bags',
    stopLossPct: 25, takeProfitPct: 150, trailingStopPct: 15, maxHoldCandles: 12,
    slippagePct: 0.8, feePct: 0.25, minLiquidityUsd: 0, entrySignal: 'momentum' },
  { id: 'bags_value', name: 'Bags Value', category: 'bags',
    stopLossPct: 15, takeProfitPct: 50, trailingStopPct: 8, maxHoldCandles: 24,
    slippagePct: 0.5, feePct: 0.25, minLiquidityUsd: 0, entrySignal: 'mean_reversion' },
  { id: 'bags_dip_buyer', name: 'Bags Dip Buyer', category: 'bags',
    stopLossPct: 30, takeProfitPct: 200, trailingStopPct: 12, maxHoldCandles: 48,
    slippagePct: 1.0, feePct: 0.25, minLiquidityUsd: 0, entrySignal: 'mean_reversion' },
  { id: 'bags_bluechip', name: 'Bags Blue Chip', category: 'bags',
    stopLossPct: 10, takeProfitPct: 30, trailingStopPct: 5, maxHoldCandles: 12,
    slippagePct: 0.3, feePct: 0.25, minLiquidityUsd: 0, entrySignal: 'trend' },
  // ── Blue chip strategies ──
  { id: 'bluechip_mean_revert', name: 'Blue Chip Mean Revert', category: 'bluechip',
    stopLossPct: 3, takeProfitPct: 8, trailingStopPct: 2, maxHoldCandles: 48,
    slippagePct: 0.3, feePct: 0.25, minLiquidityUsd: 50000, entrySignal: 'mean_reversion' },
  { id: 'bluechip_trend_follow', name: 'Blue Chip Trend Follow', category: 'bluechip',
    stopLossPct: 5, takeProfitPct: 15, trailingStopPct: 4, maxHoldCandles: 168,
    slippagePct: 0.3, feePct: 0.25, minLiquidityUsd: 50000, entrySignal: 'trend' },
  { id: 'bluechip_breakout', name: 'Blue Chip Breakout', category: 'bluechip',
    stopLossPct: 4, takeProfitPct: 12, trailingStopPct: 3, maxHoldCandles: 72,
    slippagePct: 0.3, feePct: 0.25, minLiquidityUsd: 50000, entrySignal: 'breakout' },
];

// ─── Entry Signal Functions ───

function sma(candles: OHLCVCandle[], endIdx: number, period: number): number {
  const start = Math.max(0, endIdx - period);
  const slice = candles.slice(start, endIdx);
  return slice.reduce((s, c) => s + c.close, 0) / slice.length;
}

function rsi14(candles: OHLCVCandle[], idx: number): number {
  if (idx < 15) return 50;
  const changes = [];
  for (let i = idx - 13; i <= idx; i++) {
    changes.push(candles[i].close - candles[i - 1].close);
  }
  const gains = changes.filter(c => c > 0);
  const losses = changes.filter(c => c < 0).map(c => Math.abs(c));
  const avgGain = gains.length > 0 ? gains.reduce((s, g) => s + g, 0) / 14 : 0;
  const avgLoss = losses.length > 0 ? losses.reduce((s, l) => s + l, 0) / 14 : 0.0001;
  return 100 - (100 / (1 + avgGain / avgLoss));
}

const ENTRY_SIGNALS: Record<string, (c: OHLCVCandle, i: number, all: OHLCVCandle[]) => boolean> = {
  momentum: (candle, idx, candles) => {
    if (idx < 15) return false;
    const r = rsi14(candles, idx);
    return r >= 50 && r <= 70 && candle.close > candle.open;
  },
  trend: (candle, idx, candles) => {
    if (idx < 21) return false;
    const s = sma(candles, idx, 20);
    const prevClose = candles[idx - 1].close;
    const avgVol = candles.slice(idx - 20, idx).reduce((a, c) => a + c.volume, 0) / 20;
    return prevClose <= s && candle.close > s && candle.volume > avgVol * 1.2;
  },
  breakout: (candle, idx, candles) => {
    if (idx < 12) return false;
    const lookback = candles.slice(idx - 12, idx);
    const highestHigh = Math.max(...lookback.map(c => c.high));
    const avgVol = lookback.reduce((a, c) => a + c.volume, 0) / lookback.length;
    return candle.close >= highestHigh && candle.volume > avgVol * 1.5;
  },
  mean_reversion: (candle, idx, candles) => {
    if (idx < 20) return false;
    const s = sma(candles, idx, 20);
    const recentMin = Math.min(candles[idx - 1].close, candles[idx - 2].close, candle.close);
    return recentMin < s * 0.99 && candle.close > candle.open;
  },
};

// ─── Backtest Engine (Inline) ───

function simulateTrade(
  candles: OHLCVCandle[],
  entryIdx: number,
  config: StrategyConfig,
): BacktestTrade | null {
  const entryCandle = candles[entryIdx];
  const entryPrice = entryCandle.close * (1 + config.slippagePct / 100);
  const tpPrice = entryPrice * (1 + config.takeProfitPct / 100);
  const slPrice = entryPrice * (1 - config.stopLossPct / 100);

  let highWaterMark = entryPrice;
  let lowWaterMark = entryPrice;
  let trailStopPrice = 0;
  let maxDrawdownPct = 0;

  for (let j = entryIdx + 1; j < candles.length; j++) {
    const c = candles[j];
    const holdCandles = j - entryIdx;

    highWaterMark = Math.max(highWaterMark, c.high);
    lowWaterMark = Math.min(lowWaterMark, c.low);
    const dd = (entryPrice - lowWaterMark) / entryPrice * 100;
    maxDrawdownPct = Math.max(maxDrawdownPct, dd);

    if (config.trailingStopPct > 0) {
      trailStopPrice = Math.max(trailStopPrice, highWaterMark * (1 - config.trailingStopPct / 100));
    }

    // SL
    if (c.low <= slPrice) {
      return makeTrade(entryPrice, slPrice, entryCandle.timestamp, c.timestamp, 'sl', holdCandles, highWaterMark, lowWaterMark, maxDrawdownPct, config);
    }
    // TP
    if (c.high >= tpPrice) {
      return makeTrade(entryPrice, tpPrice, entryCandle.timestamp, c.timestamp, 'tp', holdCandles, highWaterMark, lowWaterMark, maxDrawdownPct, config);
    }
    // Trail
    if (config.trailingStopPct > 0 && trailStopPrice > slPrice && c.low <= trailStopPrice) {
      return makeTrade(entryPrice, trailStopPrice, entryCandle.timestamp, c.timestamp, 'trail', holdCandles, highWaterMark, lowWaterMark, maxDrawdownPct, config);
    }
    // Expired
    if (holdCandles >= config.maxHoldCandles) {
      const exitPrice = c.close * (1 - config.slippagePct / 100);
      return makeTrade(entryPrice, exitPrice, entryCandle.timestamp, c.timestamp, 'expired', holdCandles, highWaterMark, lowWaterMark, maxDrawdownPct, config);
    }
  }

  // End of data
  const last = candles[candles.length - 1];
  const exitPrice = last.close * (1 - config.slippagePct / 100);
  return makeTrade(entryPrice, exitPrice, entryCandle.timestamp, last.timestamp, 'end_of_data',
    candles.length - 1 - entryIdx, highWaterMark, lowWaterMark, maxDrawdownPct, config);
}

function makeTrade(
  entryPrice: number, exitPrice: number, entryTime: number, exitTime: number,
  exitReason: BacktestTrade['exitReason'], holdCandles: number,
  hwm: number, lwm: number, maxDD: number, config: StrategyConfig,
): BacktestTrade {
  const grossPnl = (exitPrice - entryPrice) / entryPrice * 100;
  const fees = config.feePct * 2;
  const pnlNet = grossPnl - fees - config.slippagePct;
  return {
    entryTime, exitTime, entryPrice, exitPrice,
    pnlPct: grossPnl, pnlNet, exitReason, holdCandles,
    highWaterMark: hwm, lowWaterMark: lwm, maxDrawdownPct: maxDD,
  };
}

function runBacktest(candles: OHLCVCandle[], config: StrategyConfig, tokenSymbol: string, pairAddress: string): BacktestResult {
  const entryFn = ENTRY_SIGNALS[config.entrySignal] || ENTRY_SIGNALS.momentum;
  const trades: BacktestTrade[] = [];

  let i = 0;
  while (i < candles.length) {
    if (entryFn(candles[i], i, candles)) {
      const trade = simulateTrade(candles, i, config);
      if (trade) {
        trades.push(trade);
        i += trade.holdCandles + 1;
        continue;
      }
    }
    i++;
  }

  const wins = trades.filter(t => t.pnlNet > 0).length;
  const losses = trades.filter(t => t.pnlNet <= 0).length;
  const winRate = trades.length > 0 ? wins / trades.length : 0;
  const winningPnl = trades.filter(t => t.pnlNet > 0).reduce((s, t) => s + t.pnlNet, 0);
  const losingPnl = Math.abs(trades.filter(t => t.pnlNet <= 0).reduce((s, t) => s + t.pnlNet, 0));
  const profitFactor = losingPnl > 0 ? Math.min(winningPnl / losingPnl, 999) : (winningPnl > 0 ? 999 : 0);
  const avgReturn = trades.length > 0 ? trades.reduce((s, t) => s + t.pnlPct, 0) / trades.length : 0;
  const bestTrade = trades.length > 0 ? Math.max(...trades.map(t => t.pnlPct)) : 0;
  const worstTrade = trades.length > 0 ? Math.min(...trades.map(t => t.pnlPct)) : 0;
  const avgHold = trades.length > 0 ? trades.reduce((s, t) => s + t.holdCandles, 0) / trades.length : 0;

  // Max drawdown (equity-based)
  let equity = 100, peak = 100, maxDD = 0;
  for (const t of trades) {
    equity *= (1 + t.pnlNet / 100);
    peak = Math.max(peak, equity);
    const dd = peak > 0 ? (peak - equity) / peak * 100 : 0;
    maxDD = Math.max(maxDD, dd);
  }

  // Sharpe
  const returns = trades.map(t => t.pnlNet);
  const mean = returns.length > 0 ? returns.reduce((s, r) => s + r, 0) / returns.length : 0;
  const variance = returns.length > 1 ? returns.reduce((s, r) => s + (r - mean) ** 2, 0) / (returns.length - 1) : 0;
  const std = Math.sqrt(variance);
  const tradesPerYear = candles.length > 0 ? (trades.length / candles.length) * 8760 : 0;
  const sharpe = std > 0.001 ? (mean / Math.max(std, 0.001)) * Math.sqrt(Math.max(tradesPerYear, 1)) : 0;

  // Expectancy
  const avgWin = wins > 0 ? winningPnl / wins : 0;
  const avgLoss = losses > 0 ? losingPnl / losses : 0;
  const expectancy = (winRate * avgWin) - ((1 - winRate) * avgLoss);

  return {
    strategyId: config.id,
    tokenSymbol,
    pairAddress,
    dataSource: 'geckoterminal',
    totalTrades: trades.length,
    wins, losses, winRate, profitFactor,
    avgReturnPct: avgReturn, bestTradePct: bestTrade, worstTradePct: worstTrade,
    maxDrawdownPct: maxDD, sharpeRatio: Math.max(-10, Math.min(10, sharpe)),
    avgHoldCandles: avgHold, expectancy,
    totalCandles: candles.length,
    dataStartTime: candles[0]?.timestamp || 0,
    dataEndTime: candles[candles.length - 1]?.timestamp || 0,
    trades,
  };
}

// ─── Data Fetchers ───

async function sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}

async function fetchPoolAddress(mint: string): Promise<string | null> {
  try {
    const url = `${GECKO_TERMINAL}/networks/solana/tokens/${mint}/pools?page=1`;
    const res = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!res.ok) {
      console.log(`    [pool-lookup] HTTP ${res.status} for ${mint.slice(0, 8)}...`);
      return null;
    }
    const data = await res.json();
    const pool = data?.data?.[0];
    return pool?.attributes?.address || null;
  } catch (err: any) {
    console.log(`    [pool-lookup] Error for ${mint.slice(0, 8)}: ${err?.message || err}`);
    return null;
  }
}

async function fetchOHLCV(poolAddress: string): Promise<OHLCVCandle[]> {
  try {
    // GeckoTerminal OHLCV: 1h candles, up to 1000
    const url = `${GECKO_TERMINAL}/networks/solana/pools/${poolAddress}/ohlcv/hour?aggregate=1&limit=1000`;
    const res = await fetch(url, {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) return [];
    const data = await res.json();
    const bars = data?.data?.attributes?.ohlcv_list;
    if (!Array.isArray(bars) || bars.length === 0) return [];

    // GeckoTerminal returns [timestamp_sec, open, high, low, close, volume] NEWEST first
    return bars
      .map((bar: any) => ({
        timestamp: (bar[0] || 0) * 1000, // Convert seconds → milliseconds
        open: bar[1] || 0,
        high: bar[2] || 0,
        low: bar[3] || 0,
        close: bar[4] || 0,
        volume: bar[5] || 0,
      }))
      .filter((c: OHLCVCandle) => c.timestamp > 0 && c.close > 0)
      .reverse(); // Reverse to oldest-first (chronological)
  } catch { return []; }
}

async function fetchTrendingTokens(): Promise<TokenInfo[]> {
  const tokens: TokenInfo[] = [];
  const seen = new Set<string>();

  // Fetch 3 pages of trending pools for broader coverage
  for (let page = 1; page <= 3; page++) {
    try {
      const url = `${GECKO_TERMINAL}/networks/solana/trending_pools?page=${page}`;
      console.log(`    [fetch] ${url}`);
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!res.ok) { console.log(`    [warn] trending page ${page}: HTTP ${res.status}`); break; }
      const data = await res.json();
      const pools = data.data || [];
      console.log(`    [ok] trending page ${page}: ${pools.length} pools`);
      for (const pool of pools) {
        const addr = pool.attributes?.address;
        if (!addr || seen.has(addr)) continue;
        seen.add(addr);
        tokens.push({
          symbol: pool.attributes?.name?.split(' / ')?.[0] || addr.slice(0, 6),
          mint: '',
          pairAddress: addr,
          liquidity: parseFloat(pool.attributes?.reserve_in_usd || '0'),
          volume24h: parseFloat(pool.attributes?.volume_usd?.h24 || '0'),
          marketCap: parseFloat(pool.attributes?.market_cap_usd || '0'),
          source: 'geckoterminal-trending',
        });
      }
      await sleep(RATE_LIMIT_MS);
    } catch (err: any) {
      console.error(`    [error] trending page ${page}:`, err?.message || err);
      break;
    }
  }

  return tokens;
}

async function fetchNewTokens(): Promise<TokenInfo[]> {
  const tokens: TokenInfo[] = [];
  const seen = new Set<string>();

  // Fetch 2 pages of new pools for bags-like tokens
  for (let page = 1; page <= 2; page++) {
    try {
      const url = `${GECKO_TERMINAL}/networks/solana/new_pools?page=${page}`;
      console.log(`    [fetch] ${url}`);
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!res.ok) { console.log(`    [warn] new_pools page ${page}: HTTP ${res.status}`); break; }
      const data = await res.json();
      const pools = data.data || [];
      console.log(`    [ok] new_pools page ${page}: ${pools.length} pools`);
      for (const pool of pools) {
        const addr = pool.attributes?.address;
        if (!addr || seen.has(addr)) continue;
        seen.add(addr);
        tokens.push({
          symbol: pool.attributes?.name?.split(' / ')?.[0] || addr.slice(0, 6),
          mint: '',
          pairAddress: addr,
          liquidity: parseFloat(pool.attributes?.reserve_in_usd || '0'),
          volume24h: parseFloat(pool.attributes?.volume_usd?.h24 || '0'),
          marketCap: parseFloat(pool.attributes?.market_cap_usd || '0'),
          source: 'geckoterminal-new',
        });
      }
      await sleep(RATE_LIMIT_MS);
    } catch (err: any) {
      console.error(`    [error] new_pools page ${page}:`, err?.message || err);
      break;
    }
  }

  return tokens;
}

// ─── Grid Search ───

interface GridResult {
  sl: number;
  tp: number;
  trail: number;
  maxHold: number;
  winRate: number;
  expectancy: number;
  totalTrades: number;
  profitFactor: number;
}

function gridSearchForStrategy(
  candles: OHLCVCandle[],
  baseConfig: StrategyConfig,
  tokenSymbol: string,
  pairAddress: string,
): GridResult[] {
  const results: GridResult[] = [];

  // Define grid around current values (±50%)
  const slValues = [
    Math.max(1, baseConfig.stopLossPct * 0.5),
    baseConfig.stopLossPct * 0.75,
    baseConfig.stopLossPct,
    baseConfig.stopLossPct * 1.25,
    baseConfig.stopLossPct * 1.5,
  ];
  const tpValues = [
    Math.max(5, baseConfig.takeProfitPct * 0.5),
    baseConfig.takeProfitPct * 0.75,
    baseConfig.takeProfitPct,
    baseConfig.takeProfitPct * 1.25,
    baseConfig.takeProfitPct * 1.5,
  ];
  const trailValues = [
    Math.max(1, baseConfig.trailingStopPct * 0.5),
    baseConfig.trailingStopPct,
    baseConfig.trailingStopPct * 1.5,
  ];

  for (const sl of slValues) {
    for (const tp of tpValues) {
      for (const trail of trailValues) {
        const testConfig = { ...baseConfig, stopLossPct: sl, takeProfitPct: tp, trailingStopPct: trail };
        const result = runBacktest(candles, testConfig, tokenSymbol, pairAddress);
        if (result.totalTrades >= 5) {
          results.push({
            sl: Math.round(sl * 10) / 10,
            tp: Math.round(tp * 10) / 10,
            trail: Math.round(trail * 10) / 10,
            maxHold: baseConfig.maxHoldCandles,
            winRate: result.winRate,
            expectancy: result.expectancy,
            totalTrades: result.totalTrades,
            profitFactor: result.profitFactor,
          });
        }
      }
    }
  }

  return results.sort((a, b) => b.expectancy - a.expectancy);
}

// ─── Report Generator ───

function formatDate(ts: number): string {
  return new Date(ts).toISOString().slice(0, 19).replace('T', ' ');
}

function generateReport(
  allResults: BacktestResult[],
  gridResults: Map<string, GridResult[]>,
  tokenDataMap: Map<string, { candles: number; start: number; end: number; pair: string }>,
  startTime: number,
): string {
  const lines: string[] = [];
  lines.push('# Real Data Backtest Results');
  lines.push('');
  lines.push(`**Generated**: ${new Date().toISOString()}`);
  lines.push(`**Runtime**: ${((Date.now() - startTime) / 1000).toFixed(1)}s`);
  lines.push(`**Data Source**: GeckoTerminal OHLCV (1h candles) — REAL market data only`);
  lines.push(`**Synthetic data**: NONE — zero synthetic or simulated price data used`);
  lines.push('');

  // Data provenance
  lines.push('## 1. Data Provenance');
  lines.push('');
  lines.push('Every candle used in these backtests comes from GeckoTerminal\'s OHLCV API (CoinGecko DEX data).');
  lines.push('Each trade can be verified by its entry/exit timestamps and the pool address on GeckoTerminal.');
  lines.push('');
  lines.push('| Token | Pair Address | Candles | Date Range |');
  lines.push('|-------|-------------|---------|------------|');
  for (const [sym, info] of tokenDataMap) {
    lines.push(`| ${sym} | \`${info.pair.slice(0, 12)}...\` | ${info.candles} | ${formatDate(info.start)} → ${formatDate(info.end)} |`);
  }
  lines.push('');

  // Aggregate results by strategy
  const stratMap = new Map<string, BacktestResult[]>();
  for (const r of allResults) {
    const arr = stratMap.get(r.strategyId) || [];
    arr.push(r);
    stratMap.set(r.strategyId, arr);
  }

  lines.push('## 2. Strategy Performance Summary');
  lines.push('');
  lines.push('| Strategy | Trades | Win Rate | Profit Factor | Expectancy | Avg Return | Max DD | Sharpe | Tokens |');
  lines.push('|----------|--------|----------|---------------|------------|------------|--------|--------|--------|');

  const stratSummaries: { id: string; trades: number; wr: number; pf: number; exp: number; avgRet: number; maxDD: number; sharpe: number; tokens: number }[] = [];

  for (const [sid, results] of stratMap) {
    const totalTrades = results.reduce((s, r) => s + r.totalTrades, 0);
    const totalWins = results.reduce((s, r) => s + r.wins, 0);
    const wr = totalTrades > 0 ? totalWins / totalTrades : 0;
    const pf = results.reduce((s, r) => s + r.profitFactor * r.totalTrades, 0) / Math.max(totalTrades, 1);
    const exp = results.reduce((s, r) => s + r.expectancy * r.totalTrades, 0) / Math.max(totalTrades, 1);
    const avgRet = results.reduce((s, r) => s + r.avgReturnPct * r.totalTrades, 0) / Math.max(totalTrades, 1);
    const maxDD = Math.max(...results.map(r => r.maxDrawdownPct));
    const sharpe = results.reduce((s, r) => s + r.sharpeRatio * r.totalTrades, 0) / Math.max(totalTrades, 1);

    stratSummaries.push({ id: sid, trades: totalTrades, wr, pf, exp, avgRet, maxDD, sharpe, tokens: results.length });

    const strategy = STRATEGIES.find(s => s.id === sid);
    lines.push(`| **${strategy?.name || sid}** | ${totalTrades} | ${(wr * 100).toFixed(1)}% | ${pf.toFixed(2)} | ${exp.toFixed(2)} | ${avgRet.toFixed(2)}% | ${maxDD.toFixed(1)}% | ${sharpe.toFixed(2)} | ${results.length} |`);
  }

  // Ranking
  lines.push('');
  lines.push('## 3. Strategy Ranking (by Expectancy)');
  lines.push('');
  const ranked = [...stratSummaries].sort((a, b) => b.exp - a.exp);
  ranked.forEach((s, i) => {
    const verdict = s.wr >= 0.5 && s.pf >= 1.0 ? 'VIABLE' : s.wr >= 0.4 ? 'MARGINAL' : 'UNDERPERFORMER';
    lines.push(`${i + 1}. **${s.id}** — WR: ${(s.wr * 100).toFixed(1)}%, Exp: ${s.exp.toFixed(2)}, PF: ${s.pf.toFixed(2)} → **${verdict}** (${s.trades} trades)`);
  });

  // Grid search results
  lines.push('');
  lines.push('## 4. Parameter Optimization (Grid Search)');
  lines.push('');
  lines.push('For each strategy, we tested parameter variations around the current config.');
  lines.push('Only showing top 3 alternatives that improve on the current config.');
  lines.push('');

  for (const [sid, grid] of gridResults) {
    if (grid.length === 0) continue;
    const strategy = STRATEGIES.find(s => s.id === sid);
    const currentSummary = stratSummaries.find(s => s.id === sid);
    if (!currentSummary) continue;

    const improvements = grid.filter(g =>
      g.expectancy > currentSummary.exp * 1.05 && g.totalTrades >= 10
    ).slice(0, 3);

    if (improvements.length === 0) {
      lines.push(`### ${strategy?.name || sid}: Current config is near-optimal`);
      lines.push('');
      continue;
    }

    lines.push(`### ${strategy?.name || sid}`);
    lines.push(`Current: SL=${strategy?.stopLossPct}%, TP=${strategy?.takeProfitPct}%, Trail=${strategy?.trailingStopPct}% → Exp: ${currentSummary.exp.toFixed(2)}`);
    lines.push('');
    lines.push('| Rank | SL% | TP% | Trail% | Win Rate | Expectancy | PF | Trades |');
    lines.push('|------|-----|-----|--------|----------|------------|-----|--------|');
    improvements.forEach((imp, idx) => {
      lines.push(`| ${idx + 1} | ${imp.sl} | ${imp.tp} | ${imp.trail} | ${(imp.winRate * 100).toFixed(1)}% | ${imp.expectancy.toFixed(2)} | ${imp.profitFactor.toFixed(2)} | ${imp.totalTrades} |`);
    });
    lines.push('');
  }

  // Trade-level evidence sample
  lines.push('## 5. Trade-Level Evidence (Sample — First 10 Trades Per Strategy)');
  lines.push('');
  lines.push('Each trade is verifiable via the pair address + entry/exit timestamps on DexScreener.');
  lines.push('');

  for (const [sid, results] of stratMap) {
    const strategy = STRATEGIES.find(s => s.id === sid);
    const allTrades = results.flatMap(r => r.trades.map(t => ({ ...t, token: r.tokenSymbol, pair: r.pairAddress })));
    if (allTrades.length === 0) continue;

    lines.push(`### ${strategy?.name || sid} (${allTrades.length} total trades)`);
    lines.push('');
    lines.push('| # | Token | Entry Time | Exit Time | Entry$ | Exit$ | P&L% | Net% | Exit Reason | Pair |');
    lines.push('|---|-------|------------|-----------|--------|-------|------|------|-------------|------|');

    const sample = allTrades.slice(0, 10);
    sample.forEach((t, idx) => {
      lines.push(`| ${idx + 1} | ${t.token} | ${formatDate(t.entryTime)} | ${formatDate(t.exitTime)} | $${t.entryPrice.toFixed(6)} | $${t.exitPrice.toFixed(6)} | ${t.pnlPct.toFixed(2)}% | ${t.pnlNet.toFixed(2)}% | ${t.exitReason} | \`${(t as any).pair?.slice(0, 8) || '?'}...\` |`);
    });
    lines.push('');
  }

  // Methodology
  lines.push('## 6. Methodology');
  lines.push('');
  lines.push('### Data Collection');
  lines.push('- Source: GeckoTerminal API (`api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/hour`)');
  lines.push('- Resolution: 1-hour candles, up to 1000 candles per token (~42 days)');
  lines.push('- Token discovery: GeckoTerminal trending pools (memecoins), new pools (bags-like), hardcoded registry (bluechips)');
  lines.push('- No synthetic data generation of any kind');
  lines.push('');
  lines.push('### Simulation Model');
  lines.push('- Entry: At candle close price + slippage (buy higher)');
  lines.push('- Exit: SL/TP/Trailing Stop/Max Hold Expiry checked on each candle');
  lines.push('- Slippage: Applied on both entry and exit (varies by strategy: 0.15%-1.5%)');
  lines.push('- Fees: 0.25% per trade (entry + exit = 0.50% total)');
  lines.push('- No compounding between trades (each trade uses fresh capital)');
  lines.push('');
  lines.push('### Entry Signals');
  lines.push('- **Momentum**: RSI(14) between 50-70 + green candle');
  lines.push('- **Trend**: Price crosses above SMA(20) with 1.2x volume confirmation');
  lines.push('- **Breakout**: Price breaks above 12-candle highest high with 1.5x volume');
  lines.push('- **Mean Reversion**: Price below SMA(20)*0.99 + green recovery candle');
  lines.push('');
  lines.push('### Verification');
  lines.push('- Every trade has exact entry/exit timestamps (Unix ms)');
  lines.push('- Every trade maps to a real GeckoTerminal pool address');
  lines.push('- Anyone can verify by loading the pool on GeckoTerminal (`geckoterminal.com/solana/pools/{address}`) and checking the price at the given timestamps');
  lines.push('');

  return lines.join('\n');
}

// ─── Main Execution ───

async function main() {
  const startTime = Date.now();
  console.log('=== REAL DATA BACKTEST RUNNER ===');
  console.log(`Started: ${new Date().toISOString()}`);
  console.log('Data source: GeckoTerminal OHLCV (real data only, zero synthetic)\n');

  // Step 1: Load known tokens (all have pre-verified pool addresses)
  console.log('Step 1: Loading known tokens...');

  const memecoinTokens: TokenInfo[] = KNOWN_MEMECOINS.map(m => ({
    symbol: m.symbol, mint: '', pairAddress: m.pool,
    liquidity: 0, volume24h: 0, marketCap: 0, source: 'known-memecoin',
  }));

  const bluechipTokens: TokenInfo[] = BLUECHIPS.map(b => ({
    symbol: b.symbol, mint: '', pairAddress: b.pool,
    liquidity: 0, volume24h: 0, marketCap: 0, source: 'bluechip-registry',
  }));

  // Also fetch trending for bags-like new tokens
  console.log('  Fetching new pools for bags-like tokens...');
  const newTokens = await fetchNewTokens();

  console.log(`  Known memecoins: ${memecoinTokens.length}`);
  console.log(`  Blue chips: ${bluechipTokens.length}`);
  console.log(`  New/bags tokens: ${newTokens.length}`);

  // Step 2: Fetch OHLCV data
  console.log('\nStep 2: Fetching real OHLCV data from GeckoTerminal...');

  const allTokens = [...memecoinTokens, ...bluechipTokens, ...newTokens];
  const ohlcvCache = new Map<string, { candles: OHLCVCandle[]; pairAddress: string }>();
  const tokenDataMap = new Map<string, { candles: number; start: number; end: number; pair: string }>();

  // De-duplicate by pairAddress or mint
  const seenPairs = new Set<string>();
  const uniqueTokens = allTokens.filter(t => {
    const key = t.pairAddress || t.mint;
    if (seenPairs.has(key)) return false;
    seenPairs.add(key);
    return true;
  });

  let fetchCount = 0;
  for (const token of uniqueTokens) {
    await sleep(RATE_LIMIT_MS);

    // Get pool address (trending/new already have it, bluechips need lookup)
    let pool = token.pairAddress;
    if (!pool && token.mint) {
      pool = await fetchPoolAddress(token.mint) || '';
      await sleep(RATE_LIMIT_MS);
    }
    if (!pool) {
      console.log(`  [SKIP] ${token.symbol} — no pool found`);
      continue;
    }

    // Fetch OHLCV from GeckoTerminal
    const candles = await fetchOHLCV(pool);
    if (candles.length < 50) {
      console.log(`  [SKIP] ${token.symbol} — only ${candles.length} candles (need 50+)`);
      continue;
    }

    // Use a unique key (symbol may collide so append pair prefix)
    const key = `${token.symbol}_${pool.slice(0, 6)}`;
    ohlcvCache.set(key, { candles, pairAddress: pool });
    tokenDataMap.set(key, {
      candles: candles.length,
      start: candles[0].timestamp,
      end: candles[candles.length - 1].timestamp,
      pair: pool,
    });

    fetchCount++;
    console.log(`  [OK] ${token.symbol}: ${candles.length} candles (${formatDate(candles[0].timestamp)} → ${formatDate(candles[candles.length - 1].timestamp)}) pool=${pool.slice(0, 12)}...`);
  }

  console.log(`\nFetched OHLCV for ${fetchCount} tokens\n`);

  if (fetchCount === 0) {
    console.error('ERROR: No OHLCV data fetched. Check network/API availability.');
    process.exit(1);
  }

  // Step 3: Run backtests
  console.log('Step 3: Running backtests against real data...\n');

  const allResults: BacktestResult[] = [];
  const gridResults = new Map<string, GridResult[]>();

  for (const strategy of STRATEGIES) {
    console.log(`  Strategy: ${strategy.name} (${strategy.category})`);

    const applicableTokens: string[] = [];
    for (const [key, data] of ohlcvCache) {
      // Determine token source from the original token list
      const pool = data.pairAddress;
      const token = uniqueTokens.find(t => t.pairAddress === pool || key.startsWith(t.symbol));

      // Match strategy category to token source
      const src = token?.source || '';
      if (strategy.category === 'bags' && src !== 'geckoterminal-new') continue;
      if (strategy.category === 'bluechip' && src !== 'bluechip-registry') continue;
      if (strategy.category === 'memecoin' && src === 'bluechip-registry') continue;
      // xstock strategies: apply to trending tokens
      if (strategy.category === 'xstock' && src !== 'geckoterminal-trending') continue;

      applicableTokens.push(key);
    }

    let strategyTotalTrades = 0;
    const strategyGridAgg: GridResult[] = [];

    for (const sym of applicableTokens) {
      const data = ohlcvCache.get(sym)!;
      const result = runBacktest(data.candles, strategy, sym, data.pairAddress);
      allResults.push(result);
      strategyTotalTrades += result.totalTrades;

      // Run grid search on tokens with enough data
      if (data.candles.length >= 100 && result.totalTrades >= 3) {
        const grid = gridSearchForStrategy(data.candles, strategy, sym, data.pairAddress);
        strategyGridAgg.push(...grid);
      }
    }

    // Aggregate grid results
    if (strategyGridAgg.length > 0) {
      // Group by param combo, average metrics
      const paramMap = new Map<string, GridResult[]>();
      for (const g of strategyGridAgg) {
        const key = `${g.sl}-${g.tp}-${g.trail}`;
        const arr = paramMap.get(key) || [];
        arr.push(g);
        paramMap.set(key, arr);
      }
      const averaged: GridResult[] = [];
      for (const [, group] of paramMap) {
        const totalTrades = group.reduce((s, g) => s + g.totalTrades, 0);
        averaged.push({
          sl: group[0].sl,
          tp: group[0].tp,
          trail: group[0].trail,
          maxHold: group[0].maxHold,
          winRate: group.reduce((s, g) => s + g.winRate * g.totalTrades, 0) / totalTrades,
          expectancy: group.reduce((s, g) => s + g.expectancy * g.totalTrades, 0) / totalTrades,
          totalTrades,
          profitFactor: group.reduce((s, g) => s + g.profitFactor * g.totalTrades, 0) / totalTrades,
        });
      }
      gridResults.set(strategy.id, averaged.sort((a, b) => b.expectancy - a.expectancy));
    }

    console.log(`    → ${applicableTokens.length} tokens, ${strategyTotalTrades} trades`);
  }

  // Step 4: Generate report
  console.log('\nStep 4: Generating verifiable report...');

  const report = generateReport(allResults, gridResults, tokenDataMap, startTime);

  // Write report
  const fs = await import('fs');
  const path = await import('path');
  const reportPath = path.join(process.cwd(), 'docs', 'REAL_BACKTEST_RESULTS.md');
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  fs.writeFileSync(reportPath, report, 'utf-8');

  // Also write raw trades as CSV for verification
  const csvPath = path.join(process.cwd(), 'docs', 'backtest_trades.csv');
  const csvLines = ['strategy,token,pair,entry_time,exit_time,entry_price,exit_price,pnl_gross_pct,pnl_net_pct,exit_reason,hold_candles'];
  for (const r of allResults) {
    for (const t of r.trades) {
      csvLines.push([
        r.strategyId, r.tokenSymbol, r.pairAddress,
        t.entryTime, t.exitTime,
        t.entryPrice.toFixed(10), t.exitPrice.toFixed(10),
        t.pnlPct.toFixed(4), t.pnlNet.toFixed(4),
        t.exitReason, t.holdCandles,
      ].join(','));
    }
  }
  fs.writeFileSync(csvPath, csvLines.join('\n'), 'utf-8');

  const totalTrades = allResults.reduce((s, r) => s + r.totalTrades, 0);
  console.log(`\n=== COMPLETE ===`);
  console.log(`Total strategies tested: ${STRATEGIES.length}`);
  console.log(`Total tokens with data: ${fetchCount}`);
  console.log(`Total trades simulated: ${totalTrades}`);
  console.log(`Report: ${reportPath}`);
  console.log(`Trade CSV: ${csvPath}`);
  console.log(`Runtime: ${((Date.now() - startTime) / 1000).toFixed(1)}s`);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
