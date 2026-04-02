import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('price-stream-config', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('defaults PRICE_STREAM_MODE to dexpaprika', async () => {
    delete process.env.NEXT_PUBLIC_PRICE_STREAM;
    const mod = await import('@/lib/price-stream-config');
    expect(mod.PRICE_STREAM_MODE).toBe('dexpaprika');
  });

  it('exports correct DexPaprika stream URL', async () => {
    delete process.env.NEXT_PUBLIC_DEXPAPRIKA_URL;
    const mod = await import('@/lib/price-stream-config');
    expect(mod.DEXPAPRIKA_STREAM_URL).toBe('https://streaming.dexpaprika.com/stream');
  });

  it('SSE_ACTIVE_POLL_MS is 15 seconds', async () => {
    const mod = await import('@/lib/price-stream-config');
    expect(mod.SSE_ACTIVE_POLL_MS).toBe(15_000);
  });

  it('DEFAULT_POLL_MS is 3 seconds', async () => {
    const mod = await import('@/lib/price-stream-config');
    expect(mod.DEFAULT_POLL_MS).toBe(3_000);
  });
});
