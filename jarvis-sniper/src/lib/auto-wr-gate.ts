import type {
  AssetType,
  BacktestMetaEntry,
  SniperConfig,
  StrategyPreset,
} from '@/stores/useSniperStore';

export interface WrGateCandidate {
  strategyId: string;
  assetType?: AssetType;
  meta?: BacktestMetaEntry;
  primaryThresholdOverridePct?: number;
}

export interface WrGateQualification {
  ok: boolean;
  reason:
    | 'missing_meta'
    | 'not_backtested'
    | 'insufficient_sample'
    | 'missing_metric'
    | 'below_threshold'
    | 'passed';
  effectiveWrPct: number;
  thresholdPct: number;
  metric: 'winRateLower95Pct' | 'winRatePct';
  totalTrades: number;
}

export interface WrGateResolution {
  usedThreshold: number;
  eligibleCount: number;
  eligible: WrGateCandidate[];
  mode: 'primary' | 'fallback' | 'none';
}

export interface WrGateSelection {
  selected: WrGateCandidate | null;
  resolution: WrGateResolution;
  selectedThresholdPct?: number;
  selectedThresholdSource?: 'global_primary' | 'primary_override' | 'fallback';
}

function toFiniteNumber(value: unknown, fallback = 0): number {
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function parseWinRatePct(meta: BacktestMetaEntry | undefined): number {
  if (!meta) return 0;
  if (Number.isFinite(meta.winRatePct)) return Number(meta.winRatePct);
  const parsed = Number.parseFloat(String(meta.winRate || '').replace('%', '').trim());
  return Number.isFinite(parsed) ? parsed : 0;
}

function getMetric(meta: BacktestMetaEntry, method: SniperConfig['autoWrMethod']): {
  metric: 'winRateLower95Pct' | 'winRatePct';
  value: number;
} {
  if (method === 'wilson95_lower') {
    const lower = toFiniteNumber(meta.winRateLower95Pct, Number.NaN);
    if (Number.isFinite(lower)) {
      return { metric: 'winRateLower95Pct', value: lower };
    }
  }
  return { metric: 'winRatePct', value: parseWinRatePct(meta) };
}

export function scopeAllowsAsset(
  scope: SniperConfig['autoWrScope'],
  assetType: AssetType | undefined,
): boolean {
  const asset = assetType || 'memecoin';
  if (scope === 'all') return true;
  if (scope === 'memecoin') return asset === 'memecoin';
  return asset === 'memecoin' || asset === 'bags';
}

export function qualifiesByWrGate(
  meta: BacktestMetaEntry | undefined,
  config: Pick<
    SniperConfig,
    'autoWrMinTrades' | 'autoWrMethod' | 'autoWrPrimaryPct'
  >,
  thresholdPct = config.autoWrPrimaryPct,
): WrGateQualification {
  if (!meta) {
    return {
      ok: false,
      reason: 'missing_meta',
      effectiveWrPct: 0,
      thresholdPct,
      metric: config.autoWrMethod === 'wilson95_lower' ? 'winRateLower95Pct' : 'winRatePct',
      totalTrades: 0,
    };
  }
  if (!meta.backtested) {
    return {
      ok: false,
      reason: 'not_backtested',
      effectiveWrPct: 0,
      thresholdPct,
      metric: config.autoWrMethod === 'wilson95_lower' ? 'winRateLower95Pct' : 'winRatePct',
      totalTrades: Math.max(0, Math.floor(toFiniteNumber(meta.totalTrades, meta.trades))),
    };
  }

  const totalTrades = Math.max(0, Math.floor(toFiniteNumber(meta.totalTrades, meta.trades)));
  if (totalTrades < Math.max(0, Math.floor(toFiniteNumber(config.autoWrMinTrades, 0)))) {
    return {
      ok: false,
      reason: 'insufficient_sample',
      effectiveWrPct: 0,
      thresholdPct,
      metric: config.autoWrMethod === 'wilson95_lower' ? 'winRateLower95Pct' : 'winRatePct',
      totalTrades,
    };
  }

  const resolvedMetric = getMetric(meta, config.autoWrMethod);
  const wrValue = toFiniteNumber(resolvedMetric.value, Number.NaN);
  if (!Number.isFinite(wrValue)) {
    return {
      ok: false,
      reason: 'missing_metric',
      effectiveWrPct: 0,
      thresholdPct,
      metric: resolvedMetric.metric,
      totalTrades,
    };
  }

  if (wrValue < thresholdPct) {
    return {
      ok: false,
      reason: 'below_threshold',
      effectiveWrPct: wrValue,
      thresholdPct,
      metric: resolvedMetric.metric,
      totalTrades,
    };
  }

  return {
    ok: true,
    reason: 'passed',
    effectiveWrPct: wrValue,
    thresholdPct,
    metric: resolvedMetric.metric,
    totalTrades,
  };
}

export function resolveAdaptiveThreshold(
  candidates: WrGateCandidate[],
  config: Pick<
    SniperConfig,
    'autoWrPrimaryPct' | 'autoWrFallbackPct' | 'autoWrMinTrades' | 'autoWrMethod'
  >,
): WrGateResolution {
  const primary = Math.max(0, toFiniteNumber(config.autoWrPrimaryPct, 70));
  const fallback = Math.max(0, toFiniteNumber(config.autoWrFallbackPct, 50));

  const primaryEligible = candidates.filter((c) =>
    qualifiesByWrGate(
      c.meta,
      config,
      Number.isFinite(c.primaryThresholdOverridePct)
        ? Math.max(0, Number(c.primaryThresholdOverridePct))
        : primary,
    ).ok,
  );
  if (primaryEligible.length > 0) {
    return {
      usedThreshold: primary,
      eligibleCount: primaryEligible.length,
      eligible: primaryEligible,
      mode: 'primary',
    };
  }

  const fallbackEligible = candidates.filter((c) =>
    qualifiesByWrGate(c.meta, config, fallback).ok,
  );
  if (fallbackEligible.length > 0) {
    return {
      usedThreshold: fallback,
      eligibleCount: fallbackEligible.length,
      eligible: fallbackEligible,
      mode: 'fallback',
    };
  }

  return {
    usedThreshold: primary,
    eligibleCount: 0,
    eligible: [],
    mode: 'none',
  };
}

function candidateSortScore(candidate: WrGateCandidate): {
  netPnlPct: number;
  lower95: number;
  profitFactor: number;
  pointWr: number;
  trades: number;
} {
  const meta = candidate.meta;
  return {
    netPnlPct: toFiniteNumber(meta?.netPnlPct, Number.NEGATIVE_INFINITY),
    lower95: toFiniteNumber(meta?.winRateLower95Pct, Number.NEGATIVE_INFINITY),
    profitFactor: toFiniteNumber(meta?.profitFactorValue, Number.NEGATIVE_INFINITY),
    pointWr: parseWinRatePct(meta),
    trades: Math.max(0, Math.floor(toFiniteNumber(meta?.totalTrades, meta?.trades))),
  };
}

function compareCandidates(a: WrGateCandidate, b: WrGateCandidate): number {
  const sa = candidateSortScore(a);
  const sb = candidateSortScore(b);
  if (sb.netPnlPct !== sa.netPnlPct) return sb.netPnlPct - sa.netPnlPct;
  if (sb.lower95 !== sa.lower95) return sb.lower95 - sa.lower95;
  if (sb.profitFactor !== sa.profitFactor) return sb.profitFactor - sa.profitFactor;
  if (sb.pointWr !== sa.pointWr) return sb.pointWr - sa.pointWr;
  if (sb.trades !== sa.trades) return sb.trades - sa.trades;
  return a.strategyId.localeCompare(b.strategyId);
}

export function selectBestWrGateStrategy(
  candidates: WrGateCandidate[],
  config: Pick<
    SniperConfig,
    | 'autoWrPrimaryPct'
    | 'autoWrFallbackPct'
    | 'autoWrMinTrades'
    | 'autoWrMethod'
  >,
): WrGateSelection {
  const resolution = resolveAdaptiveThreshold(candidates, config);
  if (resolution.eligible.length === 0) {
    return { selected: null, resolution };
  }
  const [selected] = [...resolution.eligible].sort(compareCandidates);
  const primary = Math.max(0, toFiniteNumber(config.autoWrPrimaryPct, 70));
  const overridePct = Number.isFinite(selected?.primaryThresholdOverridePct)
    ? Math.max(0, Number(selected?.primaryThresholdOverridePct))
    : undefined;
  if (resolution.mode === 'fallback') {
    return {
      selected: selected || null,
      resolution,
      selectedThresholdPct: Math.max(0, toFiniteNumber(config.autoWrFallbackPct, 50)),
      selectedThresholdSource: 'fallback',
    };
  }
  return {
    selected: selected || null,
    resolution,
    selectedThresholdPct: overridePct ?? primary,
    selectedThresholdSource: overridePct !== undefined ? 'primary_override' : 'global_primary',
  };
}

export function buildWrGateCandidates(
  presets: StrategyPreset[],
  backtestMeta: Record<string, BacktestMetaEntry>,
  scope: SniperConfig['autoWrScope'],
): WrGateCandidate[] {
  return presets
    .filter((p) => scopeAllowsAsset(scope, p.assetType))
    .map((p) => ({
      strategyId: p.id,
      assetType: p.assetType || 'memecoin',
      meta: backtestMeta[p.id],
      primaryThresholdOverridePct: p.autoWrPrimaryOverridePct,
    }));
}

export function gateStatusBadge(
  meta: BacktestMetaEntry | undefined,
  config: Pick<
    SniperConfig,
    | 'autoWrPrimaryPct'
    | 'autoWrFallbackPct'
    | 'autoWrMinTrades'
    | 'autoWrMethod'
  >,
  primaryThresholdOverridePct?: number,
): 'Gate Pass @70' | 'Gate Pass @50' | 'Insufficient Sample' | null {
  if (!meta?.backtested) return null;
  const trades = Math.max(0, Math.floor(toFiniteNumber(meta.totalTrades, meta.trades)));
  if (trades < Math.max(0, Math.floor(toFiniteNumber(config.autoWrMinTrades, 0)))) {
    return 'Insufficient Sample';
  }
  const primary = Number.isFinite(primaryThresholdOverridePct)
    ? Math.max(0, Number(primaryThresholdOverridePct))
    : Math.max(0, toFiniteNumber(config.autoWrPrimaryPct, 70));
  const fallback = Math.max(0, toFiniteNumber(config.autoWrFallbackPct, 50));
  if (qualifiesByWrGate(meta, config, primary).ok) {
    return primary >= 70 ? 'Gate Pass @70' : 'Gate Pass @50';
  }
  if (qualifiesByWrGate(meta, config, fallback).ok) return 'Gate Pass @50';
  return null;
}
