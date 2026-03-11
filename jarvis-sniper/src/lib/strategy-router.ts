/**
 * Thompson Sampling Strategy Router
 *
 * Multi-armed bandit strategy selection using Thompson Sampling.
 * Each strategy has a Beta distribution based on historical performance.
 *
 * This automatically:
 * - Routes capital to proven strategies
 * - Explores new strategies probabilistically
 * - Self-corrects when market regimes change
 *
 * @module strategy-router
 */

export interface StrategyPerformance {
  strategyId: string;
  wins: number;
  losses: number;
  totalTrades: number;
  totalProfitUsd: number;
  lastUpdated: number;
}

export interface StrategyRouterState {
  strategies: Map<string, StrategyPerformance>;
  minTradesForSelection: number;
}

const DEFAULT_MIN_TRADES = 10;

/**
 * Thompson Sampling Strategy Router
 *
 * Each strategy is modeled as a Beta distribution:
 * - alpha = wins + 1 (successes + 1 for prior)
 * - beta = losses + 1 (failures + 1 for prior)
 *
 * On each signal:
 * 1. Sample from each eligible strategy's Beta distribution
 * 2. Select strategy with highest sample
 * 3. Execute that strategy
 * 4. Update alpha or beta based on outcome
 */
export class StrategyRouter {
  private strategies: Map<string, StrategyPerformance> = new Map();
  private minTradesForSelection: number;

  constructor(minTradesForSelection: number = DEFAULT_MIN_TRADES) {
    this.minTradesForSelection = minTradesForSelection;
  }

  /**
   * Register a new strategy or update existing
   */
  registerStrategy(
    strategyId: string,
    initialWins: number = 0,
    initialLosses: number = 0,
    initialProfit: number = 0
  ): void {
    const existing = this.strategies.get(strategyId);

    if (existing) {
      // Update existing
      existing.wins += initialWins;
      existing.losses += initialLosses;
      existing.totalTrades = existing.wins + existing.losses;
      existing.totalProfitUsd += initialProfit;
      existing.lastUpdated = Date.now();
    } else {
      // Register new
      this.strategies.set(strategyId, {
        strategyId,
        wins: initialWins + 1, // Start with 1 for uninformative prior
        losses: initialLosses + 1,
        totalTrades: initialWins + initialLosses + 2,
        totalProfitUsd: initialProfit,
        lastUpdated: Date.now(),
      });
    }
  }

  /**
   * Get Beta distribution parameters for a strategy
   */
  private getBetaParams(strategyId: string): { alpha: number; beta: number } | null {
    const perf = this.strategies.get(strategyId);
    if (!perf || perf.totalTrades < 2) {
      // Return uniform prior if not enough data
      return { alpha: 1, beta: 1 };
    }
    return {
      alpha: perf.wins,
      beta: perf.losses,
    };
  }

  /**
   * Sample from Beta distribution (approximation)
   *
   * Using the approximation that Beta(a, b) ≈ Gamma(a, 1) / (Gamma(a, 1) + Gamma(b, 1))
   * For simplicity, we use a uniform random weighted by the strategy's performance
   */
  private sampleFromBeta(alpha: number, beta: number): number {
    // Simple approximation: use inverse transform sampling
    // For large alpha + beta, Beta approaches Normal
    const total = alpha + beta;

    if (total > 100) {
      // Use normal approximation
      const mean = alpha / total;
      const variance = (alpha * beta) / (total * total * (total + 1));
      const std = Math.sqrt(variance);

      // Box-Muller transform for normal random
      const u1 = Math.random();
      const u2 = Math.random();
      const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);

      return Math.max(0.001, Math.min(0.999, mean + z * std));
    }

    // For small samples, use weighted random
    const samples = 10;
    let sum = 0;
    for (let i = 0; i < samples; i++) {
      // Generate sample using geometric mean approximation
      const r = Math.random();
      sum += Math.pow(r, alpha - 1) * Math.pow(1 - r, beta - 1);
    }

    return sum / samples;
  }

  /**
   * Select the best strategy using Thompson Sampling
   *
   * @param eligibleStrategyIds - List of strategies that can be selected
   * @returns The selected strategy ID or null if none eligible
   */
  selectStrategy(eligibleStrategyIds: string[]): string | null {
    if (eligibleStrategyIds.length === 0) {
      return null;
    }

    if (eligibleStrategyIds.length === 1) {
      return eligibleStrategyIds[0];
    }

    // Sample from each eligible strategy's Beta distribution
    let bestStrategy = eligibleStrategyIds[0];
    let bestSample = -1;

    for (const strategyId of eligibleStrategyIds) {
      const params = this.getBetaParams(strategyId);
      if (!params) continue;

      // Skip strategies without enough trades for selection
      const perf = this.strategies.get(strategyId);
      if (perf && perf.totalTrades < this.minTradesForSelection) {
        // Give new strategies a chance with a random sample
        const sample = this.sampleFromBeta(params.alpha, params.beta) * 0.5;
        if (sample > bestSample) {
          bestSample = sample;
          bestStrategy = strategyId;
        }
        continue;
      }

      const sample = this.sampleFromBeta(params.alpha, params.beta);

      if (sample > bestSample) {
        bestSample = sample;
        bestStrategy = strategyId;
      }
    }

    return bestStrategy;
  }

  /**
   * Update strategy performance after a trade
   *
   * @param strategyId - The strategy that was executed
   * @param profitable - Whether the trade was profitable
   * @param profitUsd - Profit in USD (positive) or loss (negative)
   */
  updateOutcome(strategyId: string, profitable: boolean, profitUsd: number = 0): void {
    let perf = this.strategies.get(strategyId);

    if (!perf) {
      // Register new strategy if not exists
      this.registerStrategy(strategyId);
      perf = this.strategies.get(strategyId)!;
    }

    if (profitable) {
      perf.wins += 1;
    } else {
      perf.losses += 1;
    }

    perf.totalTrades = perf.wins + perf.losses;
    perf.totalProfitUsd += profitUsd;
    perf.lastUpdated = Date.now();
  }

  /**
   * Get effective win rate for a strategy
   * Expected value of Beta distribution = alpha / (alpha + beta)
   */
  getEffectiveWinRate(strategyId: string): number {
    const params = this.getBetaParams(strategyId);
    if (!params) return 0.5;

    return params.alpha / (params.alpha + params.beta);
  }

  /**
   * Get all strategies sorted by performance
   */
  getRankedStrategies(): StrategyPerformance[] {
    return Array.from(this.strategies.values())
      .sort((a, b) => {
        const wrA = a.wins / a.totalTrades;
        const wrB = b.wins / b.totalTrades;
        return wrB - wrA;
      });
  }

  /**
   * Get statistics for a specific strategy
   */
  getStrategyStats(strategyId: string): {
    winRate: number;
    effectiveWinRate: number;
    totalTrades: number;
    totalProfit: number;
    isDeployable: boolean;
  } | null {
    const perf = this.strategies.get(strategyId);
    if (!perf) return null;

    const winRate = perf.wins / perf.totalTrades;
    const effectiveWinRate = this.getEffectiveWinRate(strategyId);

    return {
      winRate,
      effectiveWinRate,
      totalTrades: perf.totalTrades,
      totalProfit: perf.totalProfitUsd,
      isDeployable: perf.totalTrades >= this.minTradesForSelection,
    };
  }

  /**
   * Persist router state to JSON
   */
  toJSON(): object {
    return {
      strategies: Array.from(this.strategies.entries()),
      minTradesForSelection: this.minTradesForSelection,
    };
  }

  /**
   * Load router state from JSON
   */
  static fromJSON(json: any): StrategyRouter {
    const router = new StrategyRouter(json.minTradesForSelection || DEFAULT_MIN_TRADES);

    if (json.strategies && Array.isArray(json.strategies)) {
      for (const [id, perf] of json.strategies) {
        router.strategies.set(id, perf as StrategyPerformance);
      }
    }

    return router;
  }
}

/**
 * Check if a strategy is deployable based on Wilson Score
 */
export function isStrategyDeployable(
  wins: number,
  totalTrades: number,
  confidence: number = 0.95
): { deployable: boolean; reason: string; wilsonLowerBound: number } {
  if (totalTrades < 10) {
    return {
      deployable: false,
      reason: `Insufficient trades: ${totalTrades} (minimum 10 for Thompson Sampling)`,
      wilsonLowerBound: 0,
    };
  }

  // Wilson Score Interval calculation
  const pHat = wins / totalTrades;
  const z = 1.96; // 95% confidence
  const denominator = 1 + (z * z) / totalTrades;
  const center = pHat + (z * z) / (2 * totalTrades);
  const margin = z * Math.sqrt((pHat * (1 - pHat) / totalTrades) + (z * z / (4 * totalTrades * totalTrades)));

  const wilsonLowerBound = (center - margin) / denominator;

  // Require at least 52% lower bound for deployment
  if (wilsonLowerBound < 0.52) {
    return {
      deployable: false,
      reason: `Wilson lower bound ${wilsonLowerBound.toFixed(3)} < 0.52 threshold`,
      wilsonLowerBound,
    };
  }

  return {
    deployable: true,
    reason: `Wilson LB: ${wilsonLowerBound.toFixed(3)}, WR: ${(pHat * 100).toFixed(1)}%, n=${totalTrades}`,
    wilsonLowerBound,
  };
}
