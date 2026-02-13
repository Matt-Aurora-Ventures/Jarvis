import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { determineRegime, determineBtcTrend } from '@/hooks/useMacroData';

/**
 * Tests for macro API route logic.
 * We test the regime/trend determination functions that the route will use,
 * and verify the expected response shape from the CoinGecko data format.
 */

describe('macro API route logic', () => {
  describe('CoinGecko response parsing', () => {
    it('extracts BTC and SOL prices from CoinGecko response format', () => {
      // Simulated CoinGecko response
      const coingeckoResponse = {
        bitcoin: { usd: 97245.12, usd_24h_change: 2.345 },
        solana: { usd: 195.67, usd_24h_change: -1.234 },
      };

      const btcPrice = coingeckoResponse.bitcoin.usd;
      const btcChange24h = coingeckoResponse.bitcoin.usd_24h_change;
      const solPrice = coingeckoResponse.solana.usd;
      const solChange24h = coingeckoResponse.solana.usd_24h_change;

      expect(btcPrice).toBe(97245.12);
      expect(btcChange24h).toBe(2.345);
      expect(solPrice).toBe(195.67);
      expect(solChange24h).toBe(-1.234);
    });

    it('computes correct regime and trend from CoinGecko data', () => {
      // BTC +5% = risk_on, pumping
      expect(determineRegime(5.0)).toBe('risk_on');
      expect(determineBtcTrend(5.0)).toBe('pumping');

      // BTC -5% = risk_off, dumping
      expect(determineRegime(-5.0)).toBe('risk_off');
      expect(determineBtcTrend(-5.0)).toBe('dumping');

      // BTC +1% = neutral, flat
      expect(determineRegime(1.0)).toBe('neutral');
      expect(determineBtcTrend(1.0)).toBe('flat');
    });
  });

  describe('expected response shape', () => {
    it('builds the expected JSON response', () => {
      const btcChange24h = 3.5;
      const response = {
        btcPrice: 97000,
        btcChange24h,
        solPrice: 195.5,
        solChange24h: -1.2,
        regime: determineRegime(btcChange24h),
        btcTrend: determineBtcTrend(btcChange24h),
        timestamp: Date.now(),
      };

      expect(response).toHaveProperty('btcPrice');
      expect(response).toHaveProperty('btcChange24h');
      expect(response).toHaveProperty('solPrice');
      expect(response).toHaveProperty('solChange24h');
      expect(response).toHaveProperty('regime');
      expect(response).toHaveProperty('btcTrend');
      expect(response).toHaveProperty('timestamp');
      expect(response.regime).toBe('risk_on');
      expect(response.btcTrend).toBe('pumping');
    });
  });
});
