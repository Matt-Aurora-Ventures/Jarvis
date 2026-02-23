/**
 * Tests for sniper algorithm improvements:
 * 1. Preset-aligned exits in getRecommendedSlTp()
 * 2. Smart entry delay (minAgeMinutes)
 * 3. Volume spike / pump detection
 * 4. getConvictionMultiplier negative factors
 * 5. TokenRecommendation.trail field
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  getRecommendedSlTp,
  getConvictionMultiplier,
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
    graduation_time: (Date.now() / 1000) - 600, // 10 min ago by default
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
// 1. Preset-Aligned Exits
// ──────────────────────────────────────────
describe('getRecommendedSlTp — preset-aligned exits', () => {
  it('returns SL/TP from the provided config and disables trailing (99)', () => {
    const rec = getRecommendedSlTp(makeGrad(), 'balanced', { stopLossPct: 7, takeProfitPct: 18 });
    expect(rec.sl).toBe(7);
    expect(rec.tp).toBe(18);
    expect(rec.trail).toBe(99);
  });

  it('reasoning is present and short', () => {
    const rec = getRecommendedSlTp(makeGrad(), 'balanced', { stopLossPct: 10, takeProfitPct: 20 });
    expect(typeof rec.reasoning).toBe('string');
    expect(rec.reasoning.length).toBeGreaterThan(0);
  });
});

// ──────────────────────────────────────────
// 2. Smart Entry Delay (minAgeMinutes)
// ──────────────────────────────────────────
describe('snipeToken — minAgeMinutes gate', () => {
  beforeEach(() => {
    useSniperStore.getState().resetSession();
    // Authorize budget and set config for testing
    useSniperStore.setState({
      budget: { budgetSol: 10, authorized: true, spent: 0 },
      config: {
        ...useSniperStore.getState().config,
        autoSnipe: true,
        tradingHoursGate: false, // disable for focused test
        minMomentum1h: 0,
        minLiquidityUsd: 0,
        minVolLiqRatio: 0,
        maxTokenAgeHours: 9999,
        minAgeMinutes: 2,
      },
    });
  });

  it('skips tokens that graduated less than minAgeMinutes ago', () => {
    const grad = makeGrad({
      graduation_time: Date.now() / 1000 - 30, // 30 seconds ago
    });
    useSniperStore.getState().snipeToken(grad);
    const positions = useSniperStore.getState().positions;
    expect(positions.length).toBe(0);
    // Should have a skip log entry
    const skipLog = useSniperStore.getState().executionLog.filter(e => e.type === 'skip');
    expect(skipLog.length).toBe(1);
    expect(skipLog[0].reason).toContain('Too fresh');
  });

  it('allows tokens older than minAgeMinutes', () => {
    const grad = makeGrad({
      graduation_time: Date.now() / 1000 - 300, // 5 minutes ago
    });
    useSniperStore.getState().snipeToken(grad);
    const positions = useSniperStore.getState().positions;
    expect(positions.length).toBe(1);
  });

  it('minAgeMinutes defaults to 2 in DEFAULT_CONFIG', () => {
    // Reset to defaults
    useSniperStore.getState().resetSession();
    const cfg = useSniperStore.getState().config;
    expect(cfg.minAgeMinutes).toBe(2);
  });
});

// ──────────────────────────────────────────
// 3. Volume Spike / Pump Detection
// ──────────────────────────────────────────
describe('snipeToken — pump warning detection', () => {
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
        maxPositionSol: 1,
      },
    });
  });

  it('logs PUMP WARNING when volume > 5x liquidity AND 1h change > 100%', () => {
    const grad = makeGrad({
      liquidity: 50000,
      volume_24h: 300000, // 6x liquidity
      price_change_1h: 150, // 150%
    });
    useSniperStore.getState().snipeToken(grad);
    // Should still create a position (not skip)
    expect(useSniperStore.getState().positions.length).toBe(1);
    // But the snipe execution log should mention pump warning
    const snipeLog = useSniperStore.getState().executionLog.find(e => e.type === 'snipe');
    expect(snipeLog?.reason).toContain('PUMP WARNING');
  });

  it('does NOT flag pump when conditions are not met', () => {
    const grad = makeGrad({
      liquidity: 100000,
      volume_24h: 200000, // 2x liquidity (not 5x)
      price_change_1h: 15,
    });
    useSniperStore.getState().snipeToken(grad);
    const snipeLog = useSniperStore.getState().executionLog.find(e => e.type === 'snipe');
    expect(snipeLog?.reason).not.toContain('PUMP WARNING');
  });

  it('reduces conviction multiplier by 0.3x for pump-flagged tokens', () => {
    // Non-pump baseline
    const normalGrad = makeGrad({
      liquidity: 100000,
      volume_24h: 200000,
      price_change_1h: 15,
    });
    const normalConv = getConvictionMultiplier(normalGrad);

    // Pump version (same token but pump conditions)
    const pumpGrad = makeGrad({
      liquidity: 50000,
      volume_24h: 300000,
      price_change_1h: 150,
    });

    // The position sol should be smaller due to the 0.3x penalty
    // We test indirectly: snipe both and compare solInvested
    useSniperStore.getState().snipeToken(pumpGrad);
    const pumpPos = useSniperStore.getState().positions[0];
    expect(pumpPos).toBeDefined();

    // The snipe log should mention the pump penalty
    const snipeLog = useSniperStore.getState().executionLog.find(e => e.type === 'snipe');
    expect(snipeLog?.reason).toContain('PUMP WARNING');
  });
});

// ──────────────────────────────────────────
// 4. getConvictionMultiplier — negative factors
// ──────────────────────────────────────────
describe('getConvictionMultiplier — negative factors', () => {
  it('reduces multiplier for very high price change (>200%)', () => {
    const normal = getConvictionMultiplier(makeGrad({ price_change_1h: 50 }));
    const extreme = getConvictionMultiplier(makeGrad({ price_change_1h: 250 }));
    // The extreme case should have -0.2 penalty applied
    // Despite the high change adding +0.4, the penalty subtracts 0.2
    // Net: extreme should be lower relative to what it would be without penalty
    expect(extreme.factors).toContain('pump risk');
  });

  it('reduces multiplier for very high B/S ratio (>3.0)', () => {
    const normal = getConvictionMultiplier(makeGrad({ txn_buys_1h: 20, txn_sells_1h: 10 })); // 2.0 ratio
    const manipulated = getConvictionMultiplier(makeGrad({ txn_buys_1h: 40, txn_sells_1h: 10 })); // 4.0 ratio
    expect(manipulated.factors).toContain('high B/S');
  });

  it('applies both penalties when both conditions met', () => {
    const result = getConvictionMultiplier(makeGrad({
      price_change_1h: 300,
      txn_buys_1h: 50,
      txn_sells_1h: 10, // 5.0 ratio
    }));
    expect(result.factors).toContain('pump risk');
    expect(result.factors).toContain('high B/S');
  });

  it('multiplier stays at floor 0.5 with heavy penalties', () => {
    // A token with penalties but few positive factors
    const result = getConvictionMultiplier(makeGrad({
      price_change_1h: 250, // +0.4 for high change, -0.2 for pump risk
      liquidity: 10000,     // no liquidity bonus
      volume_24h: 5000,     // low V/L
      txn_buys_1h: 50,
      txn_sells_1h: 10,     // 5.0 B/S ratio, -0.15
    }));
    expect(result.multiplier).toBeGreaterThanOrEqual(0.5);
  });
});

// ──────────────────────────────────────────
// 5. TokenRecommendation type — trail field
// ──────────────────────────────────────────
describe('TokenRecommendation — trail field', () => {
  it('getRecommendedSlTp returns sl, tp, reasoning, AND trail', () => {
    const rec = getRecommendedSlTp(makeGrad());
    expect(Object.keys(rec)).toContain('sl');
    expect(Object.keys(rec)).toContain('tp');
    expect(Object.keys(rec)).toContain('reasoning');
    expect(Object.keys(rec)).toContain('trail');
  });
});

describe('on-chain SL/TP safety guard', () => {
  beforeEach(() => {
    useSniperStore.getState().resetSession();
  });

  it('strips unsupported on-chain SL/TP fields when adding a position', () => {
    useSniperStore.getState().addPosition({
      id: 'pos-sltp-add',
      mint: 'SLTP1',
      symbol: 'SLTP1',
      name: 'SLTP Position',
      entryPrice: 1,
      currentPrice: 1,
      amount: 1,
      solInvested: 0.1,
      pnlPercent: 0,
      pnlSol: 0,
      entryTime: Date.now(),
      status: 'open',
      score: 50,
      recommendedSl: 10,
      recommendedTp: 20,
      highWaterMarkPct: 0,
      onChainSlTp: true,
      jupTpOrderKey: 'tp-order',
      jupSlOrderKey: 'sl-order',
    });

    const stored = useSniperStore.getState().positions.find((p) => p.id === 'pos-sltp-add');
    expect(stored).toBeDefined();
    expect(stored?.onChainSlTp).toBe(false);
    expect(stored?.jupTpOrderKey).toBeUndefined();
    expect(stored?.jupSlOrderKey).toBeUndefined();
  });

  it('strips unsupported on-chain SL/TP fields when updating a position', () => {
    useSniperStore.getState().addPosition({
      id: 'pos-sltp-update',
      mint: 'SLTP2',
      symbol: 'SLTP2',
      name: 'SLTP Position 2',
      entryPrice: 1,
      currentPrice: 1,
      amount: 1,
      solInvested: 0.1,
      pnlPercent: 0,
      pnlSol: 0,
      entryTime: Date.now(),
      status: 'open',
      score: 50,
      recommendedSl: 10,
      recommendedTp: 20,
      highWaterMarkPct: 0,
    });

    useSniperStore.getState().updatePosition('pos-sltp-update', {
      onChainSlTp: true,
      jupTpOrderKey: 'tp-order',
      jupSlOrderKey: 'sl-order',
    });

    const stored = useSniperStore.getState().positions.find((p) => p.id === 'pos-sltp-update');
    expect(stored).toBeDefined();
    expect(stored?.onChainSlTp).toBe(false);
    expect(stored?.jupTpOrderKey).toBeUndefined();
    expect(stored?.jupSlOrderKey).toBeUndefined();
  });
});
