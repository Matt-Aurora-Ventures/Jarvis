import { describe, expect, it, vi } from 'vitest';
import { checkSignerSolBalance } from '@/lib/solana-balance-guard';

describe('solana-balance-guard', () => {
  it('passes when available lamports covers required plus reserve', async () => {
    const connection = {
      getBalance: vi.fn().mockResolvedValue(6_000_000),
    } as any;

    const res = await checkSignerSolBalance(
      connection,
      '11111111111111111111111111111111',
      2_000_000,
      3_000_000,
    );

    expect(res.ok).toBe(true);
    expect(res.availableLamports).toBe(6_000_000);
    expect(res.requiredLamports).toBe(5_000_000);
  });

  it('fails when available lamports is below required plus reserve', async () => {
    const connection = {
      getBalance: vi.fn().mockResolvedValue(4_999_999),
    } as any;

    const res = await checkSignerSolBalance(
      connection,
      '11111111111111111111111111111111',
      2_000_000,
      3_000_000,
    );

    expect(res.ok).toBe(false);
    expect(res.requiredLamports).toBe(5_000_000);
  });

  it('fails closed on invalid wallet address', async () => {
    const connection = {
      getBalance: vi.fn(),
    } as any;

    const res = await checkSignerSolBalance(connection, 'not-a-pubkey', 1_000_000, 3_000_000);
    expect(res.ok).toBe(false);
    expect(res.error).toBeTruthy();
  });
});
