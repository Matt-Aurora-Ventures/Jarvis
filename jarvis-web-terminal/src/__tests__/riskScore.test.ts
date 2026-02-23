import { describe, it, expect } from 'vitest';
import { computeRiskScore, type RiskAssessment } from '@/lib/risk-score';

// ---------------------------------------------------------------------------
// Constants for time calculations
// ---------------------------------------------------------------------------
const ONE_HOUR = 60 * 60 * 1000;
const ONE_DAY = 24 * ONE_HOUR;
const SEVEN_DAYS = 7 * ONE_DAY;

// ---------------------------------------------------------------------------
// Helper: build default "safe" params and override selectively
// ---------------------------------------------------------------------------
function safeParams(overrides: Partial<Parameters<typeof computeRiskScore>[0]> = {}) {
  return {
    pnlPercent: 5,                // positive P&L
    holdDurationMs: 30 * 60_000,  // 30 minutes
    hasStopLoss: true,
    hasTakeProfit: true,
    positionSizeSol: 0.5,
    volatility24h: undefined,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Individual risk factor tests
// ---------------------------------------------------------------------------

describe('computeRiskScore', () => {
  describe('stop loss factor', () => {
    it('should add 30 points when no stop loss is set', () => {
      const withSL = computeRiskScore(safeParams({ hasStopLoss: true }));
      const withoutSL = computeRiskScore(safeParams({ hasStopLoss: false }));
      expect(withoutSL.score - withSL.score).toBe(30);
    });
  });

  describe('take profit factor', () => {
    it('should add 10 points when no take profit is set', () => {
      const withTP = computeRiskScore(safeParams({ hasTakeProfit: true }));
      const withoutTP = computeRiskScore(safeParams({ hasTakeProfit: false }));
      expect(withoutTP.score - withTP.score).toBe(10);
    });
  });

  describe('negative P&L factor', () => {
    it('should add 20 points when P&L is below -10%', () => {
      const above = computeRiskScore(safeParams({ pnlPercent: -5 }));
      const below = computeRiskScore(safeParams({ pnlPercent: -12 }));
      expect(below.score - above.score).toBe(20);
    });

    it('should add 10 more points (cumulative) when P&L is below -25%', () => {
      const at15 = computeRiskScore(safeParams({ pnlPercent: -15 }));
      const at30 = computeRiskScore(safeParams({ pnlPercent: -30 }));
      // -15% triggers the -10% rule (+20); -30% triggers both -10% (+20) and -25% (+10)
      expect(at30.score - at15.score).toBe(10);
    });
  });

  describe('hold duration factors', () => {
    it('should add 15 points when holding > 24h with negative P&L', () => {
      const shortHold = computeRiskScore(
        safeParams({ pnlPercent: -5, holdDurationMs: 12 * ONE_HOUR }),
      );
      const longHold = computeRiskScore(
        safeParams({ pnlPercent: -5, holdDurationMs: 25 * ONE_HOUR }),
      );
      expect(longHold.score - shortHold.score).toBe(15);
    });

    it('should NOT add 15 points when holding > 24h with positive P&L', () => {
      const shortHold = computeRiskScore(
        safeParams({ pnlPercent: 5, holdDurationMs: 12 * ONE_HOUR }),
      );
      const longHold = computeRiskScore(
        safeParams({ pnlPercent: 5, holdDurationMs: 25 * ONE_HOUR }),
      );
      expect(longHold.score - shortHold.score).toBe(0);
    });

    it('should add 10 points when holding > 7 days', () => {
      const under7d = computeRiskScore(
        safeParams({ holdDurationMs: 6 * ONE_DAY }),
      );
      const over7d = computeRiskScore(
        safeParams({ holdDurationMs: 8 * ONE_DAY }),
      );
      expect(over7d.score - under7d.score).toBe(10);
    });
  });

  describe('position size factors', () => {
    it('should add 5 points when position > 1 SOL', () => {
      const small = computeRiskScore(safeParams({ positionSizeSol: 0.8 }));
      const medium = computeRiskScore(safeParams({ positionSizeSol: 2 }));
      expect(medium.score - small.score).toBe(5);
    });

    it('should add 10 more points when position > 5 SOL (cumulative with >1 SOL)', () => {
      const at2sol = computeRiskScore(safeParams({ positionSizeSol: 2 }));
      const at6sol = computeRiskScore(safeParams({ positionSizeSol: 6 }));
      // >1 SOL already applied to both; >5 SOL adds 10 more
      expect(at6sol.score - at2sol.score).toBe(10);
    });
  });

  describe('volatility factor', () => {
    it('should add 10 points for high volatility (>20% 24h)', () => {
      const noVol = computeRiskScore(safeParams({ volatility24h: 10 }));
      const highVol = computeRiskScore(safeParams({ volatility24h: 25 }));
      expect(highVol.score - noVol.score).toBe(10);
    });

    it('should handle undefined volatility without adding points', () => {
      const result = computeRiskScore(safeParams({ volatility24h: undefined }));
      // Safe position baseline should be LOW risk
      expect(result.score).toBeLessThanOrEqual(25);
    });
  });

  // -------------------------------------------------------------------------
  // Level thresholds
  // -------------------------------------------------------------------------

  describe('risk level thresholds', () => {
    it('should classify score 0-25 as LOW', () => {
      const result = computeRiskScore(safeParams());
      expect(result.score).toBeLessThanOrEqual(25);
      expect(result.level).toBe('LOW');
    });

    it('should classify score 26-50 as MEDIUM', () => {
      // No SL (+30) with safe defaults -> ~30
      const result = computeRiskScore(safeParams({ hasStopLoss: false }));
      expect(result.score).toBeGreaterThanOrEqual(26);
      expect(result.score).toBeLessThanOrEqual(50);
      expect(result.level).toBe('MEDIUM');
    });

    it('should classify score 51-75 as HIGH', () => {
      // No SL (+30) + No TP (+10) + PNL -15% (+20) = 60
      const result = computeRiskScore(
        safeParams({
          hasStopLoss: false,
          hasTakeProfit: false,
          pnlPercent: -15,
        }),
      );
      expect(result.score).toBeGreaterThanOrEqual(51);
      expect(result.score).toBeLessThanOrEqual(75);
      expect(result.level).toBe('HIGH');
    });

    it('should classify score 76-100 as EXTREME', () => {
      // No SL (+30) + No TP (+10) + PNL -30% (+20+10) + >24h neg (+15)
      // + >7d (+10) + >5 SOL (+5+10) + high vol (+10) = 120 -> capped at 100
      const result = computeRiskScore({
        hasStopLoss: false,
        hasTakeProfit: false,
        pnlPercent: -30,
        holdDurationMs: 8 * ONE_DAY,
        positionSizeSol: 10,
        volatility24h: 50,
      });
      expect(result.score).toBeGreaterThanOrEqual(76);
      expect(result.score).toBeLessThanOrEqual(100);
      expect(result.level).toBe('EXTREME');
    });
  });

  // -------------------------------------------------------------------------
  // Factors array
  // -------------------------------------------------------------------------

  describe('risk factors descriptions', () => {
    it('should include "No stop loss set" when SL is missing', () => {
      const result = computeRiskScore(safeParams({ hasStopLoss: false }));
      expect(result.factors).toContain('No stop loss set');
    });

    it('should include "No take profit set" when TP is missing', () => {
      const result = computeRiskScore(safeParams({ hasTakeProfit: false }));
      expect(result.factors).toContain('No take profit set');
    });

    it('should include a negative P&L description when below -10%', () => {
      const result = computeRiskScore(safeParams({ pnlPercent: -15 }));
      const hasPnlFactor = result.factors.some((f) => f.includes('P&L') && f.includes('-15'));
      expect(hasPnlFactor).toBe(true);
    });

    it('should include a deep loss description when below -25%', () => {
      const result = computeRiskScore(safeParams({ pnlPercent: -30 }));
      const hasDeepLoss = result.factors.some(
        (f) => f.toLowerCase().includes('deep') || f.toLowerCase().includes('-30'),
      );
      expect(hasDeepLoss).toBe(true);
    });

    it('should include hold duration factor for stale negative positions', () => {
      const result = computeRiskScore(
        safeParams({ pnlPercent: -5, holdDurationMs: 3 * ONE_DAY }),
      );
      const hasHoldFactor = result.factors.some(
        (f) => f.toLowerCase().includes('hold') || f.toLowerCase().includes('day'),
      );
      expect(hasHoldFactor).toBe(true);
    });

    it('should have no factors for a completely safe position', () => {
      const result = computeRiskScore(safeParams());
      expect(result.factors).toHaveLength(0);
    });
  });

  // -------------------------------------------------------------------------
  // Combined scenarios
  // -------------------------------------------------------------------------

  describe('combined scenarios', () => {
    it('no SL + -15% PNL + held 3 days = HIGH risk', () => {
      const result = computeRiskScore({
        hasStopLoss: false,       // +30
        hasTakeProfit: true,
        pnlPercent: -15,          // +20
        holdDurationMs: 3 * ONE_DAY, // +15 (>24h with neg PNL)
        positionSizeSol: 0.5,
      });
      // 30 + 20 + 15 = 65 -> HIGH
      expect(result.score).toBe(65);
      expect(result.level).toBe('HIGH');
    });

    it('safe position: has SL + TP + positive PNL + held < 1h = LOW risk', () => {
      const result = computeRiskScore({
        hasStopLoss: true,
        hasTakeProfit: true,
        pnlPercent: 10,
        holdDurationMs: 30 * 60_000, // 30 minutes
        positionSizeSol: 0.3,
      });
      expect(result.score).toBe(0);
      expect(result.level).toBe('LOW');
      expect(result.factors).toHaveLength(0);
    });
  });

  // -------------------------------------------------------------------------
  // Edge cases
  // -------------------------------------------------------------------------

  describe('edge cases', () => {
    it('should cap score at 100', () => {
      const result = computeRiskScore({
        hasStopLoss: false,
        hasTakeProfit: false,
        pnlPercent: -50,
        holdDurationMs: 10 * ONE_DAY,
        positionSizeSol: 20,
        volatility24h: 80,
      });
      expect(result.score).toBe(100);
    });

    it('should not go below 0', () => {
      const result = computeRiskScore(safeParams());
      expect(result.score).toBeGreaterThanOrEqual(0);
    });
  });
});
