import { describe, expect, it } from 'vitest';
import {
  calibrateWrFamilyThresholds,
  strategyFamilyFromId,
  type CalibrationRow,
} from '@/lib/wr-family-calibration';

const SAMPLE_ROWS: CalibrationRow[] = [
  { strategyId: 'bags_momentum', trades: 420, winRatePct: 54.2 },
  { strategyId: 'bags_value', trades: 360, winRatePct: 50.1 },
  { strategyId: 'bluechip_trend_follow', trades: 520, winRatePct: 47.4 },
  { strategyId: 'bluechip_breakout', trades: 480, winRatePct: 45.8 },
  { strategyId: 'pump_fresh_tight', trades: 610, winRatePct: 57.6 },
];

describe('wr-family calibration', () => {
  it('maps strategy IDs to expected families', () => {
    expect(strategyFamilyFromId('bags_momentum')).toBe('bags');
    expect(strategyFamilyFromId('bluechip_trend_follow')).toBe('bluechip');
    expect(strategyFamilyFromId('xstock_intraday')).toBe('xstock');
    expect(strategyFamilyFromId('index_leveraged')).toBe('index');
    expect(strategyFamilyFromId('pump_fresh_tight')).toBe('memecoin');
  });

  it('produces per-family threshold recommendations from weighted WR data', () => {
    const out = calibrateWrFamilyThresholds(SAMPLE_ROWS, { minFamilyTrades: 300 });
    expect(out.bags).toBeDefined();
    expect(out.bluechip).toBeDefined();
    expect(out.memecoin).toBeDefined();
    expect(out.bags?.primaryPct).toBeGreaterThanOrEqual(40);
    expect(out.bags?.primaryPct).toBeLessThanOrEqual(70);
    expect(out.bags?.fallbackPct).toBeLessThanOrEqual(out.bags?.primaryPct || 100);
    expect(out.bags?.minTrades).toBeGreaterThanOrEqual(40);
  });

  it('does not recommend thresholds for families below minimum data volume', () => {
    const out = calibrateWrFamilyThresholds(
      [{ strategyId: 'index_intraday', trades: 30, winRatePct: 75 }],
      { minFamilyTrades: 200 },
    );
    expect(out.index).toBeUndefined();
  });
});
