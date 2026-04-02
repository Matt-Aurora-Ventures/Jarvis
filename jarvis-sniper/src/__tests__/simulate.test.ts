import { describe, it, expect, vi, beforeEach } from 'vitest';
import { simulateSwap } from '@/lib/simulate';
import type { Connection, VersionedTransaction } from '@solana/web3.js';

describe('simulateSwap', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns ok: true when simulation succeeds', async () => {
    const mockConnection = {
      simulateTransaction: vi.fn().mockResolvedValue({
        value: { err: null, unitsConsumed: 150_000 },
      }),
    } as unknown as Connection;

    const mockTx = {} as VersionedTransaction;

    const result = await simulateSwap(mockConnection, mockTx);
    expect(result.ok).toBe(true);
    expect(result.unitsConsumed).toBe(150_000);
    expect(result.error).toBeUndefined();
  });

  it('returns ok: false with error string when simulation fails', async () => {
    const mockConnection = {
      simulateTransaction: vi.fn().mockResolvedValue({
        value: {
          err: { InstructionError: [0, { Custom: 6001 }] },
          unitsConsumed: 50_000,
        },
      }),
    } as unknown as Connection;

    const mockTx = {} as VersionedTransaction;

    const result = await simulateSwap(mockConnection, mockTx);
    expect(result.ok).toBe(false);
    expect(result.error).toContain('Simulation failed');
    expect(result.error).toContain('InstructionError');
    expect(result.unitsConsumed).toBe(50_000);
  });

  it('returns ok: false with plain string error', async () => {
    const mockConnection = {
      simulateTransaction: vi.fn().mockResolvedValue({
        value: { err: 'AccountNotFound', unitsConsumed: 0 },
      }),
    } as unknown as Connection;

    const mockTx = {} as VersionedTransaction;

    const result = await simulateSwap(mockConnection, mockTx);
    expect(result.ok).toBe(false);
    expect(result.error).toContain('AccountNotFound');
  });

  it('allows tx through on network error (graceful pass-through)', async () => {
    const mockConnection = {
      simulateTransaction: vi.fn().mockRejectedValue(new Error('Network timeout')),
    } as unknown as Connection;

    const mockTx = {} as VersionedTransaction;

    const result = await simulateSwap(mockConnection, mockTx);
    // Should NOT throw — graceful pass-through
    expect(result.ok).toBe(true);
  });

  it('handles undefined unitsConsumed', async () => {
    const mockConnection = {
      simulateTransaction: vi.fn().mockResolvedValue({
        value: { err: null, unitsConsumed: undefined },
      }),
    } as unknown as Connection;

    const mockTx = {} as VersionedTransaction;

    const result = await simulateSwap(mockConnection, mockTx);
    expect(result.ok).toBe(true);
    expect(result.unitsConsumed).toBeUndefined();
  });

  it('passes correct options to simulateTransaction', async () => {
    const simulateFn = vi.fn().mockResolvedValue({
      value: { err: null, unitsConsumed: 100_000 },
    });
    const mockConnection = { simulateTransaction: simulateFn } as unknown as Connection;
    const mockTx = {} as VersionedTransaction;

    await simulateSwap(mockConnection, mockTx);

    expect(simulateFn).toHaveBeenCalledWith(mockTx, {
      replaceRecentBlockhash: true,
      commitment: 'processed',
    });
  });
});
