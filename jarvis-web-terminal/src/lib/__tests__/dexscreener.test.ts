import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  searchDexScreener,
  filterSolanaPairs,
  type DexScreenerPair,
} from '../dexscreener';

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  mockFetch.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Test Data ────────────────────────────────────────────────────────

function makePair(overrides: Partial<DexScreenerPair> = {}): DexScreenerPair {
  return {
    chainId: 'solana',
    dexId: 'raydium',
    url: 'https://dexscreener.com/solana/pair123',
    baseToken: {
      address: 'So11111111111111111111111111111111111111112',
      name: 'Wrapped SOL',
      symbol: 'SOL',
    },
    quoteToken: {
      address: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
      name: 'USD Coin',
      symbol: 'USDC',
    },
    priceUsd: '185.50',
    priceChange: { h24: 3.2 },
    volume: { h24: 5000000 },
    liquidity: { usd: 12000000 },
    fdv: 80000000000,
    pairAddress: 'pair123',
    ...overrides,
  };
}

// ── Tests ────────────────────────────────────────────────────────────

describe('dexscreener', () => {
  describe('searchDexScreener', () => {
    it('should call DexScreener search API with encoded query', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ pairs: [] }),
      });

      await searchDexScreener('bonk dog');

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const calledUrl = mockFetch.mock.calls[0][0] as string;
      expect(calledUrl).toContain('https://api.dexscreener.com/latest/dex/search');
      expect(calledUrl).toContain('q=bonk%20dog');
    });

    it('should return pairs from API response', async () => {
      const pair = makePair();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ pairs: [pair] }),
      });

      const result = await searchDexScreener('SOL');

      expect(result).toHaveLength(1);
      expect(result[0].baseToken.symbol).toBe('SOL');
    });

    it('should return empty array when pairs is null', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ pairs: null }),
      });

      const result = await searchDexScreener('nonexistent');

      expect(result).toEqual([]);
    });

    it('should return empty array on API failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 429,
      });

      const result = await searchDexScreener('SOL');

      expect(result).toEqual([]);
    });

    it('should return empty array on network error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const result = await searchDexScreener('SOL');

      expect(result).toEqual([]);
    });

    it('should handle empty query gracefully', async () => {
      const result = await searchDexScreener('');

      expect(result).toEqual([]);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('should handle whitespace-only query gracefully', async () => {
      const result = await searchDexScreener('   ');

      expect(result).toEqual([]);
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('filterSolanaPairs', () => {
    it('should filter to only solana chainId pairs', () => {
      const pairs = [
        makePair({ chainId: 'solana' }),
        makePair({ chainId: 'ethereum', baseToken: { address: '0x1', name: 'ETH Token', symbol: 'ETK' } }),
        makePair({ chainId: 'solana', baseToken: { address: 'mint2', name: 'Bonk', symbol: 'BONK' } }),
        makePair({ chainId: 'bsc' }),
      ];

      const filtered = filterSolanaPairs(pairs);

      expect(filtered).toHaveLength(2);
      expect(filtered.every((p) => p.chainId === 'solana')).toBe(true);
    });

    it('should return empty array when no solana pairs exist', () => {
      const pairs = [
        makePair({ chainId: 'ethereum' }),
        makePair({ chainId: 'bsc' }),
      ];

      const filtered = filterSolanaPairs(pairs);

      expect(filtered).toHaveLength(0);
    });

    it('should return empty array for empty input', () => {
      const filtered = filterSolanaPairs([]);

      expect(filtered).toHaveLength(0);
    });

    it('should limit results to maxResults parameter', () => {
      const pairs = Array.from({ length: 20 }, (_, i) =>
        makePair({
          chainId: 'solana',
          baseToken: { address: `mint${i}`, name: `Token ${i}`, symbol: `T${i}` },
        })
      );

      const filtered = filterSolanaPairs(pairs, 10);

      expect(filtered).toHaveLength(10);
    });

    it('should default to 10 results when no maxResults specified', () => {
      const pairs = Array.from({ length: 15 }, (_, i) =>
        makePair({
          chainId: 'solana',
          baseToken: { address: `mint${i}`, name: `Token ${i}`, symbol: `T${i}` },
        })
      );

      const filtered = filterSolanaPairs(pairs);

      expect(filtered).toHaveLength(10);
    });

    it('should deduplicate by base token address', () => {
      const pairs = [
        makePair({
          chainId: 'solana',
          baseToken: { address: 'mintA', name: 'Token A', symbol: 'TOKA' },
          dexId: 'raydium',
        }),
        makePair({
          chainId: 'solana',
          baseToken: { address: 'mintA', name: 'Token A', symbol: 'TOKA' },
          dexId: 'orca',
        }),
        makePair({
          chainId: 'solana',
          baseToken: { address: 'mintB', name: 'Token B', symbol: 'TOKB' },
        }),
      ];

      const filtered = filterSolanaPairs(pairs);

      expect(filtered).toHaveLength(2);
      const addresses = filtered.map((p) => p.baseToken.address);
      expect(addresses).toContain('mintA');
      expect(addresses).toContain('mintB');
    });
  });
});
