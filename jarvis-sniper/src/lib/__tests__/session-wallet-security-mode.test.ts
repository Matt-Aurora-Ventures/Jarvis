import { afterEach, describe, expect, it } from 'vitest';

describe('session-wallet creation mode', () => {
  const ORIGINAL_MODE = process.env.NEXT_PUBLIC_SESSION_WALLET_CREATION_MODE;
  const ORIGINAL_LEGACY = process.env.NEXT_PUBLIC_SESSION_WALLET_DETERMINISTIC;

  async function readMode() {
    const mod = await import('@/lib/session-wallet-security');
    return mod.getSessionWalletCreationMode();
  }

  afterEach(() => {
    process.env.NEXT_PUBLIC_SESSION_WALLET_CREATION_MODE = ORIGINAL_MODE;
    process.env.NEXT_PUBLIC_SESSION_WALLET_DETERMINISTIC = ORIGINAL_LEGACY;
  });

  it('defaults to random when no env flag is set', async () => {
    delete process.env.NEXT_PUBLIC_SESSION_WALLET_CREATION_MODE;
    delete process.env.NEXT_PUBLIC_SESSION_WALLET_DETERMINISTIC;
    await expect(readMode()).resolves.toBe('random');
  });

  it('uses deterministic mode only when explicitly configured', async () => {
    process.env.NEXT_PUBLIC_SESSION_WALLET_CREATION_MODE = 'deterministic';
    delete process.env.NEXT_PUBLIC_SESSION_WALLET_DETERMINISTIC;
    await expect(readMode()).resolves.toBe('deterministic');
  });

  it('accepts legacy deterministic flag for backward compatibility', async () => {
    delete process.env.NEXT_PUBLIC_SESSION_WALLET_CREATION_MODE;
    process.env.NEXT_PUBLIC_SESSION_WALLET_DETERMINISTIC = 'true';
    await expect(readMode()).resolves.toBe('deterministic');
  });
});
