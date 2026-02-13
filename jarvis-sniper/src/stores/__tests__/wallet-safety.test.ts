/**
 * Tests for Phase 2.3 — Wallet Safety, Per-Asset Circuit Breakers, Edge Case Hardening
 *
 * Covers:
 * 1. PerAssetBreakerConfig type + defaults
 * 2. Per-asset circuit breaker isolation (memecoin loss doesn't block bluechip)
 * 3. Cooldown auto-reset on per-asset breakers
 * 4. Migration handles missing fields
 * 5. makeDefaultAssetBreaker includes cooldownUntil
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  useSniperStore,
} from '../useSniperStore';
import type { BagsGraduation } from '@/lib/bags-api';

/** Helper: minimal graduation object with overrides */
function makeGrad(overrides: Partial<BagsGraduation> & Record<string, any> = {}): BagsGraduation & Record<string, any> {
  return {
    mint: 'TEST' + Math.random().toString(36).slice(2, 6),
    symbol: 'TEST',
    name: 'Test Token',
    score: 70,
    graduation_time: (Date.now() / 1000) - 600,
    bonding_curve_score: 50,
    holder_distribution_score: 50,
    liquidity_score: 50,
    social_score: 50,
    market_cap: 200000,
    price_usd: 0.001,
    liquidity: 100000,
    volume_24h: 200000,
    price_change_1h: 15,
    txn_buys_1h: 30,
    txn_sells_1h: 20,
    age_hours: 50,
    buy_sell_ratio: 1.5,
    ...overrides,
  };
}

// ──────────────────────────────────────────
// 1. PerAssetBreakerConfig defaults
// ──────────────────────────────────────────
describe('PerAssetBreakerConfig defaults', () => {
  beforeEach(() => {
    useSniperStore.getState().resetSession();
  });

  it('config has perAssetBreakerConfig with all 5 asset types', () => {
    const cfg = useSniperStore.getState().config;
    expect(cfg.perAssetBreakerConfig).toBeDefined();
    expect(cfg.perAssetBreakerConfig.memecoin).toBeDefined();
    expect(cfg.perAssetBreakerConfig.bluechip).toBeDefined();
    expect(cfg.perAssetBreakerConfig.xstock).toBeDefined();
    expect(cfg.perAssetBreakerConfig.index).toBeDefined();
    expect(cfg.perAssetBreakerConfig.prestock).toBeDefined();
  });

  it('memecoin has maxConsecutiveLosses=9, maxDailyLossSol=0.3, cooldownMinutes=15', () => {
    const cfg = useSniperStore.getState().config;
    expect(cfg.perAssetBreakerConfig.memecoin.maxConsecutiveLosses).toBe(9);
    expect(cfg.perAssetBreakerConfig.memecoin.maxDailyLossSol).toBe(0.3);
    expect(cfg.perAssetBreakerConfig.memecoin.cooldownMinutes).toBe(15);
  });

  it('bluechip has maxConsecutiveLosses=15, maxDailyLossSol=1.0, cooldownMinutes=30', () => {
    const cfg = useSniperStore.getState().config;
    expect(cfg.perAssetBreakerConfig.bluechip.maxConsecutiveLosses).toBe(15);
    expect(cfg.perAssetBreakerConfig.bluechip.maxDailyLossSol).toBe(1.0);
    expect(cfg.perAssetBreakerConfig.bluechip.cooldownMinutes).toBe(30);
  });
});

// ──────────────────────────────────────────
// 2. AssetClassBreaker includes cooldownUntil
// ──────────────────────────────────────────
describe('AssetClassBreaker cooldownUntil', () => {
  beforeEach(() => {
    useSniperStore.getState().resetSession();
  });

  it('default per-asset breakers have cooldownUntil = 0', () => {
    const cb = useSniperStore.getState().circuitBreaker;
    expect(cb.perAsset.memecoin.cooldownUntil).toBe(0);
    expect(cb.perAsset.bluechip.cooldownUntil).toBe(0);
    expect(cb.perAsset.xstock.cooldownUntil).toBe(0);
    expect(cb.perAsset.index.cooldownUntil).toBe(0);
    expect(cb.perAsset.prestock.cooldownUntil).toBe(0);
  });
});

// ──────────────────────────────────────────
// 3. Per-asset breaker isolation
// ──────────────────────────────────────────
describe('Per-asset circuit breaker isolation', () => {
  beforeEach(() => {
    useSniperStore.getState().resetSession();
    useSniperStore.setState({
      budget: { budgetSol: 10, authorized: true, spent: 0 },
      config: {
        ...useSniperStore.getState().config,
        autoSnipe: true,
        tradingHoursGate: false,
        minMomentum1h: 0,
        minLiquidityUsd: 0,
        minVolLiqRatio: 0,
        maxTokenAgeHours: 9999,
        minAgeMinutes: 0,
        circuitBreakerEnabled: true,
        maxConsecutiveLosses: 10, // high global limit so it doesn't trip
        maxDailyLossSol: 100,
        perAssetBreakerConfig: {
          memecoin:  { maxConsecutiveLosses: 2, maxDailyLossSol: 0.3, cooldownMinutes: 15 },
          bags:      { maxConsecutiveLosses: 4, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
          bluechip:  { maxConsecutiveLosses: 5, maxDailyLossSol: 1.0, cooldownMinutes: 30 },
          xstock:    { maxConsecutiveLosses: 4, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
          index:     { maxConsecutiveLosses: 4, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
          prestock:  { maxConsecutiveLosses: 3, maxDailyLossSol: 0.3, cooldownMinutes: 15 },
        },
      },
    });
  });

  it('tripping memecoin breaker does not trip bluechip breaker', () => {
    // Simulate 2 consecutive memecoin losses
    const store = useSniperStore.getState();
    // Add two memecoin positions and close them as losses
    const pos1 = {
      id: 'pos-mc-1', mint: 'MC1', symbol: 'MC1', name: 'Meme1',
      entryPrice: 0.001, currentPrice: 0.0005, amount: 1000,
      solInvested: 0.1, pnlPercent: -50, pnlSol: -0.05,
      entryTime: Date.now(), status: 'open' as const, score: 50,
      recommendedSl: 20, recommendedTp: 80, highWaterMarkPct: 0,
      assetType: 'memecoin' as const,
    };
    const pos2 = { ...pos1, id: 'pos-mc-2', mint: 'MC2', symbol: 'MC2' };

    useSniperStore.setState((s) => ({
      positions: [pos1, pos2, ...s.positions],
      assetFilter: 'memecoin' as const,
    }));

    // Close both as losses
    useSniperStore.getState().closePosition('pos-mc-1', 'sl_hit', undefined, 0.05);
    useSniperStore.getState().closePosition('pos-mc-2', 'sl_hit', undefined, 0.05);

    const cb = useSniperStore.getState().circuitBreaker;
    // Memecoin breaker should be tripped (2 consecutive losses >= limit of 2)
    expect(cb.perAsset.memecoin.tripped).toBe(true);
    // Bluechip breaker should NOT be tripped
    expect(cb.perAsset.bluechip.tripped).toBe(false);
    // Global breaker should NOT be tripped (global limit is 10)
    expect(cb.tripped).toBe(false);
  });

  it('per-asset breaker uses per-asset config limits, not global', () => {
    // Set up: memecoin per-asset limit is 2, global is 10
    // Add and close 2 memecoin losses
    const pos1 = {
      id: 'pos-pa-1', mint: 'PA1', symbol: 'PA1', name: 'PerAsset1',
      entryPrice: 0.001, currentPrice: 0.0005, amount: 1000,
      solInvested: 0.1, pnlPercent: -50, pnlSol: -0.05,
      entryTime: Date.now(), status: 'open' as const, score: 50,
      recommendedSl: 20, recommendedTp: 80, highWaterMarkPct: 0,
      assetType: 'memecoin' as const,
    };
    const pos2 = { ...pos1, id: 'pos-pa-2', mint: 'PA2', symbol: 'PA2' };

    useSniperStore.setState((s) => ({
      positions: [pos1, pos2, ...s.positions],
      assetFilter: 'memecoin' as const,
    }));

    useSniperStore.getState().closePosition('pos-pa-1', 'sl_hit', undefined, 0.05);
    useSniperStore.getState().closePosition('pos-pa-2', 'sl_hit', undefined, 0.05);

    // Should trip per-asset (limit 2), not global (limit 10)
    const cb = useSniperStore.getState().circuitBreaker;
    expect(cb.perAsset.memecoin.tripped).toBe(true);
    expect(cb.perAsset.memecoin.cooldownUntil).toBeGreaterThan(0);
    expect(cb.tripped).toBe(false);
  });

  it('sets cooldownUntil when per-asset breaker trips', () => {
    const pos1 = {
      id: 'pos-cd-1', mint: 'CD1', symbol: 'CD1', name: 'Cooldown1',
      entryPrice: 0.001, currentPrice: 0.0005, amount: 1000,
      solInvested: 0.1, pnlPercent: -50, pnlSol: -0.05,
      entryTime: Date.now(), status: 'open' as const, score: 50,
      recommendedSl: 20, recommendedTp: 80, highWaterMarkPct: 0,
      assetType: 'memecoin' as const,
    };
    const pos2 = { ...pos1, id: 'pos-cd-2', mint: 'CD2', symbol: 'CD2' };

    useSniperStore.setState((s) => ({
      positions: [pos1, pos2, ...s.positions],
      assetFilter: 'memecoin' as const,
    }));

    useSniperStore.getState().closePosition('pos-cd-1', 'sl_hit', undefined, 0.05);
    useSniperStore.getState().closePosition('pos-cd-2', 'sl_hit', undefined, 0.05);

    const cb = useSniperStore.getState().circuitBreaker;
    // cooldownMinutes for memecoin is 15 = 900_000 ms
    expect(cb.perAsset.memecoin.cooldownUntil).toBeGreaterThan(Date.now());
    const expectedMs = 15 * 60_000;
    // Allow 2 seconds tolerance for test execution time
    expect(cb.perAsset.memecoin.cooldownUntil).toBeLessThanOrEqual(Date.now() + expectedMs + 2000);
  });
});

// ──────────────────────────────────────────
// 4. Cooldown auto-reset in snipeToken guard
// ──────────────────────────────────────────
describe('Per-asset cooldown auto-reset', () => {
  beforeEach(() => {
    useSniperStore.getState().resetSession();
    useSniperStore.setState({
      budget: { budgetSol: 10, authorized: true, spent: 0 },
      config: {
        ...useSniperStore.getState().config,
        autoSnipe: true,
        tradingHoursGate: false,
        minMomentum1h: 0,
        minLiquidityUsd: 0,
        minVolLiqRatio: 0,
        maxTokenAgeHours: 9999,
        minAgeMinutes: 0,
        circuitBreakerEnabled: true,
        maxConsecutiveLosses: 10,
        maxDailyLossSol: 100,
        perAssetBreakerConfig: {
          memecoin:  { maxConsecutiveLosses: 2, maxDailyLossSol: 0.3, cooldownMinutes: 15 },
          bags:      { maxConsecutiveLosses: 4, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
          bluechip:  { maxConsecutiveLosses: 5, maxDailyLossSol: 1.0, cooldownMinutes: 30 },
          xstock:    { maxConsecutiveLosses: 4, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
          index:     { maxConsecutiveLosses: 4, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
          prestock:  { maxConsecutiveLosses: 3, maxDailyLossSol: 0.3, cooldownMinutes: 15 },
        },
      },
      assetFilter: 'memecoin' as const,
    });
  });

  it('blocks snipe when per-asset breaker is tripped and cooldown not expired', () => {
    // Manually trip the memecoin breaker with a future cooldown
    useSniperStore.setState((s) => ({
      circuitBreaker: {
        ...s.circuitBreaker,
        perAsset: {
          ...s.circuitBreaker.perAsset,
          memecoin: {
            ...s.circuitBreaker.perAsset.memecoin,
            tripped: true,
            reason: 'test trip',
            trippedAt: Date.now(),
            consecutiveLosses: 2,
            cooldownUntil: Date.now() + 600_000, // 10 minutes from now
          },
        },
      },
    }));

    const grad = makeGrad();
    useSniperStore.getState().snipeToken(grad);
    expect(useSniperStore.getState().positions.length).toBe(0);
  });

  it('auto-resets breaker and allows snipe after cooldown expires', () => {
    // Trip the memecoin breaker with a PAST cooldown (already expired)
    useSniperStore.setState((s) => ({
      circuitBreaker: {
        ...s.circuitBreaker,
        perAsset: {
          ...s.circuitBreaker.perAsset,
          memecoin: {
            ...s.circuitBreaker.perAsset.memecoin,
            tripped: true,
            reason: 'test trip',
            trippedAt: Date.now() - 1_000_000,
            consecutiveLosses: 2,
            dailyLossSol: 0.1,
            dailyResetAt: Date.now() + 86_400_000,
            cooldownUntil: Date.now() - 1000, // expired 1 second ago
          },
        },
      },
    }));

    const grad = makeGrad();
    useSniperStore.getState().snipeToken(grad);

    // Should have created a position (cooldown expired, breaker auto-reset)
    expect(useSniperStore.getState().positions.length).toBe(1);

    // Breaker should be reset
    const cb = useSniperStore.getState().circuitBreaker;
    expect(cb.perAsset.memecoin.tripped).toBe(false);
    expect(cb.perAsset.memecoin.consecutiveLosses).toBe(0);
    // Daily loss should be preserved
    expect(cb.perAsset.memecoin.dailyLossSol).toBe(0.1);
  });
});

// ──────────────────────────────────────────
// 5. Win resets consecutive loss counter
// ──────────────────────────────────────────
describe('Win resets per-asset consecutive losses', () => {
  beforeEach(() => {
    useSniperStore.getState().resetSession();
    useSniperStore.setState({
      budget: { budgetSol: 10, authorized: true, spent: 0 },
      config: {
        ...useSniperStore.getState().config,
        circuitBreakerEnabled: true,
        maxConsecutiveLosses: 10,
        maxDailyLossSol: 100,
        perAssetBreakerConfig: {
          memecoin:  { maxConsecutiveLosses: 5, maxDailyLossSol: 1.0, cooldownMinutes: 15 },
          bags:      { maxConsecutiveLosses: 4, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
          bluechip:  { maxConsecutiveLosses: 5, maxDailyLossSol: 1.0, cooldownMinutes: 30 },
          xstock:    { maxConsecutiveLosses: 4, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
          index:     { maxConsecutiveLosses: 4, maxDailyLossSol: 0.5, cooldownMinutes: 20 },
          prestock:  { maxConsecutiveLosses: 3, maxDailyLossSol: 0.3, cooldownMinutes: 15 },
        },
      },
      assetFilter: 'memecoin' as const,
    });
  });

  it('winning trade resets consecutiveLosses to 0', () => {
    // Add a loss position then a win position
    const lossPos = {
      id: 'pos-loss', mint: 'LOSS1', symbol: 'LOSS1', name: 'LossToken',
      entryPrice: 0.001, currentPrice: 0.0005, amount: 1000,
      solInvested: 0.1, pnlPercent: -50, pnlSol: -0.05,
      entryTime: Date.now(), status: 'open' as const, score: 50,
      recommendedSl: 20, recommendedTp: 80, highWaterMarkPct: 0,
      assetType: 'memecoin' as const,
    };
    const winPos = {
      id: 'pos-win', mint: 'WIN1', symbol: 'WIN1', name: 'WinToken',
      entryPrice: 0.001, currentPrice: 0.002, amount: 1000,
      solInvested: 0.1, pnlPercent: 100, pnlSol: 0.1,
      entryTime: Date.now(), status: 'open' as const, score: 50,
      recommendedSl: 20, recommendedTp: 80, highWaterMarkPct: 100,
      assetType: 'memecoin' as const,
    };

    useSniperStore.setState((s) => ({
      positions: [lossPos, winPos, ...s.positions],
    }));

    // Close loss first
    useSniperStore.getState().closePosition('pos-loss', 'sl_hit', undefined, 0.05);
    expect(useSniperStore.getState().circuitBreaker.perAsset.memecoin.consecutiveLosses).toBe(1);

    // Close win second
    useSniperStore.getState().closePosition('pos-win', 'tp_hit', undefined, 0.2);
    expect(useSniperStore.getState().circuitBreaker.perAsset.memecoin.consecutiveLosses).toBe(0);
  });
});
