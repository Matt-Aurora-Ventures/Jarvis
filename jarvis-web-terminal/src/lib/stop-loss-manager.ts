'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useTradeStore, type Position } from '@/stores/useTradeStore';

// ── Constants ───────────────────────────────────────────────────────

const JUPITER_PRICE_URL = 'https://api.jup.ag/price/v3/price';

/** Polling interval in milliseconds */
const POLL_INTERVAL_MS = 10_000;

// ── Types ───────────────────────────────────────────────────────────

export interface SLTPEvent {
  type: 'stop_loss' | 'take_profit';
  positionId: string;
  tokenSymbol: string;
  entryPrice: number;
  currentPrice: number;
  changePercent: number;
}

export type SLTPCallback = (event: SLTPEvent) => void;

// ── Price Fetching ──────────────────────────────────────────────────

/**
 * Fetch current prices for a list of token mints using Jupiter Price API v3.
 *
 * Batches all mints into a single HTTP request.
 * Returns a Map from mint address to USD price.
 * On any error, returns an empty Map (never throws).
 *
 * @param mints - Array of Solana token mint addresses
 * @returns Map<mintAddress, priceUsd>
 */
export async function fetchTokenPrices(
  mints: string[]
): Promise<Map<string, number>> {
  const prices = new Map<string, number>();

  if (mints.length === 0) {
    return prices;
  }

  try {
    const idsParam = encodeURIComponent(mints.join(','));
    const url = `${JUPITER_PRICE_URL}?ids=${idsParam}`;

    const response = await fetch(url);

    if (!response.ok) {
      console.warn(`[SL/TP] Jupiter Price API returned ${response.status}`);
      return prices;
    }

    const json = await response.json();
    const data: Record<string, { price: string } | null> = json.data ?? {};

    for (const [mint, entry] of Object.entries(data)) {
      if (entry && entry.price) {
        const parsed = parseFloat(entry.price);
        if (!isNaN(parsed) && parsed > 0) {
          prices.set(mint, parsed);
        }
      }
    }
  } catch (error) {
    console.warn('[SL/TP] Failed to fetch token prices:', error);
  }

  return prices;
}

// ── Threshold Checking ──────────────────────────────────────────────

/**
 * Check a list of positions against current prices and fire SL/TP events.
 *
 * This is a pure function (no side effects beyond calling the callback and
 * mutating the triggeredSet). Extracted from the hook for testability.
 *
 * @param positions     - Array of positions to check (should be open only)
 * @param prices        - Current prices map (mint -> USD price)
 * @param triggeredSet  - Set of position IDs that have already been triggered
 *                        (mutated in place when a new trigger fires)
 * @param onTrigger     - Callback invoked for each SL/TP event
 */
export function checkPositionThresholds(
  positions: Position[],
  prices: Map<string, number>,
  triggeredSet: Set<string>,
  onTrigger: SLTPCallback
): void {
  for (const position of positions) {
    // Skip non-open positions
    if (position.status !== 'open') {
      continue;
    }

    // Skip already-triggered positions
    if (triggeredSet.has(position.id)) {
      continue;
    }

    const currentPrice = prices.get(position.tokenMint);
    if (currentPrice === undefined) {
      continue;
    }

    const changePercent =
      ((currentPrice - position.entryPrice) / position.entryPrice) * 100;

    // Check stop loss first (priority over take profit when price is very low)
    if (position.stopLossPercent !== null) {
      const slThreshold =
        position.entryPrice * (1 - position.stopLossPercent / 100);

      if (currentPrice <= slThreshold) {
        triggeredSet.add(position.id);
        onTrigger({
          type: 'stop_loss',
          positionId: position.id,
          tokenSymbol: position.tokenSymbol,
          entryPrice: position.entryPrice,
          currentPrice,
          changePercent,
        });
        continue; // Don't also check TP for this position
      }
    }

    // Check take profit
    if (position.takeProfitPercent !== null) {
      const tpThreshold =
        position.entryPrice * (1 + position.takeProfitPercent / 100);

      if (currentPrice >= tpThreshold) {
        triggeredSet.add(position.id);
        onTrigger({
          type: 'take_profit',
          positionId: position.id,
          tokenSymbol: position.tokenSymbol,
          entryPrice: position.entryPrice,
          currentPrice,
          changePercent,
        });
      }
    }
  }
}

// ── React Hook ──────────────────────────────────────────────────────

/**
 * Hook: useStopLossMonitor
 *
 * Monitors all open positions every 10 seconds. When a position's current
 * price crosses its stop-loss or take-profit threshold, the `onTrigger`
 * callback fires exactly once per position.
 *
 * The hook does NOT execute trades. The consuming component decides what
 * action to take (e.g., show a toast, execute a sell via Bags SDK, etc.).
 *
 * @param onTrigger - Called when a position crosses its SL or TP threshold
 *
 * @example
 * ```tsx
 * useStopLossMonitor((event) => {
 *   if (event.type === 'stop_loss') {
 *     toast.error(`SL triggered for ${event.tokenSymbol} at ${event.changePercent.toFixed(1)}%`);
 *   } else {
 *     toast.success(`TP hit for ${event.tokenSymbol} at +${event.changePercent.toFixed(1)}%`);
 *   }
 *   // Execute sell via Bags SDK or Jupiter ...
 * });
 * ```
 */
export function useStopLossMonitor(onTrigger: SLTPCallback): void {
  // Set of position IDs that have already fired an event.
  // Using a ref so it survives re-renders without causing them.
  const triggeredRef = useRef<Set<string>>(new Set());

  // Stable reference to the callback
  const callbackRef = useRef<SLTPCallback>(onTrigger);
  callbackRef.current = onTrigger;

  const pollPrices = useCallback(async () => {
    try {
      // Get open positions from the store (non-reactive access)
      const openPositions = useTradeStore
        .getState()
        .positions.filter((p) => p.status === 'open');

      if (openPositions.length === 0) {
        return;
      }

      // Collect unique mints
      const mints = [...new Set(openPositions.map((p) => p.tokenMint))];

      // Fetch all prices in one batch
      const prices = await fetchTokenPrices(mints);

      if (prices.size === 0) {
        return;
      }

      // Check thresholds and fire events
      checkPositionThresholds(
        openPositions,
        prices,
        triggeredRef.current,
        callbackRef.current
      );
    } catch (error) {
      console.warn('[SL/TP] Monitor poll error:', error);
    }
  }, []);

  useEffect(() => {
    // Run immediately on mount
    pollPrices();

    // Then poll every POLL_INTERVAL_MS
    const intervalId = setInterval(pollPrices, POLL_INTERVAL_MS);

    return () => {
      clearInterval(intervalId);
    };
  }, [pollPrices]);
}
