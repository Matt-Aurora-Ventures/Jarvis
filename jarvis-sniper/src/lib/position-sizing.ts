/**
 * Position Sizing Module
 *
 * ATR-based position sizing with Kelly criterion and liquidity checks.
 * Ensures proper risk management for different asset classes.
 *
 * @module position-sizing
 */

import type { AssetLiquidityTier } from './fee-model';

export type AssetClass = 'native_solana' | 'mid_cap' | 'micro_cap' | 'bags_pre_grad' | 'bags_post_grad' | 'xstock' | 'memecoin';

export interface PositionSizingConfig {
  /** Account balance in USD */
  accountBalanceUsd: number;
  /** Entry price */
  entryPrice: number;
  /** Stop loss price */
  stopLossPrice: number;
  /** ATR (Average True Range) value */
  atr: number;
  /** Asset class */
  assetClass: AssetClass;
  /** Pool liquidity in USD */
  poolLiquidityUsd: number;
  /** Risk per trade as fraction (default 0.01 = 1%) */
  riskPerTrade?: number;
}

// Asset class position limits (% of portfolio)
const MAX_POSITION_BY_CLASS: Record<AssetClass, number> = {
  native_solana: 0.05,    // 5%
  mid_cap: 0.03,          // 3%
  micro_cap: 0.02,        // 2%
  bags_pre_grad: 0.0025,  // 0.25% - extremely speculative
  bags_post_grad: 0.005,   // 0.5%
  xstock: 0.02,           // 2%
  memecoin: 0.01,         // 1%
};

// Kelly fraction (use quarter Kelly for crypto)
const KELLY_FRACTION = 0.25;

// Default risk per trade
const DEFAULT_RISK_PER_TRADE = 0.01;

/**
 * Calculate position size using ATR-based method
 *
 * Formula: position_size = (account_balance × risk_per_trade) / (ATR × 3)
 *
 * @param config - Position sizing configuration
 * @returns Position size in token units
 */
export function calculatePositionSize(config: PositionSizingConfig): {
  positionSizeUsd: number;
  positionSizeTokens: number;
  riskAmountUsd: number;
  limitedBy: string;
} {
  const {
    accountBalanceUsd,
    entryPrice,
    stopLossPrice,
    atr,
    assetClass,
    poolLiquidityUsd,
    riskPerTrade = DEFAULT_RISK_PER_TRADE,
  } = config;

  // 1. Calculate risk amount
  const riskAmountUsd = accountBalanceUsd * riskPerTrade;

  // 2. Calculate ATR-based position size
  // Using ATR × 3 as stop distance
  const atrStopDistance = atr * 3;

  // Position size based on risk (in USD)
  let positionSizeUsdByRisk = 0;
  if (atrStopDistance > 0 && entryPrice > 0) {
    positionSizeUsdByRisk = riskAmountUsd / (atrStopDistance / entryPrice);
  }

  // 3. Apply asset class position limits
  const maxPositionByClass = MAX_POSITION_BY_CLASS[assetClass];
  const maxPositionUsd = accountBalanceUsd * maxPositionByClass;

  // 4. Apply liquidity check (can't trade more than 5% of pool)
  const maxPositionByLiquidity = poolLiquidityUsd * 0.05;

  // 5. Determine limiting factor and final position size
  let limitedBy = 'risk';
  let positionSizeUsd = Math.min(
    positionSizeUsdByRisk,
    maxPositionUsd,
    maxPositionByLiquidity
  );

  if (positionSizeUsd === maxPositionUsd) {
    limitedBy = 'class_limit';
  } else if (positionSizeUsd === maxPositionByLiquidity) {
    limitedBy = 'liquidity';
  }

  // 6. Convert to token units
  const positionSizeTokens = positionSizeUsd / entryPrice;

  return {
    positionSizeUsd,
    positionSizeTokens,
    riskAmountUsd,
    limitedBy,
  };
}

/**
 * Calculate Kelly position size
 *
 * Full Kelly: f* = (bp - q) / b
 * Where:
 *   b = odds received on the wager
 *   p = probability of winning
 *   q = probability of losing = 1 - p
 *
 * We use Quarter Kelly (0.25 × full Kelly) for safety
 */
export function calculateKellySize(
  accountBalanceUsd: number,
  winRate: number,
  avgWinUsd: number,
  avgLossUsd: number,
  kellyFraction: number = KELLY_FRACTION
): number {
  if (winRate <= 0 || avgWinUsd <= 0 || avgLossUsd <= 0) {
    return 0;
  }

  const b = avgWinUsd / avgLossUsd; // Odds
  const p = winRate;
  const q = 1 - p;

  // Full Kelly
  const fullKelly = (b * p - q) / b;

  // If negative, don't bet
  if (fullKelly <= 0) {
    return 0;
  }

  // Apply Kelly fraction for safety
  const adjustedKelly = fullKelly * kellyFraction;

  // Calculate position size
  const positionSize = accountBalanceUsd * adjustedKelly;

  return Math.max(0, positionSize);
}

/**
 * Check if position size is safe given liquidity
 */
export function validatePositionSize(
  positionSizeUsd: number,
  poolLiquidityUsd: number
): {
  isSafe: boolean;
  reason: string;
  suggestedReduction: number;
} {
  const poolFraction = positionSizeUsd / poolLiquidityUsd;

  if (poolFraction > 0.1) {
    // More than 10% of pool - very dangerous
    return {
      isSafe: false,
      reason: 'Position would be >10% of pool liquidity - high slippage risk',
      suggestedReduction: poolLiquidityUsd * 0.05 - positionSizeUsd,
    };
  }

  if (poolFraction > 0.05) {
    // More than 5% of pool - reduce
    return {
      isSafe: false,
      reason: 'Position would be >5% of pool liquidity',
      suggestedReduction: poolLiquidityUsd * 0.05 - positionSizeUsd,
    };
  }

  return {
    isSafe: true,
    reason: 'OK',
    suggestedReduction: 0,
  };
}

/**
 * Get position size recommendation for different asset classes
 */
export function getPositionSizeRecommendation(
  accountBalanceUsd: number,
  assetClass: AssetClass,
  poolLiquidityUsd: number
): {
  maxPositionUsd: number;
  maxPositionSol: number;
  recommendedPositionUsd: number;
  rationale: string;
} {
  const maxPositionUsd = accountBalanceUsd * MAX_POSITION_BY_CLASS[assetClass];
  const maxPositionByLiquidity = poolLiquidityUsd * 0.05;

  // Use the smaller of the two
  const finalMax = Math.min(maxPositionUsd, maxPositionByLiquidity);

  // Recommended is 50% of max to leave room
  const recommendedPositionUsd = finalMax * 0.5;

  // Convert to SOL (assuming ~$150/SOL)
  const solPrice = 150;
  const maxPositionSol = finalMax / solPrice;

  const rationales: Record<AssetClass, string> = {
    native_solana: 'Large cap - standard 5% position limit',
    mid_cap: 'Mid cap - 3% limit for moderate risk',
    micro_cap: 'Small cap - 2% limit due to volatility',
    bags_pre_grad: 'Bags pre-graduation - extremely speculative, 0.25% limit',
    bags_post_grad: 'Bags post-graduation - newly listed, 0.5% limit',
    xstock: 'Tokenized stocks - 2% limit, higher for high-liquidity tickers',
    memecoin: 'Memecoin - highest risk, 1% limit',
  };

  return {
    maxPositionUsd: finalMax,
    maxPositionSol,
    recommendedPositionUsd,
    rationale: rationales[assetClass],
  };
}

/**
 * Calculate tiered exit plan
 *
 * @param entryPrice - Entry price
 * @param positionSize - Total position size in tokens
 * @param atr - Current ATR value
 * @returns Array of exit stages
 */
export function calculateTieredExits(
  entryPrice: number,
  positionSize: number,
  atr: number
): Array<{
  pctPosition: number;
  exitPrice: number;
  atrMultiplier: number;
  description: string;
}> {
  return [
    {
      pctPosition: 0.33, // 33% of position
      exitPrice: entryPrice + (atr * 2),
      atrMultiplier: 2.0,
      description: 'Tight stop - lock in partial profits',
    },
    {
      pctPosition: 0.33, // 33% of position
      exitPrice: entryPrice + (atr * 3),
      atrMultiplier: 3.0,
      description: 'Medium stop - take more profit',
    },
    {
      pctPosition: 0.34, // 34% of position
      exitPrice: entryPrice + (atr * 5),
      atrMultiplier: 5.0,
      description: 'Wide stop - let it ride for big moves',
    },
  ];
}
