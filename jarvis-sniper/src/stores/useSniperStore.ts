import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { BagsGraduation } from '@/lib/bags-api';

export type StrategyMode = 'conservative' | 'aggressive';

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
    id: 'momentum',
    name: 'MOMENTUM',
    description: 'Score≥50 + V/L≥3 + B/S≥1.5',
    winRate: '75% (13T)',
    trades: 13,
    config: { stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8, minLiquidityUsd: 0, minScore: 50, strategyMode: 'conservative' },
  },
  {
    id: 'insight_j',
    name: 'INSIGHT-J',
    description: 'Liq≥$25K + Age<100h + 1h↑',
    winRate: '86% (7T)',
    trades: 7,
    config: { stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8, minLiquidityUsd: 25000, strategyMode: 'conservative' },
  },
  {
    id: 'hot',
    name: 'HOT',
    description: 'Score≥60 + V/L≥2 + Liq≥$10K',
    winRate: '49% (54T)',
    trades: 54,
    config: { stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8, minLiquidityUsd: 10000, minScore: 60, strategyMode: 'conservative' },
  },
  {
    id: 'hybrid_b',
    name: 'HYBRID-B v5',
    description: 'Balanced default — Liq≥$40K',
    winRate: '100% (10T)',
    trades: 10,
    config: { stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8, minLiquidityUsd: 40000, strategyMode: 'conservative' },
  },
  {
    id: 'let_it_ride',
    name: 'LET IT RIDE',
    description: '20/100 + 5% trail — max gains',
    winRate: '100% (10T)',
    trades: 10,
    config: { stopLossPct: 20, takeProfitPct: 100, trailingStopPct: 5, minLiquidityUsd: 40000, strategyMode: 'aggressive' },
  },
  {
    id: 'insight_i',
    name: 'INSIGHT-I',
    description: 'Liq≥$50K + Age<200h + B/S 1-3',
    winRate: '60% (14T)',
    trades: 14,
    config: { stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8, minLiquidityUsd: 50000, strategyMode: 'conservative' },
  },
];

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
  /** Trailing stop: highest P&L% ever reached (high water mark) */
  highWaterMarkPct: number;
}

export interface ExecutionEvent {
  id: string;
  type: 'snipe' | 'exit_pending' | 'tp_exit' | 'sl_exit' | 'manual_exit' | 'error' | 'skip';
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

  // Base SL/TP depends on strategy mode
  let sl = 20;
  let tp = mode === 'aggressive' ? 100 : 60;
  let reasoning = mode === 'aggressive' ? 'Aggressive 20/100 base' : 'Conservative 20/60 base';

  // Liquidity tier adjustments (high liq = less slippage, can tighten SL)
  if (liq > 200000) {
    sl = 15;
    reasoning = (mode === 'aggressive' ? 'Aggressive' : 'Conservative') + ', high liq ($200K+) — tighter SL';
  } else if (liq > 100000) {
    sl = 18;
    reasoning = (mode === 'aggressive' ? 'Aggressive' : 'Conservative') + ', strong liq ($100K+)';
  }
  // Low liquidity = wider SL to absorb spread
  else if (liq < 25000) {
    sl = 25; tp = mode === 'aggressive' ? 80 : 50;
    reasoning = (mode === 'aggressive' ? 'Aggressive' : 'Conservative') + ', low liq — wider SL';
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

  // Clamp values — aggressive allows higher TP cap
  sl = Math.max(10, Math.min(30, Math.round(sl)));
  tp = Math.max(30, Math.min(mode === 'aggressive' ? 200 : 120, Math.round(tp)));

  return { sl, tp, reasoning };
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

  // Factor 5: B/S sweet spot (1.2–2.0 = optimal in backtest)
  const buys = grad.txn_buys_1h || 0;
  const sells = grad.txn_sells_1h || 0;
  const bsRatio = sells > 0 ? buys / sells : buys;
  if (buys + sells > 10 && bsRatio >= 1.2 && bsRatio <= 2.0) {
    score += 0.1; factors.push(`BS${bsRatio.toFixed(1)}`);
  }

  // Base 0.5 + factors → clamp to [0.5, 2.0]
  const multiplier = Math.max(0.5, Math.min(2.0, 0.5 + score));
  return { multiplier, factors };
}

const DEFAULT_CONFIG: SniperConfig = {
  stopLossPct: 20,      // Backtested: wider SL dramatically improves win rate
  takeProfitPct: 60,    // Backtested: 20/60 = 87.5% WR with HYBRID_B v4 config
  trailingStopPct: 8,   // 928-token OHLCV: 8% trail = 94.1% WR, PF 1533 (10% = 100% WR)
  maxPositionSol: 0.1,
  maxConcurrentPositions: 10,
  minScore: 0,          // Backtested: best configs use liq+momentum, not score
  // Live feeds often show many candidates in the $40-50K range; 40K trades more while still filtering junk.
  minLiquidityUsd: 40000,
  autoSnipe: false,
  useJito: true,
  slippageBps: 150,
  strategyMode: 'conservative',
  maxPositionAgeHours: 4,  // Auto-close stale positions after 4h to free capital
  useRecommendedExits: true,
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
  /** Close a position with proper status and stats tracking */
  closePosition: (id: string, status: 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired' | 'closed', txHash?: string) => void;

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

  // Reset — clears positions, executions, stats, sniped mints
  resetSession: () => void;
}

export const useSniperStore = create<SniperState>()(
  persist(
    (set, get) => ({
  config: DEFAULT_CONFIG,
  activePreset: 'hybrid_b',
  setConfig: (partial) => set((s) => ({ config: { ...s.config, ...partial }, skippedMints: new Set() })),
  loadPreset: (presetId) => {
    const preset = STRATEGY_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    set((s) => ({
      activePreset: presetId,
      config: { ...s.config, ...preset.config },
      skippedMints: new Set(), // Re-evaluate with new filter params
    }));
  },
  setStrategyMode: (mode) => set((s) => ({
    config: {
      ...s.config,
      strategyMode: mode,
      // Auto-adjust base SL/TP/trail to match 928-token OHLCV optimums
      takeProfitPct: mode === 'aggressive' ? 100 : 60,
      stopLossPct: 20,  // Both modes use 20% SL
      trailingStopPct: mode === 'aggressive' ? 10 : 8,  // Aggressive: 10% (100% WR), Conservative: 8% (94.1% WR)
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
  closePosition: (id, status, txHash) => {
    const state = get();
    const pos = state.positions.find((p) => p.id === id);
    if (!pos) return;

    execCounter++;
    // Trail stop above entry is a win, below entry is a loss
    const isTrailWin = status === 'trail_stop' && pos.pnlPercent >= 0;
    const isExpiredWin = status === 'expired' && pos.pnlPercent >= 0;
    const exitType = status === 'tp_hit' ? 'tp_exit'
      : status === 'trail_stop' ? (isTrailWin ? 'tp_exit' : 'sl_exit')
      : status === 'sl_hit' ? 'sl_exit'
      : status === 'expired' ? (isExpiredWin ? 'tp_exit' : 'sl_exit')
      : 'manual_exit';
    const execEvent: ExecutionEvent = {
      id: `exec-${Date.now()}-${execCounter}`,
      type: exitType,
      symbol: pos.symbol,
      mint: pos.mint,
      amount: pos.solInvested,
      pnlPercent: pos.pnlPercent,
      txHash,
      timestamp: Date.now(),
      reason: `${status === 'trail_stop' ? 'TRAIL STOP' : status === 'expired' ? 'EXPIRED (age limit)' : status.replace('_', ' ').toUpperCase()} at ${pos.pnlPercent.toFixed(1)}%`,
    };

    set((s) => ({
      positions: s.positions.map((p) => p.id === id ? { ...p, status, isClosing: false, exitPending: undefined } : p),
      executionLog: [execEvent, ...s.executionLog].slice(0, 200),
      totalPnl: s.totalPnl + pos.pnlSol,
      winCount: exitType === 'tp_exit' ? s.winCount + 1 : s.winCount,
      lossCount: exitType === 'sl_exit' ? s.lossCount + 1 : s.lossCount,
      totalTrades: s.totalTrades + 1,
      budget: { ...s.budget, spent: Math.max(0, s.budget.spent - pos.solInvested) },
    }));
  },

  snipedMints: new Set(),
  skippedMints: new Set(),

  snipeToken: (grad) => {
    const state = get();
    const { config, positions, snipedMints, skippedMints, budget } = state;

    // Guard: budget not authorized
    if (!budget.authorized) return;

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

    // ═══ INSIGHT-DRIVEN FILTERS (backtested: HYBRID_B 91.7% WR) ═══
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

    // Filter 1: Minimum liquidity threshold (USD) — backtested default: $50K
    const liq = grad.liquidity || 0;
    if (liq < config.minLiquidityUsd) {
      logSkipOnce(`Low liquidity: $${Math.round(liq).toLocaleString('en-US')} < $${Math.round(config.minLiquidityUsd).toLocaleString('en-US')}`);
      return;
    }

    // Filter 2: Buy/Sell ratio 1.0-3.0 (sweet spot — extreme = pump signal)
    const buys = grad.txn_buys_1h || 0;
    const sells = grad.txn_sells_1h || 0;
    const bsRatio = sells > 0 ? buys / sells : buys;
    if (buys + sells > 10 && (bsRatio < 1.0 || bsRatio > 3.0)) {
      logSkipOnce(`B/S ratio ${bsRatio.toFixed(1)} outside 1.0-3.0 range`);
      return;
    }

    // Filter 3: Age < 500h (younger tokens = higher alpha)
    const ageHours = grad.age_hours || 0;
    if (ageHours > 500) {
      logSkipOnce(`Too old: ${Math.round(ageHours)}h > 500h limit`);
      return;
    }

    // Filter 4: Positive 1h momentum (288% predictive power in backtest)
    const change1h = grad.price_change_1h || 0;
    if (change1h < 0) {
      logSkipOnce(`Negative 1h momentum: ${change1h.toFixed(1)}%`);
      return;
    }

    // TOD note: removed hard block — OHLCV backtest had too few samples (16/200 tokens).
    // TOD is now handled as a soft penalty in getConvictionMultiplier() instead.

    // Filter 6: Vol/Liq ratio ≥ 0.5 (8x edge: 40.6% upside vs 4.9% for <0.5)
    const vol24h = grad.volume_24h || 0;
    const volLiqRatio = liq > 0 ? vol24h / liq : 0;
    if (vol24h > 0 && volLiqRatio < 0.5) {
      logSkipOnce(`Low Vol/Liq: ${volLiqRatio.toFixed(2)} < 0.5 (8x edge)`);
      return;
    }

    // ═══ All insight filters passed — proceed with snipe ═══

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
      amount: positionSol / (grad.price_usd || 1),
      solInvested: positionSol,
      pnlPercent: 0,
      pnlSol: 0,
      entryTime: Date.now(),
      status: 'open',
      score: grad.score,
      recommendedSl: rec.sl,
      recommendedTp: rec.tp,
      highWaterMarkPct: 0,
    };

    execCounter++;
    const execEvent: ExecutionEvent = {
      id: `exec-${Date.now()}-${execCounter}`,
      type: 'snipe',
      symbol: grad.symbol,
      mint: grad.mint,
      amount: positionSol,
      price: grad.price_usd,
      reason: `Score ${grad.score} | SL ${rec.sl}% TP ${rec.tp}% | ${conviction.toFixed(1)}x [${convFactors.join(',')}] | ${rec.reasoning}`,
      timestamp: Date.now(),
    };

    const newSniped = new Set(snipedMints);
    newSniped.add(grad.mint);

    set((s) => ({
      positions: [newPosition, ...s.positions],
      executionLog: [execEvent, ...s.executionLog].slice(0, 200),
      snipedMints: newSniped,
      budget: { ...s.budget, spent: s.budget.spent + positionSol },
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
        budget: state.budget,
        executionLog: state.executionLog.slice(0, 50), // Keep last 50
        snipedMintsArray: Array.from(state.snipedMints), // Set → Array for JSON
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
      },
    },
  ),
);
