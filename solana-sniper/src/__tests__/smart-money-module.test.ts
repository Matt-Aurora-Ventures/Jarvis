import { describe, it, expect } from 'vitest';
import {
  getSmartMoneyConvictionBonus,
  simulateSmartMoneyScore,
  type SmartMoneyScore,
  type SmartWallet,
  type SmartMoneySignal,
} from '../analysis/smart-money.js';

// ─── simulateSmartMoneyScore tests ──────────────────────────

describe('simulateSmartMoneyScore', () => {
  const baseToken = {
    buyCount1h: 10,
    sellCount1h: 10,
    volumeUsd24h: 5000,
    liquidityUsd: 10000,
    holderCount: 50,
  };

  it('should return 0 for a perfectly average token', () => {
    const score = simulateSmartMoneyScore({
      buyCount1h: 1,
      sellCount1h: 1,
      volumeUsd24h: 500,
      liquidityUsd: 10000,
      holderCount: 20,
    });
    expect(score).toBe(0);
  });

  it('should return positive score for volume surge', () => {
    const score = simulateSmartMoneyScore({
      ...baseToken,
      isVolumeSurge: true,
      volumeSurgeRatio: 4,
    });
    expect(score).toBeGreaterThan(0);
  });

  it('should give higher score for extreme volume surge (ratio > 3)', () => {
    const moderateSurge = simulateSmartMoneyScore({
      ...baseToken,
      isVolumeSurge: true,
      volumeSurgeRatio: 2,
    });
    const strongSurge = simulateSmartMoneyScore({
      ...baseToken,
      isVolumeSurge: true,
      volumeSurgeRatio: 4,
    });
    expect(strongSurge).toBeGreaterThan(moderateSurge);
  });

  it('should reward high buy/sell ratio (accumulation signal)', () => {
    const lowRatio = simulateSmartMoneyScore({
      ...baseToken,
      buyCount1h: 10,
      sellCount1h: 10,
    });
    const highRatio = simulateSmartMoneyScore({
      ...baseToken,
      buyCount1h: 40,
      sellCount1h: 10,
    });
    expect(highRatio).toBeGreaterThan(lowRatio);
  });

  it('should reward many holders (distribution signal)', () => {
    const fewHolders = simulateSmartMoneyScore({
      ...baseToken,
      holderCount: 30,
    });
    const manyHolders = simulateSmartMoneyScore({
      ...baseToken,
      holderCount: 250,
    });
    expect(manyHolders).toBeGreaterThan(fewHolders);
  });

  it('should reward high vol/liq ratio (active interest)', () => {
    const lowVolLiq = simulateSmartMoneyScore({
      ...baseToken,
      volumeUsd24h: 5000,
      liquidityUsd: 50000,
    });
    const highVolLiq = simulateSmartMoneyScore({
      ...baseToken,
      volumeUsd24h: 100000,
      liquidityUsd: 50000,
    });
    expect(highVolLiq).toBeGreaterThan(lowVolLiq);
  });

  it('should clamp output between -1 and 1', () => {
    // Max bullish scenario
    const maxBullish = simulateSmartMoneyScore({
      buyCount1h: 1000,
      sellCount1h: 1,
      volumeUsd24h: 1000000,
      liquidityUsd: 100000,
      holderCount: 10000,
      isVolumeSurge: true,
      volumeSurgeRatio: 100,
    });
    expect(maxBullish).toBeLessThanOrEqual(1);
    expect(maxBullish).toBeGreaterThanOrEqual(-1);
  });
});

// ─── getSmartMoneyConvictionBonus tests ─────────────────────

describe('getSmartMoneyConvictionBonus', () => {
  function makeScore(signalScore: number): SmartMoneyScore {
    return {
      mint: 'testmint123',
      smartBuyers: 0,
      smartSellers: 0,
      netFlow: 0,
      avgBuyerWinRate: 0,
      signalScore,
      recentSignals: [],
      computedAt: Date.now(),
    };
  }

  it('should return +0.5 for very high signal score (>=0.5)', () => {
    expect(getSmartMoneyConvictionBonus(makeScore(0.5))).toBe(0.5);
    expect(getSmartMoneyConvictionBonus(makeScore(0.8))).toBe(0.5);
    expect(getSmartMoneyConvictionBonus(makeScore(1.0))).toBe(0.5);
  });

  it('should return +0.3 for high signal score (>=0.3, <0.5)', () => {
    expect(getSmartMoneyConvictionBonus(makeScore(0.3))).toBe(0.3);
    expect(getSmartMoneyConvictionBonus(makeScore(0.4))).toBe(0.3);
  });

  it('should return +0.15 for moderate signal score (>=0.1, <0.3)', () => {
    expect(getSmartMoneyConvictionBonus(makeScore(0.1))).toBe(0.15);
    expect(getSmartMoneyConvictionBonus(makeScore(0.2))).toBe(0.15);
  });

  it('should return -0.3 for strong bearish signal (<=-0.3)', () => {
    expect(getSmartMoneyConvictionBonus(makeScore(-0.3))).toBe(-0.3);
    expect(getSmartMoneyConvictionBonus(makeScore(-0.5))).toBe(-0.3);
    expect(getSmartMoneyConvictionBonus(makeScore(-1.0))).toBe(-0.3);
  });

  it('should return -0.15 for moderate bearish signal (<=-0.1, >-0.3)', () => {
    expect(getSmartMoneyConvictionBonus(makeScore(-0.1))).toBe(-0.15);
    expect(getSmartMoneyConvictionBonus(makeScore(-0.2))).toBe(-0.15);
  });

  it('should return 0 for neutral signal (between -0.1 and 0.1)', () => {
    expect(getSmartMoneyConvictionBonus(makeScore(0))).toBe(0);
    expect(getSmartMoneyConvictionBonus(makeScore(0.05))).toBe(0);
    expect(getSmartMoneyConvictionBonus(makeScore(-0.05))).toBe(0);
  });
});

// ─── Type interface tests ───────────────────────────────────

describe('SmartMoney type exports', () => {
  it('SmartWallet interface should have all required fields', () => {
    const wallet: SmartWallet = {
      address: 'test_address_123',
      label: 'test_whale',
      category: 'whale',
      winRate: 0.75,
      avgReturn: 2.5,
      totalPnlSol: 500,
      lastActive: Date.now(),
    };
    expect(wallet.address).toBe('test_address_123');
    expect(wallet.category).toBe('whale');
  });

  it('SmartMoneySignal interface should have all required fields', () => {
    const signal: SmartMoneySignal = {
      walletAddress: 'wallet123',
      walletLabel: 'big_fish',
      category: 'fund',
      tokenMint: 'mint123',
      tokenSymbol: 'TEST',
      action: 'buy',
      amountSol: 100,
      timestamp: Date.now(),
      txHash: 'txhash123',
      signalStrength: 0.85,
    };
    expect(signal.action).toBe('buy');
    expect(signal.signalStrength).toBe(0.85);
  });

  it('SmartMoneyScore interface should have all required fields', () => {
    const score: SmartMoneyScore = {
      mint: 'token_mint_123',
      smartBuyers: 3,
      smartSellers: 1,
      netFlow: 2,
      avgBuyerWinRate: 0.72,
      signalScore: 0.45,
      recentSignals: [],
      computedAt: Date.now(),
    };
    expect(score.netFlow).toBe(2);
    expect(score.signalScore).toBe(0.45);
  });

  it('SmartWallet category should support all expected types', () => {
    const categories: SmartWallet['category'][] = ['whale', 'insider', 'degen_winner', 'fund', 'kol'];
    expect(categories.length).toBe(5);
  });
});
