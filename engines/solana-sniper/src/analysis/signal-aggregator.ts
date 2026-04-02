import { runSafetyPipeline } from '../safety/composite-scorer.js';
import { analyzeSentiment } from './sentiment-analyzer.js';
import { calculatePositionSize } from '../risk/position-sizer.js';
import { getDexScreenerPrice } from '../trading/jupiter-swap.js';
import { checkWalletBuys, computeSmartMoneyBoost } from './smart-money-tracker.js';
import { createModuleLogger } from '../utils/logger.js';
import type { TokenInfo, AggregatedSignal, SafetyResult } from '../types/index.js';

const log = createModuleLogger('signal-aggregator');

export interface SignalPipelineResult {
  signal: AggregatedSignal;
  safety: SafetyResult;
  positionSize: number;
  stopLossPct: number;
  takeProfitPct: number;
}

export async function aggregateSignal(token: TokenInfo): Promise<SignalPipelineResult | null> {
  const startTime = Date.now();

  log.info('Aggregating signal', { mint: token.mint.slice(0, 8), symbol: token.symbol, source: token.source });

  // 1. Run safety pipeline
  const safety = await runSafetyPipeline(token);
  if (!safety.passed) {
    log.info('Token FAILED safety', {
      mint: token.mint.slice(0, 8),
      score: (safety.overallScore * 100).toFixed(0) + '%',
      reasons: safety.failReasons.join(', '),
    });
    return null;
  }

  // 2. Get market data
  const priceData = await getDexScreenerPrice(token.mint);
  if (priceData.liquidity < 10_000) {
    log.info('Token FAILED liquidity check', {
      mint: token.mint.slice(0, 8),
      liquidity: priceData.liquidity.toFixed(0),
    });
    return null;
  }

  // 3. Run sentiment analysis
  const sentiment = await analyzeSentiment(
    token.mint,
    token.symbol,
    `Source: ${token.source}, Liquidity: $${priceData.liquidity.toFixed(0)}, Volume 24h: $${priceData.volume24h.toFixed(0)}`
  );

  // 4. Calculate position size
  const sizing = await calculatePositionSize(token.mint, safety, priceData.liquidity);
  if (sizing.recommendedUsd <= 0) {
    log.info('Token REJECTED by position sizer', {
      mint: token.mint.slice(0, 8),
      reason: sizing.reasoning,
    });
    return null;
  }

  // 5. Compute buy score (weighted multi-factor aggregate)

  // Safety factor — most critical (rug avoidance)
  const safetyFactor = safety.overallScore; // 0-1

  // Sentiment factor — AI confidence
  const sentimentFactor = Math.max(0, (sentiment.score + 1) / 2); // normalize -1..1 to 0..1
  const confidenceFactor = sentiment.confidence; // 0-1

  // Liquidity depth factor — can we exit?
  const liquidityFactor = Math.min(1, priceData.liquidity / 100_000); // 100k+ = max

  // Volume factor — is there active trading?
  const volumeFactor = Math.min(1, priceData.volume24h / 50_000);

  // Volume-to-liquidity ratio — healthy trading activity
  const volLiqRatio = priceData.volume24h / Math.max(1, priceData.liquidity);
  const activityFactor = volLiqRatio >= 1 && volLiqRatio <= 20 ? Math.min(1, volLiqRatio / 5) : 0;

  // Source bonus — pump.fun tokens have higher win rates historically
  const sourceFactor = token.source === 'pumpfun' ? 0.1 : 0;

  // 6. Smart money signal — check if tracked wallets bought this token
  let smartMoneyBoost = 0;
  try {
    const smartSignals = await checkWalletBuys(token.mint);
    smartMoneyBoost = computeSmartMoneyBoost(smartSignals);
    if (smartMoneyBoost > 0) {
      log.info('Smart money boost applied', {
        mint: token.mint.slice(0, 8),
        boost: (smartMoneyBoost * 100).toFixed(0) + '%',
        wallets: smartSignals.length,
        tiers: smartSignals.map(s => s.walletTier).join(', '),
      });
    }
  } catch {
    // Smart money check failed, continue without boost
  }

  const buyScore = Math.min(1,
    safetyFactor * 0.28 +
    sentimentFactor * 0.18 +
    liquidityFactor * 0.14 +
    volumeFactor * 0.10 +
    activityFactor * 0.10 +
    confidenceFactor * 0.10 +
    sourceFactor * 0.05 +
    smartMoneyBoost, // up to +0.30 boost
  );

  // Multi-gate conditions — ALL must pass
  const shouldBuy =
    buyScore >= 0.45 &&           // Aggregate score threshold
    safety.overallScore >= 0.55 && // Safety minimum
    sentiment.score > -0.5 &&     // Not bearish
    priceData.liquidity >= 5_000;  // Minimum liquidity

  const signal: AggregatedSignal = {
    mint: token.mint,
    symbol: token.symbol,
    buyScore,
    safetyScore: safety.overallScore,
    sentimentScore: sentiment.score,
    liquidityUsd: priceData.liquidity,
    volumeUsd24h: priceData.volume24h,
    priceUsd: priceData.price,
    shouldBuy,
    reasoning: `Safety: ${(safety.overallScore * 100).toFixed(0)}%, Sentiment: ${sentiment.score.toFixed(2)}, Liquidity: $${priceData.liquidity.toFixed(0)}, Buy Score: ${(buyScore * 100).toFixed(0)}%`,
    sources: [token.source, sentiment.source],
    timestamp: Date.now(),
  };

  const elapsed = Date.now() - startTime;
  log.info('Signal aggregated', {
    mint: token.mint.slice(0, 8),
    symbol: token.symbol,
    buyScore: (buyScore * 100).toFixed(0) + '%',
    shouldBuy,
    positionUsd: sizing.recommendedUsd.toFixed(2),
    elapsed: elapsed + 'ms',
  });

  return {
    signal,
    safety,
    positionSize: sizing.recommendedUsd,
    stopLossPct: sizing.stopLossPct,
    takeProfitPct: sizing.takeProfitPct,
  };
}
