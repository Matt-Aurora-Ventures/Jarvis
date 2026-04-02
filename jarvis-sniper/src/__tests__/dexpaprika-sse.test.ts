import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { startDexPaprikaStream, type DexPaprikaPriceEvent } from '@/lib/dexpaprika-sse';

describe('startDexPaprikaStream', () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('calls fetch with POST and correct body format', async () => {
    let capturedUrl = '';
    let capturedInit: RequestInit | undefined;

    globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      capturedUrl = url;
      capturedInit = init;
      // Return a never-resolving response to keep the stream open
      return new Promise(() => {});
    });

    const handle = startDexPaprikaStream(
      ['mint1', 'mint2'],
      () => {},
    );

    // Give time for fetch to be called
    await new Promise((r) => setTimeout(r, 50));

    expect(capturedUrl).toContain('streaming.dexpaprika.com/stream');
    expect(capturedInit?.method).toBe('POST');
    expect(capturedInit?.headers).toEqual(
      expect.objectContaining({ 'Content-Type': 'application/json' }),
    );

    const body = JSON.parse(capturedInit?.body as string);
    expect(body).toEqual([
      { chain: 'solana', address: 'mint1', method: 't_p' },
      { chain: 'solana', address: 'mint2', method: 't_p' },
    ]);

    handle.close();
  });

  it('does not connect when mints array is empty', async () => {
    globalThis.fetch = vi.fn();

    const handle = startDexPaprikaStream([], () => {});
    await new Promise((r) => setTimeout(r, 50));

    expect(globalThis.fetch).not.toHaveBeenCalled();
    handle.close();
  });

  it('calls onStatus with disconnected when fetch fails', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    const statuses: string[] = [];
    const handle = startDexPaprikaStream(
      ['mint1'],
      () => {},
      (status) => { statuses.push(status); },
    );

    await new Promise((r) => setTimeout(r, 100));

    expect(statuses).toContain('disconnected');
    handle.close();
  });

  it('reconnects with new mints when updateMints is called', async () => {
    let fetchCount = 0;
    const bodies: string[] = [];

    globalThis.fetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      fetchCount++;
      bodies.push(init?.body as string);
      return new Promise(() => {});
    });

    const handle = startDexPaprikaStream(['mint1'], () => {});
    await new Promise((r) => setTimeout(r, 50));

    expect(fetchCount).toBe(1);

    handle.updateMints(['mint1', 'mint2', 'mint3']);
    await new Promise((r) => setTimeout(r, 50));

    expect(fetchCount).toBe(2);
    const lastBody = JSON.parse(bodies[bodies.length - 1]);
    expect(lastBody).toHaveLength(3);

    handle.close();
  });

  it('does not reconnect when mints unchanged', async () => {
    let fetchCount = 0;

    globalThis.fetch = vi.fn().mockImplementation(() => {
      fetchCount++;
      return new Promise(() => {});
    });

    const handle = startDexPaprikaStream(['mint1', 'mint2'], () => {});
    await new Promise((r) => setTimeout(r, 50));

    handle.updateMints(['mint2', 'mint1']); // Same mints, different order
    await new Promise((r) => setTimeout(r, 50));

    expect(fetchCount).toBe(1); // Should NOT reconnect

    handle.close();
  });
});

describe('SSE message parsing', () => {
  it('parses DexPaprika price event format', () => {
    // Simulate parsing the SSE data line
    const line = 'data: {"a":"So11111","c":"solana","p":"187.42","t":1711612800,"t_p":1711612799}';
    const json = line.slice(5).trim();
    const data = JSON.parse(json);

    const event: DexPaprikaPriceEvent = {
      address: data.a,
      priceUsd: parseFloat(data.p),
      timestamp: data.t_p || data.t,
    };

    expect(event.address).toBe('So11111');
    expect(event.priceUsd).toBe(187.42);
    expect(event.timestamp).toBe(1711612799);
  });
});
