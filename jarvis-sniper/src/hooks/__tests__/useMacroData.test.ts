import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

/**
 * Tests for the macro data utility functions that determine market regime and BTC trend.
 * We test the pure logic (determineRegime, determineBtcTrend) separately from the hook.
 */

// Import will fail until we implement the module
import { determineRegime, determineBtcTrend, type MacroData } from '../useMacroData';

describe('determineRegime', () => {
  it('returns risk_on when BTC 24h change > +3%', () => {
    expect(determineRegime(5.2)).toBe('risk_on');
    expect(determineRegime(3.01)).toBe('risk_on');
  });

  it('returns risk_off when BTC 24h change < -3%', () => {
    expect(determineRegime(-5.0)).toBe('risk_off');
    expect(determineRegime(-3.01)).toBe('risk_off');
  });

  it('returns neutral when BTC 24h change is between -3% and +3%', () => {
    expect(determineRegime(0)).toBe('neutral');
    expect(determineRegime(2.99)).toBe('neutral');
    expect(determineRegime(-2.99)).toBe('neutral');
    expect(determineRegime(3.0)).toBe('neutral');
    expect(determineRegime(-3.0)).toBe('neutral');
  });
});

describe('determineBtcTrend', () => {
  it('returns pumping when BTC 24h change > +2%', () => {
    expect(determineBtcTrend(3.5)).toBe('pumping');
    expect(determineBtcTrend(2.01)).toBe('pumping');
  });

  it('returns dumping when BTC 24h change < -2%', () => {
    expect(determineBtcTrend(-3.5)).toBe('dumping');
    expect(determineBtcTrend(-2.01)).toBe('dumping');
  });

  it('returns flat when BTC 24h change is between -2% and +2%', () => {
    expect(determineBtcTrend(0)).toBe('flat');
    expect(determineBtcTrend(1.99)).toBe('flat');
    expect(determineBtcTrend(-1.99)).toBe('flat');
    expect(determineBtcTrend(2.0)).toBe('flat');
    expect(determineBtcTrend(-2.0)).toBe('flat');
  });
});

describe('MacroData type', () => {
  it('has the expected shape', () => {
    const data: MacroData = {
      btcPrice: 97000,
      btcChange24h: 2.5,
      solPrice: 195.5,
      solChange24h: -1.2,
      regime: 'neutral',
      btcTrend: 'pumping',
      loading: false,
    };
    expect(data.btcPrice).toBe(97000);
    expect(data.regime).toBe('neutral');
    expect(data.btcTrend).toBe('pumping');
    expect(data.loading).toBe(false);
  });
});
