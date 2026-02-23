import { describe, expect, it } from 'vitest';
import {
  applyDiscountedOutcome,
  createDefaultStrategyBelief,
  sampleBeta,
  selectStrategyWithThompson,
  type StrategyBelief,
} from '@/lib/strategy-selector';

describe('strategy-selector', () => {
  it('sampleBeta always stays in [0, 1]', () => {
    for (let i = 0; i < 200; i++) {
      const sample = sampleBeta(2 + i * 0.01, 3 + i * 0.01);
      expect(sample).toBeGreaterThanOrEqual(0);
      expect(sample).toBeLessThanOrEqual(1);
    }
  });

  it('selectStrategyWithThompson strongly favors clearly superior beliefs', () => {
    const beliefs: Record<string, StrategyBelief> = {
      strong: { ...createDefaultStrategyBelief('strong'), alpha: 30, beta: 4 },
      weak: { ...createDefaultStrategyBelief('weak'), alpha: 3, beta: 25 },
    };
    const candidates = [{ strategyId: 'strong' }, { strategyId: 'weak' }];

    let strongWins = 0;
    for (let i = 0; i < 100; i++) {
      const selection = selectStrategyWithThompson(candidates, beliefs);
      expect(selection).not.toBeNull();
      if (selection?.selected.strategyId === 'strong') strongWins += 1;
    }

    expect(strongWins).toBeGreaterThanOrEqual(90);
  });

  it('applyDiscountedOutcome decays all beliefs then updates selected strategy', () => {
    const beliefs: Record<string, StrategyBelief> = {
      a: {
        ...createDefaultStrategyBelief('a'),
        alpha: 10,
        beta: 5,
        wins: 9,
        losses: 4,
        totalOutcomes: 13,
      },
      b: {
        ...createDefaultStrategyBelief('b'),
        alpha: 6,
        beta: 9,
        wins: 5,
        losses: 8,
        totalOutcomes: 13,
      },
    };

    const next = applyDiscountedOutcome(beliefs, {
      strategyId: 'b',
      outcome: 'win',
      gamma: 0.9,
      txHash: 'sig123',
      now: 123456,
    });

    expect(next.a.alpha).toBeCloseTo(9, 6);
    expect(next.a.beta).toBeCloseTo(4.5, 6);
    expect(next.b.alpha).toBeCloseTo(6 * 0.9 + 1, 6);
    expect(next.b.beta).toBeCloseTo(9 * 0.9, 6);
    expect(next.b.wins).toBe(6);
    expect(next.b.totalOutcomes).toBe(14);
    expect(next.b.lastOutcome).toBe('win');
    expect(next.b.lastTxHash).toBe('sig123');
  });
});
