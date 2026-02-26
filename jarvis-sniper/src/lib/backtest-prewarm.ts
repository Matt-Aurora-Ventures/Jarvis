export type PrewarmFamily =
  | 'memecoin'
  | 'bags'
  | 'bluechip'
  | 'xstock'
  | 'prestock'
  | 'index'
  | 'xstock_index';

export type PrewarmMode = 'quick' | 'full' | 'grid';
export type PrewarmDataScale = 'fast' | 'thorough';
export type PrewarmSourcePolicy = 'gecko_only' | 'allow_birdeye_fallback';

export interface PrewarmBodyOptions {
  mode?: PrewarmMode;
  dataScale?: PrewarmDataScale;
  sourcePolicy?: PrewarmSourcePolicy;
  maxTokens?: number;
  lookbackHours?: number;
  includeEvidence?: boolean;
  includeReport?: boolean;
  strictNoSynthetic?: boolean;
}

type JsonLike = Record<string, unknown>;

function normalizeRunAppUrl(raw: unknown): string | null {
  if (typeof raw !== 'string') return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;
  try {
    const parsed = new URL(trimmed);
    const host = String(parsed.hostname || '').trim().toLowerCase();
    if (parsed.protocol !== 'https:') return null;
    if (!host.endsWith('.a.run.app')) return null;
    return `https://${host}`;
  } catch {
    return null;
  }
}

export function resolvePrewarmBaseUrl(healthPayload: unknown, fallbackOrigin: string): string {
  const payload = (healthPayload || {}) as JsonLike;
  const backend = (payload.backend || {}) as JsonLike;
  const direct = normalizeRunAppUrl(backend.cloudRunTagUrl);
  if (direct) return direct;
  return String(fallbackOrigin || '').trim().replace(/\/+$/, '');
}

function normalizeMode(value: unknown): PrewarmMode {
  return value === 'full' || value === 'grid' ? value : 'quick';
}

function normalizeDataScale(value: unknown): PrewarmDataScale {
  return value === 'thorough' ? 'thorough' : 'fast';
}

function normalizeSourcePolicy(value: unknown): PrewarmSourcePolicy {
  return value === 'gecko_only' ? 'gecko_only' : 'allow_birdeye_fallback';
}

export function buildPrewarmBody(
  family: PrewarmFamily,
  runId: string,
  options: PrewarmBodyOptions = {},
): JsonLike {
  const payload: JsonLike = {
    runId,
    family,
    mode: normalizeMode(options.mode),
    dataScale: normalizeDataScale(options.dataScale),
    sourcePolicy: normalizeSourcePolicy(options.sourcePolicy),
    strictNoSynthetic: options.strictNoSynthetic !== false,
    includeEvidence: options.includeEvidence === true,
    includeReport: options.includeReport === true,
  };

  if (Number.isFinite(options.maxTokens)) {
    payload.maxTokens = Math.max(1, Math.floor(Number(options.maxTokens)));
  }
  if (Number.isFinite(options.lookbackHours)) {
    payload.lookbackHours = Math.max(24, Math.floor(Number(options.lookbackHours)));
  }

  return payload;
}

export function isPrewarmTerminalState(state: string): boolean {
  return state === 'completed' || state === 'partial' || state === 'failed';
}
