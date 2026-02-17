import { describe, it, expect } from 'vitest';

// ── Pure Logic Under Test ────────────────────────────────────────────
// We test the helper functions that power the TokenCompare component.
// These are extracted to keep the component thin and the logic testable.

import {
  determineWinner,
  buildJupiterSwapUrl,
  formatComparePrice,
  formatComparePercent,
  type CompareToken,
} from '@/components/features/TokenCompare';

// ── Test Fixtures ────────────────────────────────────────────────────

function makeToken(overrides: Partial<CompareToken> = {}): CompareToken {
  return {
    address: 'So11111111111111111111111111111111111111112',
    symbol: 'SOL',
    name: 'Wrapped SOL',
    priceUsd: 150.23,
    change24h: 3.2,
    volume24h: 1_200_000_000,
    fdv: 68_500_000_000,
    liquidity: 850_000_000,
    ...overrides,
  };
}

const TOKEN_A = makeToken();
const TOKEN_B = makeToken({
  address: 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',
  symbol: 'JUP',
  name: 'Jupiter',
  priceUsd: 0.85,
  change24h: -1.5,
  volume24h: 45_000_000,
  fdv: 1_200_000_000,
  liquidity: 12_000_000,
});

// ── Tests ────────────────────────────────────────────────────────────

describe('TokenCompare helpers', () => {
  // ── determineWinner ──────────────────────────────────────────────

  describe('determineWinner', () => {
    it('should return "A" when value A is higher for higher-is-better metrics', () => {
      // Higher volume is better
      expect(determineWinner(1_200_000_000, 45_000_000, 'higher')).toBe('A');
    });

    it('should return "B" when value B is higher for higher-is-better metrics', () => {
      expect(determineWinner(45_000_000, 1_200_000_000, 'higher')).toBe('B');
    });

    it('should return "A" when value A is lower for lower-is-better metrics', () => {
      // Lower risk score is better
      expect(determineWinner(10, 50, 'lower')).toBe('A');
    });

    it('should return "B" when value B is lower for lower-is-better metrics', () => {
      expect(determineWinner(50, 10, 'lower')).toBe('B');
    });

    it('should return "tie" when values are equal', () => {
      expect(determineWinner(100, 100, 'higher')).toBe('tie');
    });

    it('should return "tie" when both values are zero', () => {
      expect(determineWinner(0, 0, 'higher')).toBe('tie');
    });

    it('should handle negative values (24h change)', () => {
      // +3.2% vs -1.5% -- higher is better
      expect(determineWinner(3.2, -1.5, 'higher')).toBe('A');
    });
  });

  // ── buildJupiterSwapUrl ──────────────────────────────────────────

  describe('buildJupiterSwapUrl', () => {
    it('should build a valid Jupiter swap URL with SOL as input', () => {
      const url = buildJupiterSwapUrl(TOKEN_A.address);
      expect(url).toBe(
        'https://jup.ag/swap/SOL-So11111111111111111111111111111111111111112'
      );
    });

    it('should build a valid Jupiter swap URL for JUP token', () => {
      const url = buildJupiterSwapUrl(TOKEN_B.address);
      expect(url).toBe(
        'https://jup.ag/swap/SOL-JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN'
      );
    });

    it('should handle empty address gracefully', () => {
      const url = buildJupiterSwapUrl('');
      expect(url).toBe('https://jup.ag/swap/SOL-');
    });
  });

  // ── formatComparePrice ───────────────────────────────────────────

  describe('formatComparePrice', () => {
    it('should format large prices with dollar sign and 2 decimals', () => {
      expect(formatComparePrice(150.23)).toBe('$150.23');
    });

    it('should format sub-dollar prices with more precision', () => {
      expect(formatComparePrice(0.85)).toBe('$0.8500');
    });

    it('should format very small prices in exponential notation', () => {
      const result = formatComparePrice(0.0000001);
      expect(result).toMatch(/^\$\d/);
      expect(result).toContain('e');
    });

    it('should format zero as $0.00', () => {
      expect(formatComparePrice(0)).toBe('$0.00');
    });

    it('should format thousands with commas', () => {
      const result = formatComparePrice(1500);
      expect(result).toBe('$1,500.00');
    });
  });

  // ── formatComparePercent ─────────────────────────────────────────

  describe('formatComparePercent', () => {
    it('should format positive change with + prefix', () => {
      expect(formatComparePercent(3.2)).toBe('+3.2%');
    });

    it('should format negative change with - prefix', () => {
      expect(formatComparePercent(-1.5)).toBe('-1.5%');
    });

    it('should format zero change', () => {
      expect(formatComparePercent(0)).toBe('0.0%');
    });

    it('should format large positive change', () => {
      expect(formatComparePercent(150.7)).toBe('+150.7%');
    });
  });

  // ── Collapsed / Expanded state logic ─────────────────────────────

  describe('component default state', () => {
    it('should define CompareToken interface with all required fields', () => {
      const token: CompareToken = makeToken();
      expect(token.address).toBeDefined();
      expect(token.symbol).toBeDefined();
      expect(token.name).toBeDefined();
      expect(typeof token.priceUsd).toBe('number');
      expect(typeof token.change24h).toBe('number');
      expect(typeof token.volume24h).toBe('number');
      expect(typeof token.fdv).toBe('number');
      expect(typeof token.liquidity).toBe('number');
    });

    it('should have all metrics available for comparison', () => {
      // Verify the comparison metrics we display
      const metrics = ['priceUsd', 'change24h', 'volume24h', 'fdv', 'liquidity'] as const;
      const token = makeToken();
      for (const metric of metrics) {
        expect(token[metric]).toBeDefined();
        expect(typeof token[metric]).toBe('number');
      }
    });
  });

  // ── Winner highlighting logic ────────────────────────────────────

  describe('metric comparison highlighting', () => {
    it('should identify SOL as winner for volume (higher is better)', () => {
      const winner = determineWinner(
        TOKEN_A.volume24h,
        TOKEN_B.volume24h,
        'higher'
      );
      expect(winner).toBe('A');
    });

    it('should identify SOL as winner for liquidity (higher is better)', () => {
      const winner = determineWinner(
        TOKEN_A.liquidity,
        TOKEN_B.liquidity,
        'higher'
      );
      expect(winner).toBe('A');
    });

    it('should identify SOL as winner for FDV (higher is better)', () => {
      const winner = determineWinner(TOKEN_A.fdv, TOKEN_B.fdv, 'higher');
      expect(winner).toBe('A');
    });

    it('should identify SOL as winner for 24h change (higher is better)', () => {
      const winner = determineWinner(
        TOKEN_A.change24h,
        TOKEN_B.change24h,
        'higher'
      );
      expect(winner).toBe('A');
    });
  });

  // ── Trade link URL generation ────────────────────────────────────

  describe('trade link URLs', () => {
    it('should generate correct Jupiter URL for token A', () => {
      const url = buildJupiterSwapUrl(TOKEN_A.address);
      expect(url).toContain('jup.ag/swap');
      expect(url).toContain(TOKEN_A.address);
    });

    it('should generate correct Jupiter URL for token B', () => {
      const url = buildJupiterSwapUrl(TOKEN_B.address);
      expect(url).toContain('jup.ag/swap');
      expect(url).toContain(TOKEN_B.address);
    });

    it('should use SOL as default input token', () => {
      const url = buildJupiterSwapUrl(TOKEN_A.address);
      expect(url).toContain('SOL-');
    });
  });
});
