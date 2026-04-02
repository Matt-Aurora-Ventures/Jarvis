import {
  isReliableTradeForStats,
  resolvePositionPnlPercent,
} from '@/lib/position-reliability';
import type {
  BacktestMetaEntry,
  Position,
  StrategyLifecycle,
  StrategyPreset,
  StrategyRegime,
} from '@/stores/useSniperStore';

export interface StrategyLiveEvidence {
  confirmedLiveTrades: number;
  confirmedWins: number;
  confirmedLosses: number;
  consecutiveConfirmedLosses: number;
  liveProfitFactor: number;
  liveMaxDrawdownPct: number;
  fillRatePct: number;
  liveWinRatePct: number;
  paperWinRateDeltaPct?: number;
  failedExits: number;
  unresolvedExits: number;
}

export interface ResolvedStrategyLifecycle {
  lifecycle: StrategyLifecycle;
  regime: StrategyRegime;
  reason: string;
  sampleStage: 'tiny' | 'sanity' | 'stability' | 'promotion';
  paperEligible: boolean;
  autoEligible: boolean;
  confirmedLiveTrades: number;
  liveProfitFactor: number;
  liveMaxDrawdownPct: number;
  fillRatePct: number;
}

export const STRATEGY_LIFECYCLE_LABELS: Record<StrategyLifecycle, string> = {
  research: 'Research',
  paper: 'Paper',
  micro_live: 'Micro Live',
  production: 'Production',
  quarantined: 'Quarantined',
  disabled: 'Disabled',
};

const STAGE_ORDER: Array<ResolvedStrategyLifecycle['sampleStage']> = [
  'tiny',
  'sanity',
  'stability',
  'promotion',
];

function toFiniteNumber(value: unknown, fallback = 0): number {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function inferSampleStage(totalTrades: number): ResolvedStrategyLifecycle['sampleStage'] {
  const trades = Math.max(0, Math.floor(totalTrades));
  if (trades >= 5000) return 'promotion';
  if (trades >= 1000) return 'stability';
  if (trades >= 100) return 'sanity';
  return 'tiny';
}

function maxStage(
  a: ResolvedStrategyLifecycle['sampleStage'],
  b: ResolvedStrategyLifecycle['sampleStage'],
): ResolvedStrategyLifecycle['sampleStage'] {
  return STAGE_ORDER[Math.max(STAGE_ORDER.indexOf(a), STAGE_ORDER.indexOf(b))] || a;
}

function winRatePctFromMeta(meta?: BacktestMetaEntry): number {
  if (!meta) return 0;
  if (Number.isFinite(meta.winRatePct)) return Number(meta.winRatePct);
  const parsed = Number.parseFloat(String(meta.winRate || '').replace('%', '').trim());
  return Number.isFinite(parsed) ? parsed : 0;
}

export function getRegimeWilsonFloor(regime: StrategyRegime): number {
  if (regime === 'established_sol' || regime === 'bluechip_sol') return 38;
  return 30;
}

export function createEmptyStrategyLiveEvidence(): StrategyLiveEvidence {
  return {
    confirmedLiveTrades: 0,
    confirmedWins: 0,
    confirmedLosses: 0,
    consecutiveConfirmedLosses: 0,
    liveProfitFactor: 0,
    liveMaxDrawdownPct: 0,
    fillRatePct: 0,
    liveWinRatePct: 0,
    paperWinRateDeltaPct: 0,
    failedExits: 0,
    unresolvedExits: 0,
  };
}

function lifecycleResult(args: {
  lifecycle: StrategyLifecycle;
  regime: StrategyRegime;
  reason: string;
  sampleStage: ResolvedStrategyLifecycle['sampleStage'];
  liveEvidence: StrategyLiveEvidence;
}): ResolvedStrategyLifecycle {
  const paperEligible =
    args.lifecycle === 'paper'
    || args.lifecycle === 'micro_live'
    || args.lifecycle === 'production';
  const autoEligible = args.lifecycle === 'micro_live' || args.lifecycle === 'production';

  return {
    lifecycle: args.lifecycle,
    regime: args.regime,
    reason: args.reason,
    sampleStage: args.sampleStage,
    paperEligible,
    autoEligible,
    confirmedLiveTrades: args.liveEvidence.confirmedLiveTrades,
    liveProfitFactor: toFiniteNumber(args.liveEvidence.liveProfitFactor, 0),
    liveMaxDrawdownPct: toFiniteNumber(args.liveEvidence.liveMaxDrawdownPct, 0),
    fillRatePct: toFiniteNumber(args.liveEvidence.fillRatePct, 0),
  };
}

function seededBaselineLifecycle(
  preset: StrategyPreset,
  regime: StrategyRegime,
): ResolvedStrategyLifecycle {
  const stage = inferSampleStage(preset.trades);
  const liveEvidence = createEmptyStrategyLiveEvidence();

  if (preset.lifecycleSeed === 'disabled') {
    return lifecycleResult({
      lifecycle: 'disabled',
      regime,
      reason: preset.statusReason,
      sampleStage: stage,
      liveEvidence,
    });
  }

  if (preset.lifecycleSeed === 'quarantined') {
    return lifecycleResult({
      lifecycle: 'quarantined',
      regime,
      reason: preset.statusReason,
      sampleStage: stage,
      liveEvidence,
    });
  }

  if (preset.lifecycleSeed === 'paper' && preset.trades >= 100) {
    return lifecycleResult({
      lifecycle: 'paper',
      regime,
      reason: preset.statusReason,
      sampleStage: maxStage(stage, 'sanity'),
      liveEvidence,
    });
  }

  return lifecycleResult({
    lifecycle: 'research',
    regime,
    reason: 'Research only until a real-data backtest clears the paper gate.',
    sampleStage: stage,
    liveEvidence,
  });
}

export function buildStrategyLiveEvidence(
  positions: Position[],
  strategyId: string,
  paperWinRatePct?: number,
): StrategyLiveEvidence {
  const relevant = positions
    .filter((position) => position.strategyId === strategyId)
    .filter((position) => position.status !== 'open')
    .filter((position) => isReliableTradeForStats(position))
    .sort((a, b) => Number(a.entryTime || 0) - Number(b.entryTime || 0));

  if (relevant.length === 0) return createEmptyStrategyLiveEvidence();

  let gains = 0;
  let losses = 0;
  let equityPct = 0;
  let peakPct = 0;
  let maxDrawdown = 0;
  let wins = 0;
  let lossCount = 0;

  for (const position of relevant) {
    const pnlSol = Number.isFinite(Number(position.realPnlSol))
      ? Number(position.realPnlSol)
      : Number(position.pnlSol || 0);
    const pnlPct = resolvePositionPnlPercent(position);
    const isWin = pnlSol > 0 || (pnlSol === 0 && pnlPct >= 0);
    if (isWin) {
      wins += 1;
      gains += Math.max(0, pnlSol);
    } else {
      lossCount += 1;
      losses += Math.abs(Math.min(0, pnlSol));
    }

    equityPct += pnlPct;
    peakPct = Math.max(peakPct, equityPct);
    maxDrawdown = Math.max(maxDrawdown, peakPct - equityPct);
  }

  let consecutiveConfirmedLosses = 0;
  for (let index = relevant.length - 1; index >= 0; index -= 1) {
    const position = relevant[index];
    const pnlSol = Number.isFinite(Number(position.realPnlSol))
      ? Number(position.realPnlSol)
      : Number(position.pnlSol || 0);
    const pnlPct = resolvePositionPnlPercent(position);
    const isWin = pnlSol > 0 || (pnlSol === 0 && pnlPct >= 0);
    if (isWin) break;
    consecutiveConfirmedLosses += 1;
  }

  const confirmedLiveTrades = relevant.length;
  const liveWinRatePct = confirmedLiveTrades > 0
    ? (wins / confirmedLiveTrades) * 100
    : 0;
  const liveProfitFactor = losses > 0 ? gains / losses : gains > 0 ? gains : 0;
  const paperWinRateDeltaPct = Number.isFinite(paperWinRatePct)
    ? Math.abs(liveWinRatePct - Number(paperWinRatePct))
    : 0;

  return {
    confirmedLiveTrades,
    confirmedWins: wins,
    confirmedLosses: lossCount,
    consecutiveConfirmedLosses,
    liveProfitFactor: Number(liveProfitFactor.toFixed(4)),
    liveMaxDrawdownPct: Number(maxDrawdown.toFixed(4)),
    fillRatePct: confirmedLiveTrades > 0 ? 100 : 0,
    liveWinRatePct: Number(liveWinRatePct.toFixed(4)),
    paperWinRateDeltaPct: Number(paperWinRateDeltaPct.toFixed(4)),
    failedExits: 0,
    unresolvedExits: 0,
  };
}

export function buildStrategyLiveEvidenceMap(
  positions: Position[],
  backtestMeta: Record<string, BacktestMetaEntry> = {},
): Record<string, StrategyLiveEvidence> {
  const strategyIds = new Set(
    positions
      .map((position) => String(position.strategyId || '').trim())
      .filter(Boolean),
  );

  const out: Record<string, StrategyLiveEvidence> = {};
  for (const strategyId of strategyIds) {
    out[strategyId] = buildStrategyLiveEvidence(
      positions,
      strategyId,
      winRatePctFromMeta(backtestMeta[strategyId]),
    );
  }
  return out;
}

export function resolveStrategyLifecycle(args: {
  preset: StrategyPreset;
  meta?: BacktestMetaEntry;
  liveEvidence?: StrategyLiveEvidence;
}): ResolvedStrategyLifecycle {
  const preset = args.preset;
  const meta = args.meta;
  const regime = preset.regime;
  const seededBaseline = seededBaselineLifecycle(preset, regime);
  const liveEvidence = {
    ...createEmptyStrategyLiveEvidence(),
    ...(args.liveEvidence || {}),
  };

  if (seededBaseline.lifecycle === 'disabled') {
    return lifecycleResult({
      lifecycle: 'disabled',
      regime,
      reason: preset.statusReason,
      sampleStage: seededBaseline.sampleStage,
      liveEvidence,
    });
  }

  const totalTrades = Math.max(
    0,
    Math.floor(toFiniteNumber(meta?.totalTrades, meta?.trades ?? preset.trades)),
  );
  const sampleStage = maxStage(
    meta?.stage || inferSampleStage(totalTrades),
    seededBaseline.sampleStage,
  );

  if (liveEvidence.consecutiveConfirmedLosses >= 3) {
    return lifecycleResult({
      lifecycle: 'quarantined',
      regime,
      reason: 'Quarantined after 3 consecutive confirmed losses.',
      sampleStage,
      liveEvidence,
    });
  }

  if (toFiniteNumber(liveEvidence.liveMaxDrawdownPct, 0) >= 15) {
    return lifecycleResult({
      lifecycle: 'quarantined',
      regime,
      reason: 'Quarantined after live drawdown breached 15%.',
      sampleStage,
      liveEvidence,
    });
  }

  const paperWinRateDeltaPct = toFiniteNumber(
    liveEvidence.paperWinRateDeltaPct,
    Math.abs(toFiniteNumber(liveEvidence.liveWinRatePct, 0) - winRatePctFromMeta(meta)),
  );
  if (paperWinRateDeltaPct > 20) {
    return lifecycleResult({
      lifecycle: 'quarantined',
      regime,
      reason: 'Quarantined because live win rate drifted too far from paper.',
      sampleStage,
      liveEvidence: {
        ...liveEvidence,
        paperWinRateDeltaPct,
      },
    });
  }

  if (seededBaseline.lifecycle === 'quarantined') {
    return lifecycleResult({
      lifecycle: 'quarantined',
      regime,
      reason: preset.statusReason,
      sampleStage,
      liveEvidence: {
        ...liveEvidence,
        paperWinRateDeltaPct,
      },
    });
  }

  if (!meta) {
    return lifecycleResult({
      lifecycle: seededBaseline.lifecycle,
      regime,
      reason: seededBaseline.reason,
      sampleStage: seededBaseline.sampleStage,
      liveEvidence,
    });
  }

  if (!meta.backtested || meta.dataSource === 'client') {
    return lifecycleResult({
      lifecycle: 'research',
      regime,
      reason: 'Research only until a real-data backtest is available.',
      sampleStage,
      liveEvidence,
    });
  }

  const winRateLower95Pct = toFiniteNumber(meta.winRateLower95Pct, Number.NaN);
  const profitFactorValue = toFiniteNumber(meta.profitFactorValue, Number.NaN);
  const netPnlPct = toFiniteNumber(meta.netPnlPct, Number.NaN);
  const regimeFloor = getRegimeWilsonFloor(regime);

  if (Number.isFinite(winRateLower95Pct) && winRateLower95Pct < regimeFloor) {
    return lifecycleResult({
      lifecycle: 'quarantined',
      regime,
      reason: `Quarantined because the Wilson lower-95 bound is below the ${regimeFloor}% regime floor.`,
      sampleStage,
      liveEvidence,
    });
  }

  if (
    (Number.isFinite(profitFactorValue) && profitFactorValue < 1.0)
    || (Number.isFinite(netPnlPct) && netPnlPct <= 0)
  ) {
    return lifecycleResult({
      lifecycle: 'quarantined',
      regime,
      reason: 'Quarantined because paper edge is not positive after costs.',
      sampleStage,
      liveEvidence,
    });
  }

  const paperEligible =
    totalTrades >= 100
    && Number.isFinite(profitFactorValue)
    && profitFactorValue >= 1.05
    && Number.isFinite(netPnlPct)
    && netPnlPct > 0
    && (!Number.isFinite(winRateLower95Pct) || winRateLower95Pct >= regimeFloor);

  if (!paperEligible) {
    return lifecycleResult({
      lifecycle: 'research',
      regime,
      reason: 'Research only until the strategy clears paper validation thresholds.',
      sampleStage,
      liveEvidence,
    });
  }

  if (
    liveEvidence.confirmedLiveTrades >= 30
    && toFiniteNumber(liveEvidence.liveProfitFactor, 0) >= 1.0
    && toFiniteNumber(liveEvidence.liveMaxDrawdownPct, 0) < 15
    && toFiniteNumber(liveEvidence.fillRatePct, 0) >= 85
    && paperWinRateDeltaPct <= 15
  ) {
    return lifecycleResult({
      lifecycle: 'production',
      regime,
      reason: 'Production eligible after confirmed micro-live evidence matched paper expectations.',
      sampleStage,
      liveEvidence: {
        ...liveEvidence,
        paperWinRateDeltaPct,
      },
    });
  }

  if (
    liveEvidence.confirmedLiveTrades >= 1
    && liveEvidence.confirmedLiveTrades < 30
    && toFiniteNumber(liveEvidence.liveProfitFactor, 0) >= 0.95
  ) {
    return lifecycleResult({
      lifecycle: 'micro_live',
      regime,
      reason: 'Micro-live eligible after confirmed reliable trades cleared the paper gate.',
      sampleStage,
      liveEvidence: {
        ...liveEvidence,
        paperWinRateDeltaPct,
      },
    });
  }

  return lifecycleResult({
    lifecycle: 'paper',
    regime,
    reason: 'Paper validated. Awaiting confirmed reliable live trades before automation.',
    sampleStage,
    liveEvidence: {
      ...liveEvidence,
      paperWinRateDeltaPct,
    },
  });
}

export function buildStrategyLifecycleMap(args: {
  presets: StrategyPreset[];
  backtestMeta?: Record<string, BacktestMetaEntry>;
  positions?: Position[];
}): Record<string, ResolvedStrategyLifecycle> {
  const backtestMeta = args.backtestMeta || {};
  const liveEvidenceById = buildStrategyLiveEvidenceMap(args.positions || [], backtestMeta);
  const out: Record<string, ResolvedStrategyLifecycle> = {};

  for (const preset of args.presets) {
    out[preset.id] = resolveStrategyLifecycle({
      preset,
      meta: backtestMeta[preset.id],
      liveEvidence: liveEvidenceById[preset.id],
    });
  }

  return out;
}
