import { beforeEach, describe, expect, it } from 'vitest';
import { useSniperStore, type Position } from '../useSniperStore';

function makeAutoPosition(overrides: Partial<Position> = {}): Position {
  return {
    id: 'pos-learning-1',
    mint: 'MintLearning11111111111111111111111111111111',
    symbol: 'LRN',
    name: 'Learning Token',
    entrySource: 'auto',
    strategyId: 'pump_fresh_tight',
    walletAddress: 'wallet-learning',
    entryPrice: 1,
    currentPrice: 1.1,
    amount: 100,
    amountLamports: '100',
    solInvested: 0.1,
    pnlPercent: 10,
    pnlSol: 0.01,
    entryTime: Date.now() - 10_000,
    status: 'open',
    score: 70,
    recommendedSl: 20,
    recommendedTp: 80,
    recommendedTrail: 8,
    highWaterMarkPct: 35,
    ...overrides,
  };
}

describe('store strategy learning', () => {
  beforeEach(() => {
    useSniperStore.getState().resetSession();
    useSniperStore.getState().resetStrategyBeliefs();
  });

  it('records discounted outcome for auto entries with tx hash evidence', () => {
    useSniperStore.setState((s) => ({
      ...s,
      positions: [makeAutoPosition()],
      budget: { ...s.budget, authorized: true, spent: 0.1 },
    }));

    useSniperStore.getState().closePosition(
      'pos-learning-1',
      'tp_hit',
      '5QNuKJCNk4sY7YQj2Q1b8Ej9M6V5sX3Dk8fJ7nP4mK2a',
      0.12,
    );

    const belief = useSniperStore.getState().strategyBeliefs.pump_fresh_tight;
    expect(belief).toBeDefined();
    expect(belief.wins).toBe(1);
    expect(belief.losses).toBe(0);
    expect(belief.totalOutcomes).toBe(1);
    expect(belief.alpha).toBeGreaterThan(1);
  });

  it('does not learn from manual entries even with tx hash', () => {
    useSniperStore.setState((s) => ({
      ...s,
      positions: [makeAutoPosition({ id: 'manual-pos', entrySource: 'manual' })],
      budget: { ...s.budget, authorized: true, spent: 0.1 },
    }));

    useSniperStore.getState().closePosition(
      'manual-pos',
      'tp_hit',
      '3C6R1wjf8Gg5nQhK2yD4xS9eM1aV7uL6pR8tW2yN5bCk',
      0.11,
    );

    expect(useSniperStore.getState().strategyBeliefs.pump_fresh_tight).toBeUndefined();
  });

  it('does not learn when tx hash evidence is missing', () => {
    useSniperStore.setState((s) => ({
      ...s,
      positions: [makeAutoPosition({ id: 'auto-no-hash' })],
      budget: { ...s.budget, authorized: true, spent: 0.1 },
    }));

    useSniperStore.getState().closePosition('auto-no-hash', 'sl_hit', undefined, 0.05);

    expect(useSniperStore.getState().strategyBeliefs.pump_fresh_tight).toBeUndefined();
  });
});
