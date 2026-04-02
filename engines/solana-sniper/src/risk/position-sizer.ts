import { config } from '../config/index.js';
import { RISK_TIERS } from '../config/constants.js';
import { createModuleLogger } from '../utils/logger.js';
import { getSolBalanceUsd } from '../utils/wallet.js';
import { getOpenPositions, getDailyPnl } from '../utils/database.js';
import type { PositionSizeResult, RiskTier, SafetyResult } from '../types/index.js';

const log = createModuleLogger('position-sizer');

// Known established tokens (lower risk)
const ESTABLISHED_TOKENS = new Set([
  'So11111111111111111111111111111111111111112', // SOL
  'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN', // JUP
  'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263', // BONK
  'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm', // WIF
]);

export function classifyRiskTier(
  mintAddress: string,
  safetyScore: number,
  liquidityUsd: number,
  holderCount: number,
): RiskTier {
  if (ESTABLISHED_TOKENS.has(mintAddress)) return 'ESTABLISHED';
  if (safetyScore >= 0.8 && liquidityUsd >= 100_000 && holderCount >= 500) return 'MID';
  if (safetyScore >= 0.6 && liquidityUsd >= 10_000 && holderCount >= 50) return 'MICRO';
  return 'HIGH_RISK';
}

export async function calculatePositionSize(
  mintAddress: string,
  safety: SafetyResult,
  liquidityUsd: number,
): Promise<PositionSizeResult> {
  const { risk } = config;

  // Check circuit breaker
  const balance = await getSolBalanceUsd();
  if (balance.usd <= risk.circuitBreakerFloorUsd) {
    log.warn('Circuit breaker active — balance below floor', {
      balance: balance.usd.toFixed(2),
      floor: risk.circuitBreakerFloorUsd,
    });
    return {
      recommendedUsd: 0,
      riskTier: 'HIGH_RISK',
      stopLossPct: 0,
      takeProfitPct: 0,
      reasoning: `CIRCUIT BREAKER: Balance $${balance.usd.toFixed(2)} below $${risk.circuitBreakerFloorUsd} floor`,
    };
  }

  // Check max concurrent positions
  const openPositions = getOpenPositions();
  if (openPositions.length >= risk.maxConcurrentPositions) {
    return {
      recommendedUsd: 0,
      riskTier: 'HIGH_RISK',
      stopLossPct: 0,
      takeProfitPct: 0,
      reasoning: `MAX POSITIONS: ${openPositions.length}/${risk.maxConcurrentPositions} positions open`,
    };
  }

  // Check daily loss limit
  const dailyPnl = getDailyPnl();
  if (dailyPnl <= -risk.maxDailyLossUsd) {
    return {
      recommendedUsd: 0,
      riskTier: 'HIGH_RISK',
      stopLossPct: 0,
      takeProfitPct: 0,
      reasoning: `DAILY LOSS LIMIT: Lost $${Math.abs(dailyPnl).toFixed(2)} today (max: $${risk.maxDailyLossUsd})`,
    };
  }

  // Check minimum liquidity
  if (liquidityUsd < risk.minLiquidityUsd) {
    return {
      recommendedUsd: 0,
      riskTier: 'HIGH_RISK',
      stopLossPct: 0,
      takeProfitPct: 0,
      reasoning: `LOW LIQUIDITY: $${liquidityUsd.toFixed(0)} below minimum $${risk.minLiquidityUsd}`,
    };
  }

  // Classify risk tier
  const holderCount = safety.holderAnalysis?.holderCount ?? 0;
  const tier = classifyRiskTier(mintAddress, safety.overallScore, liquidityUsd, holderCount);
  const tierConfig = RISK_TIERS[tier];

  // Calculate position size based on tier
  let positionUsd = risk.maxPositionUsd * tierConfig.positionPct;

  // Cap at 1% of liquidity to avoid market impact
  const maxByLiquidity = liquidityUsd * 0.01;
  positionUsd = Math.min(positionUsd, maxByLiquidity);

  // Cap at available balance
  const maxByBalance = balance.usd * 0.1; // Never more than 10% of balance in one trade
  positionUsd = Math.min(positionUsd, maxByBalance);

  // Minimum viable trade ($0.50)
  if (positionUsd < 0.5) {
    return {
      recommendedUsd: 0,
      riskTier: tier,
      stopLossPct: tierConfig.slPct,
      takeProfitPct: tierConfig.tpPct,
      reasoning: `BELOW MINIMUM: Calculated size $${positionUsd.toFixed(2)} below $0.50 minimum`,
    };
  }

  log.info('Position sized', {
    tier,
    usd: positionUsd.toFixed(2),
    sl: tierConfig.slPct + '%',
    tp: tierConfig.tpPct + '%',
    safety: (safety.overallScore * 100).toFixed(0) + '%',
  });

  return {
    recommendedUsd: positionUsd,
    riskTier: tier,
    stopLossPct: tierConfig.slPct,
    takeProfitPct: tierConfig.tpPct,
    reasoning: `${tier} tier: $${positionUsd.toFixed(2)} (${(tierConfig.positionPct * 100).toFixed(0)}% of max $${risk.maxPositionUsd})`,
  };
}
