import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { useSniperStore } from '@/stores/useSniperStore';

vi.mock('@/hooks/usePhantomWallet', () => ({
  usePhantomWallet: () => ({
    connected: false,
    connecting: false,
    connect: vi.fn(),
    address: null,
    signTransaction: vi.fn(),
    signMessage: vi.fn(),
    publicKey: null,
  }),
}));

vi.mock('@/hooks/useSnipeExecutor', () => ({
  useSnipeExecutor: () => ({
    snipe: vi.fn(),
    ready: false,
  }),
}));

vi.mock('@/lib/session-wallet', () => ({
  buildFundSessionTx: vi.fn(),
  createSessionWallet: vi.fn(),
  destroySessionWallet: vi.fn(),
  deriveDeterministicSessionWallet: vi.fn(),
  downloadSessionKeyByPubkey: vi.fn(),
  exportSessionKeyAsFile: vi.fn(),
  getDeterministicSessionWalletMessage: vi.fn(),
  getSessionBalance: vi.fn(async () => 0),
  importSessionWalletSecretKey: vi.fn(),
  isLikelyFunded: vi.fn(() => false),
  listStoredSessionWallets: vi.fn(() => []),
  loadSessionWalletByPublicKey: vi.fn(async () => null),
  loadSessionWalletFromStorage: vi.fn(async () => null),
  recoverSessionWalletFromAnyStorage: vi.fn(async () => null),
  sweepToMainWalletAndCloseTokenAccounts: vi.fn(),
}));

vi.mock('@/lib/session-wallet-security', () => ({
  getSessionWalletCreationMode: () => 'direct',
}));

vi.mock('@/lib/position-scope', () => ({
  filterOpenPositionsForActiveWallet: (positions: any[]) => positions,
  filterTradeManagedOpenPositionsForActiveWallet: (positions: any[]) => positions,
  resolveActiveWallet: () => null,
}));

vi.mock('@/lib/rpc-url', () => ({
  getConnection: vi.fn(),
}));

vi.mock('@/lib/tx-confirmation', () => ({
  waitForSignatureStatus: vi.fn(),
}));

vi.mock('@/lib/wallet-deeplinks', () => ({
  isProbablyMobile: () => false,
}));

describe('SniperControls strategy trust surface', () => {
  beforeEach(() => {
    useSniperStore.getState().resetSession();
    useSniperStore.setState({
      activePreset: 'pump_fresh_tight',
      assetFilter: 'memecoin',
      graduations: [],
      backtestMeta: {
        pump_fresh_tight: {
          winRate: '73%',
          trades: 1800,
          totalTrades: 1800,
          backtested: true,
          dataSource: 'mixed',
          underperformer: false,
          winRatePct: 73,
          winRateLower95Pct: 71.2,
          winRateUpper95Pct: 75.4,
          netPnlPct: 14.2,
          profitFactorValue: 1.31,
        },
      },
    });
  });

  it('does not render losing or unverified badges in the default picker surface', async () => {
    const { SniperControls } = await import('@/components/SniperControls');

    const html = renderToStaticMarkup(<SniperControls />);

    expect(html).not.toContain('Losing');
    expect(html).not.toContain('Unverified');
  });
});
