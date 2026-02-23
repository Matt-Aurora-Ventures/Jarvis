import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// -------------------------------------------------------------------
// Tests for MarketTicker data layer + helpers
// -------------------------------------------------------------------

// We will import these from the module once implemented:
// import { TRACKED_MINTS, fetchTickerData, formatPrice, formatChange, TickerItem } from '@/components/layout/MarketTicker';

describe('MarketTicker - TRACKED_MINTS config', () => {
  let TRACKED_MINTS: Record<string, string>;

  beforeEach(async () => {
    const mod = await import('@/components/layout/MarketTicker');
    TRACKED_MINTS = mod.TRACKED_MINTS;
  });

  it('should export a TRACKED_MINTS record with at least 5 tokens', () => {
    expect(Object.keys(TRACKED_MINTS).length).toBeGreaterThanOrEqual(5);
  });

  it('should include SOL in the tracked mints', () => {
    const symbols = Object.values(TRACKED_MINTS);
    expect(symbols).toContain('SOL');
  });

  it('should include BONK in the tracked mints', () => {
    const symbols = Object.values(TRACKED_MINTS);
    expect(symbols).toContain('BONK');
  });

  it('should include JUP in the tracked mints', () => {
    const symbols = Object.values(TRACKED_MINTS);
    expect(symbols).toContain('JUP');
  });

  it('should have valid Solana mint addresses as keys (32+ chars base58)', () => {
    for (const mint of Object.keys(TRACKED_MINTS)) {
      expect(mint.length).toBeGreaterThanOrEqual(32);
    }
  });
});

describe('MarketTicker - formatPrice', () => {
  let formatPrice: (price: number) => string;

  beforeEach(async () => {
    const mod = await import('@/components/layout/MarketTicker');
    formatPrice = mod.formatPrice;
  });

  it('should format large prices with 2 decimal places', () => {
    expect(formatPrice(98450.12)).toBe('$98,450.12');
  });

  it('should format mid-range prices with 2 decimals', () => {
    expect(formatPrice(187.42)).toBe('$187.42');
  });

  it('should format prices under $1 with appropriate decimals', () => {
    const result = formatPrice(0.85);
    expect(result).toMatch(/^\$0\.8/);
  });

  it('should format very small prices (micro-cap tokens) with significant digits', () => {
    const result = formatPrice(0.0000234);
    // Should show meaningful digits, not just $0.00
    expect(result).not.toBe('$0.00');
    expect(result).toContain('0.0000');
  });

  it('should format zero as $0.00', () => {
    expect(formatPrice(0)).toBe('$0.00');
  });
});

describe('MarketTicker - formatChange', () => {
  let formatChange: (change: number) => string;

  beforeEach(async () => {
    const mod = await import('@/components/layout/MarketTicker');
    formatChange = mod.formatChange;
  });

  it('should prefix positive changes with +', () => {
    const result = formatChange(3.2);
    expect(result).toMatch(/^\+3\.2/);
  });

  it('should format negative changes with a minus sign', () => {
    const result = formatChange(-0.5);
    expect(result).toMatch(/^-0\.5/);
  });

  it('should format zero change', () => {
    const result = formatChange(0);
    expect(result).toContain('0.0');
  });

  it('should include percent sign', () => {
    const result = formatChange(12.1);
    expect(result).toContain('%');
  });
});

describe('MarketTicker - fetchTickerData', () => {
  let fetchTickerData: () => Promise<Array<{ symbol: string; price: number; change24h: number; mint: string }>>;

  beforeEach(async () => {
    const mod = await import('@/components/layout/MarketTicker');
    fetchTickerData = mod.fetchTickerData;
    // Reset fetch mock
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should call Jupiter Price API with mint addresses', async () => {
    const mockResponse = {
      data: {
        'So11111111111111111111111111111111111111112': {
          id: 'So11111111111111111111111111111111111111112',
          type: 'derivedPrice',
          price: '187.42',
          extraInfo: {
            lastSwappedPrice: {
              lastJupiterSellAt: 1700000000,
              lastJupiterSellPrice: '187.42',
              lastJupiterBuyAt: 1700000000,
              lastJupiterBuyPrice: '187.42',
            },
            quotedPrice: {
              buyPrice: '187.42',
              buyAt: 1700000000,
              sellPrice: '187.42',
              sellAt: 1700000000,
            },
            confidenceLevel: 'high',
          },
        },
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const items = await fetchTickerData();

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const callUrl = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(callUrl).toContain('api.jup.ag/price');
    expect(callUrl).toContain('So11111111111111111111111111111111111111112');
  });

  it('should return an array of TickerItem objects with correct fields', async () => {
    const mockResponse = {
      data: {
        'So11111111111111111111111111111111111111112': {
          id: 'So11111111111111111111111111111111111111112',
          type: 'derivedPrice',
          price: '187.42',
          extraInfo: {
            lastSwappedPrice: {
              lastJupiterSellPrice: '185.00',
              lastJupiterBuyPrice: '187.42',
            },
            confidenceLevel: 'high',
          },
        },
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const items = await fetchTickerData();

    expect(items.length).toBeGreaterThanOrEqual(1);
    const sol = items.find((i) => i.symbol === 'SOL');
    expect(sol).toBeDefined();
    expect(sol!.price).toBe(187.42);
    expect(sol!.mint).toBe('So11111111111111111111111111111111111111112');
    expect(typeof sol!.change24h).toBe('number');
  });

  it('should return empty array on fetch failure', async () => {
    globalThis.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'));

    const items = await fetchTickerData();
    expect(items).toEqual([]);
  });

  it('should return empty array on malformed response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ unexpected: 'shape' }),
    });

    const items = await fetchTickerData();
    expect(items).toEqual([]);
  });
});
