/**
 * Realistic Cost Model for Solana DEX Trading
 *
 * This module provides realistic fee and cost modeling for backtesting
 * and live trading. It addresses the critical issue that basic fee models
 * underestimate real trading costs on Solana AMMs.
 *
 * Key costs modeled:
 * - DEX swap fees (0.01-2% depending on pool tier)
 * - AMM price impact (trade_size / (2 × pool_liquidity))
 * - MEV/sandwich attack costs (0.5-3%+)
 * - Creator fees (Bags.fm 1% perpetual)
 * - Priority fees (network congestion)
 *
 * @module fee-model
 */

export type AssetLiquidityTier = 'high' | 'mid' | 'micro' | 'bags_pre_grad' | 'bags_post_grad' | 'xstock';

export interface TradeCost {
  /** AMM swap fee percentage */
  dexFeePct: number;
  /** AMM price impact percentage */
  priceImpactPct: number;
  /** Expected MEV/sandwich cost percentage */
  mevCostPct: number;
  /** Creator fee percentage (Bags.fm perpetual) */
  creatorFeePct: number;
  /** Priority fee in SOL */
  priorityFeeSol: number;
  /** Total cost percentage (sum of all percentage costs) */
  totalCostPct: number;
}

export interface FeeModelConfig {
  /** Asset liquidity tier */
  tier: AssetLiquidityTier;
  /** Pool liquidity in USD */
  poolLiquidityUsd: number;
  /** Trade size in USD */
  tradeSizeUsd: number;
  /** Is this a Bags.fm token */
  isBagsToken: boolean;
  /** Is token in pre-graduation bonding curve phase */
  isPreGraduation: boolean;
  /** Current SOL price for priority fee calculation */
  solPriceUsd: number;
  /** Market volatility level */
  volatility: 'low' | 'medium' | 'high' | 'extreme';
}

// Default DEX fees by pool tier
const DEX_FEE_BY_TIER: Record<AssetLiquidityTier, number> = {
  high: 0.003,      // 0.3% - SOL/USDC major pairs
  mid: 0.01,        // 1.0% - Established tokens
  micro: 0.02,       // 2.0% - Small caps
  bags_pre_grad: 0.003, // 0.3% - Bonding curve (lower fee during curve)
  bags_post_grad: 0.025, // 2.5% - Newly graduated (thin pool)
  xstock: 0.01,     // 1.0% - Tokenized stocks
};

// MEV cost estimates by volatility
const MEV_COST_BY_VOLATILITY: Record<string, number> = {
  low: 0.005,      // 0.5%
  medium: 0.01,    // 1.0%
  high: 0.02,      // 2.0%
  extreme: 0.03,   // 3.0%
};

/**
 * Calculate realistic trade costs for a given trade
 *
 * @param config - Fee model configuration
 * @returns TradeCost object with all cost components
 */
export function calculateTradeCost(config: FeeModelConfig): TradeCost {
  const {
    tier,
    poolLiquidityUsd,
    tradeSizeUsd,
    isBagsToken,
    isPreGraduation,
    solPriceUsd,
    volatility,
  } = config;

  // 1. DEX swap fee
  let dexFeePct = DEX_FEE_BY_TIER[tier];

  // Adjust for Bags token graduation status
  if (isBagsToken && !isPreGraduation) {
    dexFeePct = DEX_FEE_BY_TIER.bags_post_grad;
  } else if (isBagsToken && isPreGraduation) {
    dexFeePct = DEX_FEE_BY_TIER.bags_pre_grad;
  }

  // 2. AMM Price Impact
  // Formula: impact = trade_size / (2 × pool_liquidity)
  // This is the classic AMM price impact formula
  let priceImpactPct = 0;
  if (poolLiquidityUsd > 0) {
    priceImpactPct = tradeSizeUsd / (2 * poolLiquidityUsd);
    // Cap at reasonable maximum (50% for extremely illiquid)
    priceImpactPct = Math.min(priceImpactPct, 0.5);
  }

  // 3. MEV/Sandwich cost
  const mevCostPct = MEV_COST_BY_VOLATILITY[volatility];

  // 4. Creator fee (Bags.fm perpetual 1% each way = 2% round trip)
  let creatorFeePct = 0;
  if (isBagsToken) {
    creatorFeePct = 0.02; // 1% entry + 1% exit
  }

  // 5. Priority fee (dynamic based on volatility)
  const priorityFeeSol = calculatePriorityFee(volatility, solPriceUsd);

  // 6. Total cost
  const totalCostPct = dexFeePct + priceImpactPct + mevCostPct + creatorFeePct;

  return {
    dexFeePct,
    priceImpactPct,
    mevCostPct,
    creatorFeePct,
    priorityFeeSol,
    totalCostPct,
  };
}

/**
 * Calculate dynamic priority fee based on market conditions
 */
function calculatePriorityFee(
  volatility: 'low' | 'medium' | 'high' | 'extreme',
  solPriceUsd: number
): number {
  const baseFees: Record<string, number> = {
    low: 0.001,      // 0.001 SOL
    medium: 0.003,   // 0.003 SOL
    high: 0.005,     // 0.005 SOL
    extreme: 0.01,   // 0.01 SOL
  };

  const baseSol = baseFees[volatility];

  // Convert to USD for reporting
  return baseSol;
}

/**
 * Get round-trip cost benchmarks by tier
 * These are realistic estimates based on historical data
 */
export function getRoundTripCostBenchmark(tier: AssetLiquidityTier): {
  min: number;
  max: number;
  typical: number;
  description: string;
} {
  const benchmarks: Record<AssetLiquidityTier, { min: number; max: number; typical: number; description: string }> = {
    high: {
      min: 0.003,
      max: 0.006,
      typical: 0.0045,
      description: 'SOL/USDC, major pairs. Pool liquidity > $1M',
    },
    mid: {
      min: 0.01,
      max: 0.03,
      typical: 0.02,
      description: 'Established tokens. Pool liquidity $100K-$1M',
    },
    micro: {
      min: 0.03,
      max: 0.08,
      typical: 0.05,
      description: 'Small caps. Pool liquidity $10K-$100K',
    },
    bags_pre_grad: {
      min: 0.02,
      max: 0.04,
      typical: 0.03,
      description: 'Bonding curve pre-graduation. Includes creator fees',
    },
    bags_post_grad: {
      min: 0.04,
      max: 0.15,
      typical: 0.08,
      description: 'Just graduated, thin new pool + creator fees',
    },
    xstock: {
      min: 0.01,
      max: 0.05,
      typical: 0.02,
      description: 'Tokenized equities. Higher during off-hours',
    },
  };

  return benchmarks[tier];
}

/**
 * Check if a trade is worth taking given expected edge
 *
 * A trade should only be taken if:
 * Expected_Edge > (total_round_trip_cost × edge_to_cost_ratio)
 *
 * @param expectedEdgePct - Expected profit percentage
 * @param totalCostPct - Total round-trip cost percentage
 * @param minEdgeToCostRatio - Minimum edge-to-cost ratio (default 2.0)
 * @returns Whether the trade is worth taking
 */
export function isTradeWorthIt(
  expectedEdgePct: number,
  totalCostPct: number,
  minEdgeToCostRatio: number = 2.0
): boolean {
  // Must cover round-trip costs AND have minimum edge
  const breakEvenCost = totalCostPct * 2; // Entry + Exit
  const requiredEdge = breakEvenCost * minEdgeToCostRatio;

  return expectedEdgePct >= requiredEdge;
}

/**
 * Apply realistic costs to a backtest trade
 *
 * @param entryPrice - Entry price
 * @param exitPrice - Exit price
 * @param config - Fee model configuration
 * @returns Net profit after all costs
 */
export function calculateNetTradePnL(
  entryPrice: number,
  exitPrice: number,
  config: FeeModelConfig
): {
  grossPnlPct: number;
  netPnlPct: number;
  costs: TradeCost;
} {
  const costs = calculateTradeCost(config);

  // Gross P&L percentage
  const grossPnlPct = ((exitPrice - entryPrice) / entryPrice) * 100;

  // Net P&L after costs (entry cost + exit cost + price impact)
  const entryCost = costs.dexFeePct + (costs.isBagsToken ? costs.creatorFeePct / 2 : 0);
  const exitCost = costs.dexFeePct + costs.priceImpactPct + (costs.isBagsToken ? costs.creatorFeePct / 2 : 0);
  const totalCosts = entryCost + exitCost + costs.mevCostPct;

  const netPnlPct = grossPnlPct - (totalCosts * 100);

  return {
    grossPnlPct,
    netPnlPct,
    costs,
  };
}

/**
 * Determine liquidity tier based on pool data
 */
export function determineLiquidityTier(
  poolLiquidityUsd: number,
  isBagsToken: boolean,
  isPreGraduation: boolean
): AssetLiquidityTier {
  if (isBagsToken) {
    return isPreGraduation ? 'bags_pre_grad' : 'bags_post_grad';
  }

  if (poolLiquidityUsd > 1_000_000) return 'high';
  if (poolLiquidityUsd > 100_000) return 'mid';
  if (poolLiquidityUsd > 10_000) return 'micro';
  return 'micro'; // Default to micro for very small pools
}
