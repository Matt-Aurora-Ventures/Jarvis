import type { SourceHealthSnapshot } from '@/lib/data-plane/types';

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

export function scoreSourceReliability(args: {
  ok: boolean;
  latencyMs?: number | null;
  httpStatus?: number | null;
  freshnessMs?: number;
  errorBudgetBurn?: number;
}): number {
  const statusPenalty = args.ok ? 0 : 0.45;
  const latencyPenalty = args.latencyMs && args.latencyMs > 0
    ? Math.min(0.25, args.latencyMs / 40_000)
    : 0;
  const statusCodePenalty = args.httpStatus && args.httpStatus >= 400
    ? Math.min(0.35, (args.httpStatus - 399) / 800)
    : 0;
  const freshnessPenalty = args.freshnessMs && args.freshnessMs > 0
    ? Math.min(0.2, args.freshnessMs / (1000 * 60 * 60 * 24))
    : 0;
  const burnPenalty = args.errorBudgetBurn && args.errorBudgetBurn > 0
    ? Math.min(0.2, args.errorBudgetBurn)
    : 0;

  return Number(clamp01(1 - statusPenalty - latencyPenalty - statusCodePenalty - freshnessPenalty - burnPenalty).toFixed(6));
}

export function deriveRedundancyState(activeSources: number): SourceHealthSnapshot['redundancyState'] {
  if (activeSources <= 1) return 'single_source';
  if (activeSources === 2) return 'degraded';
  return 'healthy';
}
