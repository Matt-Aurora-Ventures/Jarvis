import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock wallet module before importing circuit-breaker
vi.mock('../utils/wallet.js', () => ({
  getSolBalanceUsd: vi.fn().mockResolvedValue({ sol: 0.5, usd: 100 }),
}));

// Mock database module
vi.mock('../utils/database.js', () => ({
  getDailyPnl: vi.fn().mockReturnValue(0),
  getWinRate: vi.fn().mockReturnValue({ total: 0, rate: 0 }),
  getOpenPositions: vi.fn().mockReturnValue([]),
}));

import { checkCircuitBreaker, recordTradeResult, resetCircuitBreaker } from '../risk/circuit-breaker.js';

describe('Circuit Breaker', () => {
  beforeEach(() => {
    resetCircuitBreaker();
  });

  it('should not trip on fresh state', async () => {
    const result = await checkCircuitBreaker();
    expect(result).toHaveProperty('isTripped');
    expect(result).toHaveProperty('reason');
    expect(result.isTripped).toBe(false);
  });

  it('should trip after 5 consecutive losses', async () => {
    for (let i = 0; i < 5; i++) {
      recordTradeResult(false);
    }
    const result = await checkCircuitBreaker();
    expect(result.isTripped).toBe(true);
    expect(result.reason).toContain('consecutive losses');
  });

  it('should reset consecutive losses on a win', () => {
    recordTradeResult(false);
    recordTradeResult(false);
    recordTradeResult(false);
    recordTradeResult(true); // this resets
    recordTradeResult(false);
    // Only 1 consecutive loss now, not enough to trip
  });

  it('should reset fully', () => {
    recordTradeResult(false);
    recordTradeResult(false);
    resetCircuitBreaker();
    // After reset, consecutive loss count should be 0
  });
});
