import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/rate-limiter', async () => {
  const actual = await vi.importActual<typeof import('@/lib/rate-limiter')>('@/lib/rate-limiter');
  return {
    ...actual,
    apiRateLimiter: { check: vi.fn().mockReturnValue({ allowed: true, remaining: 999 }) },
    getClientIp: vi.fn().mockReturnValue('127.0.0.1'),
  };
});

vi.mock('@/lib/wallet-holdings-consensus', () => ({
  buildWalletHoldingsConsensus: vi.fn(),
}));

function mockFetchEmptyDex() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    }),
  );
}

function baseConsensus(wallet: string) {
  return {
    wallet,
    source: 'rpc' as const,
    fetchedAt: Date.now(),
    holdings: [
      {
        mint: 'So11111111111111111111111111111111111111112',
        symbol: 'SOL',
        name: 'Solana',
        decimals: 9,
        amountLamports: '1000000000',
        uiAmount: 1,
        priceUsd: 0,
        valueUsd: 0,
        sources: ['rpcParsed'],
        accountCount: 1,
        accounts: [{ tokenAccount: 'acct1', amountLamports: '1000000000', decimals: 9 }],
      },
    ],
    summary: {
      tokenCount: 1,
      totalValueUsd: 0,
      pricedCount: 0,
      unpricedCount: 1,
    },
    diagnostics: {
      sourceStatus: {
        rpcParsed: { ok: true, durationMs: 10 },
        rpcRaw: { ok: true, durationMs: 10 },
        heliusDas: { ok: true, durationMs: 10 },
        solscan: { ok: false, durationMs: 10, error: '401' },
      },
      countsBySource: { rpcParsed: 1, rpcRaw: 1, heliusDas: 0, solscan: 0 },
      consensusTokenCount: 1,
      tokensOnlyIn: { rpcParsed: [], rpcRaw: [], heliusDas: [], solscan: [] },
    },
    warnings: ['solscan unavailable'],
  };
}

describe('GET /api/session-wallet/portfolio', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    mockFetchEmptyDex();
    const { apiRateLimiter, getClientIp } = await import('@/lib/rate-limiter');
    (apiRateLimiter.check as any).mockReturnValue({ allowed: true });
    (getClientIp as any).mockReturnValue('127.0.0.1');
  });

  it('returns diagnostics, warnings, and holding evidence', async () => {
    const wallet = 'So11111111111111111111111111111111111111112';
    const { buildWalletHoldingsConsensus } = await import('@/lib/wallet-holdings-consensus');
    (buildWalletHoldingsConsensus as any).mockResolvedValue(baseConsensus(wallet));

    const route = await import('@/app/api/session-wallet/portfolio/route');
    const req = new Request(`http://localhost/api/session-wallet/portfolio?wallet=${wallet}`);
    const res = await route.GET(req);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.diagnostics).toBeDefined();
    expect(Array.isArray(data.warnings)).toBe(true);
    expect(data.holdings[0].sources).toBeDefined();
    expect(data.holdings[0].accountCount).toBe(1);
    expect(Array.isArray(data.holdings[0].accounts)).toBe(true);
  });

  it('bypasses cache on fullScan', async () => {
    const wallet = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v';
    const { buildWalletHoldingsConsensus } = await import('@/lib/wallet-holdings-consensus');
    (buildWalletHoldingsConsensus as any).mockResolvedValue(baseConsensus(wallet));

    const route = await import('@/app/api/session-wallet/portfolio/route');
    const normalReq = new Request(`http://localhost/api/session-wallet/portfolio?wallet=${wallet}`);
    const fullReq = new Request(`http://localhost/api/session-wallet/portfolio?wallet=${wallet}&fullScan=1`);
    await route.GET(normalReq);
    await route.GET(fullReq);

    expect(buildWalletHoldingsConsensus).toHaveBeenCalledTimes(2);
    expect((buildWalletHoldingsConsensus as any).mock.calls[0][1]).toEqual({ forceFullScan: false });
    expect((buildWalletHoldingsConsensus as any).mock.calls[1][1]).toEqual({ forceFullScan: true });
  });

  it('serves stale cached snapshot when fresh build fails', async () => {
    const wallet = 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN';
    const { buildWalletHoldingsConsensus } = await import('@/lib/wallet-holdings-consensus');
    (buildWalletHoldingsConsensus as any)
      .mockResolvedValueOnce(baseConsensus(wallet))
      .mockRejectedValueOnce(new Error('upstream failed'));

    const route = await import('@/app/api/session-wallet/portfolio/route');
    const req = new Request(`http://localhost/api/session-wallet/portfolio?wallet=${wallet}`);
    const first = await route.GET(req);
    expect(first.status).toBe(200);
    const second = await route.GET(new Request(`http://localhost/api/session-wallet/portfolio?wallet=${wallet}&fullScan=1`));
    expect(second.status).toBe(200);
    const data = await second.json();
    expect(data.stale).toBe(true);
    expect(data.warning).toContain('cached snapshot');
  });
});
