import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Must re-import fresh each test to reset module-level cache
let getJitoTipFloor: () => Promise<number>;

describe('getJitoTipFloor', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(async () => {
    vi.restoreAllMocks();
    // Re-import to reset the module-level cache (cachedTip)
    vi.resetModules();
    const mod = await import('@/lib/jito-tip');
    getJitoTipFloor = mod.getJitoTipFloor;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('fetches 50th percentile tip and returns lamports', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          { landed_tips_50th_percentile: 0.000005 }, // 5000 lamports
        ]),
    });

    const tip = await getJitoTipFloor();
    expect(tip).toBe(5000);
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });

  it('returns fallback (1_000_000 lamports = 0.001 SOL) when API fails', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    const tip = await getJitoTipFloor();
    expect(tip).toBe(1_000_000);
  });

  it('returns fallback when API returns non-ok status', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    });

    const tip = await getJitoTipFloor();
    expect(tip).toBe(1_000_000);
  });

  it('caches the tip for 60 seconds', async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(() => {
      callCount++;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([{ landed_tips_50th_percentile: 0.00001 }]),
      });
    });

    const tip1 = await getJitoTipFloor();
    const tip2 = await getJitoTipFloor();

    expect(tip1).toBe(tip2);
    expect(callCount).toBe(1); // Second call should use cache
  });

  it('handles zero tip value gracefully', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([{ landed_tips_50th_percentile: 0 }]),
    });

    const tip = await getJitoTipFloor();
    // Zero is not > 0, so it falls through to fallback
    expect(tip).toBe(1_000_000);
  });

  it('handles missing array response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });

    const tip = await getJitoTipFloor();
    expect(tip).toBe(1_000_000);
  });
});
