import { describe, it, expect } from 'vitest';

// Test the buy score calculation logic directly
// We extract the scoring math from signal-aggregator.ts since the full pipeline
// requires live API calls (safety, sentiment, price)

describe('Signal Aggregator - Buy Score Calculation', () => {
  function calculateBuyScore(params: {
    safetyScore: number;
    sentimentScore: number; // -1 to 1
    sentimentConfidence: number; // 0 to 1
    liquidityUsd: number;
    volumeUsd24h: number;
    source: string;
  }): { buyScore: number; shouldBuy: boolean } {
    const safetyFactor = params.safetyScore;
    const sentimentFactor = Math.max(0, (params.sentimentScore + 1) / 2);
    const confidenceFactor = params.sentimentConfidence;
    const liquidityFactor = Math.min(1, params.liquidityUsd / 100_000);
    const volumeFactor = Math.min(1, params.volumeUsd24h / 50_000);
    const volLiqRatio = params.volumeUsd24h / Math.max(1, params.liquidityUsd);
    const activityFactor = volLiqRatio >= 1 && volLiqRatio <= 20 ? Math.min(1, volLiqRatio / 5) : 0;
    const sourceFactor = params.source === 'pumpfun' ? 0.1 : 0;

    const buyScore =
      safetyFactor * 0.30 +
      sentimentFactor * 0.20 +
      liquidityFactor * 0.15 +
      volumeFactor * 0.10 +
      activityFactor * 0.10 +
      confidenceFactor * 0.10 +
      sourceFactor * 0.05;

    const shouldBuy =
      buyScore >= 0.45 &&
      params.safetyScore >= 0.55 &&
      params.sentimentScore > -0.5 &&
      params.liquidityUsd >= 5_000;

    return { buyScore, shouldBuy };
  }

  it('should give high score for excellent fundamentals', () => {
    const { buyScore, shouldBuy } = calculateBuyScore({
      safetyScore: 0.9,
      sentimentScore: 0.8,
      sentimentConfidence: 0.9,
      liquidityUsd: 200_000,
      volumeUsd24h: 500_000,
      source: 'pumpfun',
    });
    expect(buyScore).toBeGreaterThan(0.7);
    expect(shouldBuy).toBe(true);
  });

  it('should reject low safety even with good sentiment', () => {
    const { shouldBuy } = calculateBuyScore({
      safetyScore: 0.3,
      sentimentScore: 0.9,
      sentimentConfidence: 0.95,
      liquidityUsd: 100_000,
      volumeUsd24h: 200_000,
      source: 'raydium',
    });
    // Safety gate: 0.3 < 0.55
    expect(shouldBuy).toBe(false);
  });

  it('should reject bearish sentiment even with good safety', () => {
    const { shouldBuy } = calculateBuyScore({
      safetyScore: 0.85,
      sentimentScore: -0.7,
      sentimentConfidence: 0.8,
      liquidityUsd: 50_000,
      volumeUsd24h: 30_000,
      source: 'raydium',
    });
    // Sentiment gate: -0.7 < -0.5
    expect(shouldBuy).toBe(false);
  });

  it('should reject low liquidity tokens', () => {
    const { shouldBuy } = calculateBuyScore({
      safetyScore: 0.8,
      sentimentScore: 0.5,
      sentimentConfidence: 0.7,
      liquidityUsd: 2_000,
      volumeUsd24h: 10_000,
      source: 'pumpfun',
    });
    // Liquidity gate: 2000 < 5000
    expect(shouldBuy).toBe(false);
  });

  it('should give pumpfun source bonus', () => {
    const base = {
      safetyScore: 0.7,
      sentimentScore: 0.3,
      sentimentConfidence: 0.6,
      liquidityUsd: 40_000,
      volumeUsd24h: 60_000,
    };
    const pump = calculateBuyScore({ ...base, source: 'pumpfun' });
    const ray = calculateBuyScore({ ...base, source: 'raydium' });
    expect(pump.buyScore).toBeGreaterThan(ray.buyScore);
  });

  it('should value healthy volume-to-liquidity ratio', () => {
    const healthy = calculateBuyScore({
      safetyScore: 0.7,
      sentimentScore: 0.3,
      sentimentConfidence: 0.6,
      liquidityUsd: 30_000,
      volumeUsd24h: 90_000, // 3x ratio — healthy
      source: 'raydium',
    });
    const low = calculateBuyScore({
      safetyScore: 0.7,
      sentimentScore: 0.3,
      sentimentConfidence: 0.6,
      liquidityUsd: 30_000,
      volumeUsd24h: 5_000, // 0.16x ratio — dead
      source: 'raydium',
    });
    expect(healthy.buyScore).toBeGreaterThan(low.buyScore);
  });

  it('should return score between 0 and 1', () => {
    const { buyScore } = calculateBuyScore({
      safetyScore: 0.5,
      sentimentScore: 0,
      sentimentConfidence: 0.5,
      liquidityUsd: 20_000,
      volumeUsd24h: 20_000,
      source: 'raydium',
    });
    expect(buyScore).toBeGreaterThanOrEqual(0);
    expect(buyScore).toBeLessThanOrEqual(1);
  });
});
