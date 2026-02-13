import { beforeEach, describe, expect, it } from 'vitest';
import { useSniperStore, type Position } from '../useSniperStore';

function makeOpenPosition(overrides: Partial<Position> = {}): Position {
  return {
    id: 'pos-reset-1',
    mint: 'MintReset1111111111111111111111111111111111',
    symbol: 'RST',
    name: 'Reset Token',
    walletAddress: 'wallet-reset',
    entrySource: 'auto',
    entryPrice: 1,
    currentPrice: 1,
    amount: 10,
    amountLamports: '10',
    solInvested: 0.1,
    pnlPercent: 0,
    pnlSol: 0,
    entryTime: Date.now(),
    status: 'open',
    score: 60,
    recommendedSl: 20,
    recommendedTp: 80,
    recommendedTrail: 8,
    highWaterMarkPct: 0,
    ...overrides,
  };
}

describe('store resetAutoForRecovery', () => {
  beforeEach(() => {
    useSniperStore.getState().resetSession();
  });

  it('disables auto/session state while preserving open positions', () => {
    useSniperStore.setState((s) => ({
      ...s,
      positions: [makeOpenPosition()],
      config: { ...s.config, autoSnipe: true },
      budget: { ...s.budget, authorized: true, spent: 0.1, budgetSol: 0.5 },
      tradeSignerMode: 'session',
      sessionWalletPubkey: 'SessionPubkey11111111111111111111111111111',
      executionPaused: true,
      operationLock: { active: true, reason: 'test lock', mode: 'maintenance' },
      pendingTxs: {
        'sig-reset': {
          signature: 'sig-reset',
          kind: 'buy',
          status: 'submitted',
          submittedAt: Date.now(),
        },
      },
      mintCooldowns: { 'bags:wallet-reset:mintreset': Date.now() + 60_000 },
      snipedMints: new Set(['MintReset1111111111111111111111111111111111']),
    }));

    useSniperStore.getState().resetAutoForRecovery();

    const state = useSniperStore.getState();
    expect(state.positions).toHaveLength(1);
    expect(state.config.autoSnipe).toBe(false);
    expect(state.budget.authorized).toBe(false);
    expect(state.tradeSignerMode).toBe('phantom');
    expect(state.sessionWalletPubkey).toBeNull();
    expect(state.executionPaused).toBe(false);
    expect(state.operationLock.active).toBe(false);
    expect(Object.keys(state.pendingTxs)).toHaveLength(0);
    expect(Object.keys(state.mintCooldowns)).toHaveLength(0);
    expect(state.snipedMints.size).toBe(0);
    expect(state.autoResetRequired).toBe(true);
    expect(typeof state.lastAutoResetAt).toBe('number');
    expect(state.executionLog[0]?.reason || '').toContain('AUTO_STOP_RESET_AUTO');
  });

  it('resetSession clears the auto reset gate flag', () => {
    useSniperStore.setState((s) => ({ ...s, autoResetRequired: true, lastAutoResetAt: Date.now() }));
    useSniperStore.getState().resetSession();

    const state = useSniperStore.getState();
    expect(state.autoResetRequired).toBe(false);
    expect(state.lastAutoResetAt).toBeUndefined();
  });
});

