import { afterEach, describe, expect, it, vi } from 'vitest';
import { generateSessionMarkdown } from '@/lib/session-export';
import { useSniperStore } from '@/stores/useSniperStore';

describe('session-export verification output', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('includes tx verification column and excluded-PnL wording', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        result: {
          value: [
            { confirmationStatus: 'finalized', err: null },
            { confirmationStatus: 'confirmed', err: { InstructionError: [0, 'Custom'] } },
          ],
        },
      }),
    }));

    const base = useSniperStore.getState();
    const now = Date.now();
    const markdown = await generateSessionMarkdown({
      config: base.config,
      budget: { ...base.budget, spent: 0.02, authorized: true },
      circuitBreaker: base.circuitBreaker,
      activePreset: 'pump_fresh_tight',
      assetFilter: 'memecoin',
      tradeSignerMode: 'session',
      sessionWalletPubkey: 'Wallet1111111111111111111111111111111111111',
      lastSolPriceUsd: 80,
      totalPnl: 0,
      winCount: 0,
      lossCount: 0,
      totalTrades: 0,
      positions: [
        {
          id: 'p1',
          mint: 'mint1',
          symbol: 'UNK',
          name: 'Unknown',
          walletAddress: 'wallet1',
          entryPrice: 1,
          currentPrice: 0.9,
          amount: 10,
          amountLamports: '10',
          solInvested: 0.02,
          pnlPercent: 0,
          pnlSol: 0,
          entryTime: now - 120000,
          status: 'closed',
          manualOnly: true,
          recoveredFrom: 'onchain-sync',
          score: 50,
          recommendedSl: 20,
          recommendedTp: 80,
          highWaterMarkPct: 0,
        },
      ],
      executionLog: [
        {
          id: 'e1',
          type: 'snipe',
          symbol: 'AAA',
          mint: 'mintA',
          amount: 0.02,
          txHash: 'sig-confirmed',
          reason: 'buy',
          timestamp: now - 1000,
        },
        {
          id: 'e2',
          type: 'sl_exit',
          symbol: 'BBB',
          mint: 'mintB',
          amount: 0.02,
          txHash: 'sig-failed',
          reason: 'sell',
          timestamp: now - 500,
        },
      ],
    });

    expect(markdown).toContain('| Time | Type | Symbol | Verified | Details |');
    expect(markdown).toContain('confirmed');
    expect(markdown).toContain('failed');
    expect(markdown).toContain('P&L excluded (no reliable cost basis)');
  });
});
