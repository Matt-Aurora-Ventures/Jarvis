import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { BagsGraduation } from '@/lib/bags-api';
import { isLegacyRecoveredPositionId, isReliableTradeForStats, sanitizePnlPercent } from '@/lib/position-reliability';

export type StrategyMode = 'conservative' | 'balanced' | 'aggressive';
export type TradeSignerMode = 'phantom' | 'session';
export type AutomationState = 'idle' | 'scanning' | 'executing_buy' | 'cooldown' | 'closing_all' | 'paused' | 'tripped';

export type AssetType = 'memecoin' | 'xstock' | 'prestock' | 'index' | 'bluechip' | 'bags';
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
  /** If backtested and win rate < 40% or profit factor < 1.0 */
  underperformer?: boolean;
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

const STRATEGY_SEED_META = {
  strategyRevision: 'v2-seed-2026-02-11',
  seedVersion: 'seed-v2',
} as const;

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
    name: 'PUMP FRESH TIGHT',
    description: 'V2 seed: fresh pumpswap tokens with tighter risk envelope for real-data calibration',
    winRate: 'Unverified',
    trades: 0,
    assetType: 'memecoin',
    autoWrPrimaryOverridePct: 50,
    config: {
      stopLossPct: 18, takeProfitPct: 45, trailingStopPct: 5,
      minLiquidityUsd: 5000, minScore: 40, maxTokenAgeHours: 24,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'micro_cap_surge',
    name: 'MICRO CAP SURGE',
    description: 'V2 seed: micro-cap surge strategy with reduced extreme stop/target values',
    winRate: 'Unverified',
    trades: 0,
    assetType: 'memecoin',
    config: {
      stopLossPct: 28, takeProfitPct: 140, trailingStopPct: 12,
      minLiquidityUsd: 3000, minScore: 30, maxTokenAgeHours: 24,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'elite',
    name: 'SNIPER ELITE',
    description: 'V2 seed: strict high-liquidity memecoin filter with moderated exits',
    winRate: 'NEW — strictest filter',
    trades: 0,
    assetType: 'memecoin',
    config: {
      stopLossPct: 15, takeProfitPct: 45, trailingStopPct: 5,
      minLiquidityUsd: 100000, minMomentum1h: 10, maxTokenAgeHours: 100,
      minVolLiqRatio: 2.0, tradingHoursGate: false, strategyMode: 'conservative',
    },
  },
  {
    id: 'momentum',
    name: 'MOMENTUM',
    description: 'V2 seed: momentum continuation with tighter profit capture and reduced trail',
    winRate: 'Unverified',
    trades: 0,
    assetType: 'memecoin',
    config: {
      stopLossPct: 18, takeProfitPct: 45, trailingStopPct: 5,
      minLiquidityUsd: 50000, minScore: 0, minMomentum1h: 5,
      minVolLiqRatio: 1.5, tradingHoursGate: false, strategyMode: 'conservative',
    },
  },
  {
    id: 'insight_j',
    name: 'INSIGHT-J',
    description: 'V2 seed: selective quality/momentum setup for younger tokens',
    winRate: 'Unverified',
    trades: 0,
    assetType: 'memecoin',
    config: {
      stopLossPct: 18, takeProfitPct: 50, trailingStopPct: 5,
      minLiquidityUsd: 50000, maxTokenAgeHours: 100, minMomentum1h: 10,
      tradingHoursGate: false, strategyMode: 'conservative',
    },
  },
  {
    id: 'hybrid_b',
    name: 'HYBRID-B v6',
    description: 'V2 seed: balanced setup with moderated exits and standard quality filters',
    winRate: 'Unverified',
    trades: 0,
    assetType: 'memecoin',
    config: {
      stopLossPct: 18, takeProfitPct: 50, trailingStopPct: 5,
      minLiquidityUsd: 50000, minMomentum1h: 5, minVolLiqRatio: 1.0,
      tradingHoursGate: false, strategyMode: 'conservative',
    },
  },
  {
    id: 'let_it_ride',
    name: 'LET IT RIDE',
    description: 'V2 seed: long-runner profile with moderated target and tighter trailing control',
    winRate: 'Unverified',
    trades: 0,
    assetType: 'memecoin',
    config: {
      stopLossPct: 20, takeProfitPct: 75, trailingStopPct: 3,
      minLiquidityUsd: 50000, minMomentum1h: 5, tradingHoursGate: false,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'loose',
    name: 'WIDE NET',
    description: 'V2 seed: broad scanner with wider SL and lower TP for faster mean capture',
    winRate: 'Unverified',
    trades: 0,
    assetType: 'memecoin',
    config: {
      stopLossPct: 22, takeProfitPct: 45, trailingStopPct: 5,
      minLiquidityUsd: 25000, minMomentum1h: 0, maxTokenAgeHours: 500,
      minVolLiqRatio: 0.5, tradingHoursGate: false, strategyMode: 'conservative',
    },
  },
  {
    id: 'genetic_best',
    name: 'GENETIC BEST',
    description: 'V2 seed: genetic baseline with reduced risk and target extremity for stability',
    winRate: 'Unverified',
    trades: 0,
    assetType: 'memecoin',
    config: {
      stopLossPct: 24, takeProfitPct: 120, trailingStopPct: 8,
      minLiquidityUsd: 3000, minScore: 43, maxTokenAgeHours: 24,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'genetic_v2',
    name: 'GENETIC V2',
    description: 'V2 seed: genetic v2 baseline tuned for realistic risk-reward during calibration',
    winRate: 'Unverified',
    trades: 0,
    assetType: 'memecoin',
    config: {
      stopLossPct: 28, takeProfitPct: 140, trailingStopPct: 8,
      minLiquidityUsd: 5000, minScore: 0,
      strategyMode: 'aggressive',
    },
  },
  // ─── xStocks / PreStocks / Indexes ───────────────────────────────────────
  // Traditional assets: real financial instruments, guaranteed liquidity.
  // SL/TP calibrated to actual stock/index daily ranges (SPY ~1-2%, AAPL ~2-4%).
  {
    id: 'xstock_intraday',
    name: 'XSTOCK INTRADAY',
    description: 'US stocks — V2 seed intraday envelope',
    winRate: 'Calibrated to 1-3% daily ranges',
    trades: 0,
    assetType: 'xstock',
    config: {
      stopLossPct: 3, takeProfitPct: 10, trailingStopPct: 2.2,
      minLiquidityUsd: 0, minScore: 40,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'xstock_swing',
    name: 'XSTOCK SWING',
    description: 'US stocks — V2 seed multi-day swing profile',
    winRate: 'Calibrated to weekly stock ranges',
    trades: 0,
    assetType: 'xstock',
    config: {
      stopLossPct: 6, takeProfitPct: 18, trailingStopPct: 4,
      minLiquidityUsd: 0, minScore: 50,
      strategyMode: 'balanced',
    },
  },
  {
    id: 'prestock_speculative',
    name: 'PRESTOCK SPEC',
    description: 'Pre-IPO — V2 seed speculative profile',
    winRate: 'Pre-IPO volatility adjusted',
    trades: 0,
    assetType: 'prestock',
    config: {
      stopLossPct: 8, takeProfitPct: 24, trailingStopPct: 5,
      minLiquidityUsd: 0, minScore: 30,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'index_intraday',
    name: 'INDEX INTRADAY',
    description: 'SPY/QQQ — V2 seed intraday index profile',
    winRate: 'Calibrated to SPY 0.5-1.5% daily range',
    trades: 0,
    assetType: 'index',
    config: {
      stopLossPct: 2.8, takeProfitPct: 9, trailingStopPct: 2,
      minLiquidityUsd: 0, minScore: 50,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'index_leveraged',
    name: 'INDEX TQQQ SWING',
    description: 'TQQQ 3x leveraged — V2 seed amplified index swing profile',
    winRate: 'Leveraged index calibrated',
    trades: 0,
    assetType: 'index',
    config: {
      stopLossPct: 7, takeProfitPct: 20, trailingStopPct: 4.5,
      minLiquidityUsd: 0, minScore: 40,
      strategyMode: 'aggressive',
    },
  },
  // ─── Blue Chip Solana — Established Tokens, 2yr+, High Liquidity ────────
  // Research-backed strategies from systematic trading literature:
  // - Mean Reversion: Buy oversold blue chips (RSI <30 equivalent), tight SL
  // - Trend Following: Ride established momentum, trailing stop captures gains
  // - Breakout Scalp: Catch range breakouts on high-volume blue chips
  //
  // Key parameters derived from:
  // - SOL avg daily volatility: 4-6% → SL 3-5%, TP 5-12%
  // - JUP/RAY avg daily volatility: 5-8% → SL 4-6%, TP 8-15%
  // - BONK/WIF avg daily volatility: 8-12% → SL 5-8%, TP 10-20%
  // - Academic: optimal trailing stop = 1x ATR ≈ daily volatility
  {
    id: 'bluechip_mean_revert',
    name: 'BLUE CHIP MEAN REVERT',
    description: 'V2 seed: buy oversold blue chips with reduced stop-out pressure',
    winRate: 'Seed (Not Promoted)',
    trades: 0,
    assetType: 'bluechip',
    config: {
      stopLossPct: 6, takeProfitPct: 12, trailingStopPct: 3,
      minLiquidityUsd: 200000, minScore: 55,
      maxTokenAgeHours: 99999,
      minMomentum1h: 0, // mean reversion buys dips — no momentum requirement
      minVolLiqRatio: 0.3,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'bluechip_trend_follow',
    name: 'BLUE CHIP TREND',
    description: 'V2 seed: trend-following on established tokens with wider trend envelope',
    winRate: 'Seed (Not Promoted)',
    trades: 0,
    assetType: 'bluechip',
    config: {
      stopLossPct: 7, takeProfitPct: 18, trailingStopPct: 5,
      minLiquidityUsd: 200000, minScore: 60,
      maxTokenAgeHours: 99999,
      minMomentum1h: 3, // require momentum for trend following
      minVolLiqRatio: 0.5,
      tradingHoursGate: false, // blue chips trade 24/7 on Solana
      strategyMode: 'balanced',
    },
  },
  {
    id: 'bluechip_breakout',
    name: 'BLUE CHIP BREAKOUT',
    description: 'V2 seed: high-volume breakout setup on top tokens with moderated exits',
    winRate: 'Seed (Not Promoted)',
    trades: 0,
    assetType: 'bluechip',
    config: {
      stopLossPct: 6, takeProfitPct: 16, trailingStopPct: 4,
      minLiquidityUsd: 200000, minScore: 65,
      maxTokenAgeHours: 99999,
      minMomentum1h: 5, // needs clear breakout momentum
      minVolLiqRatio: 1.5, // volume surge required (breakout signal)
      strategyMode: 'balanced',
    },
  },
  // ─── Bags.fm — Locked Liquidity, Community-Driven Tokens ─────────────────
  // All bags.fm tokens have locked liquidity (enforced by the platform).
  // Liquidity is NOT a risk factor — we focus on community, momentum, longevity.
  // Typical bags pattern: pump at launch → dump → second pump on community/builder activity.
  {
    id: 'bags_fresh_snipe',
    name: 'BAGS FRESH SNIPE',
    description: 'V2 seed: snipes fresh bags launches with moderated risk envelope.',
    winRate: 'Bags: locked liq, community-driven',
    trades: 0,
    assetType: 'bags',
    config: {
      stopLossPct: 18, takeProfitPct: 55, trailingStopPct: 5,
      minLiquidityUsd: 0, // bags locks liquidity — no minimum needed
      minScore: 35, maxTokenAgeHours: 48,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'bags_momentum',
    name: 'BAGS MOMENTUM',
    description: 'V2 seed: catches post-launch momentum on bags tokens with balanced exits.',
    winRate: 'Bags: momentum-driven entries',
    trades: 0,
    assetType: 'bags',
    config: {
      stopLossPct: 20, takeProfitPct: 100, trailingStopPct: 8,
      minLiquidityUsd: 0,
      minScore: 30, maxTokenAgeHours: 168,
      minMomentum1h: 5,
      strategyMode: 'balanced',
    },
  },
  {
    id: 'bags_value',
    name: 'BAGS VALUE HUNTER',
    description: 'V2 seed: high-quality bags tokens with stable, lower-volatility exit profile.',
    winRate: 'Bags: quality-focused',
    trades: 0,
    assetType: 'bags',
    config: {
      stopLossPct: 12, takeProfitPct: 30, trailingStopPct: 4,
      minLiquidityUsd: 0,
      minScore: 55, maxTokenAgeHours: 720,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'bags_dip_buyer',
    name: 'BAGS DIP BUYER',
    description: 'V2 seed: buys post-launch dips targeting second-cycle recovery moves.',
    winRate: 'Bags: mean-reversion play',
    trades: 0,
    assetType: 'bags',
    config: {
      stopLossPct: 25, takeProfitPct: 120, trailingStopPct: 8,
      minLiquidityUsd: 0,
      minScore: 25, maxTokenAgeHours: 336, // 2 weeks
      minMomentum1h: 0, // buys dips — no momentum needed
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'bags_bluechip',
    name: 'BAGS BLUE CHIP',
    description: 'V2 seed: established bags tokens with defensive exits and quality gating.',
    winRate: 'Bags: established tokens',
    trades: 0,
    assetType: 'bags',
    config: {
      stopLossPct: 12, takeProfitPct: 28, trailingStopPct: 4,
      minLiquidityUsd: 0,
      minScore: 60,
      maxTokenAgeHours: 99999,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'bags_conservative',
    name: 'BAGS CONSERVATIVE',
    description: 'V2 seed: conservative bags profile prioritizing survival and consistency.',
    winRate: 'Seed (Not Promoted)',
    trades: 0,
    assetType: 'bags',
    config: {
      stopLossPct: 14, takeProfitPct: 35, trailingStopPct: 5,
      minLiquidityUsd: 0,
      minScore: 40, maxTokenAgeHours: 336,
      strategyMode: 'conservative',
    },
  },
  {
    id: 'bags_aggressive',
    name: 'BAGS AGGRESSIVE',
    description: 'V2 seed: aggressive bags profile with tempered but still high-conviction reward targets.',
    winRate: 'Seed (Not Promoted)',
    trades: 0,
    assetType: 'bags',
    config: {
      stopLossPct: 30, takeProfitPct: 180, trailingStopPct: 12,
      minLiquidityUsd: 0,
      minScore: 10, maxTokenAgeHours: 336,
      strategyMode: 'aggressive',
    },
  },
  {
    id: 'bags_elite',
    name: 'BAGS ELITE',
    description: 'V2 seed: strict high-score bags filter with controlled exits.',
    winRate: 'Seed (Not Promoted)',
    trades: 0,
    assetType: 'bags',
    config: {
      stopLossPct: 14, takeProfitPct: 45, trailingStopPct: 6,
      minLiquidityUsd: 0,
      minScore: 70, maxTokenAgeHours: 336,
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

  // ─── Traditional Assets / Blue Chips — separate SL/TP universe ───
  // xStocks/indexes/prestocks/bluechips have fundamentally different volatility
  // than memecoins. A 100% TP on SPY is absurd; a 3% TP is normal.

  if (source === 'xstock') {
    // US stocks: typical daily range 1-4%, weekly 3-8%
    const absM = Math.abs(priceChange1h);
    if (absM >= 3) return { sl: 2, tp: 5, trail: 1.5, reasoning: `XSTOCK: strong momentum (${priceChange1h.toFixed(1)}% 1h) — wider targets` };
    return { sl: 1.5, tp: 3, trail: 1, reasoning: 'XSTOCK: standard intraday — tight SL/TP for stock-level volatility' };
  }
  if (source === 'index') {
    // Indexes: SPY daily range 0.5-2%, TQQQ 1.5-6% (3x leveraged)
    if (grad.symbol === 'TQQQx') return { sl: 3, tp: 8, trail: 2, reasoning: 'INDEX TQQQ: 3x leveraged — wider SL/TP' };
    return { sl: 0.8, tp: 1.5, trail: 0.5, reasoning: 'INDEX: tight scalping — indexes move slowly' };
  }
  if (source === 'prestock') {
    // Pre-IPO: higher vol than stocks, lower than memes
    return { sl: 5, tp: 15, trail: 3, reasoning: 'PRESTOCK: pre-IPO volatility — moderate SL/TP' };
  }
  if (source === 'bluechip') {
    // Established Solana tokens: daily vol 4-12% depending on tier
    const absM = Math.abs(priceChange1h);
    if (absM >= 10) return { sl: 5, tp: 15, trail: 4, reasoning: `BLUECHIP: high momentum (${priceChange1h.toFixed(1)}% 1h) — trend follow` };
    if (absM >= 5) return { sl: 4, tp: 12, trail: 3, reasoning: `BLUECHIP: moderate momentum — breakout setup` };
    if (volLiqRatio >= 1.5) return { sl: 4, tp: 12, trail: 3, reasoning: `BLUECHIP: volume surge (V/L ${volLiqRatio.toFixed(1)}x) — breakout` };
    return { sl: 3, tp: 8, trail: 2, reasoning: 'BLUECHIP: mean reversion — tight SL/TP for established tokens' };
  }

  // ─── Memecoin Strategy Selection (v4 backtest champion logic) ───
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
    memecoin:  { maxConsecutiveLosses: 9, maxDailyLossSol: 0.3, cooldownMinutes: 15 },
    bags:      { maxConsecutiveLosses: 12, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
    bluechip:  { maxConsecutiveLosses: 15, maxDailyLossSol: 1.0, cooldownMinutes: 30 },
    xstock:    { maxConsecutiveLosses: 12, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
    index:     { maxConsecutiveLosses: 12, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
    prestock:  { maxConsecutiveLosses: 9, maxDailyLossSol: 0.3, cooldownMinutes: 15 },
  },
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
  /** Monotonic strategy revision. Bumped whenever algo selection/config changes. */
  strategyEpoch: number;
  assetFilter: AssetType;
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

    const pnlLabel = !hasReliableCostBasis
      ? 'cost basis unavailable (excluded from stats)'
      : exitSolReceived != null
      ? `${realPnlSol >= 0 ? '+' : ''}${realPnlSol.toFixed(4)} SOL (real)`
      : `${realPnlPct.toFixed(1)}% (est)`;

    const execEvent: ExecutionEvent = {
      id: `exec-${Date.now()}-${execCounter}`,
      type: exitType,
      symbol: pos.symbol,
      mint: pos.mint,
      amount: pos.solInvested,
      pnlPercent: hasReliableCostBasis ? realPnlPct : undefined,
      txHash,
      timestamp: Date.now(),
      reason: `${status === 'trail_stop' ? 'TRAIL STOP' : status === 'expired' ? 'EXPIRED' : status.replace('_', ' ').toUpperCase()} — ${pnlLabel}`,
    };

    set((s) => {
      // ─── Circuit Breaker Update (global + per-asset) ───
      const cb = { ...s.circuitBreaker, perAsset: { ...s.circuitBreaker.perAsset } };
      const now = Date.now();
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
      }),
      // Rehydrate: restore durable fields + reset transient runtime state.
      onRehydrateStorage: () => (state) => {
        if (!state) return;

        // Migrate config defaults (new fields, etc.)
        state.config = { ...DEFAULT_CONFIG, ...(state.config as SniperConfig | undefined) };
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
