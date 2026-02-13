import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/rate-limiter', () => ({
  swapRateLimiter: { check: vi.fn().mockReturnValue({ allowed: true }) },
  getClientIp: vi.fn().mockReturnValue('127.0.0.1'),
}));

vi.mock('@/lib/solana-balance-guard', () => ({
  checkSignerSolBalance: vi.fn(),
}));

describe('POST /api/bags/swap', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it('returns 409 with structured payload when SOL balance is insufficient', async () => {
    const { checkSignerSolBalance } = await import('@/lib/solana-balance-guard');
    (checkSignerSolBalance as any).mockResolvedValue({
      ok: false,
      availableLamports: 100_000,
      requiredLamports: 3_100_000,
      availableSol: 0.0001,
      requiredSol: 0.0031,
    });

    const route = await import('@/app/api/bags/swap/route');
    const req = new Request('http://localhost/api/bags/swap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        userPublicKey: '11111111111111111111111111111111',
        inputMint: 'So11111111111111111111111111111111111111112',
        outputMint: 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',
        amount: 100_000,
        slippageBps: 500,
      }),
    });

    const res = await route.POST(req);
    const body = await res.json();

    expect(res.status).toBe(409);
    expect(body.code).toBe('INSUFFICIENT_SIGNER_SOL');
    expect(body.availableLamports).toBe(100_000);
    expect(body.requiredLamports).toBe(3_100_000);
  });
});
