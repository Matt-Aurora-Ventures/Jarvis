import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

vi.mock('../usePerpsData', () => ({
  usePerpsData: () => ({
    prices: { sol: 0, btc: 0, eth: 0 },
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
    setHistoryMarket: () => undefined,
    setHistoryResolution: () => undefined,
    openPosition: vi.fn(async () => undefined),
    closePosition: vi.fn(async () => undefined),
    refreshStatus: vi.fn(async () => undefined),
  }),
}));

vi.mock('../PerpsCandlesChart', () => ({
  PerpsCandlesChart: () => <div>chart</div>,
}));

import { PerpsSniperPanel } from '../PerpsSniperPanel';

describe('PerpsSniperPanel', () => {
  it('does not block order entry behind LIVE/ARMED-only UI gating', () => {
    const markup = renderToStaticMarkup(<PerpsSniperPanel />);
    expect(markup).not.toContain('Live order entry requires mode=LIVE and arm stage=ARMED.');
    const openButton = markup.match(/<button[^>]*>Open LONG SOL-USD<\/button>/)?.[0] ?? '';
    expect(openButton).not.toMatch(/\sdisabled(=|(?=>))/);
  });
});
