import { describe, it, expect, beforeEach } from 'vitest';
import { useTokenStore, type TokenInfo } from '@/stores/useTokenStore';
import { POOLS } from '@/lib/chart-data';

// ---------------------------------------------------------------------------
// Constants used across tests
// ---------------------------------------------------------------------------

const SOL_POOL = '58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2';

const DEFAULT_SOL_TOKEN: TokenInfo = {
  address: 'So11111111111111111111111111111111111111112',
  name: 'Solana',
  symbol: 'SOL',
  poolAddress: SOL_POOL,
};

const MOCK_CUSTOM_TOKEN: TokenInfo = {
  address: 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
  name: 'Bonk',
  symbol: 'BONK',
  poolAddress: 'some-bonk-pool-address',
};

// ---------------------------------------------------------------------------
// Helper: derives pool address and symbol from the store state,
// mirroring the logic that page.tsx should implement.
// ---------------------------------------------------------------------------

function getActiveTokenData(selectedToken: TokenInfo | null): {
  poolAddress: string;
  tokenSymbol: string;
  isCustomToken: boolean;
} {
  if (!selectedToken) {
    return { poolAddress: SOL_POOL, tokenSymbol: 'SOL', isCustomToken: false };
  }

  // Check if the selected token matches one of the predefined markets
  const knownMarkets = Object.entries(POOLS);
  const matchedMarket = knownMarkets.find(
    ([, pool]) => pool === selectedToken.poolAddress,
  );

  return {
    poolAddress: selectedToken.poolAddress ?? SOL_POOL,
    tokenSymbol: selectedToken.symbol,
    isCustomToken: !matchedMarket,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Token Selection Wiring', () => {
  beforeEach(() => {
    // Reset token store to initial state
    useTokenStore.setState({
      selectedToken: null,
      watchlist: [],
      recentSearches: [],
    });
  });

  // ---- Store behavior ----

  describe('useTokenStore defaults', () => {
    it('should default selectedToken to null', () => {
      const state = useTokenStore.getState();
      expect(state.selectedToken).toBeNull();
    });

    it('should set a selected token', () => {
      useTokenStore.getState().setSelectedToken(MOCK_CUSTOM_TOKEN);
      const state = useTokenStore.getState();
      expect(state.selectedToken).toEqual(MOCK_CUSTOM_TOKEN);
    });

    it('should clear selected token when set to null', () => {
      useTokenStore.getState().setSelectedToken(MOCK_CUSTOM_TOKEN);
      useTokenStore.getState().setSelectedToken(null);
      const state = useTokenStore.getState();
      expect(state.selectedToken).toBeNull();
    });
  });

  // ---- Derived token data (mirroring page.tsx logic) ----

  describe('getActiveTokenData helper', () => {
    it('should default to SOL pool when no token is selected', () => {
      const result = getActiveTokenData(null);
      expect(result.poolAddress).toBe(SOL_POOL);
      expect(result.tokenSymbol).toBe('SOL');
      expect(result.isCustomToken).toBe(false);
    });

    it('should use the custom token pool when a token is selected', () => {
      const result = getActiveTokenData(MOCK_CUSTOM_TOKEN);
      expect(result.poolAddress).toBe('some-bonk-pool-address');
      expect(result.tokenSymbol).toBe('BONK');
      expect(result.isCustomToken).toBe(true);
    });

    it('should recognize known markets (SOL) as non-custom', () => {
      const result = getActiveTokenData(DEFAULT_SOL_TOKEN);
      expect(result.poolAddress).toBe(SOL_POOL);
      expect(result.tokenSymbol).toBe('SOL');
      expect(result.isCustomToken).toBe(false);
    });

    it('should recognize ETH as a known market', () => {
      const ethToken: TokenInfo = {
        address: 'eth-address',
        name: 'Ethereum',
        symbol: 'ETH',
        poolAddress: POOLS.ETH,
      };
      const result = getActiveTokenData(ethToken);
      expect(result.isCustomToken).toBe(false);
      expect(result.tokenSymbol).toBe('ETH');
    });

    it('should fallback to SOL pool if selectedToken has no poolAddress', () => {
      const tokenWithoutPool: TokenInfo = {
        address: 'some-address',
        name: 'Unknown',
        symbol: 'UNK',
        // no poolAddress
      };
      const result = getActiveTokenData(tokenWithoutPool);
      expect(result.poolAddress).toBe(SOL_POOL);
    });
  });

  // ---- Chart-data pool address mapping ----

  describe('POOLS mapping from chart-data', () => {
    it('should have SOL pool address', () => {
      expect(POOLS.SOL).toBe(SOL_POOL);
    });

    it('should have ETH pool address', () => {
      expect(POOLS.ETH).toBe('AU971DrPyhhrpRnmEBp5pDTWL2ny7nofb5vYBjDJkR2E');
    });

    it('should have BTC pool address', () => {
      expect(POOLS.BTC).toBe('55BrDTCLWayM16GwrMEQU57o4PTm6ceF9wavSdNZcEiy');
    });
  });

  // ---- Integration: selecting a token updates derived pool + symbol ----

  describe('end-to-end token selection flow', () => {
    it('should produce correct derived data after selecting a custom token', () => {
      // 1. User selects BONK via TokenSearch
      useTokenStore.getState().setSelectedToken(MOCK_CUSTOM_TOKEN);

      // 2. page.tsx reads the store and derives values
      const selected = useTokenStore.getState().selectedToken;
      const derived = getActiveTokenData(selected);

      // 3. These values get passed to PriceChart and AITradeSignals
      expect(derived.poolAddress).toBe('some-bonk-pool-address');
      expect(derived.tokenSymbol).toBe('BONK');
    });

    it('should revert to SOL defaults when token is deselected', () => {
      useTokenStore.getState().setSelectedToken(MOCK_CUSTOM_TOKEN);
      useTokenStore.getState().setSelectedToken(null);

      const selected = useTokenStore.getState().selectedToken;
      const derived = getActiveTokenData(selected);

      expect(derived.poolAddress).toBe(SOL_POOL);
      expect(derived.tokenSymbol).toBe('SOL');
    });
  });
});

// ---------------------------------------------------------------------------
// Tests for chart-data.ts new fetchOHLCVByPool function
// ---------------------------------------------------------------------------

describe('chart-data fetchOHLCVByPool', () => {
  it('should export a fetchOHLCVByPool function', async () => {
    const chartData = await import('@/lib/chart-data');
    expect(typeof chartData.fetchOHLCVByPool).toBe('function');
  });

  it('should export a fetchCurrentPriceByPool function', async () => {
    const chartData = await import('@/lib/chart-data');
    expect(typeof chartData.fetchCurrentPriceByPool).toBe('function');
  });
});
