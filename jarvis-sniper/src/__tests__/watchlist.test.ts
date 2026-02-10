import { describe, it, expect, beforeEach } from 'vitest';
import { useSniperStore } from '@/stores/useSniperStore';

// ────────────────────────────────────────────────────────────────
// Test Suite: Watchlist Feature
//
// Tests the watchlist state in useSniperStore:
//   1. Initial state is an empty array
//   2. addToWatchlist adds a mint
//   3. addToWatchlist is idempotent (no duplicates)
//   4. removeFromWatchlist removes a mint
//   5. removeFromWatchlist is safe on missing mints
//   6. resetSession clears the watchlist
// ────────────────────────────────────────────────────────────────

describe('Watchlist Store', () => {
  beforeEach(() => {
    useSniperStore.getState().resetSession();
  });

  it('should have an empty watchlist by default', () => {
    const state = useSniperStore.getState();
    expect(state.watchlist).toBeDefined();
    expect(Array.isArray(state.watchlist)).toBe(true);
    expect(state.watchlist.length).toBe(0);
  });

  it('should add a token mint to the watchlist', () => {
    const mint = 'So11111111111111111111111111111111111111112';

    useSniperStore.getState().addToWatchlist(mint);
    const state = useSniperStore.getState();

    expect(state.watchlist).toContain(mint);
    expect(state.watchlist.length).toBe(1);
  });

  it('should not add duplicate mints to the watchlist', () => {
    const mint = 'So11111111111111111111111111111111111111112';

    useSniperStore.getState().addToWatchlist(mint);
    useSniperStore.getState().addToWatchlist(mint);
    const state = useSniperStore.getState();

    expect(state.watchlist.length).toBe(1);
  });

  it('should add multiple different mints', () => {
    const mint1 = 'So11111111111111111111111111111111111111112';
    const mint2 = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v';
    const mint3 = '7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs';

    useSniperStore.getState().addToWatchlist(mint1);
    useSniperStore.getState().addToWatchlist(mint2);
    useSniperStore.getState().addToWatchlist(mint3);
    const state = useSniperStore.getState();

    expect(state.watchlist.length).toBe(3);
    expect(state.watchlist).toContain(mint1);
    expect(state.watchlist).toContain(mint2);
    expect(state.watchlist).toContain(mint3);
  });

  it('should remove a token mint from the watchlist', () => {
    const mint1 = 'So11111111111111111111111111111111111111112';
    const mint2 = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v';

    useSniperStore.getState().addToWatchlist(mint1);
    useSniperStore.getState().addToWatchlist(mint2);
    useSniperStore.getState().removeFromWatchlist(mint1);
    const state = useSniperStore.getState();

    expect(state.watchlist.length).toBe(1);
    expect(state.watchlist).not.toContain(mint1);
    expect(state.watchlist).toContain(mint2);
  });

  it('should not throw when removing a mint that is not in the watchlist', () => {
    const mint = 'So11111111111111111111111111111111111111112';

    expect(() => {
      useSniperStore.getState().removeFromWatchlist(mint);
    }).not.toThrow();

    expect(useSniperStore.getState().watchlist.length).toBe(0);
  });

  it('should clear the watchlist on resetSession', () => {
    const mint = 'So11111111111111111111111111111111111111112';

    useSniperStore.getState().addToWatchlist(mint);
    expect(useSniperStore.getState().watchlist.length).toBe(1);

    useSniperStore.getState().resetSession();
    expect(useSniperStore.getState().watchlist.length).toBe(0);
  });
});
