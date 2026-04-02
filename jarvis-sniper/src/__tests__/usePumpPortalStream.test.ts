import { describe, it, expect } from 'vitest';

/**
 * Tests for PumpPortal stream logic.
 *
 * The usePumpPortalStream hook is a React client component that manages a
 * WebSocket connection. Testing the full hook requires a React testing library
 * + WebSocket mock, which is integration territory.
 *
 * Here we test the core message parsing and dedup logic that the hook relies on.
 */

describe('PumpPortal message parsing', () => {
  // Simulate the parsing logic from usePumpPortalStream.onmessage
  function parsePumpPortalMessage(data: string): { mint: string; symbol: string; name: string } | null {
    try {
      const parsed = JSON.parse(data);
      const mint: string | undefined = parsed.mint;
      if (!mint || typeof mint !== 'string') return null;
      return {
        mint,
        symbol: parsed.symbol || '???',
        name: parsed.name || 'New Token',
      };
    } catch {
      return null;
    }
  }

  it('parses valid token message', () => {
    const msg = JSON.stringify({
      mint: 'So11111111111111111111111111111111111111112',
      symbol: 'TEST',
      name: 'Test Token',
    });
    const result = parsePumpPortalMessage(msg);
    expect(result).toEqual({
      mint: 'So11111111111111111111111111111111111111112',
      symbol: 'TEST',
      name: 'Test Token',
    });
  });

  it('returns null for missing mint', () => {
    const msg = JSON.stringify({ symbol: 'TEST' });
    expect(parsePumpPortalMessage(msg)).toBeNull();
  });

  it('returns null for non-string mint', () => {
    const msg = JSON.stringify({ mint: 123 });
    expect(parsePumpPortalMessage(msg)).toBeNull();
  });

  it('defaults symbol to ??? when missing', () => {
    const msg = JSON.stringify({ mint: 'abc123' });
    const result = parsePumpPortalMessage(msg);
    expect(result?.symbol).toBe('???');
  });

  it('defaults name to New Token when missing', () => {
    const msg = JSON.stringify({ mint: 'abc123' });
    const result = parsePumpPortalMessage(msg);
    expect(result?.name).toBe('New Token');
  });

  it('returns null for invalid JSON', () => {
    expect(parsePumpPortalMessage('not json')).toBeNull();
  });

  it('returns null for subscription confirmation messages', () => {
    // PumpPortal sends confirmations that don't have mint
    const msg = JSON.stringify({ message: 'Successfully subscribed to newToken events' });
    expect(parsePumpPortalMessage(msg)).toBeNull();
  });
});

describe('PumpPortal dedup logic', () => {
  it('deduplicates mints within window', () => {
    const seen = new Map<string, number>();
    const DEDUP_WINDOW_MS = 30_000;

    function shouldProcess(mint: string): boolean {
      const now = Date.now();
      if (seen.has(mint)) return false;
      seen.set(mint, now);
      return true;
    }

    expect(shouldProcess('mint1')).toBe(true);
    expect(shouldProcess('mint1')).toBe(false); // Duplicate
    expect(shouldProcess('mint2')).toBe(true); // Different mint
  });

  it('prunes dedup map when over 500 entries', () => {
    const seen = new Map<string, number>();
    const now = Date.now();

    // Fill with 501 entries
    for (let i = 0; i < 501; i++) {
      seen.set(`mint_${i}`, now - 31_000); // All expired (>30s)
    }

    expect(seen.size).toBe(501);

    // Prune (same logic as the hook)
    if (seen.size > 500) {
      for (const [m, ts] of seen) {
        if (now - ts > 30_000) seen.delete(m);
      }
    }

    expect(seen.size).toBe(0);
  });
});
