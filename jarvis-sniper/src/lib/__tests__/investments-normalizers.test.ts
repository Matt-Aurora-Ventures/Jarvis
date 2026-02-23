import { describe, expect, it } from 'vitest';
import {
  normalizeInvestmentBasket,
  normalizeInvestmentDecisions,
  normalizeInvestmentPerformance,
} from '@/lib/investments/normalizers';

describe('investment normalizers', () => {
  it('converts basket token-map into ordered token view', () => {
    const basket = normalizeInvestmentBasket({
      tokens: {
        SOL: { weight: 0.3, price_usd: 100, liquidity_usd: 1000000 },
        BTC: { weight: 0.7, price_usd: 95000, liquidity_usd: 5000000 },
      },
      nav_usd: 1000,
    });

    expect(basket.totalNav).toBe(1000);
    expect(basket.tokens[0].symbol).toBe('BTC');
    expect(basket.tokens[0].usdValue).toBeCloseTo(700);
  });

  it('converts performance wrapper points into point array', () => {
    const points = normalizeInvestmentPerformance({
      points: [{ ts: '2026-02-22T00:00:00Z', nav_usd: 200 }],
    });

    expect(points).toEqual([{ timestamp: '2026-02-22T00:00:00Z', nav: 200 }]);
  });

  it('maps decision fields from reasoning/nav_usd/ts/final_weights shape', () => {
    const decisions = normalizeInvestmentDecisions([
      {
        id: 9,
        action: 'REBALANCE',
        confidence: 0.8,
        nav_usd: 250,
        reasoning: 'risk-off',
        ts: '2026-02-22T00:00:00Z',
        final_weights: { SOL: 0.4 },
      },
    ]);

    expect(decisions[0].summary).toBe('risk-off');
    expect(decisions[0].navAtDecision).toBe(250);
    expect(decisions[0].timestamp).toBe('2026-02-22T00:00:00Z');
    expect(decisions[0].newWeights).toEqual({ SOL: 0.4 });
  });
});
