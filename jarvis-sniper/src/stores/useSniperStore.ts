import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { BagsGraduation } from '@/lib/bags-api';

export type StrategyMode = 'conservative' | 'aggressive';
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
  // ── Backtest v2 Winners ──
  {
    id: 'surge_hunter',
    name: 'SURGE HUNTER (RECOMMENDED)',
    description: 'V2 Best: Vol surge >=2.5x, SL35/TP150/Trail15, Liq>=$5K, Safety>=40',
    winRate: '61.8% (209% PnL)',
    trades: 0,
    config: {
      stopLossPct: 35, takeProfitPct: 150, trailingStopPct: 15,
      minLiquidityUsd: 5000, minScore: 40, minVolLiqRatio: 2.5,
      maxTokenAgeHours: 24, tradingHoursGate: false, strategyMode: 'aggressive',
    },
  },
  {
    id: 'fresh_degen',
    name: 'FRESH DEGEN',
    description: 'V2 Highest WR: Fresh tokens <24h, SL40/TP200/Trail18, Liq>=$3K',
    winRate: '73.9% (193% PnL, 23T)',
    trades: 23,
    config: {
      stopLossPct: 40, takeProfitPct: 200, trailingStopPct: 18,
      minLiquidityUsd: 3000, minScore: 35, maxTokenAgeHours: 24,
      minVolLiqRatio: 1.0, tradingHoursGate: false, strategyMode: 'aggressive',
    },
  },
  {
    id: 'pumpswap_alpha',
    name: 'PUMPSWAP ALPHA',
    description: 'V2 Risk-Adj: Lowest drawdown (1.96%), SL30/TP120/Trail12, Liq>=$10K',
    winRate: '50.0% (75% PnL, Sharpe 0.58)',
    trades: 0,
    config: {
      stopLossPct: 30, takeProfitPct: 120, trailingStopPct: 12,
      minLiquidityUsd: 10000, minScore: 45, minVolLiqRatio: 1.5,
      maxTokenAgeHours: 200, tradingHoursGate: true, strategyMode: 'conservative',
    },
  },
  // ── Legacy v1 Presets ──
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
  /** Strategy mode: conservative (20/60) vs aggressive (20/100 "let it ride") */
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

/** Per-token SL/TP recommendation — updated with backtest v2 winners.
 *
 * Backtest v2 top strategies:
 * - SURGE_HUNTER: SL35/TP150/Trail15 — 61.8% WR, 209% PnL, Fitness 0.822
 * - FRESH_DEGEN: SL40/TP200/Trail18 — 73.9% WR, 193% PnL
 * - PUMPSWAP_ALPHA: SL30/TP120/Trail12 — 50% WR, Sharpe 0.58, 1.96% DD
 *
 * Default recommendation now uses SURGE_HUNTER as base (best composite fitness).
 * Adjustments layer on top based on token characteristics.
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

  // V2 Strategy Auto-Selection based on token profile
  const isFresh = ageHours > 0 && ageHours < 24;
  const hasVolumeSurge = volLiqRatio >= 2.5;
  const isHighLiq = liq >= 10000;

  // SURGE_HUNTER base (best composite fitness 0.822) — default for all tokens
  let sl = 35;
  let tp = 150;
  let trail = 15;
  let reasoning = 'V2 SURGE_HUNTER base (SL35/TP150/Trail15)';

  // Override: FRESH_DEGEN for very young tokens (highest raw WR at 73.9%)
  if (isFresh && mode === 'aggressive') {
    sl = 40;
    tp = 200;
    trail = 18;
    reasoning = 'V2 FRESH_DEGEN (SL40/TP200/Trail18) — token <24h old';
  }
  // Override: PUMPSWAP_ALPHA for high-liq conservative (lowest drawdown 1.96%)
  else if (isHighLiq && mode === 'conservative') {
    sl = 30;
    tp = 120;
    trail = 12;
    reasoning = 'V2 PUMPSWAP_ALPHA (SL30/TP120/Trail12) — high liq, risk-adjusted';
  }

  // Liquidity-based adjustments (layered on v2 base)
  if (liq > 200000) {
    sl -= 5;
    reasoning += ', high liq ($200K+) — tighter SL';
  } else if (liq < 3000) {
    sl += 5; tp -= 20;
    reasoning += ', micro liq — wider SL, lower TP';
  }

  // Strong momentum = extend TP (let winners run even more)
  if (priceChange1h > 20) {
    tp += 20;
    reasoning += ', strong momentum (+20%+1h)';
  } else if (priceChange1h > 10) {
    tp += 10;
    reasoning += ', good momentum';
  }

  // Volume surge bonus — key SURGE_HUNTER signal
  if (hasVolumeSurge) {
    tp += 15;
    reasoning += `, vol surge (V/L ${volLiqRatio.toFixed(1)}x)`;
  }

  // Young + active = higher potential
  if (ageHours < 24 && buySellRatio >= 1.2 && buySellRatio <= 2.5) {
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
  const GOOD_HOURS = [14, 20];
  if (GOOD_HOURS.includes(nowUtcHour)) {
    sl -= 3;
    tp += 15;
    reasoning += `, TOD boost (${nowUtcHour}h)`;
  }

  // Adaptive Trailing Stop Adjustment
  // High momentum = tighter trail (fast movers reverse quickly)
  // Low momentum = wider trail (give room to develop)
  if (priceChange1h > 50) {
    trail = Math.max(5, trail - 5);
    reasoning += ', tighter trail (high momentum)';
  } else if (priceChange1h <= 5) {
    trail = Math.min(20, trail + 3);
    reasoning += ', wider trail (low momentum)';
  }

  // Clamp values — v2 allows wider ranges (SL up to 45, TP up to 250 aggressive)
  sl = Math.max(10, Math.min(45, Math.round(sl)));
  tp = Math.max(30, Math.min(mode === 'aggressive' ? 250 : 150, Math.round(tp)));
  trail = Math.max(5, Math.min(20, Math.round(trail)));

  return { sl, tp, trail, reasoning };
}

/** Conviction-weighted position sizing — scale bets by signal quality.
 * Returns 0.5x - 2.0x multiplier on base position size.
 * Updated with backtest v2 insights:
 *   Volume surge (V/L >= 2.5) is the #1 alpha signal (SURGE_HUNTER fitness 0.822).
 *   Fresh tokens (<24h) with activity = highest raw WR (73.9%).
 *   Feature importance: Price Change 1h (244.5%), Vol/Liq (77.6%), Token Age, B/S ratio.
 */
export function getConvictionMultiplier(
  grad: BagsGraduation & Record<string, any>,
): { multiplier: number; factors: string[] } {
  let score = 0;
  const factors: string[] = [];

  // Factor 1: Price Change 1h — strongest predictor (244.5% power)
  const change1h = grad.price_change_1h || 0;
  if (change1h > 200) { score += 0.4; factors.push(`1h+${Math.round(change1h)}%`); }
  else if (change1h > 50) { score += 0.2; factors.push(`1h+${Math.round(change1h)}%`); }

  // Factor 2: Vol/Liq ratio — V2 key signal (SURGE_HUNTER requires >= 2.5)
  const liq = grad.liquidity || 0;
  const vol24h = grad.volume_24h || 0;
  const volLiq = liq > 0 ? vol24h / liq : 0;
  if (volLiq >= 2.5) {
    // Volume surge — SURGE_HUNTER core signal. Highest conviction boost.
    score += 0.5; factors.push(`VOL_SURGE ${volLiq.toFixed(1)}x`);
  } else if (volLiq > 3.0) { score += 0.3; factors.push(`V/L ${volLiq.toFixed(1)}`); }
  else if (volLiq > 1.0) { score += 0.2; factors.push(`V/L ${volLiq.toFixed(1)}`); }

  // Factor 3: Fresh token bonus (V2: FRESH_DEGEN — 73.9% WR on tokens <24h)
  const ageHours = grad.age_hours || 0;
  if (ageHours > 0 && ageHours < 24) {
    score += 0.3; factors.push(`fresh ${Math.round(ageHours)}h`);
  } else if (ageHours > 0 && ageHours < 100) {
    score += 0.1; factors.push(`young ${Math.round(ageHours)}h`);
  }

  // Factor 4: Liquidity tier — higher = safer bet
  if (liq > 200000) { score += 0.2; factors.push('$200K+'); }
  else if (liq > 100000) { score += 0.1; factors.push('$100K+'); }

  // Factor 5: Good hour (OHLCV best hours: 4=60%, 11=57%, 21=52%)
  const nowUtcHour = new Date().getUTCHours();
  if ([4, 11, 21].includes(nowUtcHour)) { score += 0.2; factors.push(`hr${nowUtcHour}`); }
  else if (nowUtcHour === 8) { score += 0.1; factors.push('hr8'); }

  // Factor 6: B/S sweet spot (1.2-2.0 = optimal in backtest)
  const buys = grad.txn_buys_1h || 0;
  const sells = grad.txn_sells_1h || 0;
  const bsRatio = sells > 0 ? buys / sells : buys;
  if (buys + sells > 10 && bsRatio >= 1.2 && bsRatio <= 2.0) {
    score += 0.1; factors.push(`BS${bsRatio.toFixed(1)}`);
  }

  // Factor 7: Combined surge + fresh = strongest V2 combo
  if (volLiq >= 2.5 && ageHours > 0 && ageHours < 24) {
    score += 0.2; factors.push('SURGE+FRESH');
  }

  // Negative Factors (risk penalties)

  // Penalty: Very high price change (>200%) — pump risk
  if (change1h > 200) {
    score -= 0.2; factors.push('pump risk');
  }

  // Penalty: Very high B/S ratio (>3.0) — potential manipulation
  if (bsRatio > 3.0 && buys + sells > 5) {
    score -= 0.15; factors.push('high B/S');
  }

  // Base 0.5 + factors -> clamp to [0.5, 2.0]
  const multiplier = Math.max(0.5, Math.min(2.0, 0.5 + score));
  return { multiplier, factors };
}

const DEFAULT_CONFIG: SniperConfig = {
  stopLossPct: 35,      // V2 SURGE_HUNTER: SL35 (best composite fitness 0.822)
  takeProfitPct: 150,   // V2 SURGE_HUNTER: TP150 (209% PnL, PF 20.0)
  trailingStopPct: 15,  // V2 SURGE_HUNTER: Trail15 (locks gains without choking runners)
  maxPositionSol: 0.1,
  maxConcurrentPositions: 10,
  minScore: 40,         // V2 SURGE_HUNTER: safety threshold 0.40 -> minScore 40
  minLiquidityUsd: 5000,    // V2 SURGE_HUNTER: $5K min (wider net for fresh tokens)
  autoSnipe: false,
  useJito: true,
  slippageBps: 150,
  strategyMode: 'aggressive', // V2 SURGE_HUNTER uses aggressive mode for wider TP range
  maxPositionAgeHours: 4,  // Auto-close stale positions after 4h to free capital
  useRecommendedExits: true,
  // V2 quality gates tuned to SURGE_HUNTER params
  minMomentum1h: 0,        // SURGE_HUNTER relies on vol surge, not momentum filter
  maxTokenAgeHours: 24,    // V2: fresh tokens (<24h) have 188% more alpha
  minVolLiqRatio: 2.5,     // V2 SURGE_HUNTER: volume surge >= 2.5x is the core signal
  tradingHoursGate: false, // SURGE_HUNTER trades any hour (volume surge overrides TOD)
  minAgeMinutes: 2,        // Don't snipe tokens that graduated < 2 min ago (post-grad dumps)
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
  activePreset: 'surge_hunter',
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
  setStrategyMode: (mode) => set((s) => ({
    config: {
      ...s.config,
      strategyMode: mode,
      // V2: Aggressive -> SURGE_HUNTER (35/150/15), Conservative -> PUMPSWAP_ALPHA (30/120/12)
      stopLossPct: mode === 'aggressive' ? 35 : 30,
      takeProfitPct: mode === 'aggressive' ? 150 : 120,
      trailingStopPct: mode === 'aggressive' ? 15 : 12,
    },
  })),
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
