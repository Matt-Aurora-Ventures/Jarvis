import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

vi.mock('@/components/StatusBar', () => ({
  StatusBar: () => <div>status-bar</div>,
}));

vi.mock('@/components/EarlyBetaModal', () => ({
  EarlyBetaModal: () => <div>early-beta</div>,
}));

vi.mock('@/components/FundRecoveryBanner', () => ({
  FundRecoveryBanner: () => <div>fund-recovery</div>,
}));

describe('ClawbotPageClient', () => {
  it('renders demo-safe coming-soon panel with disabled overlay', async () => {
    const { ClawbotPageClient } = await import('@/components/clawbot/ClawbotPageClient');

    const html = renderToStaticMarkup(<ClawbotPageClient />);

    expect(html).toContain('Clawbot');
    expect(html).toContain('Clawbot Coming Soon');
    expect(html).toContain('Panel visible (staged rollout)');
    expect(html).toContain('Clawbot is in staged rollout for this runtime.');
    expect(html).toContain('Autonomous Sweep');
    expect(html).toContain('Queue Position');
  });
});

