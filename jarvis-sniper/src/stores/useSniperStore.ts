import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { BagsGraduation } from '@/lib/bags-api';

export type StrategyMode = 'conservative' | 'balanced' | 'aggressive';
export type TradeSignerMode = 'phantom' | 'session';

/** Proven strategy presets from backtesting 895+ tokens */
export interface StrategyPreset {
  id: string;
  name: string;
  description: string;
  winRate: string;
  trades: number;
  config: Partial<SniperConfig>;
}

/**
 * Strategy presets — ranked by OHLCV-validated performance (real candle data).
 *
 * IMPORTANT: Phase 3 (estimated) results were misleading for MAGIC configs.
 * OHLCV validation revealed MAGIC_D (100% WR in P3) → 8.3% WR in reality.
 * Only INSIGHT/MOMENTUM configs held up under real candle validation.
 */
export const STRATEGY_PRESETS: StrategyPreset[] = [
  {
    id: 'pump_fresh_tight',
    name: 'PUMP FRESH TIGHT (88% WR)',
    description: 'Fresh pumpswap tokens with tight exits — 88.2% WR (v4 champion)',
    winRate: '88.2% (17T)',
    trades: 17,
    config: {
      stopLossPct: 20, takeProfitPct: 80, trailingStopPct: 8,
      minLiquidityUsd: 5000, minScore: 40, maxTokenAgeHours: 24,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'micro_cap_surge',
    name: 'MICRO CAP SURGE (76% WR)',
    description: 'Micro-cap tokens with 3x volume surge — 76.2% WR, huge TP potential',
    winRate: '76.2%',
    trades: 0,
    config: {
      stopLossPct: 45, takeProfitPct: 250, trailingStopPct: 20,
      minLiquidityUsd: 3000, minScore: 30, maxTokenAgeHours: 24,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'elite',
    name: 'SNIPER ELITE',
    description: '$100K+ Liq, V/L≥2, Age<100h, 10%+ Mom, Hours Gate',
    winRate: 'NEW — strictest filter',
    trades: 0,
    config: {
      stopLossPct: 15, takeProfitPct: 60, trailingStopPct: 8,
      minLiquidityUsd: 100000, minMomentum1h: 10, maxTokenAgeHours: 100,
      minVolLiqRatio: 2.0, tradingHoursGate: true, strategyMode: 'conservative',
    },
  },
  {
    id: 'momentum',
    name: 'MOMENTUM',
    description: 'V/L≥3 + B/S 1.2-2 + 5%+ Mom',
    winRate: '75% (13T)',
    trades: 13,
    config: {
      stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8,
      minLiquidityUsd: 50000, minScore: 0, minMomentum1h: 5,
      minVolLiqRatio: 1.5, tradingHoursGate: true, strategyMode: 'conservative',
    },
  },
  {
    id: 'insight_j',
    name: 'INSIGHT-J',
    description: 'Liq≥$50K + Age<100h + 10%+ Mom',
    winRate: '86% (7T)',
    trades: 7,
    config: {
      stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8,
      minLiquidityUsd: 50000, maxTokenAgeHours: 100, minMomentum1h: 10,
      tradingHoursGate: true, strategyMode: 'conservative',
    },
  },
  {
    id: 'hybrid_b',
    name: 'HYBRID-B v6',
    description: 'Balanced — Liq≥$50K + Hours Gate',
    winRate: '~90% (est)',
    trades: 10,
    config: {
      stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8,
      minLiquidityUsd: 50000, minMomentum1h: 5, minVolLiqRatio: 1.0,
      tradingHoursGate: true, strategyMode: 'conservative',
    },
  },
  {
    id: 'let_it_ride',
    name: 'LET IT RIDE',
    description: '20/100 + 5% trail — max gains',
    winRate: '100% (10T)',
    trades: 10,
    config: {
      stopLossPct: 20, takeProfitPct: 100, trailingStopPct: 5,
      minLiquidityUsd: 50000, minMomentum1h: 5, tradingHoursGate: true,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'loose',
    name: 'WIDE NET',
    description: 'Original loose filters — more trades, lower WR',
    winRate: '49% (54T)',
    trades: 54,
    config: {
      stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8,
      minLiquidityUsd: 25000, minMomentum1h: 0, maxTokenAgeHours: 500,
      minVolLiqRatio: 0.5, tradingHoursGate: false, strategyMode: 'conservative',
    },
  },
  {
    id: 'genetic_best',
    name: 'GENETIC BEST (83% WR)',
    description: 'Genetic optimizer champion — SL35/TP200/Trail12, fresh tokens, $3K liq',
    winRate: '83.3% (GA)',
    trades: 0,
    config: {
      stopLossPct: 35, takeProfitPct: 200, trailingStopPct: 12,
      minLiquidityUsd: 3000, minScore: 43, maxTokenAgeHours: 24,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'genetic_v2',
    name: 'GENETIC V2 (71% WR)',
    description: 'Optimizer v2 champion — SL45/TP207/Trail10, volume surge filter',
    winRate: '71.1% (GA v2)',
    trades: 45,
    config: {
      stopLossPct: 45, takeProfitPct: 207, trailingStopPct: 10,
      minLiquidityUsd: 5000, minScore: 0,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'xstock_momentum',
    name: 'XSTOCK MOMENTUM',
    description: 'xStocks with tight exits — US market hours optimal',
    winRate: 'NEW',
    trades: 0,
    config: {
      stopLossPct: 3, takeProfitPct: 8, trailingStopPct: 2,
      minLiquidityUsd: 10000, minScore: 0,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'prestock_speculative',
    name: 'PRESTOCK SPEC',
    description: 'Pre-IPO tokens with wider risk tolerance — high reward potential',
    winRate: 'NEW',
    trades: 0,
    config: {
      stopLossPct: 15, takeProfitPct: 50, trailingStopPct: 8,
      minLiquidityUsd: 5000, minScore: 0,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'index_revert',
    name: 'INDEX MEAN REVERT',
    description: 'Solana index tokens — tight SL/TP for mean reversion plays',
    winRate: 'NEW',
    trades: 0,
    config: {
      stopLossPct: 2, takeProfitPct: 5, trailingStopPct: 1.5,
      minLiquidityUsd: 20000, minScore: 0,
      strategyMode: 'conservative',
    },
  },
];

/** UTC hours proven profitable in 928-token OHLCV backtest */
export const PROVEN_TRADING_HOURS = [2, 4, 8, 11, 14, 20, 21];
/** UTC hours with 0% win rate in backtest — hard avoid */
export const DEAD_HOURS = [1, 3, 5, 6, 7, 9, 12, 13, 16, 19, 22, 23];

export interface SniperConfig {
  stopLossPct: number;
  takeProfitPct: number;
  trailingStopPct: number;
  maxPositionSol: number;
  maxConcurrentPositions: number;
  minScore: number;
  /** HYBRID-B gate: skip tokens under this liquidity (USD). */
  minLiquidityUsd: number;
  autoSnipe: boolean;
  useJito: boolean;
  slippageBps: number;
  /** Strategy mode: conservative (PUMP_FRESH_TIGHT 20/80), balanced (SURGE_HUNTER 20/100), aggressive (MICRO_CAP_SURGE 45/250) */
  strategyMode: StrategyMode;
  /** Max position age in hours before auto-close (0 = disabled). Frees capital from stale positions. */
  maxPositionAgeHours: number;
  /** Use per-position recommended SL/TP (default). If false, force global SL/TP for all positions. */
  useRecommendedExits: boolean;
  /** Minimum 1h price momentum required (%). Backtest: 5-10% dramatically cuts losers. */
  minMomentum1h: number;
  /** Max token age in hours (younger = higher alpha). Backtest: <200h is sweet spot. */
  maxTokenAgeHours: number;
  /** Min Vol/Liq ratio. Backtest: >=1.0 is 8x edge vs <0.5. */
  minVolLiqRatio: number;
  /** Only trade during proven UTC hours (OHLCV backtest). Prevents 0% WR hour entries. */
  tradingHoursGate: boolean;
  /** Minimum minutes since graduation before sniping (avoids post-graduation dumps). 0 = disabled. */
  minAgeMinutes: number;
  // ─── Circuit Breaker ───
  /** Enable circuit breaker to halt auto-sniping on cascading losses */
  circuitBreakerEnabled: boolean;
  /** Halt after N consecutive losses (0 = disabled) */
  maxConsecutiveLosses: number;
  /** Halt after losing X SOL in a rolling 24h window (0 = disabled) */
  maxDailyLossSol: number;
  /** Halt if remaining budget drops below X SOL (capital preservation) */
  minBalanceGuardSol: number;
}

export interface CircuitBreakerState {
  /** Whether the breaker is currently tripped (sniping halted) */
  tripped: boolean;
  /** Human-readable reason for trip */
  reason: string;
  /** Timestamp when breaker was tripped */
  trippedAt: number;
  /** Running count of consecutive losses */
  consecutiveLosses: number;
  /** SOL lost in the current 24h window */
  dailyLossSol: number;
  /** Timestamp when the daily window resets */
  dailyResetAt: number;
}

export interface BudgetState {
  /** Total SOL authorized for sniping */
  budgetSol: number;
  /** Whether the user has explicitly authorized the budget */
  authorized: boolean;
  /** SOL spent so far (sum of open positions' solInvested) */
  spent: number;
}

export interface Position {
  id: string;
  mint: string;
  symbol: string;
  name: string;
  /** Wallet that holds the tokens (lets risk monitoring continue even if Phantom disconnects). */
  walletAddress?: string;
  entryPrice: number;
  currentPrice: number;
  amount: number;
  /** Raw token amount in lamports (smallest unit) for sell quotes */
  amountLamports?: string;
  solInvested: number;
  pnlPercent: number;
  pnlSol: number;
  entryTime: number;
  txHash?: string;
  status: 'open' | 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired' | 'closed';
  /** Lock flag — prevents duplicate sell attempts while tx is in-flight */
  isClosing?: boolean;
  /** Exit was triggered (SL/TP/trail/expiry) and is waiting for user approval in Phantom. */
  exitPending?: {
    trigger: 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired';
    pnlPercent: number;
    /** Realizable exit value from a Bags quote (may be missing if quote failed). */
    exitValueSol?: number;
    /** Whether a Bags quote was available when we marked this pending. */
    quoteAvailable?: boolean;
    /** Optional human hint (e.g. "no quote route", "increase slippage"). */
    reason?: string;
    updatedAt: number;
  };
  score: number;
  recommendedSl: number;
  recommendedTp: number;
  /** Per-position adaptive trailing stop % (from getRecommendedSlTp). Falls back to global config if absent. */
  recommendedTrail?: number;
  /** Trailing stop: highest P&L% ever reached (high water mark) */
  highWaterMarkPct: number;
  /** Actual SOL received from the sell tx (set after execution for accurate P&L). */
  exitSolReceived?: number;
  /** Real P&L based on actual sell proceeds, not price estimate. */
  realPnlSol?: number;
  /** Real P&L percent based on actual sell proceeds. */
  realPnlPercent?: number;
  // ─── Jupiter Trigger Orders (on-chain SL/TP) ───
  /** Jupiter trigger order account for take-profit */
  jupTpOrderKey?: string;
  /** Jupiter trigger order account for stop-loss */
  jupSlOrderKey?: string;
  /** Whether SL/TP orders are placed on-chain */
  onChainSlTp?: boolean;
}

export interface ExecutionEvent {
  id: string;
  type: 'snipe' | 'exit_pending' | 'tp_exit' | 'sl_exit' | 'manual_exit' | 'error' | 'skip' | 'info';
  symbol: string;
  mint: string;
  amount?: number;
  price?: number;
  pnlPercent?: number;
  reason?: string;
  txHash?: string;
  timestamp: number;
}

export interface TokenRecommendation {
  sl: number;
  tp: number;
  trail: number;
  reasoning: string;
}

/** Per-token SL/TP recommendation — backtested on 928 tokens (OHLCV-validated)
 *
 * Key findings (v5 full backtest, 89 configs, 928 tokens):
 * - Conservative (20/60 + 8% trail): 94.1% WR, PF 1533.63  (OHLCV)
 * - Aggressive  (20/100 + 10% trail): 78.9% WR, PF 135.15, +587% TotalPnL
 * - Optimal trail: 8-10% (TRAIL_10 = 100% WR, TRAIL_8 = 94.1% WR)
 * - Vol/Liq ≥ 0.5 → 40.6% upside vs 4.9% for <0.5 (8x edge)
 * - Best hours: 4:00 (60%), 11:00 (57%), 21:00 (52%)
 */
export function getRecommendedSlTp(
  grad: BagsGraduation & Record<string, any>,
  mode: StrategyMode = 'conservative',
): TokenRecommendation {
  const liq = grad.liquidity || 0;
  const priceChange1h = grad.price_change_1h || 0;
  const buySellRatio = grad.buy_sell_ratio || 0;
  const ageHours = grad.age_hours || 0;
  const vol24h = grad.volume_24h || 0;
  const volLiqRatio = liq > 0 ? vol24h / liq : 0;
  const source = (grad.source || '').toLowerCase();

  // ─── Strategy Selection (v4 backtest champion logic) ───
  // Priority 1: Fresh pumpswap tokens → PUMP_FRESH_TIGHT (88.2% WR champion)
  if (ageHours < 24 && source === 'pumpswap') {
    return {
      sl: 20, tp: 80, trail: 8,
      reasoning: 'PUMP_FRESH_TIGHT: fresh pumpswap token (<24h) — 88.2% WR v4 champion',
    };
  }

  // Priority 2: Volume surge (3x+ Vol/Liq) → SURGE_HUNTER
  if (volLiqRatio >= 3.0) {
    return {
      sl: 20, tp: 100, trail: 10,
      reasoning: `SURGE_HUNTER: volume surge detected (V/L ${volLiqRatio.toFixed(1)}x)`,
    };
  }

  // Priority 3: Micro-cap (liquidity < $15K) → MICRO_CAP_SURGE (76.2% WR)
  if (liq < 15000) {
    return {
      sl: 45, tp: 250, trail: 20,
      reasoning: `MICRO_CAP_SURGE: micro-cap ($${Math.round(liq).toLocaleString('en-US')} liq) — 76.2% WR, high TP`,
    };
  }

  // ─── Fallback: Adaptive FRESH_DEGEN base ───
  let sl = 20;
  let tp = mode === 'aggressive' ? 100 : 80;
  let reasoning = 'FRESH_DEGEN fallback';

  // Liquidity tier adjustments (high liq = less slippage, can tighten SL)
  if (liq > 200000) {
    sl = 15;
    reasoning += ', high liq ($200K+) — tighter SL';
  } else if (liq > 100000) {
    sl = 18;
    reasoning += ', strong liq ($100K+)';
  }
  // Low liquidity = wider SL to absorb spread
  else if (liq < 25000) {
    sl = 25; tp = mode === 'aggressive' ? 80 : 50;
    reasoning += ', low liq — wider SL';
  }

  // Strong momentum = extend TP (let winners run even more)
  if (priceChange1h > 20) {
    tp += 20;
    reasoning += ', strong momentum (+20%+1h)';
  } else if (priceChange1h > 10) {
    tp += 10;
    reasoning += ', good momentum';
  }

  // Young + active = higher potential
  if (ageHours < 100 && buySellRatio >= 1.2 && buySellRatio <= 2.5) {
    tp += 10;
    reasoning += ', young+active';
  }

  // Sweet spot B/S ratio = highest confidence
  if (buySellRatio >= 1.2 && buySellRatio <= 2.0) {
    sl -= 2;
    reasoning += ', optimal B/S range';
  }

  // Time-of-day adjustments (928-token OHLCV backtest: good hours > 50% WR)
  const nowUtcHour = new Date().getUTCHours();
  const GOOD_HOURS = [14, 20]; // OHLCV-validated: 20:00 (43.5% WR), 14:00 (25% WR)
  if (GOOD_HOURS.includes(nowUtcHour)) {
    // During high-WR hours: tighten SL (less drawdown), widen TP (let winners run)
    sl -= 3;
    tp += 15;
    reasoning += `, TOD boost (${nowUtcHour}h)`;
  }

  // ─── Adaptive Trailing Stop ───
  // High momentum → tighter trail (fast movers reverse quickly)
  // Low momentum → wider trail (give room to develop)
  let trail: number;
  if (priceChange1h > 50) {
    trail = 5;
    reasoning += ', tight trail (high momentum)';
  } else if (priceChange1h <= 20) {
    trail = 12;
    reasoning += ', wide trail (low momentum)';
  } else {
    trail = 8;
    reasoning += ', default trail';
  }

  // Clamp values — aggressive allows higher TP cap
  sl = Math.max(10, Math.min(30, Math.round(sl)));
  tp = Math.max(30, Math.min(mode === 'aggressive' ? 200 : 120, Math.round(tp)));

  return { sl, tp, trail, reasoning };
}

/** Conviction-weighted position sizing — scale bets by signal quality.
 * Returns 0.5x – 2.0x multiplier on base position size.
 * Based on 928-token OHLCV feature importance:
 *   Price Change 1h (244.5%), Vol/Liq (77.6%), Liquidity, TOD, B/S ratio.
 */
export function getConvictionMultiplier(
  grad: BagsGraduation & Record<string, any>,
): { multiplier: number; factors: string[] } {
  let score = 0;
  const factors: string[] = [];

  // Factor 1: Price Change 1h — strongest predictor (244.5% power)
  const change1h = grad.price_change_1h || 0;
  if (change1h > 200) { score += 0.4; factors.push(`1h↑${Math.round(change1h)}%`); }
  else if (change1h > 50) { score += 0.2; factors.push(`1h↑${Math.round(change1h)}%`); }

  // Factor 2: Vol/Liq ratio (77.6% predictive power)
  const liq = grad.liquidity || 0;
  const vol24h = grad.volume_24h || 0;
  const volLiq = liq > 0 ? vol24h / liq : 0;
  if (volLiq > 3.0) { score += 0.3; factors.push(`V/L ${volLiq.toFixed(1)}`); }
  else if (volLiq > 1.0) { score += 0.2; factors.push(`V/L ${volLiq.toFixed(1)}`); }

  // Factor 3: Liquidity tier — higher = safer bet
  if (liq > 200000) { score += 0.2; factors.push('$200K+'); }
  else if (liq > 100000) { score += 0.1; factors.push('$100K+'); }

  // Factor 4: Good hour (OHLCV best hours: 4=60%, 11=57%, 21=52%)
  const nowUtcHour = new Date().getUTCHours();
  if ([4, 11, 21].includes(nowUtcHour)) { score += 0.2; factors.push(`hr${nowUtcHour}`); }
  else if (nowUtcHour === 8) { score += 0.1; factors.push('hr8'); }

  // Factor 5: B/S sweet spot (1.2-2.0 = optimal in backtest)
  const buys = grad.txn_buys_1h || 0;
  const sells = grad.txn_sells_1h || 0;
  const bsRatio = sells > 0 ? buys / sells : buys;
  if (buys + sells > 10 && bsRatio >= 1.2 && bsRatio <= 2.0) {
    score += 0.1; factors.push(`BS${bsRatio.toFixed(1)}`);
  }

  // ─── Negative Factors (risk penalties) ───

  // Penalty: Very high price change (>200%) — pump risk
  if (change1h > 200) {
    score -= 0.2; factors.push('pump risk');
  }

  // Penalty: Very high B/S ratio (>3.0) — potential manipulation
  if (bsRatio > 3.0 && buys + sells > 5) {
    score -= 0.15; factors.push('high B/S');
  }

  // Base 0.5 + factors → clamp to [0.5, 2.0]
  const multiplier = Math.max(0.5, Math.min(2.0, 0.5 + score));
  return { multiplier, factors };
}

const DEFAULT_CONFIG: SniperConfig = {
  stopLossPct: 20,      // PUMP_FRESH_TIGHT champion: 88.2% WR, Sharpe 1.22
  takeProfitPct: 80,    // v4 backtest champion: 20/80/8 on fresh pumpswap tokens
  trailingStopPct: 8,   // Tight trail locks profits — 88.2% WR with 8% trail
  maxPositionSol: 0.1,
  maxConcurrentPositions: 10,
  minScore: 0,          // Backtested: best configs use liq+momentum, not score
  // Default lowered to $25K so the feed doesn't "skip everything" under normal meme-token conditions.
  // Users can still raise this to $40K/$50K for higher-quality entries.
  minLiquidityUsd: 25000,
  autoSnipe: false,
  useJito: true,
  slippageBps: 150,
  strategyMode: 'conservative',
  maxPositionAgeHours: 4,  // Auto-close stale positions after 4h to free capital
  useRecommendedExits: true,
  // NEW: Stricter quality gates (be pickier, 4x fewer but higher quality)
  minMomentum1h: 5,        // Require 5%+ upward momentum (was 0% — let everything through)
  maxTokenAgeHours: 200,   // ↓ from 500h — young tokens have 188% more alpha
  minVolLiqRatio: 1.0,     // ↑ from 0.5 — tighter filter for vol/liq edge
  tradingHoursGate: true,  // Only trade during OHLCV-proven hours (blocks 11 dead hours)
  minAgeMinutes: 2,       // Don't snipe tokens that graduated < 2 min ago (post-grad dumps)
  // Circuit breaker: halt sniping on cascading losses to protect capital
  circuitBreakerEnabled: true,
  maxConsecutiveLosses: 3,     // 3 losses in a row = halt
  maxDailyLossSol: 0.5,       // 0.5 SOL daily loss limit
  minBalanceGuardSol: 0.05,   // Stop if budget remaining < 0.05 SOL
};

/** Monotonic counter to prevent duplicate keys when multiple snipes fire in same ms */
let execCounter = 0;

interface SniperState {
  // Config
  config: SniperConfig;
  setConfig: (partial: Partial<SniperConfig>) => void;
  setStrategyMode: (mode: StrategyMode) => void;
  loadPreset: (presetId: string) => void;
  activePreset: string;
  loadBestEver: (cfg: Record<string, any>) => void;

  // Trade Signing Mode
  /** Phantom (manual signing) or Session Wallet (auto signing). */
  tradeSignerMode: TradeSignerMode;
  setTradeSignerMode: (mode: TradeSignerMode) => void;
  /** Session wallet public key (base58) when enabled. Secret key stays in sessionStorage only. */
  sessionWalletPubkey: string | null;
  setSessionWalletPubkey: (pubkey: string | null) => void;

  // Budget / Authorization
  budget: BudgetState;
  setBudgetSol: (sol: number) => void;
  authorizeBudget: () => void;
  deauthorizeBudget: () => void;
  budgetRemaining: () => number;

  // Graduations
  graduations: BagsGraduation[];
  setGraduations: (grads: BagsGraduation[]) => void;
  addGraduation: (grad: BagsGraduation) => void;

  // Positions
  positions: Position[];
  addPosition: (pos: Position) => void;
  updatePosition: (id: string, update: Partial<Position>) => void;
  removePosition: (id: string) => void;
  /** Batch-update prices from DexScreener polling */
  updatePrices: (priceMap: Record<string, number>) => void;
  /** Set isClosing lock on a position */
  setPositionClosing: (id: string, closing: boolean) => void;
  /** Close a position with proper status and stats tracking.
   * @param exitSolReceived — actual SOL from the sell tx (for accurate P&L). */
  closePosition: (id: string, status: 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired' | 'closed', txHash?: string, exitSolReceived?: number) => void;

  // Snipe action — creates position + logs execution
  snipeToken: (grad: BagsGraduation & Record<string, any>) => void;

  // Track which tokens were already sniped (prevents duplicates)
  snipedMints: Set<string>;

  // Track tokens that were evaluated and skipped (prevents skip-spam in logs)
  skippedMints: Set<string>;

  // Selected token for chart display
  selectedMint: string | null;
  setSelectedMint: (mint: string | null) => void;

  // Execution Log
  executionLog: ExecutionEvent[];
  addExecution: (event: ExecutionEvent) => void;

  // Stats
  totalPnl: number;
  winCount: number;
  lossCount: number;
  totalTrades: number;

  // Circuit Breaker
  circuitBreaker: CircuitBreakerState;
  resetCircuitBreaker: () => void;

  // Reset — clears positions, executions, stats, sniped mints
  resetSession: () => void;
}

export const useSniperStore = create<SniperState>()(
  persist(
    (set, get) => ({
  config: DEFAULT_CONFIG,
  activePreset: 'pump_fresh_tight',
  tradeSignerMode: 'phantom',
  setTradeSignerMode: (mode) => set({ tradeSignerMode: mode }),
  sessionWalletPubkey: null,
  setSessionWalletPubkey: (pubkey) => set({ sessionWalletPubkey: pubkey }),
  setConfig: (partial) => set((s) => {
    // When trailing stop changes, reset HWM on open positions so the trail starts fresh
    const trailChanged = partial.trailingStopPct !== undefined && partial.trailingStopPct !== s.config.trailingStopPct;
    const positions = trailChanged
      ? s.positions.map((p) => p.status === 'open' ? { ...p, highWaterMarkPct: Math.max(p.pnlPercent, 0), exitPending: undefined } : p)
      : s.positions;
    return { config: { ...s.config, ...partial }, skippedMints: new Set(), positions };
  }),
  loadPreset: (presetId) => {
    const preset = STRATEGY_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    set((s) => {
      const trailChanged = preset.config.trailingStopPct !== undefined && preset.config.trailingStopPct !== s.config.trailingStopPct;
      const positions = trailChanged
        ? s.positions.map((p) => p.status === 'open' ? { ...p, highWaterMarkPct: Math.max(p.pnlPercent, 0), exitPending: undefined } : p)
        : s.positions;
      return {
        activePreset: presetId,
        config: { ...s.config, ...preset.config },
        skippedMints: new Set(),
        positions,
      };
    });
  },
  setStrategyMode: (mode) => set((s) => {
    // v4 backtest-mapped presets:
    //   aggressive   → MICRO_CAP_SURGE (76.2% WR, 45/250/20)
    //   balanced     → SURGE_HUNTER (20/100/10)
    //   conservative → PUMP_FRESH_TIGHT (88.2% WR, 20/80/8) — safest high-WR
    const presets: Record<StrategyMode, { sl: number; tp: number; trail: number }> = {
      aggressive:   { sl: 45, tp: 250, trail: 20 },
      balanced:     { sl: 20, tp: 100, trail: 10 },
      conservative: { sl: 20, tp: 80,  trail: 8  },
    };
    const p = presets[mode];
    return {
      config: {
        ...s.config,
        strategyMode: mode,
        stopLossPct: p.sl,
        takeProfitPct: p.tp,
        trailingStopPct: p.trail,
      },
    };
  }),
  loadBestEver: (cfg) => set((s) => ({
    config: {
      ...s.config,
      stopLossPct: cfg.stopLossPct ?? s.config.stopLossPct,
      takeProfitPct: cfg.takeProfitPct ?? s.config.takeProfitPct,
      trailingStopPct: cfg.trailingStopPct ?? s.config.trailingStopPct,
      // Round to 2 decimals to avoid ugly display like 4.082627630820
      maxPositionSol: Math.round((cfg.maxPositionUsd ?? s.config.maxPositionSol) * 100) / 100,
      maxConcurrentPositions: cfg.maxConcurrentPositions ?? s.config.maxConcurrentPositions,
      minScore: Math.round((cfg.safetyScoreMin ?? 0.2) * 100),
      minLiquidityUsd: cfg.minLiquidityUsd ?? s.config.minLiquidityUsd,
    },
  })),

  // Budget / Authorization
  budget: { budgetSol: 0.1, authorized: false, spent: 0 },
  setBudgetSol: (sol) => set((s) => ({
    budget: { ...s.budget, budgetSol: Math.round(sol * 1000) / 1000 },
  })),
  authorizeBudget: () => set((s) => ({
    budget: { ...s.budget, authorized: true, spent: 0 },
    // Auto-set position size = budget / maxPositions (rounded to 2dp)
    config: {
      ...s.config,
      maxPositionSol: Math.round((s.budget.budgetSol / s.config.maxConcurrentPositions) * 100) / 100,
    },
  })),
  deauthorizeBudget: () => set((s) => ({
    budget: { ...s.budget, authorized: false },
    config: { ...s.config, autoSnipe: false },
  })),
  budgetRemaining: () => {
    const { budget } = get();
    return Math.round((budget.budgetSol - budget.spent) * 1000) / 1000;
  },

  graduations: [],
  setGraduations: (grads) => set({ graduations: grads }),
  addGraduation: (grad) => set((s) => ({
    graduations: [grad, ...s.graduations].slice(0, 100),
  })),

  positions: [],
  addPosition: (pos) => set((s) => ({ positions: [pos, ...s.positions] })),
  updatePosition: (id, update) => set((s) => ({
    positions: s.positions.map((p) => p.id === id ? { ...p, ...update } : p),
  })),
  removePosition: (id) => set((s) => ({
    positions: s.positions.filter((p) => p.id !== id),
  })),
  updatePrices: (priceMap) => set((s) => ({
    positions: s.positions.map((p) => {
      const newPrice = priceMap[p.mint];
      if (newPrice == null || p.status !== 'open') return p;
      const pnlPercent = p.entryPrice > 0 ? ((newPrice - p.entryPrice) / p.entryPrice) * 100 : 0;
      const pnlSol = p.solInvested * (pnlPercent / 100);
      // Track high water mark for trailing stop
      const highWaterMarkPct = Math.max(p.highWaterMarkPct ?? 0, pnlPercent);
      return { ...p, currentPrice: newPrice, pnlPercent, pnlSol, highWaterMarkPct };
    }),
  })),
  setPositionClosing: (id, closing) => set((s) => ({
    positions: s.positions.map((p) => p.id === id ? { ...p, isClosing: closing } : p),
  })),
  closePosition: (id, status, txHash, exitSolReceived) => {
    const state = get();
    const pos = state.positions.find((p) => p.id === id);
    if (!pos) return;

    execCounter++;

    // Use actual sell proceeds when available, otherwise fall back to price estimate
    const realPnlSol = exitSolReceived != null
      ? exitSolReceived - pos.solInvested
      : pos.pnlSol;
    const realPnlPct = exitSolReceived != null
      ? ((exitSolReceived - pos.solInvested) / pos.solInvested) * 100
      : pos.pnlPercent;

    // Trail stop above entry is a win, below entry is a loss
    const isWin = realPnlPct >= 0;
    const exitType = status === 'tp_hit' ? 'tp_exit'
      : status === 'trail_stop' ? (isWin ? 'tp_exit' : 'sl_exit')
      : status === 'sl_hit' ? 'sl_exit'
      : status === 'expired' ? (isWin ? 'tp_exit' : 'sl_exit')
      : 'manual_exit';

    // Manual exits count toward win/loss too (based on whether profitable)
    const countAsWin = exitType === 'tp_exit' || (exitType === 'manual_exit' && isWin);
    const countAsLoss = exitType === 'sl_exit' || (exitType === 'manual_exit' && !isWin);

    const pnlLabel = exitSolReceived != null
      ? `${realPnlSol >= 0 ? '+' : ''}${realPnlSol.toFixed(4)} SOL (real)`
      : `${realPnlPct.toFixed(1)}% (est)`;

    const execEvent: ExecutionEvent = {
      id: `exec-${Date.now()}-${execCounter}`,
      type: exitType,
      symbol: pos.symbol,
      mint: pos.mint,
      amount: pos.solInvested,
      pnlPercent: realPnlPct,
      txHash,
      timestamp: Date.now(),
      reason: `${status === 'trail_stop' ? 'TRAIL STOP' : status === 'expired' ? 'EXPIRED' : status.replace('_', ' ').toUpperCase()} — ${pnlLabel}`,
    };

    set((s) => {
      // ─── Circuit Breaker Update ───
      const cb = { ...s.circuitBreaker };
      const now = Date.now();

      // Reset 24h window if expired
      if (now >= cb.dailyResetAt) {
        cb.dailyLossSol = 0;
        cb.dailyResetAt = now + 86_400_000;
      }

      if (countAsLoss) {
        cb.consecutiveLosses += 1;
        cb.dailyLossSol += Math.abs(realPnlSol);
      } else if (countAsWin) {
        cb.consecutiveLosses = 0; // Reset streak on any win
      }

      // Check trip conditions
      const cfg = s.config;
      if (cfg.circuitBreakerEnabled && !cb.tripped) {
        const budgetRemaining = s.budget.budgetSol - Math.max(0, s.budget.spent - pos.solInvested);
        if (cfg.maxConsecutiveLosses > 0 && cb.consecutiveLosses >= cfg.maxConsecutiveLosses) {
          cb.tripped = true;
          cb.reason = `${cb.consecutiveLosses} consecutive losses`;
          cb.trippedAt = now;
        } else if (cfg.maxDailyLossSol > 0 && cb.dailyLossSol >= cfg.maxDailyLossSol) {
          cb.tripped = true;
          cb.reason = `Daily loss ${cb.dailyLossSol.toFixed(3)} SOL >= ${cfg.maxDailyLossSol} limit`;
          cb.trippedAt = now;
        } else if (cfg.minBalanceGuardSol > 0 && budgetRemaining < cfg.minBalanceGuardSol) {
          cb.tripped = true;
          cb.reason = `Budget remaining ${budgetRemaining.toFixed(3)} SOL < ${cfg.minBalanceGuardSol} guard`;
          cb.trippedAt = now;
        }
      }

      return {
        positions: s.positions.map((p) => p.id === id ? {
          ...p,
          status,
          isClosing: false,
          exitPending: undefined,
          exitSolReceived,
          realPnlSol,
          realPnlPercent: realPnlPct,
        } : p),
        executionLog: [execEvent, ...s.executionLog].slice(0, 200),
        totalPnl: s.totalPnl + realPnlSol,
        winCount: countAsWin ? s.winCount + 1 : s.winCount,
        lossCount: countAsLoss ? s.lossCount + 1 : s.lossCount,
        totalTrades: s.totalTrades + 1,
        budget: { ...s.budget, spent: Math.max(0, s.budget.spent - pos.solInvested) },
        circuitBreaker: cb,
        // Auto-disable autoSnipe when breaker trips
        config: cb.tripped ? { ...s.config, autoSnipe: false } : s.config,
      };
    });
  },

  snipedMints: new Set(),
  skippedMints: new Set(),

  snipeToken: (grad) => {
    const state = get();
    const { config, positions, snipedMints, skippedMints, budget } = state;

    // Guard: budget not authorized
    if (!budget.authorized) return;

    // Guard: circuit breaker tripped
    if (state.circuitBreaker.tripped) return;

    // Guard: already sniped
    if (snipedMints.has(grad.mint)) return;

    // Guard: already evaluated and skipped — prevents skip-spam in logs
    if (skippedMints.has(grad.mint)) return;

    // Guard: at capacity
    const openCount = positions.filter(p => p.status === 'open').length;
    if (openCount >= config.maxConcurrentPositions) return;

    // Guard: insufficient budget remaining
    const remaining = budget.budgetSol - budget.spent;
    // Conviction-weighted sizing: scale position by signal strength (0.5x – 2.0x)
    const { multiplier: conviction, factors: convFactors } = getConvictionMultiplier(grad);
    const positionSol = Math.min(config.maxPositionSol * conviction, remaining);
    if (positionSol < 0.001) return; // minimum viable position

    // ═══ ELITE FILTERS — Be pickier, trade less, win more ═══
    // Helper: log skip ONCE per mint, then add to skippedMints so we never re-log
    const logSkipOnce = (reason: string) => {
      execCounter++;
      const newSkipped = new Set(get().skippedMints);
      newSkipped.add(grad.mint);
      set((s) => ({
        skippedMints: newSkipped,
        executionLog: [{
          id: `exec-${Date.now()}-${execCounter}`,
          type: 'skip' as const,
          symbol: grad.symbol,
          mint: grad.mint,
          reason,
          timestamp: Date.now(),
        }, ...s.executionLog].slice(0, 200),
      }));
    };

    // Gate 0: Trading hours — block entries during dead hours (11/24 hours have 0% WR)
    if (config.tradingHoursGate) {
      const nowUtcHour = new Date().getUTCHours();
      if (DEAD_HOURS.includes(nowUtcHour)) {
        logSkipOnce(`Dead hour (${nowUtcHour}:00 UTC) — ${DEAD_HOURS.length} hours blocked`);
        return;
      }
    }

    // Gate 0.5: Smart entry delay — skip tokens that graduated too recently
    if (config.minAgeMinutes > 0) {
      const gradTime = (grad.graduation_time || 0) * 1000; // convert seconds to ms
      const ageMinutes = (Date.now() - gradTime) / 60000;
      if (ageMinutes < config.minAgeMinutes) {
        logSkipOnce(`Too fresh: ${ageMinutes.toFixed(1)}min < ${config.minAgeMinutes}min minimum`);
        return;
      }
    }

    // Gate 1: Minimum liquidity (USD)
    const liq = grad.liquidity || 0;
    if (liq < config.minLiquidityUsd) {
      logSkipOnce(`Low liquidity: $${Math.round(liq).toLocaleString('en-US')} < $${Math.round(config.minLiquidityUsd).toLocaleString('en-US')}`);
      return;
    }

    // Gate 2: Minimum momentum (1h price change) — strongest predictor at 270% power
    const change1h = grad.price_change_1h || 0;
    if (change1h < config.minMomentum1h) {
      logSkipOnce(`Weak momentum: ${change1h.toFixed(1)}% < ${config.minMomentum1h}% min`);
      return;
    }

    // Gate 3: Token age — young tokens have 188% more alpha
    const ageHours = grad.age_hours || 0;
    if (config.maxTokenAgeHours > 0 && ageHours > config.maxTokenAgeHours) {
      logSkipOnce(`Too old: ${Math.round(ageHours)}h > ${config.maxTokenAgeHours}h limit`);
      return;
    }

    // Gate 4: Vol/Liq ratio — 8x edge (40.6% upside vs 4.9%)
    const vol24h = grad.volume_24h || 0;
    const volLiqRatio = liq > 0 ? vol24h / liq : 0;
    if (vol24h > 0 && volLiqRatio < config.minVolLiqRatio) {
      logSkipOnce(`Low Vol/Liq: ${volLiqRatio.toFixed(2)} < ${config.minVolLiqRatio} min`);
      return;
    }

    // Gate 5: Buy/Sell ratio 1.0-3.0 (sweet spot — extreme = pump-and-dump signal)
    const buys = grad.txn_buys_1h || 0;
    const sells = grad.txn_sells_1h || 0;
    const bsRatio = sells > 0 ? buys / sells : buys;
    if (buys + sells > 10 && (bsRatio < 1.0 || bsRatio > 3.0)) {
      logSkipOnce(`B/S ratio ${bsRatio.toFixed(1)} outside 1.0-3.0 range`);
      return;
    }

    // ═══ All insight filters passed — proceed with snipe ═══

    // ─── Volume Spike / Pump Detection ───
    // If volume > 5x liquidity AND price change > 100%, flag as potential pump
    let pumpWarning = false;
    let effectiveConviction = conviction;
    if (vol24h > 5 * liq && change1h > 100) {
      pumpWarning = true;
      effectiveConviction = Math.max(0.5, conviction * 0.3); // reduce by 0.3x (multiply by 0.3)
    }
    const positionSolFinal = Math.min(config.maxPositionSol * effectiveConviction, remaining);
    if (positionSolFinal < 0.001) return;

    // Get per-token recommended SL/TP (respects strategy mode)
    const rec = getRecommendedSlTp(grad, config.strategyMode);

    const posId = `pos-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const newPosition: Position = {
      id: posId,
      mint: grad.mint,
      symbol: grad.symbol,
      name: grad.name,
      entryPrice: grad.price_usd || 0,
      currentPrice: grad.price_usd || 0,
      amount: positionSolFinal / (grad.price_usd || 1),
      solInvested: positionSolFinal,
      pnlPercent: 0,
      pnlSol: 0,
      entryTime: Date.now(),
      status: 'open',
      score: grad.score,
      recommendedSl: rec.sl,
      recommendedTp: rec.tp,
      highWaterMarkPct: 0,
    };

    const pumpLabel = pumpWarning ? ' | PUMP WARNING: vol>5x liq + 1h>100%' : '';
    execCounter++;
    const execEvent: ExecutionEvent = {
      id: `exec-${Date.now()}-${execCounter}`,
      type: 'snipe',
      symbol: grad.symbol,
      mint: grad.mint,
      amount: positionSolFinal,
      price: grad.price_usd,
      reason: `Score ${grad.score} | SL ${rec.sl}% TP ${rec.tp}% Trail ${rec.trail}% | ${effectiveConviction.toFixed(1)}x [${convFactors.join(',')}] | ${rec.reasoning}${pumpLabel}`,
      timestamp: Date.now(),
    };

    const newSniped = new Set(snipedMints);
    newSniped.add(grad.mint);

    set((s) => ({
      positions: [newPosition, ...s.positions],
      executionLog: [execEvent, ...s.executionLog].slice(0, 200),
      snipedMints: newSniped,
      budget: { ...s.budget, spent: s.budget.spent + positionSolFinal },
    }));
  },

  selectedMint: null,
  setSelectedMint: (mint) => set({ selectedMint: mint }),

  executionLog: [],
  addExecution: (event) => set((s) => ({
    executionLog: [event, ...s.executionLog].slice(0, 200),
  })),

  totalPnl: 0,
  winCount: 0,
  lossCount: 0,
  totalTrades: 0,

  // Circuit Breaker
  circuitBreaker: {
    tripped: false,
    reason: '',
    trippedAt: 0,
    consecutiveLosses: 0,
    dailyLossSol: 0,
    dailyResetAt: Date.now() + 86_400_000,
  },
  resetCircuitBreaker: () => set({
    circuitBreaker: {
      tripped: false,
      reason: '',
      trippedAt: 0,
      consecutiveLosses: 0,
      dailyLossSol: 0,
      dailyResetAt: Date.now() + 86_400_000,
    },
  }),

  resetSession: () => set({
    positions: [],
    executionLog: [],
    snipedMints: new Set(),
    skippedMints: new Set(),
    selectedMint: null,
    budget: { budgetSol: 0.1, authorized: false, spent: 0 },
    totalPnl: 0,
    winCount: 0,
    lossCount: 0,
    totalTrades: 0,
    circuitBreaker: {
      tripped: false,
      reason: '',
      trippedAt: 0,
      consecutiveLosses: 0,
      dailyLossSol: 0,
      dailyResetAt: Date.now() + 86_400_000,
    },
  }),
    }),
    {
      name: 'jarvis-sniper-store',
      storage: createJSONStorage(() => {
        // SSR safety: localStorage only exists in browser
        if (typeof window === 'undefined') {
          return {
            getItem: () => null,
            setItem: () => {},
            removeItem: () => {},
          };
        }
        return localStorage;
      }),
      // Only persist positions, config, budget, execution log, and stats
      // snipedMints (Set) requires serialization
      partialize: (state) => ({
        positions: state.positions,
        config: state.config,
        tradeSignerMode: state.tradeSignerMode,
        sessionWalletPubkey: state.sessionWalletPubkey,
        budget: state.budget,
        executionLog: state.executionLog.slice(0, 50), // Keep last 50
        snipedMintsArray: Array.from(state.snipedMints), // Set → Array for JSON
        circuitBreaker: state.circuitBreaker,
        totalPnl: state.totalPnl,
        winCount: state.winCount,
        lossCount: state.lossCount,
        totalTrades: state.totalTrades,
      }),
      // Rehydrate: convert snipedMintsArray back to Set
      onRehydrateStorage: () => (state) => {
        if (!state) return;

        // Migrate config defaults (new fields, etc.)
        state.config = { ...DEFAULT_CONFIG, ...(state.config as SniperConfig | undefined) };

        // Positions may contain non-persistable transient fields (Phantom prompts, etc.). Reset them.
        if (Array.isArray(state.positions)) {
          state.positions = state.positions.map((p) => ({
            ...p,
            recommendedSl: (p as any).recommendedSl ?? DEFAULT_CONFIG.stopLossPct,
            recommendedTp: (p as any).recommendedTp ?? DEFAULT_CONFIG.takeProfitPct,
            highWaterMarkPct: (p as any).highWaterMarkPct ?? 0,
            // Derived / in-flight state should not survive reloads.
            isClosing: false,
            exitPending: undefined,
          }));
        }

        const arr = (state as unknown as Record<string, unknown>).snipedMintsArray;
        if (Array.isArray(arr)) {
          state.snipedMints = new Set(arr as string[]);
        }

        // If session signing was selected but the pubkey is missing, fall back safely.
        if (state.tradeSignerMode === 'session' && !state.sessionWalletPubkey) {
          state.tradeSignerMode = 'phantom';
        }
      },
    },
  ),
);
