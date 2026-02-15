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