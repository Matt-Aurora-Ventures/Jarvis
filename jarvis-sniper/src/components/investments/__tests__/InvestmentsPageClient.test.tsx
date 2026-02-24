import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { InvestmentsPageClient } from '@/components/investments/InvestmentsPageClient';

let mockQuery = 'tab=perps';
const mockResolveSurfaceAvailability = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    replace: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(mockQuery),
}));

vi.mock('@/lib/surface-availability', () => ({
  resolveSurfaceAvailability: (...args: unknown[]) => mockResolveSurfaceAvailability(...args),
  isSurfaceEnabled: (surface: { state: string }) => surface.state === 'enabled',
}));

vi.mock('@/components/StatusBar', () => ({
  StatusBar: () => React.createElement('div', { 'data-testid': 'status-bar' }),
}));

vi.mock('@/components/EarlyBetaModal', () => ({
  EarlyBetaModal: () => React.createElement('div', { 'data-testid': 'beta-modal' }),
}));

vi.mock('@/components/FundRecoveryBanner', () => ({
  FundRecoveryBanner: () => React.createElement('div', { 'data-testid': 'fund-recovery' }),
}));

vi.mock('@/components/investments/AlvaraBasketPanel', () => ({
  AlvaraBasketPanel: (props: { disabled?: boolean; disabledReason?: string }) =>
    React.createElement(
      'div',
      {
        'data-testid': 'basket-panel',
        'data-disabled': String(Boolean(props.disabled)),
        'data-reason': props.disabledReason ?? '',
      },
      'basket-panel',
    ),
}));

vi.mock('@/components/perps/PerpsSniperPanel', () => ({
  PerpsSniperPanel: (props: { disabled?: boolean; disabledReason?: string }) =>
    React.createElement(
      'div',
      {
        'data-testid': 'perps-panel',
        'data-disabled': String(Boolean(props.disabled)),
        'data-reason': props.disabledReason ?? '',
      },
      'perps-panel',
    ),
}));

describe('InvestmentsPageClient', () => {
  beforeEach(() => {
    mockResolveSurfaceAvailability.mockReset();
    mockQuery = 'tab=perps';
  });

  it('keeps both tabs visible even when one surface is disabled', () => {
    mockResolveSurfaceAvailability.mockReturnValue({
      investments: { state: 'enabled' },
      perps: { state: 'visible-disabled', reason: 'Perps disabled for rollout' },
      tradfi: { state: 'enabled' },
    });

    const html = renderToStaticMarkup(React.createElement(InvestmentsPageClient));

    expect(html).toContain('Alvara Basket');
    expect(html).toContain('Perps Sniper');
    expect(html).toContain('data-testid="perps-panel"');
    expect(html).toContain('data-disabled="true"');
    expect(html).toContain('Perps disabled for rollout');
  });

  it('still renders a panel when both surfaces are disabled', () => {
    mockQuery = 'tab=basket';
    mockResolveSurfaceAvailability.mockReturnValue({
      investments: { state: 'visible-disabled', reason: 'Investments disabled by policy' },
      perps: { state: 'visible-disabled', reason: 'Perps disabled by policy' },
      tradfi: { state: 'enabled' },
    });

    const html = renderToStaticMarkup(React.createElement(InvestmentsPageClient));

    expect(html).toContain('data-testid="basket-panel"');
    expect(html).toContain('data-disabled="true"');
    expect(html).toContain('Investments disabled by policy');
  });
});
