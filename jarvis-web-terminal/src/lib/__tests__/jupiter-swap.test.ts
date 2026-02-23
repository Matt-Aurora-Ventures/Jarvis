import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getJupiterQuote,
  getJupiterSwapTransaction,
  SOL_MINT,
  type JupiterQuote,
} from '../jupiter-swap';

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  mockFetch.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('jupiter-swap', () => {
  describe('SOL_MINT constant', () => {
    it('should export the correct SOL mint address', () => {
      expect(SOL_MINT).toBe('So11111111111111111111111111111111111111112');
    });
  });

  describe('getJupiterQuote', () => {
    const validQuoteResponse: JupiterQuote = {
      inputMint: SOL_MINT,
      outputMint: 'TokenMintABC123',
      inAmount: '1000000000',
      outAmount: '5000000',
      otherAmountThreshold: '4950000',
      swapMode: 'ExactIn',
      slippageBps: 50,
      priceImpactPct: '0.12',
      routePlan: [
        {
          swapInfo: {
            ammKey: 'ammKey123',
            label: 'Raydium',
            inputMint: SOL_MINT,
            outputMint: 'TokenMintABC123',
            inAmount: '1000000000',
            outAmount: '5000000',
            feeAmount: '2500',
            feeMint: SOL_MINT,
          },
          percent: 100,
        },
      ],
    };

    it('should call the Jupiter quote API with correct params', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => validQuoteResponse,
      });

      await getJupiterQuote({
        inputMint: SOL_MINT,
        outputMint: 'TokenMintABC123',
        amount: 1000000000,
        slippageBps: 50,
      });

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const calledUrl = mockFetch.mock.calls[0][0] as string;
      expect(calledUrl).toContain('https://api.jup.ag/swap/v1/quote');
      expect(calledUrl).toContain('inputMint=' + SOL_MINT);
      expect(calledUrl).toContain('outputMint=TokenMintABC123');
      expect(calledUrl).toContain('amount=1000000000');
      expect(calledUrl).toContain('slippageBps=50');
    });

    it('should return the parsed quote on success', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => validQuoteResponse,
      });

      const quote = await getJupiterQuote({
        inputMint: SOL_MINT,
        outputMint: 'TokenMintABC123',
        amount: 1000000000,
        slippageBps: 50,
      });

      expect(quote).toEqual(validQuoteResponse);
      expect(quote.inAmount).toBe('1000000000');
      expect(quote.outAmount).toBe('5000000');
      expect(quote.priceImpactPct).toBe('0.12');
    });

    it('should throw on non-ok response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
      });

      await expect(
        getJupiterQuote({
          inputMint: SOL_MINT,
          outputMint: 'TokenMintABC123',
          amount: 1000000000,
          slippageBps: 50,
        })
      ).rejects.toThrow();
    });

    it('should throw on network error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(
        getJupiterQuote({
          inputMint: SOL_MINT,
          outputMint: 'TokenMintABC123',
          amount: 1000000000,
          slippageBps: 50,
        })
      ).rejects.toThrow('Network error');
    });
  });

  describe('getJupiterSwapTransaction', () => {
    const mockQuote: JupiterQuote = {
      inputMint: SOL_MINT,
      outputMint: 'TokenMintABC123',
      inAmount: '1000000000',
      outAmount: '5000000',
      otherAmountThreshold: '4950000',
      swapMode: 'ExactIn',
      slippageBps: 50,
      priceImpactPct: '0.12',
      routePlan: [],
    };

    it('should POST to the Jupiter swap endpoint', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          swapTransaction: 'base64EncodedTransaction==',
        }),
      });

      await getJupiterSwapTransaction({
        quoteResponse: mockQuote,
        userPublicKey: 'UserPubKey123',
      });

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('https://api.jup.ag/swap/v1/swap');
      expect(options.method).toBe('POST');
      expect(options.headers['Content-Type']).toBe('application/json');

      const body = JSON.parse(options.body);
      expect(body.quoteResponse).toEqual(mockQuote);
      expect(body.userPublicKey).toBe('UserPubKey123');
      expect(body.dynamicComputeUnitLimit).toBe(true);
      expect(body.dynamicSlippage).toBe(true);
    });

    it('should return the base64 swap transaction string', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          swapTransaction: 'base64EncodedTransaction==',
        }),
      });

      const txn = await getJupiterSwapTransaction({
        quoteResponse: mockQuote,
        userPublicKey: 'UserPubKey123',
      });

      expect(txn).toBe('base64EncodedTransaction==');
    });

    it('should throw on non-ok response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      });

      await expect(
        getJupiterSwapTransaction({
          quoteResponse: mockQuote,
          userPublicKey: 'UserPubKey123',
        })
      ).rejects.toThrow();
    });

    it('should throw on network error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Connection refused'));

      await expect(
        getJupiterSwapTransaction({
          quoteResponse: mockQuote,
          userPublicKey: 'UserPubKey123',
        })
      ).rejects.toThrow('Connection refused');
    });
  });
});
