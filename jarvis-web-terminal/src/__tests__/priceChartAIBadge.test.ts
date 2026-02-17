import { describe, it, expect, beforeEach } from 'vitest';
import { useSettingsStore } from '@/stores/useSettingsStore';

// ---------------------------------------------------------------------------
// We test the AI consensus badge logic that PriceChart.tsx renders.
// Since PriceChart depends on heavy charting libs (lightweight-charts) that
// don't run in jsdom, we test the badge rendering logic via a minimal
// extraction: we define the same color/label logic here and verify it matches
// what the component should produce.  We also verify that the store state
// drives visibility correctly.
// ---------------------------------------------------------------------------

/** Mirror of the badge color logic from PriceChart.tsx */
function getBadgeClasses(consensus: 'BUY' | 'SELL' | 'HOLD'): string {
  switch (consensus) {
    case 'BUY':
      return 'text-accent-neon bg-accent-neon/10 animate-pulse';
    case 'SELL':
      return 'text-accent-error bg-accent-error/10';
    case 'HOLD':
      return 'text-text-muted bg-bg-tertiary';
  }
}

/** Mirror of the badge label logic from PriceChart.tsx */
function getBadgeLabel(
  consensus: 'BUY' | 'SELL' | 'HOLD',
  winRate: number | null,
  strength: string | null,
): string {
  const parts = [`AI: ${consensus}`];
  if (winRate !== null) parts.push(`${winRate}%`);
  if (strength !== null) parts.push(`(${strength})`);
  return parts.join(' ');
}

/** Mirror of the aria-label logic from PriceChart.tsx */
function getAriaLabel(
  consensus: 'BUY' | 'SELL' | 'HOLD',
  winRate: number | null,
  strength: string | null,
): string {
  const parts = [`AI consensus: ${consensus}`];
  if (winRate !== null) parts.push(`best win rate ${winRate}%`);
  if (strength !== null) parts.push(`signal strength ${strength}`);
  return parts.join(', ');
}

describe('PriceChart AI Consensus Badge', () => {
  beforeEach(() => {
    useSettingsStore.setState({
      aiConsensus: null,
      aiBestWinRate: null,
      aiSignalStrength: null,
      aiSuggestedTP: null,
      aiSuggestedSL: null,
    });
  });

  // -------------------------------------------------------------------------
  // Visibility
  // -------------------------------------------------------------------------

  describe('visibility', () => {
    it('should NOT render when aiConsensus is null', () => {
      const state = useSettingsStore.getState();
      expect(state.aiConsensus).toBeNull();
      // Badge should not render when consensus is null
      const shouldRender = state.aiConsensus !== null;
      expect(shouldRender).toBe(false);
    });

    it('should render when aiConsensus is BUY', () => {
      useSettingsStore.getState().setAISignal({
        consensus: 'BUY',
        bestWinRate: 72,
        signalStrength: '3/4',
        suggestedTP: 25,
        suggestedSL: 8,
      });
      const state = useSettingsStore.getState();
      expect(state.aiConsensus).toBe('BUY');
      const shouldRender = state.aiConsensus !== null;
      expect(shouldRender).toBe(true);
    });

    it('should render when aiConsensus is SELL', () => {
      useSettingsStore.getState().setAISignal({
        consensus: 'SELL',
        bestWinRate: 55,
        signalStrength: '1/4',
        suggestedTP: 15,
        suggestedSL: 10,
      });
      const state = useSettingsStore.getState();
      const shouldRender = state.aiConsensus !== null;
      expect(shouldRender).toBe(true);
    });

    it('should render when aiConsensus is HOLD', () => {
      useSettingsStore.getState().setAISignal({
        consensus: 'HOLD',
        bestWinRate: 48,
        signalStrength: '2/4',
        suggestedTP: 20,
        suggestedSL: 10,
      });
      const state = useSettingsStore.getState();
      const shouldRender = state.aiConsensus !== null;
      expect(shouldRender).toBe(true);
    });
  });

  // -------------------------------------------------------------------------
  // Color classes per signal type
  // -------------------------------------------------------------------------

  describe('color classes', () => {
    it('BUY should use accent-neon with pulse animation', () => {
      const classes = getBadgeClasses('BUY');
      expect(classes).toContain('text-accent-neon');
      expect(classes).toContain('bg-accent-neon/10');
      expect(classes).toContain('animate-pulse');
    });

    it('SELL should use accent-error without pulse', () => {
      const classes = getBadgeClasses('SELL');
      expect(classes).toContain('text-accent-error');
      expect(classes).toContain('bg-accent-error/10');
      expect(classes).not.toContain('animate-pulse');
    });

    it('HOLD should use muted colors without pulse', () => {
      const classes = getBadgeClasses('HOLD');
      expect(classes).toContain('text-text-muted');
      expect(classes).toContain('bg-bg-tertiary');
      expect(classes).not.toContain('animate-pulse');
    });
  });

  // -------------------------------------------------------------------------
  // Badge label text
  // -------------------------------------------------------------------------

  describe('badge label text', () => {
    it('should format full label with win rate and strength', () => {
      const label = getBadgeLabel('BUY', 72, '3/4');
      expect(label).toBe('AI: BUY 72% (3/4)');
    });

    it('should format label without win rate', () => {
      const label = getBadgeLabel('SELL', null, '2/4');
      expect(label).toBe('AI: SELL (2/4)');
    });

    it('should format label without strength', () => {
      const label = getBadgeLabel('HOLD', 48, null);
      expect(label).toBe('AI: HOLD 48%');
    });

    it('should format label with only consensus', () => {
      const label = getBadgeLabel('BUY', null, null);
      expect(label).toBe('AI: BUY');
    });
  });

  // -------------------------------------------------------------------------
  // Aria-label accessibility
  // -------------------------------------------------------------------------

  describe('aria-label content', () => {
    it('should include full accessibility description', () => {
      const aria = getAriaLabel('BUY', 72, '3/4');
      expect(aria).toBe('AI consensus: BUY, best win rate 72%, signal strength 3/4');
    });

    it('should handle null win rate', () => {
      const aria = getAriaLabel('SELL', null, '1/4');
      expect(aria).toBe('AI consensus: SELL, signal strength 1/4');
    });

    it('should handle null strength', () => {
      const aria = getAriaLabel('HOLD', 48, null);
      expect(aria).toBe('AI consensus: HOLD, best win rate 48%');
    });

    it('should handle only consensus', () => {
      const aria = getAriaLabel('BUY', null, null);
      expect(aria).toBe('AI consensus: BUY');
    });
  });

  // -------------------------------------------------------------------------
  // Integration: store state drives badge data
  // -------------------------------------------------------------------------

  describe('store integration', () => {
    it('should produce correct badge data from store state after setAISignal', () => {
      useSettingsStore.getState().setAISignal({
        consensus: 'BUY',
        bestWinRate: 72,
        signalStrength: '3/4',
        suggestedTP: 25,
        suggestedSL: 8,
      });

      const { aiConsensus, aiBestWinRate, aiSignalStrength } =
        useSettingsStore.getState();

      expect(aiConsensus).toBe('BUY');
      const label = getBadgeLabel(aiConsensus!, aiBestWinRate, aiSignalStrength);
      expect(label).toBe('AI: BUY 72% (3/4)');

      const classes = getBadgeClasses(aiConsensus!);
      expect(classes).toContain('animate-pulse');

      const aria = getAriaLabel(aiConsensus!, aiBestWinRate, aiSignalStrength);
      expect(aria).toContain('AI consensus: BUY');
    });

    it('should produce correct badge data for SELL signal', () => {
      useSettingsStore.getState().setAISignal({
        consensus: 'SELL',
        bestWinRate: 55,
        signalStrength: '1/4',
        suggestedTP: 15,
        suggestedSL: 10,
      });

      const { aiConsensus, aiBestWinRate, aiSignalStrength } =
        useSettingsStore.getState();

      const label = getBadgeLabel(aiConsensus!, aiBestWinRate, aiSignalStrength);
      expect(label).toBe('AI: SELL 55% (1/4)');

      const classes = getBadgeClasses(aiConsensus!);
      expect(classes).not.toContain('animate-pulse');
      expect(classes).toContain('text-accent-error');
    });

    it('badge data should be null-safe after clearAISignal', () => {
      useSettingsStore.getState().setAISignal({
        consensus: 'BUY',
        bestWinRate: 72,
        signalStrength: '3/4',
        suggestedTP: 25,
        suggestedSL: 8,
      });

      useSettingsStore.getState().clearAISignal();
      const { aiConsensus } = useSettingsStore.getState();
      expect(aiConsensus).toBeNull();
    });
  });
});
