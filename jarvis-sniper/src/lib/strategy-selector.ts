export type StrategyOutcome = 'win' | 'loss';

/**
 * Discounted Beta-Bernoulli belief state per strategy.
 *
 * This is intentionally small and deterministic so it can be persisted in the
 * client store and migrated safely over time.
 */
export interface StrategyBelief {
  strategyId: string;
  alpha: number;
  beta: number;
  wins: number;
  losses: number;
  totalOutcomes: number;
  lastOutcome?: StrategyOutcome;
  lastOutcomeAt?: number;
  lastTxHash?: string;
  updatedAt: number;
}

export interface ApplyDiscountedOutcomeArgs {
  strategyId: string;
  outcome: StrategyOutcome;
  /**
   * Discount factor in (0, 1]. Lower = forget history faster.
   * Used for non-stationary markets.
   */
  gamma: number;
  /** Used for idempotency so a single trade cannot be counted twice. */
  txHash: string;
  now?: number;
}

export interface ThompsonCandidate {
  strategyId: string;
}

export interface ThompsonRankedStrategy {
  strategyId: string;
  sample: number;
  mean: number;
  alpha: number;
  beta: number;
  evidence: number;
}

export interface ThompsonSelection {
  selected: ThompsonRankedStrategy;
  ranked: ThompsonRankedStrategy[];
}

export function createDefaultStrategyBelief(strategyId: string, now = Date.now()): StrategyBelief {
  return {
    strategyId,
    alpha: 1,
    beta: 1,
    wins: 0,
    losses: 0,
    totalOutcomes: 0,
    updatedAt: now,
  };
}

function clampShape(v: number): number {
  const n = Number(v);
  if (!Number.isFinite(n)) return 1;
  return Math.max(0.1, n);
}

/**
 * Gamma(shape, 1) sampler via Marsaglia-Tsang.
 * This is sufficient for Thompson sampling and avoids pulling in heavy deps.
 */
function sampleGamma(shapeRaw: number): number {
  let shape = clampShape(shapeRaw);
  if (shape < 1) {
    const u = Math.random();
    return sampleGamma(shape + 1) * Math.pow(u, 1 / shape);
  }

  const d = shape - 1 / 3;
  const c = 1 / Math.sqrt(9 * d);

  for (;;) {
    let x = 0;
    let v = 0;
    do {
      const u1 = Math.random();
      const u2 = Math.random();
      const z = Math.sqrt(-2 * Math.log(Math.max(Number.MIN_VALUE, u1))) * Math.cos(2 * Math.PI * u2);
      x = z;
      v = 1 + c * x;
    } while (v <= 0);

    v = v * v * v;
    const u = Math.random();

    if (u < 1 - 0.0331 * (x * x) * (x * x)) return d * v;
    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v;
  }
}

export function sampleBeta(alphaRaw: number, betaRaw: number): number {
  const alpha = clampShape(alphaRaw);
  const beta = clampShape(betaRaw);
  const x = sampleGamma(alpha);
  const y = sampleGamma(beta);
  const denom = x + y;
  if (!Number.isFinite(denom) || denom <= 0) return 0.5;
  const out = x / denom;
  if (!Number.isFinite(out)) return 0.5;
  return Math.min(1, Math.max(0, out));
}

export function selectStrategyWithThompson(
  candidates: ThompsonCandidate[],
  beliefs: Record<string, StrategyBelief>,
): ThompsonSelection | null {
  if (!Array.isArray(candidates) || candidates.length === 0) return null;

  const ranked = candidates
    .map((candidate) => {
      const strategyId = String(candidate?.strategyId || '').trim();
      if (!strategyId) return null;
      const belief = beliefs?.[strategyId] ?? createDefaultStrategyBelief(strategyId);
      const alpha = clampShape(Number(belief.alpha));
      const beta = clampShape(Number(belief.beta));
      const sample = sampleBeta(alpha, beta);
      const mean = alpha / (alpha + beta);
      const evidence = Math.max(0, Math.floor(Number(belief.totalOutcomes || 0)));

      return {
        strategyId,
        sample,
        mean: Number.isFinite(mean) ? mean : 0.5,
        alpha,
        beta,
        evidence,
      } as ThompsonRankedStrategy;
    })
    .filter((row): row is ThompsonRankedStrategy => !!row)
    .sort((a, b) => {
      if (b.sample !== a.sample) return b.sample - a.sample;
      if (b.mean !== a.mean) return b.mean - a.mean;
      if (b.evidence !== a.evidence) return b.evidence - a.evidence;
      return a.strategyId.localeCompare(b.strategyId);
    });

  if (ranked.length === 0) return null;
  return {
    selected: ranked[0],
    ranked,
  };
}

/**
 * Apply a single outcome to a strategy belief using discounted Thompson updates.
 *
 * Math: discount previous evidence away from the (1,1) prior, then add 1 win/loss.
 * alpha' = 1 + gamma * (alpha - 1) + I[outcome=win]
 * beta'  = 1 + gamma * (beta  - 1) + I[outcome=loss]
 */
export function applyDiscountedOutcome(
  beliefs: Record<string, StrategyBelief>,
  args: ApplyDiscountedOutcomeArgs,
): Record<string, StrategyBelief> {
  const strategyId = String(args.strategyId || '').trim();
  if (!strategyId) return beliefs;

  const outcome = args.outcome;
  if (outcome !== 'win' && outcome !== 'loss') return beliefs;

  const txHash = String(args.txHash || '').trim();
  if (!txHash) return beliefs;

  const gammaRaw = Number(args.gamma);
  const gamma = Number.isFinite(gammaRaw) ? Math.max(0.0, Math.min(1.0, gammaRaw)) : 1.0;
  const now = Number.isFinite(Number(args.now)) ? Number(args.now) : Date.now();

  const existing = beliefs[strategyId];
  if (existing?.lastTxHash && existing.lastTxHash === txHash) return beliefs;

  const alpha0 = Number.isFinite(existing?.alpha) ? Number(existing?.alpha) : 1;
  const beta0 = Number.isFinite(existing?.beta) ? Number(existing?.beta) : 1;

  // Discount evidence away from the (1,1) prior.
  const discountedAlpha = 1 + (alpha0 - 1) * gamma;
  const discountedBeta = 1 + (beta0 - 1) * gamma;

  const alpha = Math.max(0.1, discountedAlpha + (outcome === 'win' ? 1 : 0));
  const beta = Math.max(0.1, discountedBeta + (outcome === 'loss' ? 1 : 0));

  const wins0 = Number.isFinite(existing?.wins) ? Math.max(0, Math.floor(Number(existing?.wins))) : 0;
  const losses0 = Number.isFinite(existing?.losses) ? Math.max(0, Math.floor(Number(existing?.losses))) : 0;
  const total0 = Number.isFinite(existing?.totalOutcomes) ? Math.max(0, Math.floor(Number(existing?.totalOutcomes))) : 0;

  const next: StrategyBelief = {
    strategyId,
    alpha,
    beta,
    wins: wins0 + (outcome === 'win' ? 1 : 0),
    losses: losses0 + (outcome === 'loss' ? 1 : 0),
    totalOutcomes: total0 + 1,
    lastOutcome: outcome,
    lastOutcomeAt: now,
    lastTxHash: txHash,
    updatedAt: now,
  };

  return { ...beliefs, [strategyId]: next };
}
