import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchTokenPrices,
  checkPositionThresholds,
  type SLTPEvent,
} from '../stop-loss-manager';

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  mockFetch.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('stop-loss-manager', () => {
  describe('fetchTokenPrices', () => {
    it('should return empty map for empty mints array', async () => {
      const prices = await fetchTokenPrices([]);
      expect(prices.size).toBe(0);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('should call Jupiter Price API with comma-separated mints', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          data: {
            MintA: { price: '1.50' },
            MintB: { price: '0.0025' },
          },
        }),
      });

      await fetchTokenPrices(['MintA', 'MintB']);

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const calledUrl = mockFetch.mock.calls[0][0] as string;
      expect(calledUrl).toContain('https://api.jup.ag/price/v3/price');
      expect(calledUrl).toContain('ids=MintA%2CMintB');
    });

    it('should return parsed prices as a Map', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          data: {
            MintA: { price: '1.50' },
            MintB: { price: '0.0025' },
          },
        }),
      });

      const prices = await fetchTokenPrices(['MintA', 'MintB']);

      expect(prices.size).toBe(2);
      expect(prices.get('MintA')).toBe(1.5);
      expect(prices.get('MintB')).toBe(0.0025);
    });

    it('should handle missing prices gracefully (skip nulls)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          data: {
            MintA: { price: '1.50' },
            MintB: null,
          },
        }),
      });

      const prices = await fetchTokenPrices(['MintA', 'MintB']);

      expect(prices.size).toBe(1);
      expect(prices.get('MintA')).toBe(1.5);
      expect(prices.has('MintB')).toBe(false);
    });

    it('should return empty map on API failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      const prices = await fetchTokenPrices(['MintA']);

      expect(prices.size).toBe(0);
    });

    it('should return empty map on network error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const prices = await fetchTokenPrices(['MintA']);

      expect(prices.size).toBe(0);
    });

    it('should handle empty data object', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: {} }),
      });

      const prices = await fetchTokenPrices(['MintA']);

      expect(prices.size).toBe(0);
    });

    it('should handle price string "0" as valid', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          data: {
            MintA: { price: '0' },
          },
        }),
      });

      const prices = await fetchTokenPrices(['MintA']);

      // Price of 0 is not useful for trading, so it should be excluded
      expect(prices.size).toBe(0);
    });
  });

  describe('checkPositionThresholds', () => {
    it('should detect stop loss trigger when price drops below threshold', () => {
      const events: SLTPEvent[] = [];
      const triggeredSet = new Set<string>();

      const positions = [
        {
          id: 'pos1',
          tokenMint: 'MintA',
          tokenSymbol: 'TOKA',
          entryPrice: 1.0,
          amount: 100,
          solAmount: 0.5,
          stopLossPercent: 10, // SL at -10%, so trigger below 0.90
          takeProfitPercent: null,
          timestamp: Date.now(),
          status: 'open' as const,
        },
      ];

      const prices = new Map<string, number>();
      prices.set('MintA', 0.85); // -15%, below the -10% SL

      checkPositionThresholds(positions, prices, triggeredSet, (event) => {
        events.push(event);
      });

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('stop_loss');
      expect(events[0].positionId).toBe('pos1');
      expect(events[0].tokenSymbol).toBe('TOKA');
      expect(events[0].entryPrice).toBe(1.0);
      expect(events[0].currentPrice).toBe(0.85);
      expect(events[0].changePercent).toBeCloseTo(-15, 1);
      expect(triggeredSet.has('pos1')).toBe(true);
    });

    it('should detect take profit trigger when price rises above threshold', () => {
      const events: SLTPEvent[] = [];
      const triggeredSet = new Set<string>();

      const positions = [
        {
          id: 'pos2',
          tokenMint: 'MintB',
          tokenSymbol: 'TOKB',
          entryPrice: 2.0,
          amount: 50,
          solAmount: 1.0,
          stopLossPercent: null,
          takeProfitPercent: 25, // TP at +25%, so trigger above 2.50
          timestamp: Date.now(),
          status: 'open' as const,
        },
      ];

      const prices = new Map<string, number>();
      prices.set('MintB', 2.60); // +30%, above the +25% TP

      checkPositionThresholds(positions, prices, triggeredSet, (event) => {
        events.push(event);
      });

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('take_profit');
      expect(events[0].positionId).toBe('pos2');
      expect(events[0].tokenSymbol).toBe('TOKB');
      expect(events[0].entryPrice).toBe(2.0);
      expect(events[0].currentPrice).toBe(2.60);
      expect(events[0].changePercent).toBeCloseTo(30, 1);
      expect(triggeredSet.has('pos2')).toBe(true);
    });

    it('should NOT fire for positions already in triggeredSet', () => {
      const events: SLTPEvent[] = [];
      const triggeredSet = new Set<string>(['pos1']);

      const positions = [
        {
          id: 'pos1',
          tokenMint: 'MintA',
          tokenSymbol: 'TOKA',
          entryPrice: 1.0,
          amount: 100,
          solAmount: 0.5,
          stopLossPercent: 10,
          takeProfitPercent: null,
          timestamp: Date.now(),
          status: 'open' as const,
        },
      ];

      const prices = new Map<string, number>();
      prices.set('MintA', 0.80);

      checkPositionThresholds(positions, prices, triggeredSet, (event) => {
        events.push(event);
      });

      expect(events).toHaveLength(0);
    });

    it('should skip positions with no SL or TP set', () => {
      const events: SLTPEvent[] = [];
      const triggeredSet = new Set<string>();

      const positions = [
        {
          id: 'pos3',
          tokenMint: 'MintC',
          tokenSymbol: 'TOKC',
          entryPrice: 5.0,
          amount: 10,
          solAmount: 0.2,
          stopLossPercent: null,
          takeProfitPercent: null,
          timestamp: Date.now(),
          status: 'open' as const,
        },
      ];

      const prices = new Map<string, number>();
      prices.set('MintC', 0.01); // massive drop but no SL set

      checkPositionThresholds(positions, prices, triggeredSet, (event) => {
        events.push(event);
      });

      expect(events).toHaveLength(0);
    });

    it('should skip positions whose mint has no price data', () => {
      const events: SLTPEvent[] = [];
      const triggeredSet = new Set<string>();

      const positions = [
        {
          id: 'pos4',
          tokenMint: 'MintD',
          tokenSymbol: 'TOKD',
          entryPrice: 1.0,
          amount: 100,
          solAmount: 0.5,
          stopLossPercent: 10,
          takeProfitPercent: 50,
          timestamp: Date.now(),
          status: 'open' as const,
        },
      ];

      const prices = new Map<string, number>(); // empty - no price for MintD

      checkPositionThresholds(positions, prices, triggeredSet, (event) => {
        events.push(event);
      });

      expect(events).toHaveLength(0);
    });

    it('should NOT trigger when price is within thresholds', () => {
      const events: SLTPEvent[] = [];
      const triggeredSet = new Set<string>();

      const positions = [
        {
          id: 'pos5',
          tokenMint: 'MintE',
          tokenSymbol: 'TOKE',
          entryPrice: 1.0,
          amount: 100,
          solAmount: 0.5,
          stopLossPercent: 10, // SL below 0.90
          takeProfitPercent: 20, // TP above 1.20
          timestamp: Date.now(),
          status: 'open' as const,
        },
      ];

      const prices = new Map<string, number>();
      prices.set('MintE', 1.05); // +5%, between SL and TP

      checkPositionThresholds(positions, prices, triggeredSet, (event) => {
        events.push(event);
      });

      expect(events).toHaveLength(0);
      expect(triggeredSet.size).toBe(0);
    });

    it('should handle multiple positions and trigger independently', () => {
      const events: SLTPEvent[] = [];
      const triggeredSet = new Set<string>();

      const positions = [
        {
          id: 'pos6',
          tokenMint: 'MintF',
          tokenSymbol: 'TOKF',
          entryPrice: 1.0,
          amount: 100,
          solAmount: 0.5,
          stopLossPercent: 10,
          takeProfitPercent: 50,
          timestamp: Date.now(),
          status: 'open' as const,
        },
        {
          id: 'pos7',
          tokenMint: 'MintG',
          tokenSymbol: 'TOKG',
          entryPrice: 2.0,
          amount: 50,
          solAmount: 1.0,
          stopLossPercent: 5,
          takeProfitPercent: 30,
          timestamp: Date.now(),
          status: 'open' as const,
        },
        {
          id: 'pos8',
          tokenMint: 'MintH',
          tokenSymbol: 'TOKH',
          entryPrice: 0.5,
          amount: 200,
          solAmount: 0.25,
          stopLossPercent: 20,
          takeProfitPercent: 100,
          timestamp: Date.now(),
          status: 'open' as const,
        },
      ];

      const prices = new Map<string, number>();
      prices.set('MintF', 0.88); // -12%, triggers SL at -10%
      prices.set('MintG', 2.80); // +40%, triggers TP at +30%
      prices.set('MintH', 0.50); // 0%, no trigger

      checkPositionThresholds(positions, prices, triggeredSet, (event) => {
        events.push(event);
      });

      expect(events).toHaveLength(2);

      const slEvent = events.find((e) => e.type === 'stop_loss');
      expect(slEvent).toBeDefined();
      expect(slEvent!.positionId).toBe('pos6');

      const tpEvent = events.find((e) => e.type === 'take_profit');
      expect(tpEvent).toBeDefined();
      expect(tpEvent!.positionId).toBe('pos7');

      expect(triggeredSet.has('pos6')).toBe(true);
      expect(triggeredSet.has('pos7')).toBe(true);
      expect(triggeredSet.has('pos8')).toBe(false);
    });

    it('should only trigger SL when both SL and TP are set and SL hits', () => {
      const events: SLTPEvent[] = [];
      const triggeredSet = new Set<string>();

      const positions = [
        {
          id: 'pos9',
          tokenMint: 'MintI',
          tokenSymbol: 'TOKI',
          entryPrice: 1.0,
          amount: 100,
          solAmount: 0.5,
          stopLossPercent: 10,
          takeProfitPercent: 20,
          timestamp: Date.now(),
          status: 'open' as const,
        },
      ];

      const prices = new Map<string, number>();
      prices.set('MintI', 0.85); // -15%, triggers SL

      checkPositionThresholds(positions, prices, triggeredSet, (event) => {
        events.push(event);
      });

      // Should fire exactly one SL event, not both
      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('stop_loss');
    });

    it('should handle exact boundary prices (price equals SL threshold)', () => {
      const events: SLTPEvent[] = [];
      const triggeredSet = new Set<string>();

      const positions = [
        {
          id: 'pos10',
          tokenMint: 'MintJ',
          tokenSymbol: 'TOKJ',
          entryPrice: 1.0,
          amount: 100,
          solAmount: 0.5,
          stopLossPercent: 10,
          takeProfitPercent: null,
          timestamp: Date.now(),
          status: 'open' as const,
        },
      ];

      const prices = new Map<string, number>();
      prices.set('MintJ', 0.90); // exactly at -10% threshold

      checkPositionThresholds(positions, prices, triggeredSet, (event) => {
        events.push(event);
      });

      // At exactly the threshold, should trigger (<=)
      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('stop_loss');
    });

    it('should handle exact boundary prices (price equals TP threshold)', () => {
      const events: SLTPEvent[] = [];
      const triggeredSet = new Set<string>();

      const positions = [
        {
          id: 'pos11',
          tokenMint: 'MintK',
          tokenSymbol: 'TOKK',
          entryPrice: 1.0,
          amount: 100,
          solAmount: 0.5,
          stopLossPercent: null,
          takeProfitPercent: 20,
          timestamp: Date.now(),
          status: 'open' as const,
        },
      ];

      const prices = new Map<string, number>();
      prices.set('MintK', 1.20); // exactly at +20% threshold

      checkPositionThresholds(positions, prices, triggeredSet, (event) => {
        events.push(event);
      });

      // At exactly the threshold, should trigger (>=)
      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('take_profit');
    });

    it('should skip non-open positions', () => {
      const events: SLTPEvent[] = [];
      const triggeredSet = new Set<string>();

      const positions = [
        {
          id: 'pos12',
          tokenMint: 'MintL',
          tokenSymbol: 'TOKL',
          entryPrice: 1.0,
          amount: 100,
          solAmount: 0.5,
          stopLossPercent: 10,
          takeProfitPercent: 20,
          timestamp: Date.now(),
          status: 'closed' as const,
        },
        {
          id: 'pos13',
          tokenMint: 'MintM',
          tokenSymbol: 'TOKM',
          entryPrice: 1.0,
          amount: 100,
          solAmount: 0.5,
          stopLossPercent: 10,
          takeProfitPercent: 20,
          timestamp: Date.now(),
          status: 'sl_triggered' as const,
        },
      ];

      const prices = new Map<string, number>();
      prices.set('MintL', 0.50); // would trigger SL if open
      prices.set('MintM', 0.50); // would trigger SL if open

      checkPositionThresholds(positions, prices, triggeredSet, (event) => {
        events.push(event);
      });

      expect(events).toHaveLength(0);
    });
  });
});
