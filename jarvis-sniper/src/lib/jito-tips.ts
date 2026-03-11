/**
 * Dynamic Jito Tip Calculator
 *
 * Calculates optimal Jito tips for Solana transactions based on:
 * - Projected profit from the trade
 * - Market volatility
 * - Whether it's a sniper entry (high priority)
 *
 * This replaces static hardcoded tips with dynamic calculation.
 *
 * @module jito-tips
 */

export type MarketVolatility = 'low' | 'medium' | 'high' | 'extreme';

export interface JitoTipConfig {
  /** Projected profit in USD */
  projectedProfitUsd: number;
  /** Current market volatility */
  volatility: MarketVolatility;
  /** Is this a sniper entry (launch sniping) */
  isSniperEntry: boolean;
  /** Current SOL price in USD */
  solPriceUsd: number;
  /** Minimum tip in SOL (default 0.001) */
  minTipSol?: number;
  /** Maximum tip as fraction of projected profit (default 0.20) */
  maxProfitFraction?: number;
}

// Base tip levels in SOL
const BASE_TIP_BY_VOLATILITY: Record<MarketVolatility, number> = {
  low: 0.001,      // 0.001 SOL
  medium: 0.003,   // 0.003 SOL
  high: 0.005,     // 0.005 SOL
  extreme: 0.01,   // 0.01 SOL
};

// Sniper entry multiplier
const SNIPER_MULTIPLIER = 2.0;

// Maximum tip as fraction of projected profit
const DEFAULT_MAX_PROFIT_FRACTION = 0.20;

/**
 * Calculate optimal Jito tip for a transaction
 *
 * Rules:
 * - Baseline (low volatility, non-sniper): 0.001 SOL
 * - Medium volatility: 0.003-0.005 SOL
 * - High volatility / sniper: min(0.02 SOL, projected_profit × 0.15 / SOL_price)
 * - Extreme volatility (graduation events): min(0.05 SOL, projected_profit × 0.20 / SOL_price)
 * - Never tip more than 20% of projected profit
 *
 * @param config - Jito tip configuration
 * @returns Optimal tip in SOL
 */
export function calculateJitoTip(config: JitoTipConfig): number {
  const {
    projectedProfitUsd,
    volatility,
    isSniperEntry,
    solPriceUsd,
    minTipSol = 0.001,
    maxProfitFraction = DEFAULT_MAX_PROFIT_FRACTION,
  } = config;

  // 1. Start with base tip based on volatility
  let tipSol = BASE_TIP_BY_VOLATILITY[volatility];

  // 2. Apply sniper multiplier for high-priority entries
  if (isSniperEntry) {
    tipSol *= SNIPER_MULTIPLIER;
  }

  // 3. Calculate maximum tip based on projected profit
  const maxTipByProfit = (projectedProfitUsd / solPriceUsd) * maxProfitFraction;

  // 4. Apply volatility scaling for high/extreme volatility
  if (volatility === 'high') {
    tipSol = Math.min(tipSol, 0.02); // Cap at 0.02 SOL for high volatility
  } else if (volatility === 'extreme') {
    tipSol = Math.min(tipSol, 0.05); // Cap at 0.05 SOL for extreme volatility
  }

  // 5. Ensure we don't exceed profit-based maximum
  tipSol = Math.min(tipSol, maxTipByProfit);

  // 6. Ensure minimum tip
  tipSol = Math.max(tipSol, minTipSol);

  return Math.round(tipSol * 1000000) / 1000000; // Round to 6 decimal places
}

/**
 * Calculate tip for a specific use case
 */
export function calculateTipForUseCase(
  useCase: 'normal' | 'sniper' | 'graduation' | 'emergency',
  projectedProfitUsd: number,
  solPriceUsd: number = 150
): number {
  const volatilityMap: Record<string, MarketVolatility> = {
    normal: 'low',
    sniper: 'high',
    graduation: 'extreme',
    emergency: 'extreme',
  };

  return calculateJitoTip({
    projectedProfitUsd,
    volatility: volatilityMap[useCase],
    isSniperEntry: useCase === 'sniper' || useCase === 'graduation',
    solPriceUsd,
  });
}

/**
 * Estimate tip in USD for display
 */
export function tipToUsd(tipSol: number, solPriceUsd: number): number {
  return tipSol * solPriceUsd;
}

/**
 * Get tip recommendation for UI display
 */
export function getTipRecommendation(
  tradeSizeSol: number,
  solPriceUsd: number,
  volatility: MarketVolatility = 'medium'
): {
  tipSol: number;
  tipUsd: number;
  description: string;
} {
  const tradeSizeUsd = tradeSizeSol * solPriceUsd;

  // Estimate 5% profit for tip calculation
  const estimatedProfit = tradeSizeUsd * 0.05;

  const tipSol = calculateJitoTip({
    projectedProfitUsd: estimatedProfit,
    volatility,
    isSniperEntry: false,
    solPriceUsd,
  });

  return {
    tipSol,
    tipUsd: tipToUsd(tipSol, solPriceUsd),
    description: `${volatility} volatility tip recommendation`,
  };
}
