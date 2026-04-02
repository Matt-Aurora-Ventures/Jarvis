import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  waitForSignatureStatus,
  mapRpcStatusToPendingState,
} from '@/lib/tx-confirmation';
import type { Connection, SignatureStatus } from '@solana/web3.js';

describe('mapRpcStatusToPendingState', () => {
  it('returns settling for null status', () => {
    const result = mapRpcStatusToPendingState(null);
    expect(result.state).toBe('settling');
  });

  it('returns confirmed for confirmed status', () => {
    const status: SignatureStatus = {
      slot: 12345,
      confirmations: 1,
      err: null,
      confirmationStatus: 'confirmed',
    };
    const result = mapRpcStatusToPendingState(status);
    expect(result.state).toBe('confirmed');
    expect(result.slot).toBe(12345);
  });

  it('returns confirmed for finalized status', () => {
    const status: SignatureStatus = {
      slot: 12345,
      confirmations: null,
      err: null,
      confirmationStatus: 'finalized',
    };
    const result = mapRpcStatusToPendingState(status);
    expect(result.state).toBe('confirmed');
    expect(result.confirmationStatus).toBe('finalized');
  });

  it('returns failed for error status', () => {
    const status: SignatureStatus = {
      slot: 12345,
      confirmations: null,
      err: { InstructionError: [0, { Custom: 1 }] },
      confirmationStatus: 'confirmed',
    };
    const result = mapRpcStatusToPendingState(status);
    expect(result.state).toBe('failed');
    expect(result.error).toBeDefined();
  });

  it('returns settling for processed status without error', () => {
    const status: SignatureStatus = {
      slot: 12345,
      confirmations: 0,
      err: null,
      confirmationStatus: 'processed',
    };
    const result = mapRpcStatusToPendingState(status);
    expect(result.state).toBe('settling');
  });
});

describe('waitForSignatureStatus', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns confirmed when polling finds confirmation', async () => {
    const mockConnection = {
      getSignatureStatuses: vi.fn().mockResolvedValue({
        value: [
          {
            slot: 100,
            confirmations: 1,
            err: null,
            confirmationStatus: 'confirmed',
          },
        ],
      }),
    } as unknown as Connection;

    const result = await waitForSignatureStatus(
      mockConnection,
      'test_signature_123',
      { maxWaitMs: 5_000, pollMs: 500 },
    );

    expect(result.state).toBe('confirmed');
  });

  it('returns failed when tx has error', async () => {
    const mockConnection = {
      getSignatureStatuses: vi.fn().mockResolvedValue({
        value: [
          {
            slot: 100,
            confirmations: null,
            err: 'InsufficientFunds',
            confirmationStatus: 'confirmed',
          },
        ],
      }),
    } as unknown as Connection;

    const result = await waitForSignatureStatus(
      mockConnection,
      'test_signature_456',
      { maxWaitMs: 5_000, pollMs: 500 },
    );

    expect(result.state).toBe('failed');
    expect(result.error).toContain('InsufficientFunds');
  });

  it('returns unresolved after maxWaitMs', async () => {
    const mockConnection = {
      getSignatureStatuses: vi.fn().mockResolvedValue({
        value: [null], // Never confirms
      }),
    } as unknown as Connection;

    const result = await waitForSignatureStatus(
      mockConnection,
      'test_signature_timeout',
      { maxWaitMs: 1_500, pollMs: 500 },
    );

    expect(result.state).toBe('unresolved');
    expect(result.error).toContain('No final signature status');
  });

  it('polls with correct search history flag', async () => {
    const getStatuses = vi.fn().mockResolvedValue({
      value: [
        { slot: 100, confirmations: 1, err: null, confirmationStatus: 'confirmed' },
      ],
    });
    const mockConnection = { getSignatureStatuses: getStatuses } as unknown as Connection;

    await waitForSignatureStatus(mockConnection, 'sig_123', {
      maxWaitMs: 5_000,
      pollMs: 500,
    });

    expect(getStatuses).toHaveBeenCalledWith(['sig_123'], {
      searchTransactionHistory: true,
    });
  });
});
