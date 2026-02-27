import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

vi.mock('@/components/perps/usePerpsData', () => ({
  usePerpsData: () => ({
    prices: null,
    status: { runner_healthy: false, mode: 'disabled', arm: { stage: 'disarmed' } },
    positions: [],
    audit: [],
    historyMarket: 'SOL-USD',
    historyResolution: '5',
    historyCandles: [],
    loadingHistory: false,
    historyError: null,
    apiError: null,
    isArmed: false,
    isLive: false,
    setHistoryMarket: vi.fn(),
    setHistoryResolution: vi.fn(),
    openPosition: vi.fn(),
    closePosition: vi.fn(),
    refreshStatus: vi.fn(),
    armPrepare: vi.fn(),
    armConfirm: vi.fn(),
    disarm: vi.fn(),
    startRunner: vi.fn(),
    stopRunner: vi.fn(),
    updateLimits: vi.fn(),
  }),
}));

describe('PerpsSniperPanel controls', () => {
  it('renders runner and arm controls', async () => {
    const { PerpsSniperPanel } = await import('@/components/perps/PerpsSniperPanel');
    const html = renderToStaticMarkup(<PerpsSniperPanel />);

    expect(html).toContain('Start Runner');
    expect(html).toContain('Stop Runner');
    expect(html).toContain('Prepare Arm');
    expect(html).toContain('Confirm Arm');
    expect(html).toContain('Disarm');
  });
});
