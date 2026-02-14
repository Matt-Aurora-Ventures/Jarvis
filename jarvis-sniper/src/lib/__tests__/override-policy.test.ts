import { describe, expect, it } from 'vitest';
import {
  applyOverrideDecision,
  mergeRuntimeConfigWithStrategyOverride,
  normalizePatchAgainstBase,
} from '@/lib/autonomy/override-policy';
import type { SniperConfig } from '@/stores/useSniperStore';

const baseConfig: SniperConfig = {
  stopLossPct: 20,
  takeProfitPct: 80,
  trailingStopPct: 8,
  maxPositionSol: 0.1,
  maxConcurrentPositions: 5,
  minScore: 50,
  minLiquidityUsd: 10000,
  autoSnipe: true,
  autoWrGateEnabled: true,
  autoWrPrimaryPct: 70,
  autoWrFallbackPct: 50,
  autoWrMinTrades: 1000,
  autoWrMethod: 'wilson95_lower',
  autoWrScope: 'memecoin_bags',
  useJito: true,
  slippageBps: 150,
  strategyMode: 'conservative',
  maxPositionAgeHours: 4,
  useRecommendedExits: true,
  minMomentum1h: 5,
  maxTokenAgeHours: 200,
  minVolLiqRatio: 1,
  tradingHoursGate: false,
  minAgeMinutes: 2,
  circuitBreakerEnabled: true,
  maxConsecutiveLosses: 9,
  maxDailyLossSol: 0.5,
  minBalanceGuardSol: 0.05,
  perAssetBreakerConfig: {
    memecoin: { maxConsecutiveLosses: 9, maxDailyLossSol: 0.3, cooldownMinutes: 15 },
    bags: { maxConsecutiveLosses: 12, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
    bluechip: { maxConsecutiveLosses: 15, maxDailyLossSol: 1.0, cooldownMinutes: 30 },
    xstock: { maxConsecutiveLosses: 12, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
    index: { maxConsecutiveLosses: 12, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
    prestock: { maxConsecutiveLosses: 9, maxDailyLossSol: 0.3, cooldownMinutes: 15 },
  },
};

describe('autonomy override policy', () => {
  it('enforces allowlist and delta caps', () => {
    const normalized = normalizePatchAgainstBase(baseConfig, {
      stopLossPct: 40, // +20 should clamp to +5
      minScore: 90, // +40 should clamp to +15%
      unknownField: 123,
    });
    expect(normalized.patch.stopLossPct).toBe(25);
    expect(normalized.patch.minScore).toBeCloseTo(57.5, 5);
    expect(normalized.violations.some((v) => v.includes('unknownField'))).toBe(true);
  });

  it('merges active strategy patch over runtime config', () => {
    const merged = mergeRuntimeConfigWithStrategyOverride(baseConfig, 'pump_fresh_tight', {
      version: 2,
      updatedAt: new Date().toISOString(),
      cycleId: '2026021316',
      signature: 'sig',
      patches: [
        {
          strategyId: 'pump_fresh_tight',
          patch: { stopLossPct: 18, minScore: 45 },
          reason: 'test',
          confidence: 0.7,
          evidence: [],
          sourceCycleId: '2026021316',
          decidedAt: new Date().toISOString(),
        },
      ],
    });
    expect(merged.stopLossPct).toBe(18);
    expect(merged.minScore).toBe(45);
  });

  it('creates signed snapshot with incremented version', () => {
    const snapshot = applyOverrideDecision(null, {
      cycleId: '2026021317',
      patches: [],
    });
    expect(snapshot.version).toBe(1);
    expect(snapshot.signature.length).toBeGreaterThan(10);
  });
});

