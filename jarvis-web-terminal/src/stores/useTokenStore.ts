'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface TokenInfo {
  address: string;
  name: string;
  symbol: string;
  logoURI?: string;
  poolAddress?: string;
}

interface TokenState {
  selectedToken: TokenInfo | null;
  setSelectedToken: (token: TokenInfo | null) => void;
  watchlist: string[];
  addToWatchlist: (address: string) => void;
  removeFromWatchlist: (address: string) => void;
  recentSearches: string[];
  addRecentSearch: (query: string) => void;
  clearRecentSearches: () => void;
}

const MAX_RECENT_SEARCHES = 10;

export const useTokenStore = create<TokenState>()(
  persist(
    (set) => ({
      selectedToken: null,
      setSelectedToken: (token) => set({ selectedToken: token }),

      watchlist: [],
      addToWatchlist: (address) =>
        set((state) => {
          if (state.watchlist.includes(address)) return state;
          return { watchlist: [...state.watchlist, address] };
        }),
      removeFromWatchlist: (address) =>
        set((state) => ({
          watchlist: state.watchlist.filter((a) => a !== address),
        })),

      recentSearches: [],
      addRecentSearch: (query) =>
        set((state) => {
          const filtered = state.recentSearches.filter((q) => q !== query);
          const updated = [query, ...filtered].slice(0, MAX_RECENT_SEARCHES);
          return { recentSearches: updated };
        }),
      clearRecentSearches: () => set({ recentSearches: [] }),
    }),
    {
      name: 'jarvis-token-store',
      partialize: (state) => ({
        watchlist: state.watchlist,
        recentSearches: state.recentSearches,
      }),
    }
  )
);
