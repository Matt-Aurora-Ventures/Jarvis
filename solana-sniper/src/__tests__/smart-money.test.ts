import { describe, it, expect } from 'vitest';
import {
  computeSmartMoneyBoost,
  type SmartMoneySignal,
} from '../analysis/smart-money-tracker.js';

describe('Smart Money Tracker', () => {
  it('should return 0 boost for empty signals', () => {
    const boost = computeSmartMoneyBoost([]);
    expect(boost).toBe(0);
  });

  it('should compute boost from whale signal', () => {
    const signals: SmartMoneySignal[] = [{
      mint: 'test',
      symbol: 'TEST',
      walletAddress: 'whale1',
      walletLabel: 'whale_test',
      walletTier: 'whale',
      walletWinRate: 0.8,
      amountUsd: 5000,
      signalStrength: 0.9,
      timestamp: Date.now(),
    }];
    const boost = computeSmartMoneyBoost(signals);
    expect(boost).toBeGreaterThan(0);
    expect(boost).toBeLessThanOrEqual(0.3); // capped
  });

  it('should cap boost at 0.3 max', () => {
    const signals: SmartMoneySignal[] = [
      { mint: 'test', symbol: 'TEST', walletAddress: 'w1', walletLabel: 'a', walletTier: 'whale', walletWinRate: 0.9, amountUsd: 10000, signalStrength: 0.9, timestamp: Date.now() },
      { mint: 'test', symbol: 'TEST', walletAddress: 'w2', walletLabel: 'b', walletTier: 'whale', walletWinRate: 0.85, amountUsd: 8000, signalStrength: 0.9, timestamp: Date.now() },
      { mint: 'test', symbol: 'TEST', walletAddress: 'w3', walletLabel: 'c', walletTier: 'smart', walletWinRate: 0.6, amountUsd: 3000, signalStrength: 0.7, timestamp: Date.now() },
    ];
    const boost = computeSmartMoneyBoost(signals);
    expect(boost).toBe(0.3); // should hit cap
  });

  it('should give lower boost for tracked tier', () => {
    const smartSignal: SmartMoneySignal[] = [{
      mint: 'test', symbol: 'TEST', walletAddress: 'w1', walletLabel: 'smart', walletTier: 'smart',
      walletWinRate: 0.6, amountUsd: 2000, signalStrength: 0.7, timestamp: Date.now(),
    }];
    const trackedSignal: SmartMoneySignal[] = [{
      mint: 'test', symbol: 'TEST', walletAddress: 'w2', walletLabel: 'tracked', walletTier: 'tracked',
      walletWinRate: 0.4, amountUsd: 1000, signalStrength: 0.4, timestamp: Date.now(),
    }];
    const smartBoost = computeSmartMoneyBoost(smartSignal);
    const trackedBoost = computeSmartMoneyBoost(trackedSignal);
    expect(smartBoost).toBeGreaterThan(trackedBoost);
  });
});
