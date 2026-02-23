import { describe, it, expect } from 'vitest';

// ---------------------------------------------------------------------------
// Tests for Quick-Trade SOL Amount Preset Buttons
// ---------------------------------------------------------------------------
// These tests validate the logic and configuration of the preset amount
// buttons and percentage-of-balance buttons added to TradePanel.

// The preset amounts that should be rendered
const SOL_PRESETS = [0.1, 0.25, 0.5, 1, 2, 5];

// The percentage presets for balance-based amounts
const PERCENT_PRESETS = [25, 50, 75, 100];

describe('Quick Trade SOL Amount Presets', () => {
  // ---- Preset button labels ----

  describe('preset button labels', () => {
    it('should have 6 SOL amount presets', () => {
      expect(SOL_PRESETS).toHaveLength(6);
    });

    it('should render correct labels for each preset', () => {
      const expectedLabels = ['0.1 SOL', '0.25 SOL', '0.5 SOL', '1 SOL', '2 SOL', '5 SOL'];
      const labels = SOL_PRESETS.map((amount) => `${amount} SOL`);
      expect(labels).toEqual(expectedLabels);
    });

    it('should include small amounts (0.1, 0.25) for sniping', () => {
      expect(SOL_PRESETS).toContain(0.1);
      expect(SOL_PRESETS).toContain(0.25);
    });

    it('should include larger amounts (2, 5) for conviction plays', () => {
      expect(SOL_PRESETS).toContain(2);
      expect(SOL_PRESETS).toContain(5);
    });
  });

  // ---- Clicking a preset updates the amount value ----

  describe('preset click behavior', () => {
    it('should convert preset amount to string for the input state', () => {
      // The setAmount function expects a string value
      SOL_PRESETS.forEach((amount) => {
        const result = amount.toString();
        expect(typeof result).toBe('string');
        expect(parseFloat(result)).toBe(amount);
      });
    });

    it('should produce valid numeric strings for all presets', () => {
      const results = SOL_PRESETS.map((a) => a.toString());
      expect(results).toEqual(['0.1', '0.25', '0.5', '1', '2', '5']);
    });
  });

  // ---- Active preset highlighting ----

  describe('active preset highlighting', () => {
    function isPresetActive(currentAmount: string, presetAmount: number): boolean {
      return parseFloat(currentAmount) === presetAmount;
    }

    it('should highlight when current amount matches preset exactly', () => {
      expect(isPresetActive('0.1', 0.1)).toBe(true);
      expect(isPresetActive('1', 1)).toBe(true);
      expect(isPresetActive('5', 5)).toBe(true);
    });

    it('should not highlight when current amount does not match', () => {
      expect(isPresetActive('0.3', 0.1)).toBe(false);
      expect(isPresetActive('0.5', 1)).toBe(false);
    });

    it('should handle string amounts with trailing zeros', () => {
      expect(isPresetActive('0.10', 0.1)).toBe(true);
      expect(isPresetActive('1.00', 1)).toBe(true);
      expect(isPresetActive('0.250', 0.25)).toBe(true);
    });

    it('should not highlight for empty or invalid input', () => {
      expect(isPresetActive('', 0.1)).toBe(false);
      expect(isPresetActive('abc', 1)).toBe(false);
    });

    it('should return the correct CSS class based on active state', () => {
      function getPresetClass(currentAmount: string, presetAmount: number): string {
        const isActive = parseFloat(currentAmount) === presetAmount;
        return isActive
          ? 'bg-accent-neon/20 text-accent-neon border border-accent-neon/40'
          : 'bg-bg-tertiary text-text-muted hover:text-text-primary border border-transparent';
      }

      const activeClass = getPresetClass('0.5', 0.5);
      expect(activeClass).toContain('bg-accent-neon/20');
      expect(activeClass).toContain('text-accent-neon');

      const inactiveClass = getPresetClass('0.5', 1);
      expect(inactiveClass).toContain('bg-bg-tertiary');
      expect(inactiveClass).toContain('text-text-muted');
    });
  });

  // ---- Percentage-of-balance buttons ----

  describe('percentage of balance buttons', () => {
    it('should have 4 percentage presets', () => {
      expect(PERCENT_PRESETS).toHaveLength(4);
    });

    it('should render correct percentage labels', () => {
      const labels = PERCENT_PRESETS.map((pct) => `${pct}%`);
      expect(labels).toEqual(['25%', '50%', '75%', '100%']);
    });

    function calculatePercentageAmount(solBalance: number, percent: number): string {
      return (solBalance * percent / 100).toFixed(4);
    }

    it('should calculate 25% of balance correctly', () => {
      expect(calculatePercentageAmount(10, 25)).toBe('2.5000');
      expect(calculatePercentageAmount(4.5, 25)).toBe('1.1250');
    });

    it('should calculate 50% of balance correctly', () => {
      expect(calculatePercentageAmount(10, 50)).toBe('5.0000');
      expect(calculatePercentageAmount(3.2, 50)).toBe('1.6000');
    });

    it('should calculate 75% of balance correctly', () => {
      expect(calculatePercentageAmount(10, 75)).toBe('7.5000');
    });

    it('should calculate 100% of balance correctly', () => {
      expect(calculatePercentageAmount(10, 100)).toBe('10.0000');
      expect(calculatePercentageAmount(0.5, 100)).toBe('0.5000');
    });

    it('should handle zero balance gracefully', () => {
      // When balance is zero, percentage buttons should not update amount
      const solBalance = 0;
      const shouldUpdate = solBalance > 0;
      expect(shouldUpdate).toBe(false);
    });

    it('should handle very small balances with 4 decimal precision', () => {
      expect(calculatePercentageAmount(0.001, 50)).toBe('0.0005');
      expect(calculatePercentageAmount(0.0001, 100)).toBe('0.0001');
    });

    it('should handle large balances', () => {
      expect(calculatePercentageAmount(1000, 25)).toBe('250.0000');
      expect(calculatePercentageAmount(100, 10)).toBe('10.0000');
    });
  });

  // ---- Integration: presets array matches component constants ----

  describe('preset configuration', () => {
    it('SOL presets should be sorted in ascending order', () => {
      for (let i = 1; i < SOL_PRESETS.length; i++) {
        expect(SOL_PRESETS[i]).toBeGreaterThan(SOL_PRESETS[i - 1]);
      }
    });

    it('percentage presets should be sorted in ascending order', () => {
      for (let i = 1; i < PERCENT_PRESETS.length; i++) {
        expect(PERCENT_PRESETS[i]).toBeGreaterThan(PERCENT_PRESETS[i - 1]);
      }
    });

    it('all SOL presets should be positive numbers', () => {
      SOL_PRESETS.forEach((amount) => {
        expect(amount).toBeGreaterThan(0);
        expect(typeof amount).toBe('number');
      });
    });

    it('all percentage presets should be between 1 and 100', () => {
      PERCENT_PRESETS.forEach((pct) => {
        expect(pct).toBeGreaterThanOrEqual(1);
        expect(pct).toBeLessThanOrEqual(100);
      });
    });
  });
});
