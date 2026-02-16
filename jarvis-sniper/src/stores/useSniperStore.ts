import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { BagsGraduation } from '@/lib/bags-api';
import { isLegacyRecoveredPositionId, isReliableTradeForStats, sanitizePnlPercent } from '@/lib/position-reliability';
import {
  applyDiscountedOutcome,
  type StrategyBelief,
} from '@/lib/strategy-selector';
import type { StrategyOverrideSnapshot } from '@/lib/autonomy/types';
import { postTradeTelemetry } from '@/lib/autonomy/trade-telemetry-client';
import { STRATEGY_SEED_META } from '@/lib/strategy-seed-meta';

export type StrategyMode = 'conservative' | 'balanced' | 'aggressive';
export type TradeSignerMode = 'phantom' | 'session';
export type AutomationState = 'idle' | 'scanning' | 'executing_buy' | 'cooldown' | 'closing_all' | 'paused' | 'tripped';

export type AssetType = 'memecoin' | 'xstock' | 'prestock' | 'index' | 'bluechip' | 'bags' | 'established';
export type PendingTxStatus = 'submitted' | 'settling' | 'confirmed' | 'failed' | 'unresolved';
export type PendingTxKind = 'buy' | 'sell' | 'fund' | 'sweep';

export interface PendingTxRecord {
  signature: string;
  kind: PendingTxKind;
  mint?: string;
  submittedAt: number;
  lastCheckedAt?: number;
  status: PendingTxStatus;
  error?: string;
  sourcePage?: string;
}

export interface ImportedHoldingMemoEntry {
  wallet: string;
  mint: string;
  amountLamports: string;
  importedAt: number;
  lastSeenAt: number;
}

export interface RecentlyClosedMintMemoEntry {
  wallet: string;
  mint: string;
  closedAt: number;
  /** Token amount at (or just before) close, as raw lamports string when known. */
  amountLamports?: string;
  /** UI amount at (or just before) close, best-effort fallback when lamports unavailable. */
  uiAmount?: number;
}

const MINT_REENTRY_COOLDOWN_MS = 15 * 60 * 1000;
const RECENTLY_CLOSED_RETENTION_MS = 6 * 60 * 60 * 1000; // keep small + bounded for UI dust suppression

function normalizeMint(mint: string | undefined | null): string {
  return String(mint || '').trim();
}

function normalizeWalletForKey(wallet: string | null | undefined): string {
  return String(wallet || '').trim().toLowerCase();
}

function computeDynamicMinBalanceGuard(budgetSol: number, configuredGuardSol: number): number {
  const budget = Number.isFinite(budgetSol) ? budgetSol : 0;
  const configured = Number.isFinite(configuredGuardSol) ? configuredGuardSol : 0;
  const scaled = budget * 0.10; // 10% of budget
  const floor = 0.005; // 0.005 SOL floor
  // Never exceed configured guard; only reduce it for small budgets.
  return Math.max(floor, Math.min(configured, scaled));
}

export function buildMintCooldownKey(
  assetType: AssetType | undefined,
  walletAddress: string | null | undefined,
  mint: string | null | undefined,
): string {
  const asset = String(assetType || 'memecoin').trim().toLowerCase();
  const wallet = normalizeWalletForKey(walletAddress) || 'unknown';
  const normalizedMint = normalizeMint(mint).toLowerCase();
  return `${asset}:${wallet}:${normalizedMint}`;
}

function buildImportedHoldingMemoKey(wallet: string, mint: string): string {
  return `${normalizeWalletForKey(wallet)}:${normalizeMint(mint).toLowerCase()}`;
}

function buildRecentlyClosedMintKey(wallet: string, mint: string): string {
  return buildImportedHoldingMemoKey(wallet, mint);
}

function dedupeGraduationsByMint(input: BagsGraduation[]): BagsGraduation[] {
  const byMint = new Map<string, BagsGraduation>();
  for (const g of input) {
    const mint = normalizeMint(g?.mint);
    if (!mint) continue;
    const candidate: BagsGraduation = { ...g, mint };
    const prev = byMint.get(mint);
    if (!prev) {
      byMint.set(mint, candidate);
      continue;
    }
    // Keep the better card when the same mint appears from multiple sources.
    const prevScore = Number(prev.score || 0);
    const candScore = Number(candidate.score || 0);
    const prevTs = Number(prev.graduation_time || 0);
    const candTs = Number(candidate.graduation_time || 0);
    const pick = candScore > prevScore || (candScore === prevScore && candTs >= prevTs) ? candidate : prev;
    byMint.set(mint, pick);
  }
  return [...byMint.values()];
}

/** Proven strategy presets from backtesting 895+ tokens */
export interface StrategyPreset {
  id: string;
  name: string;
  description: string;
  winRate: string;
  trades: number;
  config: Partial<SniperConfig>;
  assetType?: AssetType;
  /** Optional primary WR threshold override for auto gate qualification. */
  autoWrPrimaryOverridePct?: number;
  strategyRevision?: string;
  seedVersion?: string;
  promotedFromRunId?: string;
  /** Set to true after this strategy has been backtested with real/calibrated data */
  backtested?: boolean;
  /** If backtested, the data source used ('geckoterminal' | 'birdeye' | 'mixed' | 'client') */
  dataSource?: string;
  /** Marked losing/unreliable by profitability-first backtest criteria. */
  underperformer?: boolean;
  /** Profitable but below promotion/proven confidence thresholds. */
  experimental?: boolean;
  /** Strategy disabled (e.g. failed backtest) */
  disabled?: boolean;
}

/** Runtime backtest metadata for a strategy preset (persisted via Zustand) */
export interface BacktestMetaEntry {
  winRate: string;
  trades: number;
  backtested: boolean;
  dataSource: string;
  underperformer: boolean;
  /** Numeric win-rate (%) for machine-readable gating/ranking. */
  winRatePct?: number;
  /** Wilson 95% lower bound (%). */
  winRateLower95Pct?: number;
  /** Wilson 95% upper bound (%). */
  winRateUpper95Pct?: number;
  /** Numeric trade count for confidence gates (defaults to `trades` when omitted). */
  totalTrades?: number;
  /** Aggregate net P&L metric (percentage points) used for strategy ranking. */
  netPnlPct?: number;
  /** Numeric profit factor for tie-breaking when available. */
  profitFactorValue?: number;
  /** Sample-size gate for how much trust to place in the numbers */
  stage?: 'tiny' | 'sanity' | 'stability' | 'promotion';
  /** True once the strategy meets the 5,000+ trades promotion gate (sample-size only). */
  promotionEligible?: boolean;
}

/**
 * Strategy presets synced to latest backtest artifacts (2026-02-16 run).
 *
 * Source: backtest-data/results/master_comparison.csv + consistency_report.csv
 * Classification policy:
 * - Proven: expectancy > 0, PF > 1, trades >= 50, min_pos_frac >= 0.70
 * - Experimental: profitable but below proven thresholds (and all TradFi)
 * - Losing/disabled: expectancy <= 0 or PF <= 1
 */
export const STRATEGY_PRESETS: StrategyPreset[] = [
  // ─── MEMECOIN CORE — 3 strategies (SL 10%, TP 20% = 2:1 R:R) ──────────
  {
    id: 'elite',
    name: 'SNIPER ELITE',
    description: 'Strict filter — PF 1.54, +3.14%/trade, 108 trades',
    winRate: '49.1%',
    trades: 108,
    assetType: 'memecoin',
    config: {
      stopLossPct: 10, takeProfitPct: 20, trailingStopPct: 99,
      minLiquidityUsd: 100000, minMomentum1h: 10, maxTokenAgeHours: 100,
      minVolLiqRatio: 2.0, tradingHoursGate: false, strategyMode: 'conservative',
    },
  },
  {
    id: 'pump_fresh_tight',
    name: 'PUMP FRESH TIGHT',
    description: 'Fresh pumpswap — PF 1.30, +1.87%/trade, 106 trades',
    winRate: '44.3%',
    trades: 106,
    assetType: 'memecoin',
    // Default strategy gets a lower primary gate to remain selectable in early, noisy backtests.
    autoWrPrimaryOverridePct: 50,
    config: {
      stopLossPct: 10, takeProfitPct: 20, trailingStopPct: 99,
      minLiquidityUsd: 5000, minScore: 40, maxTokenAgeHours: 24,
      strategyMode: 'balanced',
    },
  },
  {
    id: 'micro_cap_surge',
    name: 'MICRO CAP SURGE',
    description: 'Micro-cap surge — PF 1.80, +4.09%/trade, 106 trades',
    winRate: '54.7%',
    trades: 106,
    assetType: 'memecoin',
    config: {
      stopLossPct: 10, takeProfitPct: 20, trailingStopPct: 99,
      minLiquidityUsd: 3000, minScore: 30, maxTokenAgeHours: 24,
      strategyMode: 'aggressive',
    },
  },
  // ─── MEMECOIN WIDE — 3 strategies (SL 10%, TP 25% = 2.5:1 R:R) ────────
  // Mean-reversion family retained; currently profitable in latest run.
  {
    id: 'momentum',
    name: 'MOMENTUM RIDER',
    description: 'Mean-reversion dip buy — PF 1.75, +4.40%/trade, 69 trades',
    winRate: '46.4%',
    trades: 69,
    assetType: 'memecoin',
    config: {
      stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99,
      minLiquidityUsd: 5000, minScore: 30, maxTokenAgeHours: 200,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'hybrid_b',
    name: 'HYBRID B',
    description: 'Hybrid dip entry — PF 1.75, +4.40%/trade, 69 trades',
    winRate: '46.4%',
    trades: 69,
    assetType: 'memecoin',
    config: {
      stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99,
      minLiquidityUsd: 5000, minScore: 30, maxTokenAgeHours: 200,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'let_it_ride',
    name: 'LET IT RIDE',
    description: 'Wide hold dip buy — PF 1.56, +3.51%/trade, 56 trades',
    winRate: '44.6%',
    trades: 56,
    assetType: 'memecoin',
    config: {
      stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99,
      minLiquidityUsd: 3000, minScore: 20, maxTokenAgeHours: 500,
      strategyMode: 'aggressive',
    },
  },
  // ─── ESTABLISHED TOKENS — 5 strategies (SL 8%, TP 15% = 1.9:1 R:R) ────
  {
    id: 'utility_swing',
    name: 'UTILITY SWING',
    description: 'Utility/governance (RAY, JUP, PYTH) — PF 2.20, +4.36%/trade, 72 trades',
    winRate: '61.1%',
    trades: 72,
    assetType: 'established',
    config: {
      stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99,
      minLiquidityUsd: 10000, minScore: 55, maxTokenAgeHours: 99999,
      strategyMode: 'balanced',
    },
  },
  {
    id: 'meme_classic',
    name: 'MEME CLASSIC',
    description: 'Established memes 1yr+ (BONK, WIF) — PF 1.85, +3.43%/trade, 74 trades',
    winRate: '56.8%',
    trades: 74,
    assetType: 'established',
    config: {
      stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99,
      minLiquidityUsd: 5000, minScore: 40, maxTokenAgeHours: 99999,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'volume_spike',
    name: 'VOLUME SPIKE',
    description: 'Established volume surges — PF 1.67, +2.92%/trade, 80 trades (EXPERIMENTAL)',
    winRate: '53.8%',
    trades: 80,
    assetType: 'established',
    experimental: true,
    config: {
      stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99,
      minLiquidityUsd: 20000, minScore: 35, maxTokenAgeHours: 99999,
      minVolLiqRatio: 0.3,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'sol_veteran',
    name: 'SOL VETERAN',
    description: 'Established Solana 6mo+ ($50K+ liq) — PF 2.20, +4.36%/trade, 72 trades',
    winRate: '61.1%',
    trades: 72,
    assetType: 'established',
    config: {
      stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99,
      minLiquidityUsd: 50000, minScore: 40, maxTokenAgeHours: 99999,
      strategyMode: 'balanced',
    },
  },
  {
    id: 'established_breakout',
    name: 'ESTABLISHED BREAKOUT',
    description: '30d+ breakout signals — PF 1.80, +3.33%/trade, 18 trades (EXPERIMENTAL)',
    winRate: '55.6%',
    trades: 18,
    assetType: 'established',
    experimental: true,
    config: {
      stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99,
      minLiquidityUsd: 10000, minScore: 30, maxTokenAgeHours: 99999,
      strategyMode: 'aggressive',
    },
  },
  // ─── BAGS.FM — 8 strategies (mixed params, all optimized) ─────────────
  {
    id: 'bags_fresh_snipe',
    name: 'BAGS FRESH SNIPE',
    description: 'Fresh bags launches — PF 1.41, +2.95%/trade, 28 trades (EXPERIMENTAL)',
    winRate: '35.7%',
    trades: 28,
    assetType: 'bags',
    experimental: true,
    config: {
      stopLossPct: 10, takeProfitPct: 30, trailingStopPct: 99,
      minLiquidityUsd: 0,
      minScore: 35, maxTokenAgeHours: 48,
      strategyMode: 'balanced',
    },
  },
  {
    id: 'bags_momentum',
    name: 'BAGS MOMENTUM',
    description: 'Post-launch momentum — PF 1.36, +2.60%/trade, 23 trades (EXPERIMENTAL)',
    winRate: '34.8%',
    trades: 23,
    assetType: 'bags',
    experimental: true,
    config: {
      stopLossPct: 10, takeProfitPct: 30, trailingStopPct: 99,
      minLiquidityUsd: 0,
      minScore: 30, maxTokenAgeHours: 168,
      minMomentum1h: 5,
      strategyMode: 'balanced',
    },
  },
  {
    id: 'bags_value',
    name: 'BAGS VALUE HUNTER',
    description: 'Quality bags — PF 1.43, +1.29%/trade, 40 trades (EXPERIMENTAL)',
    winRate: '52.5%',
    trades: 40,
    assetType: 'bags',
    experimental: true,
    config: {
      stopLossPct: 5, takeProfitPct: 10, trailingStopPct: 99,
      minLiquidityUsd: 0,
      minScore: 55, maxTokenAgeHours: 720,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'bags_dip_buyer',
    name: 'BAGS DIP BUYER',
    description: 'Dip recovery — PF 1.75, +3.45%/trade, 65 trades',
    winRate: '47.7%',
    trades: 65,
    assetType: 'bags',
    config: {
      stopLossPct: 8, takeProfitPct: 25, trailingStopPct: 99,
      minLiquidityUsd: 0,
      minScore: 25, maxTokenAgeHours: 336,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'bags_bluechip',
    name: 'BAGS BLUE CHIP',
    description: 'Established bags — PF 1.20, +0.59%/trade, 51 trades',
    winRate: '51.0%',
    trades: 51,
    assetType: 'bags',
    config: {
      stopLossPct: 5, takeProfitPct: 9, trailingStopPct: 99,
      minLiquidityUsd: 0,
      minScore: 60,
      maxTokenAgeHours: 99999,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'bags_conservative',
    name: 'BAGS CONSERVATIVE',
    description: 'Conservative — PF 1.43, +1.29%/trade, 40 trades (EXPERIMENTAL)',
    winRate: '52.5%',
    trades: 40,
    assetType: 'bags',
    experimental: true,
    config: {
      stopLossPct: 5, takeProfitPct: 10, trailingStopPct: 99,
      minLiquidityUsd: 0,
      minScore: 40, maxTokenAgeHours: 336,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'bags_aggressive',
    name: 'BAGS AGGRESSIVE',
    description: 'High-conviction — PF 1.31, +1.67%/trade, 58 trades',
    winRate: '34.5%',
    trades: 58,
    assetType: 'bags',
    config: {
      stopLossPct: 7, takeProfitPct: 25, trailingStopPct: 99,
      minLiquidityUsd: 0,
      minScore: 10, maxTokenAgeHours: 336,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'bags_elite',
    name: 'BAGS ELITE',
    description: 'Top-tier filter — PF 1.26, +0.79%/trade, 40 trades (EXPERIMENTAL)',
    winRate: '52.5%',
    trades: 40,
    assetType: 'bags',
    experimental: true,
    config: {
      stopLossPct: 5, takeProfitPct: 9, trailingStopPct: 99,
      minLiquidityUsd: 0,
      minScore: 70, maxTokenAgeHours: 336,
      strategyMode: 'balanced',
    },
  },
  // ─── BLUE CHIP SOLANA — 2 strategies (SL 10%, TP 25% = 2.5:1 R:R) ────
  {
    id: 'bluechip_trend_follow',
    name: 'BLUECHIP TREND FOLLOW',
    description: 'Trend following — PF 1.14, +0.98%/trade, 610 trades (EXPERIMENTAL)',
    winRate: '35.9%',
    trades: 610,
    assetType: 'bluechip',
    experimental: true,
    config: {
      stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99,
      minLiquidityUsd: 200000, minScore: 55, maxTokenAgeHours: 99999,
      strategyMode: 'balanced',
    },
  },
  {
    id: 'bluechip_breakout',
    name: 'BLUECHIP BREAKOUT',
    description: 'Breakout catcher — PF 1.14, +0.98%/trade, 610 trades (EXPERIMENTAL)',
    winRate: '35.9%',
    trades: 610,
    assetType: 'bluechip',
    experimental: true,
    config: {
      stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99,
      minLiquidityUsd: 200000, minScore: 65, maxTokenAgeHours: 99999,
      strategyMode: 'balanced',
    },
  },
  // ─── xSTOCK & PRESTOCK — tradfi stays Experimental by policy ───
  {
    id: 'xstock_intraday',
    name: 'xSTOCK INTRADAY',
    description: 'Stock intraday (low WR / high R) — PF 1.59, +4.53%/trade, 477 trades (EXPERIMENTAL)',
    winRate: '17.6%',
    trades: 477,
    assetType: 'xstock',
    experimental: true,
    config: {
      stopLossPct: 8, takeProfitPct: 100, trailingStopPct: 99,
      maxPositionAgeHours: 336,
      minLiquidityUsd: 50000, minScore: 55, maxTokenAgeHours: 99999,
      strategyMode: 'balanced',
    },
  },
  {
    id: 'xstock_swing',
    name: 'xSTOCK SWING',
    description: 'Stock swing (low WR / high R) — PF 2.44, +11.78%/trade, 152 trades (EXPERIMENTAL)',
    winRate: '26.3%',
    trades: 152,
    assetType: 'xstock',
    experimental: true,
    config: {
      stopLossPct: 10, takeProfitPct: 100, trailingStopPct: 99,
      maxPositionAgeHours: 48,
      minLiquidityUsd: 50000, minScore: 55, maxTokenAgeHours: 99999,
      strategyMode: 'balanced',
    },
  },
  {
    id: 'prestock_speculative',
    name: 'PRESTOCK SPECULATIVE',
    description: 'Pre-stock spec — PF 0.78, -0.81%/trade, 79 trades (LOSING / EXPERIMENTAL)',
    winRate: '32.9%',
    trades: 79,
    assetType: 'prestock',
    underperformer: true,
    experimental: true,
    config: {
      stopLossPct: 4, takeProfitPct: 10, trailingStopPct: 99,
      minLiquidityUsd: 20000, minScore: 20, maxTokenAgeHours: 99999,
      strategyMode: 'aggressive',
    },
  },
  // ─── INDEX — tradfi stays Experimental by policy ────────
  {
    id: 'index_intraday',
    name: 'INDEX INTRADAY',
    description: 'Index intraday — PF 0.63, -1.43%/trade, 144 trades (LOSING / EXPERIMENTAL)',
    winRate: '28.5%',
    trades: 144,
    assetType: 'index',
    underperformer: true,
    experimental: true,
    config: {
      stopLossPct: 4, takeProfitPct: 10, trailingStopPct: 99,
      minLiquidityUsd: 100000, minScore: 50, maxTokenAgeHours: 99999,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'index_leveraged',
    name: 'INDEX LEVERAGED',
    description: 'Index leveraged — PF 0.72, -1.04%/trade, 112 trades (LOSING / EXPERIMENTAL)',
    winRate: '31.3%',
    trades: 112,
    assetType: 'index',
    underperformer: true,
    experimental: true,
    config: {
      stopLossPct: 4, takeProfitPct: 10, trailingStopPct: 99,
      minLiquidityUsd: 50000, minScore: 40, maxTokenAgeHours: 99999,
      strategyMode: 'balanced',
    },
  },
].map((preset) => ({ ...preset, ...STRATEGY_SEED_META } as StrategyPreset));

/** Deprecated: hour-based gating is disabled globally (crypto trades 24/7). */
export const PROVEN_TRADING_HOURS: number[] = [];
/** Deprecated: hour-based gating is disabled globally (crypto trades 24/7). */
export const DEAD_HOURS: number[] = [];

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
  /** If true, auto/manual closes in session mode sweep excess SOL to main wallet. */
  autoSweepToMainWalletOnClose: boolean;
  /** Enable backtest win-rate gate for automatic strategy selection. */
  autoWrGateEnabled: boolean;
  /** Primary win-rate threshold (%) for automatic strategy selection. */
  autoWrPrimaryPct: number;
  /** Fallback win-rate threshold (%) when no strategy passes primary. */
  autoWrFallbackPct: number;
  /** Minimum sample size before a strategy can pass WR gating. */
  autoWrMinTrades: number;
  /** WR gate metric selector. */
  autoWrMethod: 'wilson95_lower' | 'point';
  /** Asset scope for WR gate enforcement. */
  autoWrScope: 'memecoin_bags' | 'all' | 'memecoin';
  useJito: boolean;
  slippageBps: number;
  /** Strategy mode: R4 mapping (realistic TPs, trail disabled). */
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
  /** Deprecated compatibility flag; hour gating is hard-disabled for continuous 24/7 trading. */
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
  /** Per-asset-class circuit breaker overrides. Missing keys fall back to global limits. */
  perAssetBreakerConfig: Record<AssetType, PerAssetBreakerConfig>;
}

/** Per-asset-class circuit breaker overrides (CIRCUIT-02: Phase 2.3) */
export interface PerAssetBreakerConfig {
  /** Max consecutive losses for this asset class (0 = use global default) */
  maxConsecutiveLosses: number;
  /** Max daily loss in SOL for this asset class (0 = use global default) */
  maxDailyLossSol: number;
  /** Cooldown in minutes after breaker trips before auto-reset (0 = no auto-reset, manual only) */
  cooldownMinutes: number;
}

/** Per-asset-class circuit breaker counters (CIRCUIT-01) */
export interface AssetClassBreaker {
  tripped: boolean;
  reason: string;
  trippedAt: number;
  consecutiveLosses: number;
  dailyLossSol: number;
  dailyResetAt: number;
  /** Timestamp when cooldown expires and breaker auto-resets (0 = no cooldown active) */
  cooldownUntil: number;
}

export interface CircuitBreakerState {
  /** Whether the breaker is currently tripped (sniping halted) — global fallback */
  tripped: boolean;
  /** Human-readable reason for trip */
  reason: string;
  /** Timestamp when breaker was tripped */
  trippedAt: number;
  /** Running count of consecutive losses (global) */
  consecutiveLosses: number;
  /** SOL lost in the current 24h window (global) */
  dailyLossSol: number;
  /** Timestamp when the daily window resets */
  dailyResetAt: number;
  /** Per-asset-class breakers — isolates losses by asset type (CIRCUIT-01) */
  perAsset: Record<AssetType, AssetClassBreaker>;
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
  /** Position creation source (used for automation dedupe/reporting). */
  entrySource?: 'auto' | 'manual';
  /** Strategy preset ID used at entry time (for auto learning attribution). */
  strategyId?: string;
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
  /** Asset class this position belongs to (for per-asset circuit breakers) */
  assetType?: AssetType;
  /**
   * Recovered/imported position from on-chain sync.
   * Manual-only positions are excluded from automated SL/TP execution
   * until explicitly re-opened as a normal strategy position.
   */
  manualOnly?: boolean;
  /** Optional provenance for recovered positions */
  recoveredFrom?: 'onchain-sync';
  /** Reconciled by on-chain sync because no live balance exists for active wallet. */
  reconciled?: boolean;
  /** Reconciliation reason enum for auditability. */
  reconciledReason?: 'no_onchain_balance' | 'buy_tx_unresolved' | 'buy_tx_failed';
  /** Reconciliation timestamp (ms). */
  reconciledAt?: number;
}

export interface ExecutionEvent {
  id: string;
  type: 'snipe' | 'exit_pending' | 'tp_exit' | 'sl_exit' | 'manual_exit' | 'error' | 'skip' | 'info';
  /** Optional lifecycle marker for truthful tx-state logging. */
  phase?: 'attempt' | 'submitted' | 'confirmed' | 'failed';
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

/**
 * Preset-aligned exits (R4).
 *
 * This intentionally avoids per-token heuristics so the selected preset (or manual
 * config) is the only source of truth. Otherwise, runtime "recommendations" can
 * silently override backtested preset SL/TP at entry time.
 *
 * Trailing stops are disabled by default in R4 (`trail = 99`).
 */
export function getRecommendedSlTp(
  _grad: BagsGraduation & Record<string, any>,
  _mode: StrategyMode = 'conservative',
  config?: Pick<SniperConfig, 'stopLossPct' | 'takeProfitPct'>,
): TokenRecommendation {
  const cfg = config || DEFAULT_CONFIG;
  const slRaw = Number(cfg.stopLossPct);
  const tpRaw = Number(cfg.takeProfitPct);
  const sl = Number.isFinite(slRaw) ? slRaw : DEFAULT_CONFIG.stopLossPct;
  const tp = Number.isFinite(tpRaw) ? tpRaw : DEFAULT_CONFIG.takeProfitPct;

  return {
    sl,
    tp,
    trail: 99,
    reasoning: `Preset exits: SL ${sl}% / TP ${tp}% (trail disabled)`,
  };
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
  // R4 defaults: realistic TP/SL and trailing stops disabled.
  // Keep these aligned with the default homepage preset (pump_fresh_tight)
  // so new users don't accidentally run legacy exits.
  stopLossPct: 10,
  takeProfitPct: 20,
  trailingStopPct: 99,  // 99 = disabled (effectively never triggers)
  maxPositionSol: 0.1,
  maxConcurrentPositions: 10,
  minScore: 0,          // Backtested: best configs use liq+momentum, not score
  // Default lowered to $25K so the feed doesn't "skip everything" under normal meme-token conditions.
  // Users can still raise this to $40K/$50K for higher-quality entries.
  minLiquidityUsd: 25000,
  autoSnipe: false,
  autoSweepToMainWalletOnClose: false,
  autoWrGateEnabled: true,
  autoWrPrimaryPct: 70,
  autoWrFallbackPct: 50,
  autoWrMinTrades: 1000,
  autoWrMethod: 'wilson95_lower',
  autoWrScope: 'memecoin_bags',
  useJito: true,
  slippageBps: 150,
  strategyMode: 'conservative',
  maxPositionAgeHours: 4,  // Auto-close stale positions after 4h to free capital
  useRecommendedExits: true,
  // NEW: Stricter quality gates (be pickier, 4x fewer but higher quality)
  minMomentum1h: 5,        // Require 5%+ upward momentum (was 0% — let everything through)
  maxTokenAgeHours: 200,   // ↓ from 500h — young tokens have 188% more alpha
  minVolLiqRatio: 1.0,     // ↑ from 0.5 — tighter filter for vol/liq edge
  tradingHoursGate: false, // Hour gating disabled for continuous operation
  minAgeMinutes: 2,       // Don't snipe tokens that graduated < 2 min ago (post-grad dumps)
  // Circuit breaker: halt sniping on cascading losses to protect capital
  circuitBreakerEnabled: true,
  maxConsecutiveLosses: 9,     // 3x fail tolerance: 9 losses in a row = halt
  maxDailyLossSol: 0.5,       // 0.5 SOL daily loss limit
  minBalanceGuardSol: 0.05,   // Stop if budget remaining < 0.05 SOL
  // Per-asset circuit breaker overrides (Phase 2.3)
  perAssetBreakerConfig: {
    memecoin:     { maxConsecutiveLosses: 9, maxDailyLossSol: 0.3, cooldownMinutes: 15 },
    bags:         { maxConsecutiveLosses: 12, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
    bluechip:     { maxConsecutiveLosses: 15, maxDailyLossSol: 1.0, cooldownMinutes: 30 },
    xstock:       { maxConsecutiveLosses: 12, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
    index:        { maxConsecutiveLosses: 12, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
    prestock:     { maxConsecutiveLosses: 9, maxDailyLossSol: 0.3, cooldownMinutes: 15 },
    established:  { maxConsecutiveLosses: 12, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
  },
};

const STRATEGY_BELIEF_DECAY_GAMMA = 0.90;

/** Monotonic counter to prevent duplicate keys when multiple snipes fire in same ms */
let execCounter = 0;

interface SniperState {
  // Config
  config: SniperConfig;
  setConfig: (partial: Partial<SniperConfig>) => void;
  setStrategyMode: (mode: StrategyMode) => void;
  loadPreset: (presetId: string) => void;
  activePreset: string;
  /** Monotonic strategy revision. Bumped whenever algo selection/config changes. */
  strategyEpoch: number;
  assetFilter: AssetType;
  showExperimentalStrategies: boolean;
  setShowExperimentalStrategies: (show: boolean) => void;
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
  /** Batch-update prices from DexScreener polling.
   *  @param solPriceUsd — current SOL/USD price for accurate SOL-denominated P&L. */
  updatePrices: (priceMap: Record<string, number>, solPriceUsd?: number) => void;
  /** Set isClosing lock on a position */
  setPositionClosing: (id: string, closing: boolean) => void;
  /** Close a position with proper status and stats tracking.
   * @param exitSolReceived — actual SOL from the sell tx (for accurate P&L). */
  closePosition: (id: string, status: 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired' | 'closed', txHash?: string, exitSolReceived?: number) => void;
  /**
   * Reconcile a local position against on-chain truth without counting win/loss stats.
   * Intended for stale/phantom rows where no reliable executed exit exists.
   */
  reconcilePosition: (
    id: string,
    reason: 'no_onchain_balance' | 'buy_tx_unresolved' | 'buy_tx_failed',
    opts?: { releaseBudget?: boolean },
  ) => void;

  // Snipe action — creates position + logs execution
  snipeToken: (grad: BagsGraduation & Record<string, any>) => void;

  // Track which tokens were already sniped (prevents duplicates)
  snipedMints: Set<string>;
  /** Re-entry cooldown per asset+wallet+mint. */
  mintCooldowns: Record<string, number>;
  setMintCooldown: (key: string, nextEligibleAt: number) => void;
  clearExpiredMintCooldowns: (now?: number) => void;

  // Track tokens that were evaluated and skipped (prevents skip-spam in logs)
  skippedMints: Set<string>;

  /** Suppress repeated "Import Missing Holdings" prompts unless balances change materially. */
  importedHoldingsMemo: Record<string, ImportedHoldingMemoEntry>;
  recordImportedHolding: (wallet: string, mint: string, amountLamports: string) => void;
  updateImportedHoldingSeen: (wallet: string, mint: string, amountLamports: string, seenAt?: number) => void;
  pruneImportedHoldingMemo: (wallet: string, liveHoldingsByMint: string[]) => void;

  /** Recently closed positions (per wallet+mint) used to suppress post-sell dust re-import prompts. */
  recentlyClosedMints: Record<string, RecentlyClosedMintMemoEntry>;
  recordRecentlyClosedMint: (wallet: string, mint: string, memo: Omit<RecentlyClosedMintMemoEntry, 'wallet' | 'mint'>) => void;
  pruneRecentlyClosedMints: (maxAgeMs?: number) => void;

  // Watchlist — track tokens to monitor
  watchlist: string[];
  addToWatchlist: (mint: string) => void;
  removeFromWatchlist: (mint: string) => void;

  // Selected token for chart display
  selectedMint: string | null;
  setSelectedMint: (mint: string | null) => void;

  // Execution Log
  executionLog: ExecutionEvent[];
  addExecution: (event: ExecutionEvent) => void;
  /** Global safety lock for new entries (used during Close All / emergency ops). */
  executionPaused: boolean;
  /** Temporary safety gate after a debug reset; requires explicit re-arm flow. */
  autoResetRequired: boolean;
  /** Timestamp for last debug reset action. */
  lastAutoResetAt?: number;
  setExecutionPaused: (paused: boolean, reason?: string) => void;
  /** Debug-only recovery action: disable auto/session and require fresh activation settings. */
  resetAutoForRecovery: () => void;
  /** Automation lifecycle state for UI/debug telemetry. */
  automationState: AutomationState;
  setAutomationState: (state: AutomationState) => void;
  /** Heartbeat timestamp for long-running orchestration visibility. */
  automationHeartbeatAt: number;
  touchAutomationHeartbeat: () => void;
  /** Global operation lock to block new buys while critical operations are running. */
  operationLock: { active: boolean; reason: string; mode: 'none' | 'close_all' | 'maintenance' };
  acquireOperationLock: (reason: string, mode?: 'close_all' | 'maintenance') => void;
  releaseOperationLock: () => void;
  /** Route-independent transaction reconciliation state. */
  pendingTxs: Record<string, PendingTxRecord>;
  txReconcilerRunning: boolean;
  setTxReconcilerRunning: (running: boolean) => void;
  registerPendingTx: (record: PendingTxRecord) => void;
  updatePendingTx: (signature: string, patch: Partial<PendingTxRecord>) => void;
  finalizePendingTx: (signature: string, status: Extract<PendingTxStatus, 'confirmed' | 'failed' | 'unresolved'>, error?: string) => void;
  pruneOldPendingTxs: (maxAgeMs?: number) => void;

  // Stats
  totalPnl: number;
  winCount: number;
  lossCount: number;
  totalTrades: number;

  /** Last known SOL/USD price — updated by PnL tracker for accurate SOL-denominated P&L. */
  lastSolPriceUsd: number;

  // Circuit Breaker
  circuitBreaker: CircuitBreakerState;
  resetCircuitBreaker: () => void;

  // Backtest Metadata — runtime overlay on const STRATEGY_PRESETS
  /** Per-strategy backtest results (keyed by strategyId) — populated after backtest runs */
  backtestMeta: Record<string, BacktestMetaEntry>;
  /** Update backtest metadata for one or more strategy presets */
  updatePresetBacktestResults: (results: Array<{
    strategyId: string;
    winRate: string;
    trades: number;
    backtested: boolean;
    dataSource: string;
    underperformer: boolean;
    winRatePct?: number;
    winRateLower95Pct?: number;
    winRateUpper95Pct?: number;
    totalTrades?: number;
    netPnlPct?: number;
    profitFactorValue?: number;
    stage?: 'tiny' | 'sanity' | 'stability' | 'promotion';
    promotionEligible?: boolean;
  }>) => void;

  // Discounted Thompson learning state (browser-persisted, no backend dependency).
  strategyBeliefs: Record<string, StrategyBelief>;
  recordStrategyOutcome: (args: {
    strategyId?: string;
    outcome: 'win' | 'loss';
    txHash?: string;
    entrySource?: Position['entrySource'];
    decayGamma?: number;
  }) => void;
  resetStrategyBeliefs: () => void;
  /** Server-provided runtime strategy overrides for auto mode (signed snapshot). */
  strategyOverrideSnapshot: StrategyOverrideSnapshot | null;
  setStrategyOverrideSnapshot: (snapshot: StrategyOverrideSnapshot | null) => void;

  // Reset — clears positions, executions, stats, sniped mints
  resetSession: () => void;
}

export function makeDefaultAssetBreaker(): AssetClassBreaker {
  return {
    tripped: false,
    reason: '',
    trippedAt: 0,
    consecutiveLosses: 0,
    dailyLossSol: 0,
    dailyResetAt: Date.now() + 86_400_000,
    cooldownUntil: 0,
  };
}

function makeDefaultCircuitBreaker(): CircuitBreakerState {
  return {
    tripped: false,
    reason: '',
    trippedAt: 0,
    consecutiveLosses: 0,
    dailyLossSol: 0,
    dailyResetAt: Date.now() + 86_400_000,
    perAsset: {
      memecoin: makeDefaultAssetBreaker(),
      bags: makeDefaultAssetBreaker(),
      bluechip: makeDefaultAssetBreaker(),
      xstock: makeDefaultAssetBreaker(),
      index: makeDefaultAssetBreaker(),
      prestock: makeDefaultAssetBreaker(),
      established: makeDefaultAssetBreaker(),
    },
  };
}

export const useSniperStore = create<SniperState>()(
  persist(
    (set, get) => ({
  config: DEFAULT_CONFIG,
  activePreset: 'pump_fresh_tight',
  strategyEpoch: 0,
  assetFilter: 'memecoin' as AssetType,
  showExperimentalStrategies: false,
  setShowExperimentalStrategies: (show) => set({ showExperimentalStrategies: !!show }),
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
    return {
      config: { ...s.config, ...partial },
      skippedMints: new Set(),
      positions,
      strategyEpoch: s.strategyEpoch + 1,
    };
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
        assetFilter: preset.assetType || 'memecoin',
        config: { ...s.config, ...preset.config },
        skippedMints: new Set(),
        positions,
        strategyEpoch: s.strategyEpoch + 1,
      };
    });
  },
  setStrategyMode: (mode) => set((s) => {
    // R4 backtest-mapped presets (realistic TPs, trail disabled):
    //   aggressive   → SL 10 / TP 25 (memecoin wide R:R)
    //   balanced     → SL 8 / TP 15 (established token R:R)
    //   conservative → SL 5 / TP 10 (bags tight R:R)
    const presets: Record<StrategyMode, { sl: number; tp: number; trail: number }> = {
      aggressive:   { sl: 10, tp: 25, trail: 99 },
      balanced:     { sl: 8,  tp: 15, trail: 99 },
      conservative: { sl: 5,  tp: 10, trail: 99 },
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
      strategyEpoch: s.strategyEpoch + 1,
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

  // Budget / Authorization — default 0.5 SOL is a reasonable starting budget for new users
  budget: { budgetSol: 0.5, authorized: false, spent: 0 },
  setBudgetSol: (sol) => set((s) => ({
    budget: { ...s.budget, budgetSol: Math.round(sol * 1000) / 1000 },
  })),
  authorizeBudget: () => set((s) => ({
    budget: { ...s.budget, authorized: true, spent: 0 },
    // Safety: never INCREASE per-trade size on authorize (prevents accidental "all-in" sizing).
    // We only clamp DOWN to a reasonable per-slot suggestion (budget / maxPositions).
    config: {
      ...s.config,
      maxPositionSol: (() => {
        const maxPos = Number(s.config.maxPositionSol || 0);
        const slots = Math.max(1, Number(s.config.maxConcurrentPositions || 1));
        const suggested = Math.round((s.budget.budgetSol / slots) * 100) / 100;
        const next = Math.min(maxPos, suggested);
        return Math.max(0.001, Math.round(next * 100) / 100);
      })(),
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
  setGraduations: (grads) => set({ graduations: dedupeGraduationsByMint(grads).slice(0, 220) }),
  addGraduation: (grad) => set((s) => ({
    graduations: dedupeGraduationsByMint([grad, ...s.graduations]).slice(0, 220),
  })),

  positions: [],
  addPosition: (pos) => set((s) => ({ positions: [pos, ...s.positions] })),
  updatePosition: (id, update) => set((s) => ({
    positions: s.positions.map((p) => p.id === id ? { ...p, ...update } : p),
  })),
  removePosition: (id) => set((s) => ({
    positions: s.positions.filter((p) => p.id !== id),
  })),
  updatePrices: (priceMap, solPriceUsd) => set((s) => ({
    ...(solPriceUsd && solPriceUsd > 0 ? { lastSolPriceUsd: solPriceUsd } : {}),
    positions: s.positions.map((p) => {
      const newPrice = priceMap[p.mint];
      if (newPrice == null || p.status !== 'open') return p;
      // Recovered/manual-only holdings are tracked for visibility + manual close,
      // but excluded from performance math to prevent distorted metrics.
      if (p.manualOnly) {
        return {
          ...p,
          currentPrice: newPrice,
          pnlPercent: 0,
          pnlSol: 0,
          highWaterMarkPct: p.highWaterMarkPct ?? 0,
        };
      }
      const pnlPercent = p.entryPrice > 0 ? ((newPrice - p.entryPrice) / p.entryPrice) * 100 : 0;
      // SOL-denominated P&L: use actual token holdings + SOL price for real positions
      let pnlSol: number;
      if (solPriceUsd && solPriceUsd > 0 && p.amountLamports && p.amount > 0) {
        // Real on-chain position: compute current SOL value from token count * USD price / SOL price
        const currentValueSol = (p.amount * newPrice) / solPriceUsd;
        pnlSol = currentValueSol - p.solInvested;
      } else {
        // Paper position or SOL price unavailable: approximate (assumes constant SOL price)
        pnlSol = p.solInvested * (pnlPercent / 100);
      }
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
    const closedAt = Date.now();

    execCounter++;

    // Use actual sell proceeds when available, otherwise fall back to price estimate.
    // Guard against bad/unknown cost basis (manual recovered holdings, dust, zero-ish invested)
    // to prevent absurd win/loss and recent-close percentages.
    const rawPnlSol = exitSolReceived != null
      ? exitSolReceived - pos.solInvested
      : pos.pnlSol;
    const rawPnlPct = exitSolReceived != null && pos.solInvested > 0
      ? ((exitSolReceived - pos.solInvested) / pos.solInvested) * 100
      : pos.pnlPercent;
    const hasReliableCostBasis = isReliableTradeForStats({
      id: pos.id,
      manualOnly: pos.manualOnly,
      recoveredFrom: pos.recoveredFrom,
      solInvested: pos.solInvested,
      pnlPercent: rawPnlPct,
      status: pos.status,
    });
    const realPnlSol = hasReliableCostBasis ? rawPnlSol : 0;
    const realPnlPct = hasReliableCostBasis ? rawPnlPct : 0;

    // Trail stop above entry is a win, below entry is a loss
    const isWin = realPnlPct >= 0;
    const exitType = status === 'tp_hit' ? 'tp_exit'
      : status === 'trail_stop' ? (isWin ? 'tp_exit' : 'sl_exit')
      : status === 'sl_hit' ? 'sl_exit'
      : status === 'expired' ? (isWin ? 'tp_exit' : 'sl_exit')
      : 'manual_exit';

    // Manual exits count toward win/loss too (based on whether profitable)
    const countAsWin = hasReliableCostBasis && (exitType === 'tp_exit' || (exitType === 'manual_exit' && isWin));
    const countAsLoss = hasReliableCostBasis && (exitType === 'sl_exit' || (exitType === 'manual_exit' && !isWin));
    const countAsTrade = hasReliableCostBasis;
    const strategyOutcome = (
      pos.entrySource === 'auto' &&
      !!pos.strategyId &&
      !!txHash &&
      (countAsWin || countAsLoss)
    )
      ? {
          strategyId: pos.strategyId,
          outcome: countAsWin ? 'win' as const : 'loss' as const,
          decayGamma: Math.abs(Number(pos.highWaterMarkPct || 0)) >= 80 ? 0.85 : STRATEGY_BELIEF_DECAY_GAMMA,
        }
      : null;

    const pnlLabel = !hasReliableCostBasis
      ? 'cost basis unavailable (excluded from stats)'
      : exitSolReceived != null
      ? `${realPnlSol >= 0 ? '+' : ''}${realPnlSol.toFixed(4)} SOL (real)`
      : `${realPnlPct.toFixed(1)}% (est)`;

    const execEvent: ExecutionEvent = {
      id: `exec-${closedAt}-${execCounter}`,
      type: exitType,
      symbol: pos.symbol,
      mint: pos.mint,
      amount: pos.solInvested,
      pnlPercent: hasReliableCostBasis ? realPnlPct : undefined,
      txHash,
      timestamp: closedAt,
      reason: `${status === 'trail_stop' ? 'TRAIL STOP' : status === 'expired' ? 'EXPIRED' : status.replace('_', ' ').toUpperCase()} — ${pnlLabel}`,
    };

    set((s) => {
      // ─── Circuit Breaker Update (global + per-asset) ───
      const cb = { ...s.circuitBreaker, perAsset: { ...s.circuitBreaker.perAsset } };
      const now = closedAt;
      const posAssetType: AssetType = pos.assetType || s.assetFilter;

      // Reset 24h window if expired (global)
      if (now >= cb.dailyResetAt) {
        cb.dailyLossSol = 0;
        cb.dailyResetAt = now + 86_400_000;
      }

      // Update global counters
      if (countAsLoss) {
        cb.consecutiveLosses += 1;
        cb.dailyLossSol += Math.abs(realPnlSol);
      } else if (countAsWin) {
        cb.consecutiveLosses = 0;
      }

      // Update per-asset counters
      const ab = { ...(cb.perAsset[posAssetType] || makeDefaultAssetBreaker()) };
      if (now >= ab.dailyResetAt) {
        ab.dailyLossSol = 0;
        ab.dailyResetAt = now + 86_400_000;
      }
      if (countAsLoss) {
        ab.consecutiveLosses += 1;
        ab.dailyLossSol += Math.abs(realPnlSol);
      } else if (countAsWin) {
        ab.consecutiveLosses = 0;
      }
      cb.perAsset[posAssetType] = ab;

      // Check global trip conditions
      const cfg = s.config;
      if (cfg.circuitBreakerEnabled && !cb.tripped) {
        const budgetRemaining = s.budget.budgetSol - Math.max(0, s.budget.spent - pos.solInvested);
        const guard = computeDynamicMinBalanceGuard(s.budget.budgetSol, cfg.minBalanceGuardSol);
        if (cfg.maxConsecutiveLosses > 0 && cb.consecutiveLosses >= cfg.maxConsecutiveLosses) {
          cb.tripped = true;
          cb.reason = `${cb.consecutiveLosses} consecutive losses (global)`;
          cb.trippedAt = now;
        } else if (cfg.maxDailyLossSol > 0 && cb.dailyLossSol >= cfg.maxDailyLossSol) {
          cb.tripped = true;
          cb.reason = `Daily loss ${cb.dailyLossSol.toFixed(3)} SOL >= ${cfg.maxDailyLossSol} limit (global)`;
          cb.trippedAt = now;
        } else if (guard > 0 && budgetRemaining < guard) {
          cb.tripped = true;
          cb.reason = `Budget remaining ${budgetRemaining.toFixed(3)} SOL < ${guard.toFixed(3)} guard`;
          cb.trippedAt = now;
        }
      }

      // Check per-asset trip conditions (isolate losses by asset class)
      // Use per-asset config limits when available, fall back to global
      const assetCfg = cfg.perAssetBreakerConfig?.[posAssetType];
      const assetMaxLosses = assetCfg?.maxConsecutiveLosses || cfg.maxConsecutiveLosses;
      const assetMaxDailyLoss = assetCfg?.maxDailyLossSol || cfg.maxDailyLossSol;
      const assetCooldownMs = (assetCfg?.cooldownMinutes || 0) * 60_000;

      if (cfg.circuitBreakerEnabled && !ab.tripped) {
        if (assetMaxLosses > 0 && ab.consecutiveLosses >= assetMaxLosses) {
          ab.tripped = true;
          ab.reason = `${ab.consecutiveLosses} consecutive ${posAssetType} losses`;
          ab.trippedAt = now;
          ab.cooldownUntil = assetCooldownMs > 0 ? now + assetCooldownMs : 0;
        } else if (assetMaxDailyLoss > 0 && ab.dailyLossSol >= assetMaxDailyLoss) {
          ab.tripped = true;
          ab.reason = `${posAssetType} daily loss ${ab.dailyLossSol.toFixed(3)} SOL >= ${assetMaxDailyLoss} SOL`;
          ab.trippedAt = now;
          ab.cooldownUntil = assetCooldownMs > 0 ? now + assetCooldownMs : 0;
        }
      }

      const nextSniped = new Set(s.snipedMints);
      nextSniped.delete(pos.mint);

      let nextMintCooldowns = s.mintCooldowns;
      if (!pos.manualOnly && pos.recoveredFrom !== 'onchain-sync') {
        const walletKey =
          String(pos.walletAddress || (s.tradeSignerMode === 'session' ? s.sessionWalletPubkey : 'phantom-shared') || '').trim() || 'unknown';
        const cooldownKey = buildMintCooldownKey(pos.assetType || s.assetFilter, walletKey, pos.mint);
        nextMintCooldowns = {
          ...s.mintCooldowns,
          [cooldownKey]: now + MINT_REENTRY_COOLDOWN_MS,
        };
      }

      // Record recently-closed mints so post-sell residues (often missing price data) don't
      // re-trigger "Import Missing Holdings" prompts or block reconciliation.
      const walletKeyForClose =
        String(pos.walletAddress || (s.tradeSignerMode === 'session' ? s.sessionWalletPubkey : 'phantom-shared') || '').trim() || 'unknown';
      const walletNorm = normalizeWalletForKey(walletKeyForClose) || 'unknown';
      const mintNorm = normalizeMint(pos.mint).toLowerCase();
      const closeMemoKey = buildRecentlyClosedMintKey(walletNorm, mintNorm);
      const nextRecentlyClosedMints: Record<string, RecentlyClosedMintMemoEntry> = {
        ...(s.recentlyClosedMints || {}),
        [closeMemoKey]: {
          wallet: walletNorm,
          mint: mintNorm,
          closedAt: now,
          amountLamports: typeof pos.amountLamports === 'string' ? pos.amountLamports : undefined,
          uiAmount: Number.isFinite(Number(pos.amount)) ? Number(pos.amount) : undefined,
        },
      };
      // Prune old entries to keep persisted state bounded.
      for (const [k, v] of Object.entries(nextRecentlyClosedMints)) {
        const closedAt = Number((v as any)?.closedAt || 0);
        if (!Number.isFinite(closedAt) || closedAt <= 0 || now - closedAt > RECENTLY_CLOSED_RETENTION_MS) {
          delete nextRecentlyClosedMints[k];
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
          pnlSol: realPnlSol,
          pnlPercent: realPnlPct,
        } : p),
        executionLog: [execEvent, ...s.executionLog].slice(0, 200),
        totalPnl: s.totalPnl + realPnlSol,
        winCount: countAsWin ? s.winCount + 1 : s.winCount,
        lossCount: countAsLoss ? s.lossCount + 1 : s.lossCount,
        totalTrades: countAsTrade ? s.totalTrades + 1 : s.totalTrades,
        budget: { ...s.budget, spent: Math.max(0, s.budget.spent - pos.solInvested) },
        snipedMints: nextSniped,
        mintCooldowns: nextMintCooldowns,
        recentlyClosedMints: nextRecentlyClosedMints,
        circuitBreaker: cb,
        // Breaker pauses execution but does not change user intent (auto toggle stays as-is).
        config: s.config,
      };
    });

    if (strategyOutcome) {
      get().recordStrategyOutcome({
        strategyId: strategyOutcome.strategyId,
        outcome: strategyOutcome.outcome,
        decayGamma: strategyOutcome.decayGamma,
        txHash,
        entrySource: pos.entrySource,
      });
    }

    // Persist a minimal trade ledger record server-side so autonomy/backtests can
    // learn from real executions across sessions/devices. Without this, swaps
    // exist only in the executing browser's localStorage.
    postTradeTelemetry({
      schemaVersion: 1,
      positionId: pos.id,
      mint: pos.mint,
      status,
      symbol: pos.symbol,
      walletAddress: pos.walletAddress,
      strategyId: pos.strategyId ?? null,
      entrySource: pos.entrySource,
      entryTime: pos.entryTime,
      exitTime: closedAt,
      solInvested: pos.solInvested,
      exitSolReceived: exitSolReceived ?? null,
      pnlSol: hasReliableCostBasis ? realPnlSol : 0,
      pnlPercent: hasReliableCostBasis ? realPnlPct : 0,
      buyTxHash: pos.txHash ?? null,
      sellTxHash: txHash ?? null,
      includedInStats: hasReliableCostBasis,
      manualOnly: !!pos.manualOnly,
      recoveredFrom: pos.recoveredFrom ?? null,
      tradeSignerMode: state.tradeSignerMode,
      sessionWalletPubkey: state.sessionWalletPubkey,
      activePreset: state.activePreset,
    });
  },
  reconcilePosition: (id, reason, opts) => {
    const state = get();
    const pos = state.positions.find((p) => p.id === id);
    if (!pos || pos.status !== 'open') return;

    const now = Date.now();
    const shouldReleaseBudget = opts?.releaseBudget
      ?? (!pos.manualOnly && pos.recoveredFrom !== 'onchain-sync');
    const spentDelta = shouldReleaseBudget ? Math.max(0, Number(pos.solInvested || 0)) : 0;

    set((s) => ({
      positions: s.positions.map((p) => (
        p.id === id
          ? {
              ...p,
              status: 'closed',
              pnlPercent: 0,
              pnlSol: 0,
              realPnlPercent: 0,
              realPnlSol: 0,
              isClosing: false,
              exitPending: undefined,
              reconciled: true,
              reconciledReason: reason,
              reconciledAt: now,
            }
          : p
      )),
      budget: {
        ...s.budget,
        spent: Math.max(0, Number(s.budget.spent || 0) - spentDelta),
      },
      snipedMints: new Set([...s.snipedMints].filter((mint) => mint !== pos.mint)),
    }));
  },

  snipedMints: new Set(),
  mintCooldowns: {},
  setMintCooldown: (key, nextEligibleAt) => set((s) => {
    const normalizedKey = String(key || '').trim().toLowerCase();
    if (!normalizedKey || !Number.isFinite(nextEligibleAt) || nextEligibleAt <= 0) return s;
    return {
      mintCooldowns: {
        ...s.mintCooldowns,
        [normalizedKey]: nextEligibleAt,
      },
    };
  }),
  clearExpiredMintCooldowns: (now = Date.now()) => set((s) => {
    const entries = Object.entries(s.mintCooldowns || {});
    if (entries.length === 0) return s;
    const next: Record<string, number> = {};
    let changed = false;
    for (const [key, ts] of entries) {
      if (!Number.isFinite(ts) || ts <= now) {
        changed = true;
        continue;
      }
      next[key] = ts;
    }
    return changed ? { mintCooldowns: next } : s;
  }),
  skippedMints: new Set(),
  importedHoldingsMemo: {},
  recordImportedHolding: (wallet, mint, amountLamports) => set((s) => {
    const walletNorm = normalizeWalletForKey(wallet);
    const mintNorm = normalizeMint(mint).toLowerCase();
    if (!walletNorm || !mintNorm) return s;
    const key = buildImportedHoldingMemoKey(walletNorm, mintNorm);
    const now = Date.now();
    return {
      importedHoldingsMemo: {
        ...s.importedHoldingsMemo,
        [key]: {
          wallet: walletNorm,
          mint: mintNorm,
          amountLamports: String(amountLamports || '0'),
          importedAt: s.importedHoldingsMemo[key]?.importedAt || now,
          lastSeenAt: now,
        },
      },
    };
  }),
  updateImportedHoldingSeen: (wallet, mint, amountLamports, seenAt) => set((s) => {
    const walletNorm = normalizeWalletForKey(wallet);
    const mintNorm = normalizeMint(mint).toLowerCase();
    if (!walletNorm || !mintNorm) return s;
    const key = buildImportedHoldingMemoKey(walletNorm, mintNorm);
    const existing = s.importedHoldingsMemo[key];
    if (!existing) return s;
    return {
      importedHoldingsMemo: {
        ...s.importedHoldingsMemo,
        [key]: {
          ...existing,
          amountLamports: String(amountLamports || existing.amountLamports || '0'),
          lastSeenAt: Number(seenAt || Date.now()),
        },
      },
    };
  }),
  pruneImportedHoldingMemo: (wallet, liveHoldingsByMint) => set((s) => {
    const walletNorm = normalizeWalletForKey(wallet);
    if (!walletNorm) return s;
    const live = new Set((liveHoldingsByMint || []).map((m) => normalizeMint(m).toLowerCase()).filter(Boolean));
    const now = Date.now();
    const retentionMs = 24 * 60 * 60 * 1000; // retain suppression memory for 24h after mint disappears
    const next: Record<string, ImportedHoldingMemoEntry> = {};
    let changed = false;
    for (const [key, value] of Object.entries(s.importedHoldingsMemo || {})) {
      if (value.wallet !== walletNorm) {
        next[key] = value;
        continue;
      }
      if (live.has(value.mint)) {
        next[key] = value;
      } else {
        if (now - Number(value.lastSeenAt || value.importedAt || 0) < retentionMs) {
          next[key] = value;
        } else {
          changed = true;
        }
      }
    }
    return changed ? { importedHoldingsMemo: next } : s;
  }),

  recentlyClosedMints: {},
  recordRecentlyClosedMint: (wallet, mint, memo) => set((s) => {
    const walletNorm = normalizeWalletForKey(wallet) || 'unknown';
    const mintNorm = normalizeMint(mint).toLowerCase();
    if (!mintNorm) return s;
    const key = buildRecentlyClosedMintKey(walletNorm, mintNorm);
    const now = Date.now();
    const next: Record<string, RecentlyClosedMintMemoEntry> = {
      ...(s.recentlyClosedMints || {}),
      [key]: {
        wallet: walletNorm,
        mint: mintNorm,
        closedAt: Number((memo as any)?.closedAt || now),
        amountLamports: (memo as any)?.amountLamports ? String((memo as any).amountLamports) : undefined,
        uiAmount: Number.isFinite(Number((memo as any)?.uiAmount)) ? Number((memo as any).uiAmount) : undefined,
      },
    };
    // Prune old entries to keep persisted state bounded.
    for (const [k, v] of Object.entries(next)) {
      const closedAt = Number((v as any)?.closedAt || 0);
      if (!Number.isFinite(closedAt) || closedAt <= 0 || now - closedAt > RECENTLY_CLOSED_RETENTION_MS) {
        delete next[k];
      }
    }
    return { recentlyClosedMints: next };
  }),
  pruneRecentlyClosedMints: (maxAgeMs = RECENTLY_CLOSED_RETENTION_MS) => set((s) => {
    const now = Date.now();
    const entries = Object.entries(s.recentlyClosedMints || {});
    if (entries.length === 0) return s;
    const next: Record<string, RecentlyClosedMintMemoEntry> = {};
    let changed = false;
    for (const [k, v] of entries) {
      const closedAt = Number((v as any)?.closedAt || 0);
      if (!Number.isFinite(closedAt) || closedAt <= 0 || now - closedAt > maxAgeMs) {
        changed = true;
        continue;
      }
      next[k] = v;
    }
    return changed ? { recentlyClosedMints: next } : s;
  }),

  // Watchlist
  watchlist: [],
  addToWatchlist: (mint) => set((s) => ({
    watchlist: s.watchlist.includes(mint) ? s.watchlist : [...s.watchlist, mint],
  })),
  removeFromWatchlist: (mint) => set((s) => ({
    watchlist: s.watchlist.filter((m) => m !== mint),
  })),

  snipeToken: (grad) => {
    const state = get();
    const { config, positions, snipedMints, skippedMints, budget, mintCooldowns } = state;

    // Guard: budget not authorized
    if (!budget.authorized) return;
    if (state.operationLock.active) return;

    // Guard: circuit breaker tripped (global or per-asset)
    if (state.circuitBreaker.tripped) return;
    const assetBreaker = state.circuitBreaker.perAsset[state.assetFilter];
    if (assetBreaker?.tripped) {
      // Check cooldown expiry — auto-reset if cooldown has passed
      if (assetBreaker.cooldownUntil > 0 && Date.now() >= assetBreaker.cooldownUntil) {
        // Auto-reset this asset's breaker (cooldown expired)
        set((s) => {
          const cb = { ...s.circuitBreaker, perAsset: { ...s.circuitBreaker.perAsset } };
          cb.perAsset[s.assetFilter] = {
            ...makeDefaultAssetBreaker(),
            dailyLossSol: assetBreaker.dailyLossSol,
            dailyResetAt: assetBreaker.dailyResetAt,
          };
          return { circuitBreaker: cb };
        });
        // Don't return — allow the snipe to proceed after reset
      } else {
        return; // Still in cooldown, block the snipe
      }
    }

    // Guard: already evaluated and skipped — prevents skip-spam in logs
    if (skippedMints.has(grad.mint)) return;

    // Guard: mint cooldown active (asset+wallet+mint scoped)
    const fallbackWallet = state.tradeSignerMode === 'session'
      ? state.sessionWalletPubkey
      : 'phantom-shared';
    const cooldownKey = buildMintCooldownKey(state.assetFilter, fallbackWallet, grad.mint);
    const cooldownUntil = Number(mintCooldowns[cooldownKey] || 0);
    if (cooldownUntil > Date.now()) return;

    // Guard: at capacity
    const openCount = positions.filter((p) => {
      if (p.status !== 'open') return false;
      if (p.manualOnly) return false;
      if (p.recoveredFrom === 'onchain-sync') return false;
      if (p.isClosing) return false;
      return true;
    }).length;
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

    // Gate 0 (disabled): do not hard-block by UTC "dead hours".
    // Requirement: continuous trading flow without hour-based hard pauses.

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

    // Snapshot exits at entry (preset-aligned; prevents runtime drift).
    const rec = getRecommendedSlTp(grad, config.strategyMode, config);

    const posId = `pos-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const newPosition: Position = {
      id: posId,
      mint: grad.mint,
      symbol: grad.symbol,
      name: grad.name,
      entrySource: 'manual',
      strategyId: state.activePreset,
      entryPrice: grad.price_usd || 0,
      currentPrice: grad.price_usd || 0,
      // Estimate token amount: (SOL * SOL_USD) / token_USD. Falls back to SOL/token_USD if no SOL price.
      amount: grad.price_usd ? (positionSolFinal * (get().lastSolPriceUsd || 1)) / grad.price_usd : 0,
      solInvested: positionSolFinal,
      pnlPercent: 0,
      pnlSol: 0,
      entryTime: Date.now(),
      status: 'open',
      score: grad.score,
      recommendedSl: rec.sl,
      recommendedTp: rec.tp,
      recommendedTrail: rec.trail,
      highWaterMarkPct: 0,
      assetType: state.assetFilter,
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
  executionPaused: false,
  autoResetRequired: false,
  lastAutoResetAt: undefined,
  automationState: 'idle',
  setAutomationState: (state) => set({ automationState: state }),
  automationHeartbeatAt: 0,
  touchAutomationHeartbeat: () => set({ automationHeartbeatAt: Date.now() }),
  operationLock: { active: false, reason: '', mode: 'none' },
  acquireOperationLock: (reason, mode = 'maintenance') => set({
    operationLock: { active: true, reason, mode },
  }),
  releaseOperationLock: () => set({
    operationLock: { active: false, reason: '', mode: 'none' },
  }),
  pendingTxs: {},
  txReconcilerRunning: false,
  setTxReconcilerRunning: (running) => set({ txReconcilerRunning: running }),
  registerPendingTx: (record) => set((s) => {
    const signature = String(record.signature || '').trim();
    if (!signature) return s;
    const existing = s.pendingTxs[signature];
    return {
      pendingTxs: {
        ...s.pendingTxs,
        [signature]: {
          signature,
          kind: record.kind,
          mint: record.mint || existing?.mint,
          submittedAt: existing?.submittedAt || Number(record.submittedAt || Date.now()),
          lastCheckedAt: record.lastCheckedAt || existing?.lastCheckedAt,
          status: record.status || existing?.status || 'submitted',
          error: record.error || existing?.error,
          sourcePage: record.sourcePage || existing?.sourcePage,
        },
      },
    };
  }),
  updatePendingTx: (signature, patch) => set((s) => {
    const key = String(signature || '').trim();
    if (!key || !s.pendingTxs[key]) return s;
    return {
      pendingTxs: {
        ...s.pendingTxs,
        [key]: {
          ...s.pendingTxs[key],
          ...patch,
          signature: key,
          lastCheckedAt: patch.lastCheckedAt ?? Date.now(),
        },
      },
    };
  }),
  finalizePendingTx: (signature, status, error) => set((s) => {
    const key = String(signature || '').trim();
    const existing = s.pendingTxs[key];
    if (!key || !existing) return s;
    if (existing.status === 'confirmed' || existing.status === 'failed' || existing.status === 'unresolved') {
      return s;
    }
    return {
      pendingTxs: {
        ...s.pendingTxs,
        [key]: {
          ...existing,
          status,
          error: error ?? existing.error,
          lastCheckedAt: Date.now(),
        },
      },
    };
  }),
  pruneOldPendingTxs: (maxAgeMs = 6 * 60 * 60 * 1000) => set((s) => {
    const now = Date.now();
    const next: Record<string, PendingTxRecord> = {};
    for (const [sig, rec] of Object.entries(s.pendingTxs)) {
      const age = now - Number(rec.submittedAt || 0);
      const isFinal = rec.status === 'confirmed' || rec.status === 'failed' || rec.status === 'unresolved';
      if (isFinal && age > maxAgeMs) continue;
      next[sig] = rec;
    }
    return { pendingTxs: next };
  }),
  setExecutionPaused: (paused, reason) => set((s) => {
    if (s.executionPaused === paused && !reason) return s;
    const now = Date.now();
    let nextLog = s.executionLog;
    if (reason) {
      execCounter++;
      nextLog = [{
        id: `exec-${now}-${execCounter}`,
        type: 'info' as const,
        symbol: 'SYSTEM',
        mint: '',
        amount: 0,
        reason,
        timestamp: now,
      }, ...s.executionLog].slice(0, 200);
    }
    return {
      executionPaused: paused,
      // Do not mutate user intent (auto toggle). Pausing gates execution only.
      config: s.config,
      automationState: paused ? 'paused' : (s.automationState === 'paused' ? 'idle' : s.automationState),
      executionLog: nextLog,
    };
  }),
  resetAutoForRecovery: () => set((s) => {
    const now = Date.now();
    execCounter++;
    const event: ExecutionEvent = {
      id: `exec-${now}-${execCounter}`,
      type: 'info',
      symbol: 'SYSTEM',
      mint: '',
      amount: 0,
      phase: 'failed',
      reason: 'AUTO_STOP_RESET_AUTO: Auto + session mode disabled. Re-arm budget/max settings before enabling auto again.',
      timestamp: now,
    };
    return {
      config: { ...s.config, autoSnipe: false },
      budget: { ...s.budget, authorized: false, spent: Math.max(0, Number(s.budget.spent || 0)) },
      tradeSignerMode: 'phantom',
      sessionWalletPubkey: null,
      executionPaused: false,
      operationLock: { active: false, reason: '', mode: 'none' },
      pendingTxs: {},
      txReconcilerRunning: false,
      snipedMints: new Set(),
      mintCooldowns: {},
      skippedMints: new Set(),
      autoResetRequired: true,
      lastAutoResetAt: now,
      automationState: 'idle',
      automationHeartbeatAt: 0,
      executionLog: [event, ...s.executionLog].slice(0, 200),
    };
  }),

  totalPnl: 0,
  winCount: 0,
  lossCount: 0,
  totalTrades: 0,
  lastSolPriceUsd: 0,

  // Circuit Breaker
  circuitBreaker: makeDefaultCircuitBreaker(),
  resetCircuitBreaker: () => set({
    circuitBreaker: makeDefaultCircuitBreaker(),
  }),

  // Backtest Metadata
  backtestMeta: {} as Record<string, BacktestMetaEntry>,
  updatePresetBacktestResults: (results) => set((s) => {
    const updated = { ...s.backtestMeta };
    for (const r of results) {
      updated[r.strategyId] = {
        winRate: r.winRate,
        trades: r.trades,
        backtested: r.backtested,
        dataSource: r.dataSource,
        underperformer: r.underperformer,
        winRatePct: r.winRatePct,
        winRateLower95Pct: r.winRateLower95Pct,
        winRateUpper95Pct: r.winRateUpper95Pct,
        totalTrades: r.totalTrades,
        netPnlPct: r.netPnlPct,
        profitFactorValue: r.profitFactorValue,
        stage: r.stage,
        promotionEligible: r.promotionEligible,
      };
    }
    return { backtestMeta: updated };
  }),
  strategyBeliefs: {},
  recordStrategyOutcome: (args) => set((s) => {
    const strategyId = String(args.strategyId || '').trim();
    const txHash = String(args.txHash || '').trim();
    const gamma = Number.isFinite(args.decayGamma)
      ? Math.max(0.5, Math.min(0.999, Number(args.decayGamma)))
      : STRATEGY_BELIEF_DECAY_GAMMA;
    if (!strategyId) return s;
    // Fail-closed learning: only auto entries with confirmed signature evidence can update beliefs.
    if (args.entrySource && args.entrySource !== 'auto') return s;
    if (!txHash) return s;
    return {
      strategyBeliefs: applyDiscountedOutcome(
        s.strategyBeliefs,
        {
          strategyId,
          outcome: args.outcome,
          gamma,
          txHash,
        },
      ),
    };
  }),
  resetStrategyBeliefs: () => set({ strategyBeliefs: {} }),
  strategyOverrideSnapshot: null,
  setStrategyOverrideSnapshot: (snapshot) => set({ strategyOverrideSnapshot: snapshot }),

  resetSession: () => set((s) => ({
    positions: [],
    executionLog: [],
    snipedMints: new Set(),
    mintCooldowns: {},
    skippedMints: new Set(),
    importedHoldingsMemo: {},
    recentlyClosedMints: {},
    watchlist: [],
    selectedMint: null,
    // Safety defaults: do not resume automation after reset.
    tradeSignerMode: 'phantom',
    sessionWalletPubkey: null,
    config: { ...s.config, autoSnipe: false },
    executionPaused: false,
    autoResetRequired: false,
    lastAutoResetAt: undefined,
    automationState: 'idle',
    automationHeartbeatAt: 0,
    operationLock: { active: false, reason: '', mode: 'none' },
    pendingTxs: {},
    txReconcilerRunning: false,
    budget: { budgetSol: 0.5, authorized: false, spent: 0 },
    totalPnl: 0,
    winCount: 0,
    lossCount: 0,
    totalTrades: 0,
    circuitBreaker: makeDefaultCircuitBreaker(),
  })),
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
      // Only persist durable session state (not transient in-flight dedupe sets).
      partialize: (state) => ({
        positions: state.positions,
        config: state.config,
        showExperimentalStrategies: state.showExperimentalStrategies,
        tradeSignerMode: state.tradeSignerMode,
        sessionWalletPubkey: state.sessionWalletPubkey,
        budget: state.budget,
        autoResetRequired: state.autoResetRequired,
        lastAutoResetAt: state.lastAutoResetAt,
        executionLog: state.executionLog.slice(0, 50), // Keep last 50
        watchlist: state.watchlist,
        circuitBreaker: state.circuitBreaker,
        mintCooldowns: state.mintCooldowns,
        importedHoldingsMemo: state.importedHoldingsMemo,
        recentlyClosedMints: state.recentlyClosedMints,
        totalPnl: state.totalPnl,
        winCount: state.winCount,
        lossCount: state.lossCount,
        totalTrades: state.totalTrades,
        backtestMeta: state.backtestMeta,
        strategyBeliefs: state.strategyBeliefs,
        strategyOverrideSnapshot: state.strategyOverrideSnapshot,
      }),
      // Rehydrate: restore durable fields + reset transient runtime state.
      onRehydrateStorage: () => (state) => {
        if (!state) return;

        // Migrate config defaults (new fields, etc.)
        state.config = { ...DEFAULT_CONFIG, ...(state.config as SniperConfig | undefined) };
        state.showExperimentalStrategies = !!(state as any).showExperimentalStrategies;
        state.autoResetRequired = !!state.autoResetRequired;
        state.lastAutoResetAt = Number(state.lastAutoResetAt || 0) || undefined;
        // Enforce upgraded circuit-breaker fail thresholds for existing persisted sessions.
        state.config.maxConsecutiveLosses = Math.max(
          Number(state.config.maxConsecutiveLosses || 0),
          DEFAULT_CONFIG.maxConsecutiveLosses,
        );

        // Migrate circuit breaker shape (per-asset counters were added after initial launch).
        const cbDefault = makeDefaultCircuitBreaker();
        const cbAny = (state.circuitBreaker as any) || {};
        state.circuitBreaker = {
          ...cbDefault,
          ...cbAny,
          perAsset: {
            ...cbDefault.perAsset,
            ...(cbAny.perAsset || {}),
          },
        };
        for (const k of Object.keys(cbDefault.perAsset) as AssetType[]) {
          (state.circuitBreaker.perAsset as any)[k] = {
            ...makeDefaultAssetBreaker(),
            ...((state.circuitBreaker.perAsset as any)[k] || {}),
          };
          // Migrate cooldownUntil on existing per-asset breakers (Phase 2.3)
          const ab = (state.circuitBreaker.perAsset as any)[k];
          if (ab && typeof ab.cooldownUntil === 'undefined') {
            ab.cooldownUntil = 0;
          }
        }

        // Migrate perAssetBreakerConfig (Phase 2.3 hardening)
        const defaultPAC = DEFAULT_CONFIG.perAssetBreakerConfig;
        if (state.config.perAssetBreakerConfig) {
          for (const k of Object.keys(defaultPAC) as AssetType[]) {
            if (!state.config.perAssetBreakerConfig[k]) {
              state.config.perAssetBreakerConfig[k] = defaultPAC[k];
            } else {
              state.config.perAssetBreakerConfig[k].maxConsecutiveLosses = Math.max(
                Number(state.config.perAssetBreakerConfig[k].maxConsecutiveLosses || 0),
                defaultPAC[k].maxConsecutiveLosses,
              );
            }
          }
        } else {
          state.config.perAssetBreakerConfig = defaultPAC;
        }

        // Positions may contain non-persistable transient fields (Phantom prompts, etc.). Reset them.
        if (Array.isArray(state.positions)) {
          state.positions = state.positions.map((p) => ({
            ...p,
            // Legacy recovery rows used "recovered-*" IDs before manualOnly/recoveredFrom
            // flags existed. Mark them explicitly so they don't pollute W/L stats.
            ...(isLegacyRecoveredPositionId((p as any).id) ? {
              manualOnly: true,
              recoveredFrom: 'onchain-sync' as const,
            } : {}),
            // Clamp persisted extreme percentages from earlier math/scale bugs.
            pnlPercent: sanitizePnlPercent((p as any).pnlPercent),
            realPnlPercent: typeof (p as any).realPnlPercent === 'number'
              ? sanitizePnlPercent((p as any).realPnlPercent)
              : (p as any).realPnlPercent,
            recommendedSl: (p as any).recommendedSl ?? DEFAULT_CONFIG.stopLossPct,
            recommendedTp: (p as any).recommendedTp ?? DEFAULT_CONFIG.takeProfitPct,
            highWaterMarkPct: (p as any).highWaterMarkPct ?? 0,
            // Derived / in-flight state should not survive reloads.
            isClosing: false,
            exitPending: undefined,
          }));
        }

        state.snipedMints = new Set();

        // Migrate mint cooldown map; prune expired entries during hydration.
        const rawCooldowns = (state as unknown as Record<string, unknown>).mintCooldowns;
        if (!rawCooldowns || typeof rawCooldowns !== 'object') {
          state.mintCooldowns = {};
        } else {
          const now = Date.now();
          const next: Record<string, number> = {};
          for (const [key, value] of Object.entries(rawCooldowns as Record<string, unknown>)) {
            const ts = Number(value);
            if (!Number.isFinite(ts) || ts <= now) continue;
            next[String(key).toLowerCase()] = ts;
          }
          state.mintCooldowns = next;
        }

        // Migrate imported holdings prompt-suppression memo.
        const rawMemo = (state as unknown as Record<string, unknown>).importedHoldingsMemo;
        if (!rawMemo || typeof rawMemo !== 'object') {
          state.importedHoldingsMemo = {};
        } else {
          const memoNext: Record<string, ImportedHoldingMemoEntry> = {};
          for (const [rawKey, rawValue] of Object.entries(rawMemo as Record<string, unknown>)) {
            const value = rawValue as Partial<ImportedHoldingMemoEntry> | null;
            const wallet = normalizeWalletForKey(value?.wallet);
            const mint = normalizeMint(value?.mint).toLowerCase();
            if (!wallet || !mint) continue;
            const key = buildImportedHoldingMemoKey(wallet, mint);
            memoNext[key] = {
              wallet,
              mint,
              amountLamports: String(value?.amountLamports || '0'),
              importedAt: Number(value?.importedAt || Date.now()),
              lastSeenAt: Number(value?.lastSeenAt || value?.importedAt || Date.now()),
            };
          }
          state.importedHoldingsMemo = memoNext;
        }

        // Migrate recentlyClosedMints (post-sell dust suppression window).
        const rawClosed = (state as unknown as Record<string, unknown>).recentlyClosedMints;
        if (!rawClosed || typeof rawClosed !== 'object') {
          state.recentlyClosedMints = {};
        } else {
          const now = Date.now();
          const next: Record<string, RecentlyClosedMintMemoEntry> = {};
          for (const [rawKey, rawValue] of Object.entries(rawClosed as Record<string, unknown>)) {
            const value = rawValue as Partial<RecentlyClosedMintMemoEntry> | null;
            const wallet = normalizeWalletForKey(value?.wallet) || 'unknown';
            const mint = normalizeMint(value?.mint).toLowerCase();
            const closedAt = Number(value?.closedAt || 0);
            if (!mint || !Number.isFinite(closedAt) || closedAt <= 0) continue;
            if (now - closedAt > RECENTLY_CLOSED_RETENTION_MS) continue;
            const key = buildRecentlyClosedMintKey(wallet, mint);
            next[key] = {
              wallet,
              mint,
              closedAt,
              amountLamports: value?.amountLamports ? String(value.amountLamports) : undefined,
              uiAmount: Number.isFinite(Number(value?.uiAmount)) ? Number(value?.uiAmount) : undefined,
            };
          }
          state.recentlyClosedMints = next;
        }

        // Migrate backtestMeta (added in Plan 02.1-03)
        if (!state.backtestMeta || typeof state.backtestMeta !== 'object') {
          state.backtestMeta = {};
        }

        // Migrate strategyBeliefs (Discounted Thompson state).
        if (!(state as any).strategyBeliefs || typeof (state as any).strategyBeliefs !== 'object') {
          (state as any).strategyBeliefs = {};
        } else {
          const nextBeliefs: Record<string, StrategyBelief> = {};
          for (const [rawId, rawBelief] of Object.entries((state as any).strategyBeliefs as Record<string, any>)) {
            const strategyId = String(rawId || '').trim();
            if (!strategyId) continue;
            const b = rawBelief || {};
            nextBeliefs[strategyId] = {
              strategyId,
              alpha: Math.max(0.1, Number(b.alpha || 1)),
              beta: Math.max(0.1, Number(b.beta || 1)),
              wins: Math.max(0, Math.floor(Number(b.wins || 0))),
              losses: Math.max(0, Math.floor(Number(b.losses || 0))),
              totalOutcomes: Math.max(0, Math.floor(Number(b.totalOutcomes || 0))),
              lastOutcome: b.lastOutcome === 'win' || b.lastOutcome === 'loss' ? b.lastOutcome : undefined,
              lastOutcomeAt: Number(b.lastOutcomeAt || 0) || undefined,
              lastTxHash: b.lastTxHash ? String(b.lastTxHash) : undefined,
              updatedAt: Number(b.updatedAt || Date.now()),
            };
          }
          (state as any).strategyBeliefs = nextBeliefs;
        }

        // Migrate strategy override snapshot.
        if (!(state as any).strategyOverrideSnapshot || typeof (state as any).strategyOverrideSnapshot !== 'object') {
          (state as any).strategyOverrideSnapshot = null;
        }

        // If session signing was selected but the key isn't available, fall back safely
        // (prevents auto-mode from thrashing Phantom popups / failing silently).
        if (state.tradeSignerMode === 'session') {
          const pk = state.sessionWalletPubkey;
          if (!pk) {
            state.tradeSignerMode = 'phantom';
          } else if (typeof window !== 'undefined') {
            const hasKey = (() => {
              try {
                const sources: Array<{ storage: Storage | undefined; key: string }> = [
                  { storage: typeof localStorage !== 'undefined' ? localStorage : undefined, key: `__jarvis_session_wallet_by_pubkey:${pk}` },
                  { storage: typeof localStorage !== 'undefined' ? localStorage : undefined, key: '__jarvis_wallet_persistent' },
                  { storage: typeof sessionStorage !== 'undefined' ? sessionStorage : undefined, key: '__jarvis_session_wallet' },
                ];
                for (const { storage, key } of sources) {
                  if (!storage) continue;
                  const raw = storage.getItem(key);
                  if (!raw) continue;
                  const parsed = JSON.parse(raw);
                  if (String(parsed?.publicKey || '') === pk) return true;
                }
              } catch {
                // ignore
              }
              return false;
            })();

            if (!hasKey) {
              state.tradeSignerMode = 'phantom';
              state.config = { ...state.config, autoSnipe: false };
            }
          }
        }
      },
    },
  ),
);

/**
 * Get a strategy preset merged with its runtime backtest metadata.
 *
 * Returns the const STRATEGY_PRESETS entry overlaid with backtestMeta from
 * the Zustand store (win rate, trades, validated status, underperformer flag).
 * If no backtest has been run for this preset, returns the original preset unchanged.
 *
 * @param presetId - The strategy preset ID (e.g. 'pump_fresh_tight')
 * @returns StrategyPreset with backtested metadata merged, or undefined if not found
 */
export function getPresetWithMeta(presetId: string): StrategyPreset | undefined {
  const preset = STRATEGY_PRESETS.find(p => p.id === presetId);
  if (!preset) return undefined;

  const meta = useSniperStore.getState().backtestMeta[presetId];
  if (!meta) return preset;

  return {
    ...preset,
    winRate: meta.winRate,
    trades: meta.trades,
    backtested: meta.backtested,
    dataSource: meta.dataSource,
    underperformer: meta.underperformer,
  };
}
