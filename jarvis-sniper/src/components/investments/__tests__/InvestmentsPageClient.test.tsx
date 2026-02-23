import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams('tab=basket'),
}));

vi.mock('@/components/StatusBar', () => ({
  StatusBar: () => <div>status-bar</div>,
}));

vi.mock('@/components/EarlyBetaModal', () => ({
  EarlyBetaModal: () => <div>beta-modal</div>,
}));

vi.mock('@/components/FundRecoveryBanner', () => ({
  FundRecoveryBanner: () => <div>fund-recovery-banner</div>,
}));

vi.mock('@/components/investments/AlvaraBasketPanel', () => ({
  AlvaraBasketPanel: () => <div>basket-panel</div>,
}));

vi.mock('@/components/perps/PerpsSniperPanel', () => ({
  PerpsSniperPanel: () => <div>perps-panel</div>,
}));

vi.mock('@/lib/investments-perps-flags', () => ({
  isInvestmentsEnabled: () => true,
  isPerpsEnabled: () => true,
}));

import { InvestmentsPageClient } from '../InvestmentsPageClient';

describe('InvestmentsPageClient', () => {
  it('does not render fund recovery banner on investments page', () => {
    const markup = renderToStaticMarkup(<InvestmentsPageClient />);
    expect(markup).not.toContain('fund-recovery-banner');
  });
});
