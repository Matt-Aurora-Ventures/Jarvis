export interface StrategyBelief {
  strategyId: string;
  alpha: number;
  beta: number;
  wins: number;
  losses: number;
  totalOutcomes: number;
  lastOutcome?: 'win' | 'loss';
  lastOutcomeAt?: number;
  lastTxHash?: string;
  updatedAt: number;
}

export interface ThompsonCandidate {
  strategyId: string;
}

export interface ThompsonSample {
  strategyId: string;
  sample: number;
  alpha: number;
  beta: number;
  mean: number;
}

export interface ThompsonSelection {
  selected: ThompsonSample;
  ranked: ThompsonSample[];
}

const DEFAULT_ALPHA = 1;
const DEFAULT_BETA = 1;
const DEFAULT_MIN_PARAM = 0.1;
const MIN_GAMMA = 0.5;
const MAX_GAMMA = 0.999;

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

function safeParam(value: number, fallback: number): number {
  return Math.max(DEFAULT_MIN_PARAM, Number.isFinite(value) ? value : fallback);
}

function standardNormal(random: () => number): number {
  let u = 0;
  let v = 0;
  while (u <= Number.EPSILON) u = random();
  while (v <= Number.EPSILON) v = random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

/**
 * Marsaglia-Tsang gamma sampler.
 * Uses the shape-boost trick for k < 1 to keep a single stable implementation path.
 */
export function sampleGamma(shape: number, random: () => number = Math.random): number {
  const k = Number(shape);
  if (!Number.isFinite(k) || k <= 0) return 0;
  if (k < 1) {
    const u = Math.max(Number.EPSILON, random());
    return sampleGamma(k + 1, random) * Math.pow(u, 1 / k);
  }

  const d = k - 1 / 3;
  const c = 1 / Math.sqrt(9 * d);
  for (let i = 0; i < 256; i++) {
    const x = standardNormal(random);
    const vBase = 1 + c * x;
    if (vBase <= 0) continue;
    const v = vBase * vBase * vBase;
    const u = random();
    if (u < 1 - 0.0331 * x * x * x * x) return d * v;
    if (Math.log(Math.max(Number.EPSILON, u)) < 0.5 * x * x + d * (1 - v + Math.log(v))) {
      return d * v;
    }
  }
  return Math.max(DEFAULT_MIN_PARAM, k);
}

export function sampleBeta(alpha: number, beta: number, random: () => number = Math.random): number {
  const a = safeParam(alpha, DEFAULT_ALPHA);
  const b = safeParam(beta, DEFAULT_BETA);
  const x = sampleGamma(a, random);
  const y = sampleGamma(b, random);
  const denom = x + y;
  if (!Number.isFinite(denom) || denom <= Number.EPSILON) return 0.5;
  return clamp(x / denom, 0, 1);
}

function compareSamples(a: ThompsonSample, b: ThompsonSample): number {
  if (b.sample !== a.sample) return b.sample - a.sample;
  if (b.mean !== a.mean) return b.mean - a.mean;
  return a.strategyId.localeCompare(b.strategyId);
}

export function selectStrategyWithThompson(
  candidates: ThompsonCandidate[],
  beliefs: Record<string, StrategyBelief>,
  random: () => number = Math.random,
): ThompsonSelection | null {
  if (!Array.isArray(candidates) || candidates.length === 0) return null;

  const ranked: ThompsonSample[] = candidates
    .map((candidate) => {
      const strategyId = String(candidate.strategyId || '').trim();
      if (!strategyId) return null;
      const belief = beliefs[strategyId];
      const alpha = safeParam(Number(belief?.alpha), DEFAULT_ALPHA);
      const beta = safeParam(Number(belief?.beta), DEFAULT_BETA);
      return {
        strategyId,
        sample: sampleBeta(alpha, beta, random),
        alpha,
        beta,
        mean: alpha / (alpha + beta),
      } as ThompsonSample;
    })
    .filter((row): row is ThompsonSample => !!row)
    .sort(compareSamples);

  if (ranked.length === 0) return null;
  return { selected: ranked[0], ranked };
}

export function createDefaultStrategyBelief(strategyId: string, now = Date.now()): StrategyBelief {
  return {
    strategyId,
    alpha: DEFAULT_ALPHA,
    beta: DEFAULT_BETA,
    wins: 0,
    losses: 0,
    totalOutcomes: 0,
    updatedAt: now,
  };
}

export function applyDiscountedOutcome(
  beliefs: Record<string, StrategyBelief>,
  args: {
    strategyId: string;
    outcome: 'win' | 'loss';
    gamma?: number;
    minParam?: number;
    now?: number;
    txHash?: string;
  },
): Record<string, StrategyBelief> {
  const now = Number(args.now || Date.now());
  const gamma = clamp(Number(args.gamma ?? 0.9), MIN_GAMMA, MAX_GAMMA);
  const minParam = Math.max(DEFAULT_MIN_PARAM, Number(args.minParam ?? DEFAULT_MIN_PARAM));
  const strategyId = String(args.strategyId || '').trim();
  if (!strategyId) return beliefs;

  const next: Record<string, StrategyBelief> = {};
  for (const [id, belief] of Object.entries(beliefs || {})) {
    const alpha = Math.max(minParam, safeParam(Number(belief?.alpha), DEFAULT_ALPHA) * gamma);
    const beta = Math.max(minParam, safeParam(Number(belief?.beta), DEFAULT_BETA) * gamma);
    next[id] = {
      ...belief,
      strategyId: id,
      alpha,
      beta,
      wins: Math.max(0, Math.floor(Number(belief?.wins || 0))),
      losses: Math.max(0, Math.floor(Number(belief?.losses || 0))),
      totalOutcomes: Math.max(0, Math.floor(Number(belief?.totalOutcomes || 0))),
      updatedAt: now,
    };
  }

  const current = next[strategyId] || createDefaultStrategyBelief(strategyId, now);
  const isWin = args.outcome === 'win';
  next[strategyId] = {
    ...current,
    strategyId,
    alpha: isWin ? current.alpha + 1 : current.alpha,
    beta: isWin ? current.beta : current.beta + 1,
    wins: current.wins + (isWin ? 1 : 0),
    losses: current.losses + (isWin ? 0 : 1),
    totalOutcomes: current.totalOutcomes + 1,
    lastOutcome: isWin ? 'win' : 'loss',
    lastOutcomeAt: now,
    lastTxHash: args.txHash ? String(args.txHash) : current.lastTxHash,
    updatedAt: now,
  };

  return next;
}
