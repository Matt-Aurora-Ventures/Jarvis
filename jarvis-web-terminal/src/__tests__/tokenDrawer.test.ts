import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { useTokenStore, type TokenInfo } from '@/stores/useTokenStore';
import { ToastProvider } from '@/components/ui/Toast';

// Mock wallet adapter so QuickBuyWidget doesn't blow up
vi.mock('@solana/wallet-adapter-react', () => ({
  useWallet: () => ({
    publicKey: null,
    signTransaction: vi.fn(),
    connected: false,
  }),
}));

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const MOCK_TOKEN: TokenInfo = {
  address: 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
  name: 'Bonk',
  symbol: 'BONK',
  logoURI: 'https://example.com/bonk.png',
  poolAddress: 'some-bonk-pool-address',
};

const MOCK_DEX_RESPONSE = {
  pairs: [
    {
      baseToken: { symbol: 'BONK', name: 'Bonk' },
      priceUsd: '0.00002345',
      priceChange: { h24: 12.5 },
      volume: { h24: 5000000 },
      fdv: 1500000000,
      liquidity: { usd: 8000000 },
    },
  ],
};

// ---------------------------------------------------------------------------
// Mock fetch globally
// ---------------------------------------------------------------------------

const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock clipboard API
const mockClipboard = {
  writeText: vi.fn().mockResolvedValue(undefined),
};
Object.defineProperty(navigator, 'clipboard', {
  value: mockClipboard,
  writable: true,
  configurable: true,
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TokenDrawer', () => {
  let TokenDrawer: React.ComponentType;

  beforeEach(async () => {
    // Reset token store
    useTokenStore.setState({
      selectedToken: null,
      watchlist: [],
      recentSearches: [],
    });

    // Reset fetch mock
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => MOCK_DEX_RESPONSE,
    });

    // Reset clipboard mock
    mockClipboard.writeText.mockReset();
    mockClipboard.writeText.mockResolvedValue(undefined);

    // Dynamic import to get fresh module
    const mod = await import('@/components/features/TokenDrawer');
    TokenDrawer = mod.TokenDrawer;
  });

  afterEach(() => {
    cleanup();
  });

  // ---- Visibility ----

  describe('visibility', () => {
    it('should be hidden by default when no selectedToken', () => {
      render(React.createElement(ToastProvider, null, React.createElement(TokenDrawer)));

      // The overlay should not be present when drawer is closed
      const overlay = document.querySelector('[data-testid="token-drawer-overlay"]');
      expect(overlay).toBeNull();
    });

    it('should open when selectedToken is set', async () => {
      render(React.createElement(ToastProvider, null, React.createElement(TokenDrawer)));

      // Set a selected token
      useTokenStore.getState().setSelectedToken(MOCK_TOKEN);

      await waitFor(() => {
        const drawer = document.querySelector('[data-testid="token-drawer"]');
        expect(drawer).not.toBeNull();
      });
    });
  });

  // ---- Close behavior ----

  describe('close behavior', () => {
    it('should close when close button is clicked', async () => {
      render(React.createElement(ToastProvider, null, React.createElement(TokenDrawer)));

      // Open the drawer
      useTokenStore.getState().setSelectedToken(MOCK_TOKEN);

      await waitFor(() => {
        expect(document.querySelector('[data-testid="token-drawer"]')).not.toBeNull();
      });

      // Click close button
      const closeBtn = document.querySelector('[data-testid="token-drawer-close"]');
      expect(closeBtn).not.toBeNull();
      fireEvent.click(closeBtn!);

      await waitFor(() => {
        const overlay = document.querySelector('[data-testid="token-drawer-overlay"]');
        expect(overlay).toBeNull();
      });
    });

    it('should close when Escape key is pressed', async () => {
      render(React.createElement(ToastProvider, null, React.createElement(TokenDrawer)));

      // Open the drawer
      useTokenStore.getState().setSelectedToken(MOCK_TOKEN);

      await waitFor(() => {
        expect(document.querySelector('[data-testid="token-drawer"]')).not.toBeNull();
      });

      // Press Escape
      fireEvent.keyDown(document, { key: 'Escape' });

      await waitFor(() => {
        const overlay = document.querySelector('[data-testid="token-drawer-overlay"]');
        expect(overlay).toBeNull();
      });
    });

    it('should close when overlay is clicked', async () => {
      render(React.createElement(ToastProvider, null, React.createElement(TokenDrawer)));

      // Open the drawer
      useTokenStore.getState().setSelectedToken(MOCK_TOKEN);

      await waitFor(() => {
        expect(document.querySelector('[data-testid="token-drawer-overlay"]')).not.toBeNull();
      });

      // Click overlay
      const overlay = document.querySelector('[data-testid="token-drawer-overlay"]');
      fireEvent.click(overlay!);

      await waitFor(() => {
        const overlayAfter = document.querySelector('[data-testid="token-drawer-overlay"]');
        expect(overlayAfter).toBeNull();
      });
    });
  });

  // ---- Content ----

  describe('content', () => {
    it('should display the token symbol and name', async () => {
      render(React.createElement(ToastProvider, null, React.createElement(TokenDrawer)));

      useTokenStore.getState().setSelectedToken(MOCK_TOKEN);

      await waitFor(() => {
        expect(screen.getByText('BONK')).toBeTruthy();
        expect(screen.getByText('Bonk')).toBeTruthy();
      });
    });

    it('should render the Jupiter swap link with correct URL', async () => {
      render(React.createElement(ToastProvider, null, React.createElement(TokenDrawer)));

      useTokenStore.getState().setSelectedToken(MOCK_TOKEN);

      await waitFor(() => {
        const jupiterLink = document.querySelector('[data-testid="jupiter-swap-link"]');
        expect(jupiterLink).not.toBeNull();
        expect(jupiterLink?.getAttribute('href')).toBe(
          `https://jup.ag/swap/SOL-${MOCK_TOKEN.address}`
        );
      });
    });

    it('should render external links that open in new tabs', async () => {
      render(React.createElement(ToastProvider, null, React.createElement(TokenDrawer)));

      useTokenStore.getState().setSelectedToken(MOCK_TOKEN);

      await waitFor(() => {
        const externalLinks = document.querySelectorAll('a[target="_blank"]');
        expect(externalLinks.length).toBeGreaterThan(0);
      });
    });
  });

  // ---- Copy functionality ----

  describe('copy address', () => {
    it('should copy token address to clipboard when clicked', async () => {
      render(React.createElement(ToastProvider, null, React.createElement(TokenDrawer)));

      useTokenStore.getState().setSelectedToken(MOCK_TOKEN);

      await waitFor(() => {
        expect(document.querySelector('[data-testid="copy-address"]')).not.toBeNull();
      });

      const copyBtn = document.querySelector('[data-testid="copy-address"]');
      fireEvent.click(copyBtn!);

      await waitFor(() => {
        expect(mockClipboard.writeText).toHaveBeenCalledWith(MOCK_TOKEN.address);
      });
    });
  });

  // ---- DexScreener fetch ----

  describe('DexScreener data', () => {
    it('should fetch DexScreener data when token is selected', async () => {
      render(React.createElement(ToastProvider, null, React.createElement(TokenDrawer)));

      useTokenStore.getState().setSelectedToken(MOCK_TOKEN);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining(MOCK_TOKEN.address)
        );
      });
    });
  });
});
