import { create } from 'zustand';
import type { BagsGraduation } from '@/lib/bags-api';

export interface SniperConfig {
  stopLossPct: number;
  takeProfitPct: number;
  trailingStopPct: number;
  maxPositionSol: number;
  maxConcurrentPositions: number;
  minScore: number;
  autoSnipe: boolean;
  useJito: boolean;
  slippageBps: number;
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
  status: 'open' | 'tp_hit' | 'sl_hit' | 'closed';
  /** Lock flag — prevents duplicate sell attempts while tx is in-flight */
  isClosing?: boolean;
  score: number;
  recommendedSl: number;
  recommendedTp: number;
}

export interface ExecutionEvent {
  id: string;
  type: 'snipe' | 'tp_exit' | 'sl_exit' | 'manual_exit' | 'error' | 'skip';
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

/** Per-token SL/TP recommendation based on score, liquidity, volatility */
export function getRecommendedSlTp(grad: BagsGraduation & Record<string, any>): TokenRecommendation {
  const score = grad.score || 0;
  const liq = grad.liquidity || 0;
  const priceChange1h = grad.price_change_1h || 0;
  const volume = grad.volume_24h || 0;

  let sl: number;
  let tp: number;
  let reasoning: string;

  // Base SL/TP from score tier
  if (score >= 80) {
    sl = 15; tp = 60;
    reasoning = 'High conviction — tight SL, wide TP';
  } else if (score >= 65) {
    sl = 20; tp = 40;
    reasoning = 'Strong setup — moderate risk/reward';
  } else if (score >= 50) {
    sl = 25; tp = 30;
    reasoning = 'Moderate — balanced SL/TP';
  } else {
    sl = 30; tp = 20;
    reasoning = 'Speculative — quick in/out';
  }

  // Adjust for liquidity — high liquidity = tighter SL (less slippage risk)
  if (liq > 200000) { sl -= 3; tp += 5; }
  else if (liq > 50000) { sl -= 1; tp += 2; }
  else if (liq < 5000) { sl += 5; tp -= 5; reasoning += ', low liq caution'; }

  // Adjust for momentum — strong upward = wider TP
  if (priceChange1h > 20) { tp += 15; reasoning += ', strong momentum'; }
  else if (priceChange1h > 5) { tp += 5; }
  else if (priceChange1h < -10) { sl += 5; tp -= 5; reasoning += ', declining'; }

  // Adjust for volume — high volume = more reliable move
  if (volume > 500000) { tp += 10; sl -= 2; }
  else if (volume > 100000) { tp += 5; }

  // Clamp values
  sl = Math.max(5, Math.min(50, Math.round(sl)));
  tp = Math.max(10, Math.min(150, Math.round(tp)));

  return { sl, tp, reasoning };
}

const DEFAULT_CONFIG: SniperConfig = {
  stopLossPct: 8,
  takeProfitPct: 35,
  trailingStopPct: 4,
  maxPositionSol: 0.1,
  maxConcurrentPositions: 10,
  minScore: 50,
  autoSnipe: false,
  useJito: true,
  slippageBps: 150,
};

/** Monotonic counter to prevent duplicate keys when multiple snipes fire in same ms */
let execCounter = 0;

interface SniperState {
  // Config
  config: SniperConfig;
  setConfig: (partial: Partial<SniperConfig>) => void;
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
  closePosition: (id: string, status: 'tp_hit' | 'sl_hit' | 'closed', txHash?: string) => void;

  // Snipe action — creates position + logs execution
  snipeToken: (grad: BagsGraduation & Record<string, any>) => void;

  // Track which tokens were already sniped (prevents duplicates)
  snipedMints: Set<string>;

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

export const useSniperStore = create<SniperState>((set, get) => ({
  config: DEFAULT_CONFIG,
  setConfig: (partial) => set((s) => ({ config: { ...s.config, ...partial } })),
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
      return { ...p, currentPrice: newPrice, pnlPercent, pnlSol };
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
    const exitType = status === 'tp_hit' ? 'tp_exit' : status === 'sl_hit' ? 'sl_exit' : 'manual_exit';
    const execEvent: ExecutionEvent = {
      id: `exec-${Date.now()}-${execCounter}`,
      type: exitType,
      symbol: pos.symbol,
      mint: pos.mint,
      amount: pos.solInvested,
      pnlPercent: pos.pnlPercent,
      txHash,
      timestamp: Date.now(),
      reason: `${status.replace('_', ' ').toUpperCase()} at ${pos.pnlPercent.toFixed(1)}%`,
    };

    set((s) => ({
      positions: s.positions.map((p) => p.id === id ? { ...p, status, isClosing: false } : p),
      executionLog: [execEvent, ...s.executionLog].slice(0, 200),
      totalPnl: s.totalPnl + pos.pnlSol,
      winCount: exitType === 'tp_exit' ? s.winCount + 1 : s.winCount,
      lossCount: exitType === 'sl_exit' ? s.lossCount + 1 : s.lossCount,
      totalTrades: s.totalTrades + 1,
      budget: { ...s.budget, spent: Math.max(0, s.budget.spent - pos.solInvested) },
    }));
  },

  snipedMints: new Set(),

  snipeToken: (grad) => {
    const state = get();
    const { config, positions, snipedMints, budget } = state;

    // Guard: budget not authorized
    if (!budget.authorized) return;

    // Guard: already sniped
    if (snipedMints.has(grad.mint)) return;

    // Guard: at capacity
    const openCount = positions.filter(p => p.status === 'open').length;
    if (openCount >= config.maxConcurrentPositions) return;

    // Guard: insufficient budget remaining
    const remaining = budget.budgetSol - budget.spent;
    const positionSol = Math.min(config.maxPositionSol, remaining);
    if (positionSol < 0.001) return; // minimum viable position

    // Get per-token recommended SL/TP
    const rec = getRecommendedSlTp(grad);

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
    };

    execCounter++;
    const execEvent: ExecutionEvent = {
      id: `exec-${Date.now()}-${execCounter}`,
      type: 'snipe',
      symbol: grad.symbol,
      mint: grad.mint,
      amount: positionSol,
      price: grad.price_usd,
      reason: `Score ${grad.score} | SL ${rec.sl}% TP ${rec.tp}% | ${rec.reasoning}`,
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
    totalPnl: event.pnlPercent != null ? s.totalPnl + (event.pnlPercent > 0 ? event.amount ?? 0 : -(event.amount ?? 0)) : s.totalPnl,
    winCount: event.type === 'tp_exit' ? s.winCount + 1 : s.winCount,
    lossCount: event.type === 'sl_exit' ? s.lossCount + 1 : s.lossCount,
    totalTrades: ['tp_exit', 'sl_exit', 'manual_exit'].includes(event.type) ? s.totalTrades + 1 : s.totalTrades,
  })),

  totalPnl: 0,
  winCount: 0,
  lossCount: 0,
  totalTrades: 0,

  resetSession: () => set({
    positions: [],
    executionLog: [],
    snipedMints: new Set(),
    selectedMint: null,
    budget: { budgetSol: 0.1, authorized: false, spent: 0 },
    totalPnl: 0,
    winCount: 0,
    lossCount: 0,
    totalTrades: 0,
  }),
}));
