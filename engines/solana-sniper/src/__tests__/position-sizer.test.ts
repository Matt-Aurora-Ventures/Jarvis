import { describe, it, expect } from 'vitest';
import { classifyRiskTier } from '../risk/position-sizer.js';

describe('Position Sizer - Risk Tier Classification', () => {
  it('should classify high safety + high liquidity as ESTABLISHED or MID', () => {
    // Use the actual SOL mint address from ESTABLISHED_TOKENS set
    const tier = classifyRiskTier('So11111111111111111111111111111111111111112', 0.9, 1_000_000, 5000);
    expect(tier).toBe('ESTABLISHED');
  });

  it('should classify unknown token with high scores as MID', () => {
    // MID requires: safetyScore >= 0.8, liquidityUsd >= 100_000, holderCount >= 500
    const tier = classifyRiskTier('unknownmint123456789012345678901234', 0.85, 150_000, 600);
    expect(tier).toBe('MID');
  });

  it('should classify low safety as HIGH_RISK', () => {
    const tier = classifyRiskTier('unknownmint123456789012345678901234', 0.3, 5_000, 30);
    expect(tier).toBe('HIGH_RISK');
  });

  it('should classify medium safety + medium liquidity as MICRO', () => {
    // MICRO requires: safetyScore >= 0.6, liquidityUsd >= 10_000, holderCount >= 50
    const tier = classifyRiskTier('unknownmint123456789012345678901234', 0.65, 20_000, 100);
    expect(tier).toBe('MICRO');
  });

  it('should fall to HIGH_RISK when just below MICRO thresholds', () => {
    // safetyScore 0.55 < 0.6 threshold
    const tier = classifyRiskTier('unknownmint123456789012345678901234', 0.55, 15_000, 100);
    expect(tier).toBe('HIGH_RISK');
  });

  it('should fall to MICRO when just below MID thresholds', () => {
    // safetyScore 0.75 < 0.8 threshold for MID, but >= 0.6 for MICRO
    const tier = classifyRiskTier('unknownmint123456789012345678901234', 0.75, 100_000, 500);
    expect(tier).toBe('MICRO');
  });
});
