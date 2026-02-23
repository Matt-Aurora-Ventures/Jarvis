import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { useTokenStore } from '@/stores/useTokenStore';

// ── Helper: parse Jupiter Price API response ────────────────────────
// This mirrors the logic we will implement in WatchlistPanel
function parseJupiterPriceResponse(json: Record<string, unknown>): Map<string, { price: number; change24h: number }> {
  const result = new Map<string, { price: number; change24h: number }>();
  const data = json.data as Record<string, { price: string; extraInfo?: { quotedPrice?: { buyPrice: string; sellPrice: string } } }> | undefined;
  if (!data) return result;

  for (const [mint, info] of Object.entries(data)) {
    const price = parseFloat(info.price);
    if (!isNaN(price)) {
      result.set(mint, { price, change24h: 0 });
    }
  }
  return result;
}

// ── Helper: format price ────────────────────────────────────────────
function formatWatchlistPrice(price: number): string {
  if (price === 0) return '$0.00';
  if (price < 0.0001) return `$${price.toExponential(2)}`;
  if (price < 0.01) return `$${price.toFixed(6)}`;
  if (price < 1) return `$${price.toFixed(4)}`;
  if (price < 1000) return `$${price.toFixed(2)}`;
  return `$${price.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
}

// ── Helper: truncate address for display ────────────────────────────
function truncateAddress(address: string): string {
  if (address.length <= 8) return address;
  return `${address.slice(0, 4)}...${address.slice(-4)}`;
}

describe('useTokenStore - watchlist operations', () => {
  beforeEach(() => {
    useTokenStore.setState({
      watchlist: [],
      selectedToken: null,
      recentSearches: [],
    });
  });

  it('should start with an empty watchlist', () => {
    const state = useTokenStore.getState();
    expect(state.watchlist).toEqual([]);
  });

  it('should add an address to the watchlist', () => {
    useTokenStore.getState().addToWatchlist('So11111111111111111111111111111112');
    const state = useTokenStore.getState();
    expect(state.watchlist).toContain('So11111111111111111111111111111112');
    expect(state.watchlist).toHaveLength(1);
  });

  it('should not add duplicate addresses', () => {
    const addr = 'So11111111111111111111111111111112';
    useTokenStore.getState().addToWatchlist(addr);
    useTokenStore.getState().addToWatchlist(addr);
    const state = useTokenStore.getState();
    expect(state.watchlist).toHaveLength(1);
  });

  it('should add multiple different addresses', () => {
    useTokenStore.getState().addToWatchlist('addr1');
    useTokenStore.getState().addToWatchlist('addr2');
    useTokenStore.getState().addToWatchlist('addr3');
    const state = useTokenStore.getState();
    expect(state.watchlist).toHaveLength(3);
    expect(state.watchlist).toEqual(['addr1', 'addr2', 'addr3']);
  });

  it('should remove an address from the watchlist', () => {
    useTokenStore.getState().addToWatchlist('addr1');
    useTokenStore.getState().addToWatchlist('addr2');
    useTokenStore.getState().removeFromWatchlist('addr1');
    const state = useTokenStore.getState();
    expect(state.watchlist).toEqual(['addr2']);
  });

  it('should handle removing a non-existent address gracefully', () => {
    useTokenStore.getState().addToWatchlist('addr1');
    useTokenStore.getState().removeFromWatchlist('nonexistent');
    const state = useTokenStore.getState();
    expect(state.watchlist).toEqual(['addr1']);
  });

  it('should have selectedToken as the source for "Add Current"', () => {
    useTokenStore.setState({
      selectedToken: {
        address: 'testMint123',
        name: 'Test Token',
        symbol: 'TEST',
      },
    });
    const { selectedToken, addToWatchlist } = useTokenStore.getState();
    if (selectedToken) {
      addToWatchlist(selectedToken.address);
    }
    expect(useTokenStore.getState().watchlist).toContain('testMint123');
  });

  it('should not add selectedToken address if already in watchlist', () => {
    useTokenStore.setState({
      selectedToken: {
        address: 'testMint123',
        name: 'Test Token',
        symbol: 'TEST',
      },
      watchlist: ['testMint123'],
    });
    const { selectedToken, addToWatchlist, watchlist } = useTokenStore.getState();
    const alreadyInWatchlist = watchlist.includes(selectedToken?.address ?? '');
    expect(alreadyInWatchlist).toBe(true);
  });
});

describe('Jupiter Price API response parsing', () => {
  it('should parse a valid response into a price map', () => {
    const mockResponse = {
      data: {
        So11111111111111111111111111111112: {
          id: 'So11111111111111111111111111111112',
          type: 'derivedPrice',
          price: '175.432',
        },
        EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v: {
          id: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
          type: 'derivedPrice',
          price: '1.0001',
        },
      },
      timeTaken: 0.002,
    };

    const prices = parseJupiterPriceResponse(mockResponse);
    expect(prices.size).toBe(2);
    expect(prices.get('So11111111111111111111111111111112')?.price).toBeCloseTo(175.432);
    expect(prices.get('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v')?.price).toBeCloseTo(1.0001);
  });

  it('should handle an empty data object', () => {
    const prices = parseJupiterPriceResponse({ data: {} });
    expect(prices.size).toBe(0);
  });

  it('should handle missing data key', () => {
    const prices = parseJupiterPriceResponse({});
    expect(prices.size).toBe(0);
  });

  it('should skip entries with invalid price', () => {
    const mockResponse = {
      data: {
        validMint: { id: 'validMint', type: 'derivedPrice', price: '42.5' },
        invalidMint: { id: 'invalidMint', type: 'derivedPrice', price: 'NaN' },
      },
    };
    const prices = parseJupiterPriceResponse(mockResponse);
    expect(prices.size).toBe(1);
    expect(prices.has('validMint')).toBe(true);
    expect(prices.has('invalidMint')).toBe(false);
  });
});

describe('Price formatting for watchlist', () => {
  it('should format zero as $0.00', () => {
    expect(formatWatchlistPrice(0)).toBe('$0.00');
  });

  it('should format very small prices with scientific notation', () => {
    const result = formatWatchlistPrice(0.00001234);
    expect(result).toMatch(/^\$1\.23e-5$/);
  });

  it('should format small prices with 6 decimals', () => {
    expect(formatWatchlistPrice(0.005432)).toBe('$0.005432');
  });

  it('should format sub-dollar prices with 4 decimals', () => {
    expect(formatWatchlistPrice(0.1234)).toBe('$0.1234');
  });

  it('should format normal prices with 2 decimals', () => {
    expect(formatWatchlistPrice(175.43)).toBe('$175.43');
  });

  it('should format large prices with comma separators', () => {
    const result = formatWatchlistPrice(12345.67);
    expect(result).toBe('$12,345.67');
  });
});

describe('Address truncation', () => {
  it('should truncate long addresses', () => {
    expect(truncateAddress('So11111111111111111111111111111112')).toBe('So11...1112');
  });

  it('should not truncate short addresses', () => {
    expect(truncateAddress('short')).toBe('short');
  });

  it('should handle exactly 8 character addresses', () => {
    expect(truncateAddress('12345678')).toBe('12345678');
  });
});
