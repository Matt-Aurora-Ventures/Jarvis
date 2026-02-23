import type { StrategyFamily } from './backtest-campaign-ledger';

export interface StrategyMetrics {
  strategyId: string;
  family: StrategyFamily;
  trades: number;
  winRate: number; // 0..1
  expectancy: number;
  profitFactor: number;
  maxDrawdownPct: number;
  netPnl: number;
  sharpe?: number;
  stability?: number;
  sourceDiagnostics?: Record<string, unknown>;
}

export interface ScoredStrategyMetrics extends StrategyMetrics {
  normalizedExpectancy: number;
  normalizedStability: number;
  normalizedWinRate: number;
  normalizedNetPnl: number;
  compositeScore: number;
}

export interface PromotionDecision {
  promoted: boolean;
  reason: string;
}

function clamp01(v: number): number {
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(1, v));
}

function normalizeSeries(values: number[]): number[] {
  if (values.length === 0) return [];
  const finite = values.map((v) => (Number.isFinite(v) ? v : 0));
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  if (max === min) return finite.map(() => 0.5);
  return finite.map((v) => clamp01((v - min) / (max - min)));
}

export function drawdownPenalizedStability(metric: StrategyMetrics): number {
  const sharpe = Number.isFinite(metric.sharpe ?? NaN) ? (metric.sharpe as number) : 0;
  const fallbackStability = Number.isFinite(metric.stability ?? NaN) ? (metric.stability as number) : sharpe;
  const ddPenalty = (Number.isFinite(metric.maxDrawdownPct) ? metric.maxDrawdownPct : 100) / 100;
  return fallbackStability - ddPenalty;
}

export function scoreStrategySet(input: StrategyMetrics[]): ScoredStrategyMetrics[] {
  if (input.length === 0) return [];

  const expectancyNorm = normalizeSeries(input.map((m) => m.expectancy));
  const stabilityNorm = normalizeSeries(input.map((m) => drawdownPenalizedStability(m)));
  const winNorm = normalizeSeries(input.map((m) => m.winRate));
  const pnlNorm = normalizeSeries(input.map((m) => m.netPnl));

  const out: ScoredStrategyMetrics[] = [];
  for (let i = 0; i < input.length; i++) {
    const composite =
      0.4 * expectancyNorm[i] +
      0.3 * stabilityNorm[i] +
      0.2 * winNorm[i] +
      0.1 * pnlNorm[i];
    out.push({
      ...input[i],
      normalizedExpectancy: expectancyNorm[i],
      normalizedStability: stabilityNorm[i],
      normalizedWinRate: winNorm[i],
      normalizedNetPnl: pnlNorm[i],
      compositeScore: composite,
    });
  }
  return out.sort((a, b) => b.compositeScore - a.compositeScore);
}

function familyDrawdownGate(family: StrategyFamily): number {
  return family === 'memecoin' || family === 'bags' ? 45 : 30;
}

function familyWinRateGate(family: StrategyFamily): number {
  return family === 'memecoin' || family === 'bags' ? 0.4 : 0.45;
}

export function evaluatePromotion(metric: StrategyMetrics): PromotionDecision {
  if (metric.trades < 5000) {
    return { promoted: false, reason: `trades ${metric.trades} < 5000` };
  }
  if (!(metric.expectancy > 0)) {
    return { promoted: false, reason: `expectancy ${metric.expectancy.toFixed(4)} <= 0` };
  }
  if (!(metric.profitFactor >= 1.05)) {
    return { promoted: false, reason: `profitFactor ${metric.profitFactor.toFixed(3)} < 1.05` };
  }
  const ddGate = familyDrawdownGate(metric.family);
  if (!(metric.maxDrawdownPct <= ddGate)) {
    return { promoted: false, reason: `maxDrawdownPct ${metric.maxDrawdownPct.toFixed(2)} > ${ddGate}` };
  }
  const wrGate = familyWinRateGate(metric.family);
  if (!(metric.winRate >= wrGate)) {
    return { promoted: false, reason: `winRate ${(metric.winRate * 100).toFixed(2)}% < ${(wrGate * 100).toFixed(0)}%` };
  }
  return { promoted: true, reason: 'passed promotion gates' };
}

export function aggregateRunSummaries(
  strategyId: string,
  family: StrategyFamily,
  rows: Array<{
    trades: number;
    winRate: number;
    expectancy: number;
    profitFactor: number;
    maxDrawdownPct: number;
    netPnl: number;
    sharpe?: number;
  }>,
): StrategyMetrics {
  if (rows.length === 0) {
    return {
      strategyId,
      family,
      trades: 0,
      winRate: 0,
      expectancy: 0,
      profitFactor: 0,
      maxDrawdownPct: 100,
      netPnl: 0,
      sharpe: 0,
    };
  }
  const totalTrades = rows.reduce((s, r) => s + Math.max(0, r.trades), 0);
  const weight = (tr: number) => (totalTrades > 0 ? Math.max(0, tr) / totalTrades : 0);
  const weighted = <T extends keyof (typeof rows)[number]>(k: T): number =>
    rows.reduce((s, r) => s + (Number(r[k]) || 0) * weight(r.trades), 0);

  return {
    strategyId,
    family,
    trades: totalTrades,
    winRate: weighted('winRate'),
    expectancy: weighted('expectancy'),
    profitFactor: weighted('profitFactor'),
    maxDrawdownPct: Math.max(...rows.map((r) => Number(r.maxDrawdownPct) || 0)),
    netPnl: rows.reduce((s, r) => s + (Number(r.netPnl) || 0), 0),
    sharpe: weighted('sharpe'),
  };
}

