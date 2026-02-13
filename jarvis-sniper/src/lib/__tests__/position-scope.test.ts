import { describe, expect, it } from 'vitest';
import type { Position } from '@/stores/useSniperStore';
import {
  filterOpenPositionsForActiveWallet,
  filterTradeManagedOpenPositionsForActiveWallet,
  isPositionInActiveWallet,
  resolveActiveWallet,
} from '@/lib/position-scope';

function makePosition(
  id: string,
  walletAddress: string | undefined,
  status: Position['status'] = 'open',
): Position {
  return {
    id,
    mint: `mint-${id}`,
    symbol: `SYM${id}`,
    name: `Token ${id}`,
    walletAddress,
    entryPrice: 1,
    currentPrice: 1,
    amount: 1,
    amountLamports: '1',
    solInvested: 0.1,
    pnlPercent: 0,
    pnlSol: 0,
    entryTime: Date.now(),
    status,
    score: 50,
    recommendedSl: 20,
    recommendedTp: 80,
    highWaterMarkPct: 0,
  };
}

describe('position-scope', () => {
  it('resolves active wallet for session mode', () => {
    expect(resolveActiveWallet('session', 'sess123', 'phantom123')).toBe('sess123');
  });

  it('resolves active wallet for phantom mode', () => {
    expect(resolveActiveWallet('phantom', 'sess123', 'phantom123')).toBe('phantom123');
  });

  it('checks if a position belongs to active wallet', () => {
    const pos = makePosition('1', 'walletA');
    expect(isPositionInActiveWallet(pos, 'walletA')).toBe(true);
    expect(isPositionInActiveWallet(pos, 'walletB')).toBe(false);
  });

  it('filters open positions to active wallet only', () => {
    const positions: Position[] = [
      makePosition('1', 'walletA', 'open'),
      makePosition('2', 'walletB', 'open'),
      makePosition('3', 'walletA', 'closed'),
      makePosition('4', undefined, 'open'),
    ];
    const scoped = filterOpenPositionsForActiveWallet(positions, 'walletA');
    expect(scoped.map((p) => p.id)).toEqual(['1']);
  });

  it('can exclude manual-only positions', () => {
    const manual = makePosition('m', 'walletA', 'open');
    manual.manualOnly = true;
    const normal = makePosition('n', 'walletA', 'open');
    const scoped = filterOpenPositionsForActiveWallet([manual, normal], 'walletA', { includeManualOnly: false });
    expect(scoped.map((p) => p.id)).toEqual(['n']);
  });

  it('filters to trade-managed positions only', () => {
    const manual = makePosition('m', 'walletA', 'open');
    manual.manualOnly = true;
    const recovered = makePosition('r', 'walletA', 'open');
    recovered.recoveredFrom = 'onchain-sync';
    const closing = makePosition('c', 'walletA', 'open');
    closing.isClosing = true;
    const normal = makePosition('n', 'walletA', 'open');
    const scoped = filterTradeManagedOpenPositionsForActiveWallet([manual, recovered, closing, normal], 'walletA');
    expect(scoped.map((p) => p.id)).toEqual(['n']);
  });
});
