import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

const replaceMock = vi.fn();
let searchParams = new URLSearchParams('tab=basket');

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock }),
  useSearchParams: () => searchParams,
}));

vi.mock('@/components/StatusBar', () => ({
  StatusBar: () => <div>status-bar</div>,
}));

vi.mock('@/components/EarlyBetaModal', () => ({
  EarlyBetaModal: () => <div>early-beta</div>,
}));

vi.mock('@/components/FundRecoveryBanner', () => ({
  FundRecoveryBanner: () => <div>fund-recovery</div>,
}));

vi.mock('@/components/investments/AlvaraBasketPanel', () => ({
  AlvaraBasketPanel: ({ forceDisabledReason }: { forceDisabledReason?: string | null }) => (
    <div>alvara-panel:{forceDisabledReason || 'enabled'}</div>
  ),
}));

vi.mock('@/components/perps/PerpsSniperPanel', () => ({
  PerpsSniperPanel: ({ forceDisabledReason }: { forceDisabledReason?: string | null }) => (
    <div>perps-panel:{forceDisabledReason || 'enabled'}</div>
  ),
}));

describe('InvestmentsPageClient disabled-surface behavior', () => {
  beforeEach(() => {
    vi.resetModules();
    replaceMock.mockReset();
    searchParams = new URLSearchParams('tab=basket');
    delete process.env.NEXT_PUBLIC_ENABLE_INVESTMENTS;
    delete process.env.NEXT_PUBLIC_ENABLE_PERPS;
  });

  it('shows disabled labels and overlay when both surfaces are disabled', async () => {
    process.env.NEXT_PUBLIC_ENABLE_INVESTMENTS = 'false';
    process.env.NEXT_PUBLIC_ENABLE_PERPS = 'false';
    const { InvestmentsPageClient } = await import('@/components/investments/InvestmentsPageClient');

    const html = renderToStaticMarkup(<InvestmentsPageClient />);

    expect(html).toContain('Manage the Alvara basket from one operator panel.');
    expect(html).toContain('Fast path');
    expect(html).toContain('Investments (disabled)');
    expect(html).toContain('role="tablist"');
    expect(html).toContain('role="tab"');
    expect(html).toContain('role="tabpanel"');
    expect(html).toContain('Panel visible (staged rollout)');
    expect(html).toContain('Investments is in staged rollout for this runtime.');
  });

  it('falls back to the investments panel when the requested perps tab is disabled', async () => {
    process.env.NEXT_PUBLIC_ENABLE_INVESTMENTS = 'true';
    process.env.NEXT_PUBLIC_ENABLE_PERPS = 'false';
    searchParams = new URLSearchParams('tab=perps');
    const { InvestmentsPageClient } = await import('@/components/investments/InvestmentsPageClient');

    const html = renderToStaticMarkup(<InvestmentsPageClient />);

    expect(html).toContain('alvara-panel:enabled');
    expect(html).not.toContain('perps-panel');
    expect(html).not.toContain('Perps (disabled)');
  });

  it('hides the disabled perps path when investments is the only active surface', async () => {
    process.env.NEXT_PUBLIC_ENABLE_INVESTMENTS = 'true';
    process.env.NEXT_PUBLIC_ENABLE_PERPS = 'false';
    searchParams = new URLSearchParams('tab=investments');
    const { InvestmentsPageClient } = await import('@/components/investments/InvestmentsPageClient');

    const html = renderToStaticMarkup(<InvestmentsPageClient />);

    expect(html).toContain('Investments Workspace');
    expect(html).toContain('Investments');
    expect(html).not.toContain('Perps (disabled)');
    expect(html).not.toContain('Get Updates on Telegram');
  });
});

