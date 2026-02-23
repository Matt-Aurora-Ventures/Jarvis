import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

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

function makeBoostedToken(overrides: Record<string, unknown> = {}) {
  return {
    url: 'https://dexscreener.com/solana/abc123',
    chainId: 'solana',
    tokenAddress: 'So11111111111111111111111111111111111111112',
    icon: 'https://example.com/icon.png',
    header: 'https://example.com/header.png',
    openGraph: 'https://example.com/og.png',
    description: 'Wrapped SOL',
    links: [],
    amount: 500,
    totalAmount: 1500,
    ...overrides,
  };
}

// ── Tests ────────────────────────────────────────────────────────────

describe('dexscreener trending API', () => {
  describe('fetchTrendingTokens', () => {
    let fetchTrendingTokens: () => Promise<Array<{
      tokenAddress: string;
      chainId: string;
      url: string;
      amount: number;
    }>>;

    beforeEach(async () => {
      const mod = await import('../dexscreener');
      fetchTrendingTokens = mod.fetchTrendingTokens;
    });

    it('should call the DexScreener token-boosts API', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await fetchTrendingTokens();

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const calledUrl = mockFetch.mock.calls[0][0] as string;
      expect(calledUrl).toContain('api.dexscreener.com/token-boosts/top/v1');
    });

    it('should return only Solana tokens from the response', async () => {
      const tokens = [
        makeBoostedToken({ chainId: 'solana', tokenAddress: 'sol1' }),
        makeBoostedToken({ chainId: 'ethereum', tokenAddress: 'eth1' }),
        makeBoostedToken({ chainId: 'solana', tokenAddress: 'sol2' }),
        makeBoostedToken({ chainId: 'bsc', tokenAddress: 'bsc1' }),
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => tokens,
      });

      const result = await fetchTrendingTokens();
      expect(result.every((t) => t.chainId === 'solana')).toBe(true);
      expect(result).toHaveLength(2);
    });

    it('should return empty array on API failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      const result = await fetchTrendingTokens();
      expect(result).toEqual([]);
    });

    it('should return empty array on network error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const result = await fetchTrendingTokens();
      expect(result).toEqual([]);
    });

    it('should return empty array on malformed response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ not: 'an array' }),
      });

      const result = await fetchTrendingTokens();
      expect(result).toEqual([]);
    });

    it('should deduplicate tokens by address', async () => {
      const tokens = [
        makeBoostedToken({ chainId: 'solana', tokenAddress: 'same-addr', amount: 500 }),
        makeBoostedToken({ chainId: 'solana', tokenAddress: 'same-addr', amount: 300 }),
        makeBoostedToken({ chainId: 'solana', tokenAddress: 'different', amount: 200 }),
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => tokens,
      });

      const result = await fetchTrendingTokens();
      expect(result).toHaveLength(2);
    });
  });

  describe('enrichTrendingTokens', () => {
    let enrichTrendingTokens: (addresses: string[]) => Promise<Array<{
      address: string;
      name: string;
      symbol: string;
      priceUsd: string;
      priceChange24h: number;
      volume24h: number;
      liquidity: number;
      fdv: number;
      poolAddress: string;
    }>>;

    beforeEach(async () => {
      const mod = await import('../dexscreener');
      enrichTrendingTokens = mod.enrichTrendingTokens;
    });

    it('should call DexScreener token detail API with comma-separated addresses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ pairs: [] }),
      });

      await enrichTrendingTokens(['addr1', 'addr2']);

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const calledUrl = mockFetch.mock.calls[0][0] as string;
      expect(calledUrl).toContain('api.dexscreener.com/latest/dex/tokens');
      expect(calledUrl).toContain('addr1');
      expect(calledUrl).toContain('addr2');
    });

    it('should return enriched token data with price, change, volume', async () => {
      const mockPairs = [
        {
          chainId: 'solana',
          dexId: 'raydium',
          url: 'https://dexscreener.com/solana/pair123',
          baseToken: {
            address: 'addr1',
            name: 'Token One',
            symbol: 'TOK1',
          },
          quoteToken: {
            address: 'USDC',
            name: 'USDC',
            symbol: 'USDC',
          },
          priceUsd: '1.23',
          priceChange: { h24: 45.2 },
          volume: { h24: 12000000 },
          liquidity: { usd: 500000 },
          fdv: 50000000,
          pairAddress: 'pool123',
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ pairs: mockPairs }),
      });

      const result = await enrichTrendingTokens(['addr1']);

      expect(result).toHaveLength(1);
      expect(result[0]).toMatchObject({
        address: 'addr1',
        name: 'Token One',
        symbol: 'TOK1',
        priceUsd: '1.23',
        priceChange24h: 45.2,
        volume24h: 12000000,
        poolAddress: 'pool123',
      });
    });

    it('should filter to Solana pairs only', async () => {
      const mockPairs = [
        {
          chainId: 'solana',
          dexId: 'raydium',
          url: '',
          baseToken: { address: 'addr1', name: 'A', symbol: 'A' },
          quoteToken: { address: 'USDC', name: 'USDC', symbol: 'USDC' },
          priceUsd: '1.0',
          priceChange: { h24: 5 },
          volume: { h24: 1000 },
          liquidity: { usd: 500 },
          fdv: 10000,
          pairAddress: 'pool1',
        },
        {
          chainId: 'ethereum',
          dexId: 'uniswap',
          url: '',
          baseToken: { address: 'addr1', name: 'A', symbol: 'A' },
          quoteToken: { address: 'USDT', name: 'USDT', symbol: 'USDT' },
          priceUsd: '1.1',
          priceChange: { h24: 6 },
          volume: { h24: 2000 },
          liquidity: { usd: 600 },
          fdv: 11000,
          pairAddress: 'pool2',
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ pairs: mockPairs }),
      });

      const result = await enrichTrendingTokens(['addr1']);
      expect(result).toHaveLength(1);
      expect(result[0].poolAddress).toBe('pool1');
    });

    it('should return empty array on API error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 429,
      });

      const result = await enrichTrendingTokens(['addr1']);
      expect(result).toEqual([]);
    });

    it('should return empty array for empty input', async () => {
      const result = await enrichTrendingTokens([]);
      expect(result).toEqual([]);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('should pick highest-volume Solana pair per unique token address', async () => {
      const mockPairs = [
        {
          chainId: 'solana',
          dexId: 'raydium',
          url: '',
          baseToken: { address: 'addr1', name: 'A', symbol: 'A' },
          quoteToken: { address: 'USDC', name: 'USDC', symbol: 'USDC' },
          priceUsd: '1.0',
          priceChange: { h24: 5 },
          volume: { h24: 500 },
          liquidity: { usd: 200 },
          fdv: 10000,
          pairAddress: 'low-vol-pool',
        },
        {
          chainId: 'solana',
          dexId: 'orca',
          url: '',
          baseToken: { address: 'addr1', name: 'A', symbol: 'A' },
          quoteToken: { address: 'SOL', name: 'SOL', symbol: 'SOL' },
          priceUsd: '1.01',
          priceChange: { h24: 5.1 },
          volume: { h24: 5000 },
          liquidity: { usd: 2000 },
          fdv: 10100,
          pairAddress: 'high-vol-pool',
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ pairs: mockPairs }),
      });

      const result = await enrichTrendingTokens(['addr1']);
      expect(result).toHaveLength(1);
      expect(result[0].poolAddress).toBe('high-vol-pool');
    });
  });

  describe('formatCompactNumber', () => {
    let formatCompactNumber: (num: number) => string;

    beforeEach(async () => {
      const mod = await import('../dexscreener');
      formatCompactNumber = mod.formatCompactNumber;
    });

    it('should format billions', () => {
      expect(formatCompactNumber(1_500_000_000)).toBe('$1.5B');
    });

    it('should format millions', () => {
      expect(formatCompactNumber(12_000_000)).toBe('$12.0M');
    });

    it('should format thousands', () => {
      expect(formatCompactNumber(350_000)).toBe('$350.0K');
    });

    it('should format small numbers', () => {
      expect(formatCompactNumber(500)).toBe('$500');
    });

    it('should handle zero', () => {
      expect(formatCompactNumber(0)).toBe('$0');
    });
  });
});
