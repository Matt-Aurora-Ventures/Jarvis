import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Keypair, TransactionMessage, VersionedTransaction } from '@solana/web3.js';

vi.mock('@/lib/tx-confirmation', () => ({
  waitForSignatureStatus: vi.fn(),
}));

vi.mock('@/lib/async-timeout', () => ({
  withTimeout: async <T,>(promise: Promise<T>) => await promise,
}));

import { waitForSignatureStatus } from '@/lib/tx-confirmation';
import { executeSwap, executeSwapFromQuote, SOL_MINT, type SwapQuote } from '@/lib/bags-trading';

function makeTxBase64(): string {
  const payer = Keypair.generate().publicKey;
  const message = new TransactionMessage({
    payerKey: payer,
    recentBlockhash: '11111111111111111111111111111111',
    instructions: [],
  }).compileToV0Message();
  const tx = new VersionedTransaction(message);
  return Buffer.from(tx.serialize()).toString('base64');
}

function makeConnection() {
  return {
    getLatestBlockhash: vi.fn().mockResolvedValue({
      blockhash: 'fresh-blockhash',
      lastValidBlockHeight: 123,
    }),
    sendRawTransaction: vi.fn().mockResolvedValue('sig-test-123'),
    getSignatureStatuses: vi.fn().mockResolvedValue({
      value: [{ confirmationStatus: 'processed', err: null }],
    }),
  } as any;
}

describe('bags-trading confirmation handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
    (waitForSignatureStatus as any).mockResolvedValue({ state: 'unresolved' });
  });

  it('treats unresolved buy confirmation as failure', async () => {
    const connection = makeConnection();
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        transaction: makeTxBase64(),
        quote: {
          inAmount: '20000000',
          outAmount: '123456',
          priceImpactPct: '0.1',
          routePlan: [],
        },
      }),
    });

    const result = await executeSwap(
      connection,
      'wallet-abc',
      SOL_MINT,
      'mint-xyz',
      0.02,
      150,
      async () => ({ serialize: () => new Uint8Array([1, 2, 3]) } as any),
      false,
    );

    expect(connection.sendRawTransaction).toHaveBeenCalledWith(
      expect.any(Uint8Array),
      expect.objectContaining({ skipPreflight: false, maxRetries: 3 }),
    );
    expect(result.success).toBe(false);
    expect(result.confirmationState).toBe('unresolved');
    expect(result.failureCode).toBe('unresolved');
    expect(result.error).toContain('not confirmed on-chain');
  });

  it('treats unresolved sell confirmation as failure', async () => {
    const connection = makeConnection();
    const quote: SwapQuote = {
      inputMint: 'mint-xyz',
      outputMint: SOL_MINT,
      inAmount: '123',
      outAmount: '4560000',
      otherAmountThreshold: '0',
      priceImpactPct: '0.2',
      routePlan: [],
    };
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        transaction: makeTxBase64(),
      }),
    });

    const result = await executeSwapFromQuote(
      connection,
      'wallet-abc',
      quote,
      async () => ({ serialize: () => new Uint8Array([4, 5, 6]) } as any),
      false,
    );

    expect(connection.sendRawTransaction).toHaveBeenCalledWith(
      expect.any(Uint8Array),
      expect.objectContaining({ skipPreflight: false, maxRetries: 3 }),
    );
    expect(result.success).toBe(false);
    expect(result.confirmationState).toBe('unresolved');
    expect(result.failureCode).toBe('unresolved');
    expect(result.error).toContain('not confirmed on-chain');
  });

  it('maps slippage failure code from server response detail', async () => {
    const connection = makeConnection();
    (global.fetch as any).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({
        error: 'Program failed: custom program error: 0x3a99 (15001 SlippageLimitExceeded)',
      }),
    });

    const result = await executeSwap(
      connection,
      'wallet-abc',
      SOL_MINT,
      'mint-xyz',
      0.02,
      150,
      async () => ({ serialize: () => new Uint8Array([1, 2, 3]) } as any),
      false,
    );

    expect(result.success).toBe(false);
    expect(result.failureCode).toBe('slippage_limit');
  });

  it('maps on-chain custom 3005 failure to slippage_limit', async () => {
    const connection = makeConnection();
    (waitForSignatureStatus as any).mockResolvedValue({
      state: 'failed',
      error: 'InstructionError:[3,{"Custom":3005}]',
    });
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        transaction: makeTxBase64(),
        quote: {
          inAmount: '20000000',
          outAmount: '123456',
          priceImpactPct: '0.1',
          routePlan: [],
        },
      }),
    });

    const result = await executeSwap(
      connection,
      'wallet-abc',
      SOL_MINT,
      'mint-xyz',
      0.02,
      150,
      async () => ({ serialize: () => new Uint8Array([1, 2, 3]) } as any),
      false,
    );

    expect(result.success).toBe(false);
    expect(result.failureCode).toBe('slippage_limit');
    expect(result.confirmationState).toBe('failed');
  });
});
