import type { SourceHealthSnapshot } from '@/lib/data-plane/types';
import { deriveRedundancyState, scoreSourceReliability } from '@/lib/data-plane/reliability';

export async function runSourceProbe<T>(args: {
  source: string;
  fetcher: () => Promise<T>;
  activeSources?: number;
  message?: string;
}): Promise<{ ok: true; value: T; snapshot: SourceHealthSnapshot } | { ok: false; error: string; snapshot: SourceHealthSnapshot }> {
  const started = Date.now();
  try {
    const value = await args.fetcher();
    const latencyMs = Date.now() - started;
    const reliabilityScore = scoreSourceReliability({ ok: true, latencyMs, httpStatus: 200, freshnessMs: 0, errorBudgetBurn: 0 });
    return {
      ok: true,
      value,
      snapshot: {
        source: args.source,
        checkedAt: new Date().toISOString(),
        ok: true,
        freshnessMs: 0,
        latencyMs,
        httpStatus: 200,
        reliabilityScore,
        errorBudgetBurn: 0,
        redundancyState: deriveRedundancyState(args.activeSources ?? 1),
        message: args.message,
      },
    };
  } catch (error) {
    const latencyMs = Date.now() - started;
    const message = error instanceof Error ? error.message : 'source fetch failed';
    const reliabilityScore = scoreSourceReliability({ ok: false, latencyMs, httpStatus: 500, freshnessMs: 0, errorBudgetBurn: 1 });
    return {
      ok: false,
      error: message,
      snapshot: {
        source: args.source,
        checkedAt: new Date().toISOString(),
        ok: false,
        freshnessMs: 0,
        latencyMs,
        httpStatus: 500,
        reliabilityScore,
        errorBudgetBurn: 1,
        redundancyState: deriveRedundancyState(args.activeSources ?? 1),
        message,
      },
    };
  }
}
