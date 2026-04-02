'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useSniperStore } from '@/stores/useSniperStore';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';
import { filterOpenPositionsForActiveWallet, resolveActiveWallet } from '@/lib/position-scope';
import { startDexPaprikaStream, type DexPaprikaPriceEvent } from '@/lib/dexpaprika-sse';
import { PRICE_STREAM_MODE } from '@/lib/price-stream-config';

/**
 * Real-time P&L price updates via DexPaprika SSE (free, ~1s latency).
 *
 * Subscribes to SSE price events for all open position mints.
 * Feeds prices into the Zustand store (same `updatePrices` path as usePnlTracker).
 * Also forwards prices to the risk worker via `workerRef` for immediate trigger computation.
 * When active, usePnlTracker slows its REST polling to 15s (fallback only).
 *
 * Feature-flagged: only active when NEXT_PUBLIC_PRICE_STREAM=dexpaprika (default).
 */
export function useDexPaprikaStream(
  workerRef?: React.RefObject<Worker | null>,
): { isActive: boolean; connected: boolean } {
  const { address } = usePhantomWallet();
  const positions = useSniperStore((s) => s.positions);
  const tradeSignerMode = useSniperStore((s) => s.tradeSignerMode);
  const sessionWalletPubkey = useSniperStore((s) => s.sessionWalletPubkey);
  const updatePrices = useSniperStore((s) => s.updatePrices);

  const isActive = PRICE_STREAM_MODE === 'dexpaprika';
  const connectedRef = useRef(false);
  const streamRef = useRef<ReturnType<typeof startDexPaprikaStream> | null>(null);

  // Buffer prices and flush to store every 500ms to avoid excessive re-renders
  const priceBufferRef = useRef<Record<string, number>>({});
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flushPrices = useCallback(() => {
    const buf = priceBufferRef.current;
    if (Object.keys(buf).length === 0) return;
    const snapshot = { ...buf };
    priceBufferRef.current = {};

    // Update Zustand store (drives UI)
    updatePrices(snapshot);

    // Forward to risk worker for immediate trigger computation
    workerRef?.current?.postMessage({ type: 'PRICE_INJECT', prices: snapshot });
  }, [updatePrices, workerRef]);

  const handlePrice = useCallback((event: DexPaprikaPriceEvent) => {
    priceBufferRef.current[event.address] = event.priceUsd;

    // Debounced flush: batch updates every 500ms
    if (!flushTimerRef.current) {
      flushTimerRef.current = setTimeout(() => {
        flushTimerRef.current = null;
        flushPrices();
      }, 500);
    }
  }, [flushPrices]);

  useEffect(() => {
    if (!isActive) return;

    const activeWallet = resolveActiveWallet(tradeSignerMode, sessionWalletPubkey, address);
    const openPositions = filterOpenPositionsForActiveWallet(positions, activeWallet);
    const mints = [...new Set(openPositions.map((p) => p.mint))];

    if (mints.length === 0) {
      // No positions — close any existing stream
      streamRef.current?.close();
      streamRef.current = null;
      connectedRef.current = false;
      return;
    }

    // If stream exists, just update the mint list
    if (streamRef.current) {
      streamRef.current.updateMints(mints);
      return;
    }

    // Create new stream
    streamRef.current = startDexPaprikaStream(
      mints,
      handlePrice,
      (status) => {
        connectedRef.current = status === 'connected';
        if (status === 'connected') {
          console.log(`[dexpaprika] Connected — streaming ${mints.length} token prices`);
        } else if (status === 'disconnected') {
          console.warn('[dexpaprika] Disconnected — REST fallback active');
        }
      },
    );

    return () => {
      streamRef.current?.close();
      streamRef.current = null;
      connectedRef.current = false;
      if (flushTimerRef.current) {
        clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
      // Flush any remaining buffered prices
      flushPrices();
    };
  }, [isActive, positions, address, tradeSignerMode, sessionWalletPubkey, handlePrice, flushPrices]);

  return { isActive, connected: connectedRef.current };
}
