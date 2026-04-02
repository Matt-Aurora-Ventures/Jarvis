import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock axios before imports
vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
  },
}));

// Mock fs
vi.mock('fs', () => ({
  default: {
    existsSync: vi.fn().mockReturnValue(false),
    readFileSync: vi.fn(),
    writeFileSync: vi.fn(),
    mkdirSync: vi.fn(),
  },
}));

// Mock logger
vi.mock('../utils/logger.js', () => ({
  createModuleLogger: () => ({
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  }),
}));

import axios from 'axios';
import fs from 'fs';
import {
  getMacroSnapshot,
  getCorrelationAdjustment,
  estimateBtcCorrelation,
  type MacroSnapshot,
} from '../analysis/macro-correlator.js';

const mockedAxios = vi.mocked(axios, { deep: true });
const mockedFs = vi.mocked(fs);

// ─── Helper: Build a MacroSnapshot ──────────────────────────

function buildSnapshot(overrides: Partial<MacroSnapshot> = {}): MacroSnapshot {
  return {
    btc: { price: 100000, change24h: 0, change7d: 0 },
    eth: { price: 3500, change24h: 0 },
    sol: { price: 200, change24h: 0 },
    dxy: null,
    gold: null,
    regime: 'neutral',
    btcTrend: 'flat',
    memeExposureMultiplier: 1.0,
    fetchedAt: Date.now(),
    ...overrides,
  };
}

// ─── Tests: computeRegime (via getMacroSnapshot) ─────────────

describe('Macro Correlator', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: no cache
    mockedFs.existsSync.mockReturnValue(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ─── getMacroSnapshot ────────────────────────────────────

  describe('getMacroSnapshot', () => {
    it('should return a complete MacroSnapshot object', async () => {
      mockedAxios.get.mockResolvedValue({
        data: {
          bitcoin: { usd: 100000, usd_24h_change: 2.5 },
          ethereum: { usd: 3500, usd_24h_change: 1.2 },
          solana: { usd: 200, usd_24h_change: 3.1 },
        },
      });

      const snap = await getMacroSnapshot();

      expect(snap).toHaveProperty('btc');
      expect(snap).toHaveProperty('eth');
      expect(snap).toHaveProperty('sol');
      expect(snap).toHaveProperty('dxy');
      expect(snap).toHaveProperty('gold');
      expect(snap).toHaveProperty('regime');
      expect(snap).toHaveProperty('btcTrend');
      expect(snap).toHaveProperty('memeExposureMultiplier');
      expect(snap).toHaveProperty('fetchedAt');
    });

    it('should parse BTC price and change correctly', async () => {
      mockedAxios.get.mockResolvedValue({
        data: {
          bitcoin: { usd: 95000, usd_24h_change: -4.2 },
          ethereum: { usd: 3200, usd_24h_change: -2.1 },
          solana: { usd: 180, usd_24h_change: -5.0 },
        },
      });

      const snap = await getMacroSnapshot();

      expect(snap.btc.price).toBe(95000);
      expect(snap.btc.change24h).toBe(-4.2);
      expect(snap.eth.price).toBe(3200);
      expect(snap.sol.price).toBe(180);
    });

    it('should compute risk_on regime when BTC pumping strongly', async () => {
      mockedAxios.get.mockResolvedValue({
        data: {
          bitcoin: { usd: 105000, usd_24h_change: 5.0 },
          ethereum: { usd: 3800, usd_24h_change: 4.0 },
          solana: { usd: 220, usd_24h_change: 6.0 },
        },
      });

      const snap = await getMacroSnapshot();

      expect(snap.regime).toBe('risk_on');
      expect(snap.btcTrend).toBe('pumping');
    });

    it('should compute risk_off regime when BTC dumping', async () => {
      mockedAxios.get.mockResolvedValue({
        data: {
          bitcoin: { usd: 88000, usd_24h_change: -5.0 },
          ethereum: { usd: 2900, usd_24h_change: -6.0 },
          solana: { usd: 160, usd_24h_change: -8.0 },
        },
      });

      const snap = await getMacroSnapshot();

      expect(snap.regime).toBe('risk_off');
      expect(snap.btcTrend).toBe('dumping');
    });

    it('should compute neutral regime with mixed signals', async () => {
      mockedAxios.get.mockResolvedValue({
        data: {
          bitcoin: { usd: 100000, usd_24h_change: 0.5 },
          ethereum: { usd: 3500, usd_24h_change: -0.3 },
          solana: { usd: 200, usd_24h_change: 1.0 },
        },
      });

      const snap = await getMacroSnapshot();

      expect(snap.regime).toBe('neutral');
      expect(snap.btcTrend).toBe('flat');
    });

    it('should use cache when available and fresh', async () => {
      const cached: MacroSnapshot = buildSnapshot({
        fetchedAt: Date.now() - 60_000, // 1 minute ago (within 3 min TTL)
      });
      mockedFs.existsSync.mockReturnValue(true);
      mockedFs.readFileSync.mockReturnValue(JSON.stringify(cached));

      const snap = await getMacroSnapshot();

      // Should NOT have called axios since cache is fresh
      expect(mockedAxios.get).not.toHaveBeenCalled();
      expect(snap.regime).toBe('neutral');
    });

    it('should bypass stale cache', async () => {
      const stale: MacroSnapshot = buildSnapshot({
        fetchedAt: Date.now() - 5 * 60_000, // 5 minutes ago (past 3 min TTL)
      });
      mockedFs.existsSync.mockReturnValue(true);
      mockedFs.readFileSync.mockReturnValue(JSON.stringify(stale));

      // Mock fresh API data
      mockedAxios.get.mockResolvedValue({
        data: {
          bitcoin: { usd: 100000, usd_24h_change: 1.0 },
          ethereum: { usd: 3500, usd_24h_change: 0.5 },
          solana: { usd: 200, usd_24h_change: 1.2 },
        },
      });

      const snap = await getMacroSnapshot();

      // Should have fetched fresh data
      expect(mockedAxios.get).toHaveBeenCalled();
      expect(snap.btc.price).toBe(100000);
    });

    it('should handle CoinGecko failure gracefully', async () => {
      mockedAxios.get.mockRejectedValue(new Error('Network error'));

      const snap = await getMacroSnapshot();

      // Should return zero prices but not throw
      expect(snap.btc.price).toBe(0);
      expect(snap.eth.price).toBe(0);
      expect(snap.sol.price).toBe(0);
    });

    it('should write cache after successful fetch', async () => {
      mockedAxios.get.mockResolvedValue({
        data: {
          bitcoin: { usd: 100000, usd_24h_change: 1.0 },
          ethereum: { usd: 3500, usd_24h_change: 0.5 },
          solana: { usd: 200, usd_24h_change: 1.0 },
        },
      });

      await getMacroSnapshot();

      expect(mockedFs.writeFileSync).toHaveBeenCalled();
    });
  });

  // ─── Meme Exposure Multiplier ────────────────────────────

  describe('memeExposureMultiplier', () => {
    it('should be 0.3x when risk_off and BTC down hard', async () => {
      mockedAxios.get.mockResolvedValue({
        data: {
          bitcoin: { usd: 85000, usd_24h_change: -7.0 },
          ethereum: { usd: 2800, usd_24h_change: -8.0 },
          solana: { usd: 140, usd_24h_change: -10.0 },
        },
      });

      const snap = await getMacroSnapshot();

      expect(snap.memeExposureMultiplier).toBe(0.3);
    });

    it('should be 0.5x when risk_off but moderate dump', async () => {
      mockedAxios.get.mockResolvedValue({
        data: {
          bitcoin: { usd: 95000, usd_24h_change: -4.0 },
          ethereum: { usd: 3200, usd_24h_change: -3.0 },
          solana: { usd: 185, usd_24h_change: -5.0 },
        },
      });

      const snap = await getMacroSnapshot();

      expect(snap.memeExposureMultiplier).toBe(0.5);
    });

    it('should be 1.3x when risk_on and BTC pumping hard', async () => {
      mockedAxios.get.mockResolvedValue({
        data: {
          bitcoin: { usd: 110000, usd_24h_change: 7.0 },
          ethereum: { usd: 4000, usd_24h_change: 5.0 },
          solana: { usd: 240, usd_24h_change: 8.0 },
        },
      });

      const snap = await getMacroSnapshot();

      expect(snap.memeExposureMultiplier).toBe(1.3);
    });

    it('should be 1.1x when risk_on with moderate pump', async () => {
      mockedAxios.get.mockResolvedValue({
        data: {
          bitcoin: { usd: 103000, usd_24h_change: 4.0 },
          ethereum: { usd: 3600, usd_24h_change: 3.0 },
          solana: { usd: 210, usd_24h_change: 4.5 },
        },
      });

      const snap = await getMacroSnapshot();

      expect(snap.memeExposureMultiplier).toBe(1.1);
    });

    it('should be 1.0x when neutral', async () => {
      mockedAxios.get.mockResolvedValue({
        data: {
          bitcoin: { usd: 100000, usd_24h_change: 0.5 },
          ethereum: { usd: 3500, usd_24h_change: 0.2 },
          solana: { usd: 200, usd_24h_change: 0.8 },
        },
      });

      const snap = await getMacroSnapshot();

      expect(snap.memeExposureMultiplier).toBe(1.0);
    });
  });

  // ─── getCorrelationAdjustment ────────────────────────────

  describe('getCorrelationAdjustment', () => {
    it('should penalize fresh tokens during BTC dump', () => {
      const macro = buildSnapshot({
        btcTrend: 'dumping',
        btc: { price: 88000, change24h: -5.0, change7d: -8.0 },
        regime: 'risk_off',
      });

      const adj = getCorrelationAdjustment(macro, 'fresh', false);

      // Should be significantly negative
      expect(adj).toBeLessThan(-0.15);
    });

    it('should penalize young tokens less than fresh during dump', () => {
      const macro = buildSnapshot({
        btcTrend: 'dumping',
        btc: { price: 90000, change24h: -4.0, change7d: -6.0 },
        regime: 'risk_off',
      });

      const adjFresh = getCorrelationAdjustment(macro, 'fresh', false);
      const adjYoung = getCorrelationAdjustment(macro, 'young', false);

      expect(adjFresh).toBeLessThan(adjYoung);
    });

    it('should give xStocks partial insulation during dump', () => {
      const macro = buildSnapshot({
        btcTrend: 'dumping',
        btc: { price: 90000, change24h: -4.0, change7d: -6.0 },
        regime: 'risk_off',
      });

      const adjRegular = getCorrelationAdjustment(macro, 'established', false);
      const adjXStock = getCorrelationAdjustment(macro, 'established', true);

      // xStock should have less negative adjustment
      expect(adjXStock).toBeGreaterThan(adjRegular);
    });

    it('should give bonus to fresh tokens when BTC pumps', () => {
      const macro = buildSnapshot({
        btcTrend: 'pumping',
        btc: { price: 105000, change24h: 5.0, change7d: 8.0 },
        regime: 'risk_on',
      });

      const adj = getCorrelationAdjustment(macro, 'fresh', false);

      expect(adj).toBeGreaterThan(0);
    });

    it('should penalize with strong DXY (strong dollar)', () => {
      const macro = buildSnapshot({
        btcTrend: 'flat',
        regime: 'neutral',
        dxy: { value: 105, change24h: 0.8 },
      });

      const adj = getCorrelationAdjustment(macro, 'established', false);

      expect(adj).toBeLessThan(0);
    });

    it('should give slight boost with weak DXY', () => {
      const macro = buildSnapshot({
        btcTrend: 'flat',
        regime: 'neutral',
        dxy: { value: 99, change24h: -0.7 },
      });

      const adj = getCorrelationAdjustment(macro, 'established', false);

      expect(adj).toBeGreaterThan(0);
    });

    it('should penalize when gold surges (flight to safety)', () => {
      const macro = buildSnapshot({
        btcTrend: 'flat',
        regime: 'neutral',
        gold: { price: 2800, change24h: 3.0 },
      });

      const adj = getCorrelationAdjustment(macro, 'established', false);

      expect(adj).toBeLessThan(0);
    });

    it('should clamp adjustment to [-0.30, +0.30]', () => {
      // Create extreme conditions
      const macro = buildSnapshot({
        btcTrend: 'dumping',
        btc: { price: 70000, change24h: -15.0, change7d: -25.0 },
        regime: 'risk_off',
        dxy: { value: 110, change24h: 2.0 },
        gold: { price: 3000, change24h: 5.0 },
      });

      const adj = getCorrelationAdjustment(macro, 'fresh', false);

      expect(adj).toBeGreaterThanOrEqual(-0.30);
      expect(adj).toBeLessThanOrEqual(0.30);
    });

    it('should return zero or near-zero for neutral conditions', () => {
      const macro = buildSnapshot({
        btcTrend: 'flat',
        regime: 'neutral',
        dxy: null,
        gold: null,
      });

      const adj = getCorrelationAdjustment(macro, 'established', false);

      expect(Math.abs(adj)).toBeLessThanOrEqual(0.05);
    });
  });

  // ─── estimateBtcCorrelation ──────────────────────────────

  describe('estimateBtcCorrelation', () => {
    it('should return positive correlation when both move up', () => {
      const corr = estimateBtcCorrelation(10.0, 5.0);

      expect(corr).toBeGreaterThan(0);
      expect(corr).toBeLessThanOrEqual(1);
    });

    it('should return positive correlation when both move down', () => {
      const corr = estimateBtcCorrelation(-8.0, -4.0);

      expect(corr).toBeGreaterThan(0);
      expect(corr).toBeLessThanOrEqual(1);
    });

    it('should return negative correlation when moving opposite', () => {
      const corr = estimateBtcCorrelation(10.0, -5.0);

      expect(corr).toBeLessThan(0);
      expect(corr).toBeGreaterThanOrEqual(-1);
    });

    it('should return 0 when BTC is flat', () => {
      const corr = estimateBtcCorrelation(5.0, 0.2);

      expect(corr).toBe(0);
    });

    it('should scale with magnitude ratio', () => {
      // Token moves same as BTC -> higher correlation
      const corrSame = estimateBtcCorrelation(5.0, 5.0);
      // Token moves less than BTC -> lower correlation
      const corrLess = estimateBtcCorrelation(2.0, 5.0);

      expect(corrSame).toBeGreaterThan(corrLess);
    });

    it('should cap correlation magnitude at 0.8', () => {
      // Even with huge token move, cap at 0.8
      const corr = estimateBtcCorrelation(50.0, 5.0);

      expect(Math.abs(corr)).toBeLessThanOrEqual(0.8);
    });
  });
});
