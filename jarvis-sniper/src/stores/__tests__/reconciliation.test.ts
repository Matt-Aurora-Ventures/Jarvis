import { beforeEach, describe, expect, it } from 'vitest';
import { useSniperStore, type Position } from '../useSniperStore';

function makeOpenPosition(overrides: Partial<Position> = {}): Position {
  return {
    id: 'pos-test',
    mint: 'MintTest11111111111111111111111111111111111',
    symbol: 'TEST',
    name: 'Test Token',
    walletAddress: 'wallet-1',
    entryPrice: 1,
    currentPrice: 1,
    amount: 10,
    amountLamports: '10',
    solInvested: 0.15,
    pnlPercent: 0,
    pnlSol: 0,
    entryTime: Date.now() - 10 * 60 * 1000,
    status: 'open',
    score: 50,
    recommendedSl: 20,
    recommendedTp: 80,
    recommendedTrail: 8,
    highWaterMarkPct: 0,
    ...overrides,
  };
}

describe('store reconcilePosition', () => {
  beforeEach(() => {
    useSniperStore.getState().resetSession();
  });

  it('closes phantom position, releases spent budget, and keeps stats unchanged', () => {
    const initial = {
      totalTrades: 7,
      winCount: 3,
      lossCount: 4,
      spent: 0.20,
    };
    useSniperStore.setState((s) => ({
      ...s,
      positions: [makeOpenPosition()],
      budget: { ...s.budget, authorized: true, spent: initial.spent },
      totalTrades: initial.totalTrades,
      winCount: initial.winCount,
      lossCount: initial.lossCount,
    }));

    useSniperStore.getState().reconcilePosition('pos-test', 'buy_tx_unresolved');

    const state = useSniperStore.getState();
    const pos = state.positions.find((p) => p.id === 'pos-test');
    expect(pos?.status).toBe('closed');
    expect(pos?.reconciled).toBe(true);
    expect(pos?.reconciledReason).toBe('buy_tx_unresolved');
    expect(state.budget.spent).toBeCloseTo(0.05, 6);
    expect(state.totalTrades).toBe(initial.totalTrades);
    expect(state.winCount).toBe(initial.winCount);
    expect(state.lossCount).toBe(initial.lossCount);
  });

  it('does not release budget by default for manual/recovered rows', () => {
    useSniperStore.setState((s) => ({
      ...s,
      positions: [makeOpenPosition({
        id: 'recovered-1',
        manualOnly: true,
        recoveredFrom: 'onchain-sync',
      })],
      budget: { ...s.budget, authorized: true, spent: 0.2 },
    }));

    useSniperStore.getState().reconcilePosition('recovered-1', 'no_onchain_balance');

    const state = useSniperStore.getState();
    expect(state.budget.spent).toBeCloseTo(0.2, 6);
    const pos = state.positions.find((p) => p.id === 'recovered-1');
    expect(pos?.status).toBe('closed');
    expect(pos?.reconciledReason).toBe('no_onchain_balance');
  });
});
