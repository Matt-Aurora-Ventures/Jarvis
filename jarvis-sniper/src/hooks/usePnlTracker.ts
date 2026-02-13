'use client';

import { useEffect, useRef } from 'react';
import { useSniperStore } from '@/stores/useSniperStore';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';
import { filterOpenPositionsForActiveWallet, resolveActiveWallet } from '@/lib/position-scope';

const DEXSCREENER_TOKENS = 'https://api.dexscreener.com/tokens/v1/solana';
const POLL_INTERVAL_MS = 3000;
const MAX_CONSECUTIVE_ERRORS = 10;
const BASE_BACKOFF_MS = 3_000;

/**
 * Polls DexScreener batch API every 3s to update open position prices.
 * Batches up to 30 token addresses per request (DexScreener limit).
 * Updates the store's positions with currentPrice, pnlPercent, pnlSol.
 */
export function usePnlTracker() {
  const { address } = usePhantomWallet();
  const positions = useSniperStore((s) => s.positions);
  const tradeSignerMode = useSniperStore((s) => s.tradeSignerMode);
  const sessionWalletPubkey = useSniperStore((s) => s.sessionWalletPubkey);
  const updatePrices = useSniperStore((s) => s.updatePrices);
  const isPollingRef = useRef(false);
  const errorCountRef = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const activeWallet = resolveActiveWallet(tradeSignerMode, sessionWalletPubkey, address);
    const openPositions = filterOpenPositionsForActiveWallet(positions, activeWallet);
    if (openPositions.length === 0) return;

    let mounted = true;

    const fetchPrices = async () => {
      if (isPollingRef.current) return;
      isPollingRef.current = true;

      try {
        // Deduplicate mints
        const mints = [...new Set(openPositions.map((p) => p.mint))];

        // DexScreener supports up to 30 addresses per call
        const batches: string[][] = [];
        for (let i = 0; i < mints.length; i += 30) {
          batches.push(mints.slice(i, i + 30));
        }

        const priceMap: Record<string, number> = {};
        let batchErrors = 0;

        for (const batch of batches) {
          try {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 8_000); // 8s timeout
            const res = await fetch(`${DEXSCREENER_TOKENS}/${batch.join(',')}`, {
              headers: { Accept: 'application/json' },
              signal: controller.signal,
            });
            clearTimeout(timer);

            if (!res.ok) {
              batchErrors++;
              continue;
            }

            const pairs: any[] = await res.json();

            // Group by baseToken.address, pick pair with highest liquidity
            const bestPair = new Map<string, any>();
            for (const pair of pairs) {
              const mint = pair.baseToken?.address;
              if (!mint) continue;
              const liq = parseFloat(pair.liquidity?.usd || '0');
              const existing = bestPair.get(mint);
              if (!existing || liq > (existing._liq || 0)) {
                bestPair.set(mint, { ...pair, _liq: liq });
              }
            }

            for (const [mint, pair] of bestPair) {
              const price = parseFloat(pair.priceUsd || '0');
              if (price > 0) {
                priceMap[mint] = price;
              }
            }
          } catch {
            batchErrors++;
            // Silent -- don't crash the loop on a single batch failure
          }
        }

        // Fetch current SOL price for accurate SOL-denominated P&L
        let solPriceUsd: number | undefined;
        try {
          const controller = new AbortController();
          const timer = setTimeout(() => controller.abort(), 5_000);
          const macroRes = await fetch('/api/macro', { signal: controller.signal });
          clearTimeout(timer);
          if (macroRes.ok) {
            const macroData = await macroRes.json();
            if (typeof macroData?.solPrice === 'number' && macroData.solPrice > 0) {
              solPriceUsd = macroData.solPrice;
            }
          }
        } catch {
          // SOL price unavailable -- P&L will use approximation
        }

        if (Object.keys(priceMap).length > 0) {
          updatePrices(priceMap, solPriceUsd);
          errorCountRef.current = 0; // Reset on success
        } else if (batchErrors > 0) {
          errorCountRef.current = Math.min(errorCountRef.current + 1, MAX_CONSECUTIVE_ERRORS);
          console.warn(
            `[usePnlTracker] All batches failed (${errorCountRef.current}/${MAX_CONSECUTIVE_ERRORS})`,
          );
        }
      } finally {
        isPollingRef.current = false;
      }

      // Schedule next poll with exponential backoff on consecutive errors
      if (!mounted) return;
      const backoff = errorCountRef.current > 0
        ? Math.min(BASE_BACKOFF_MS * Math.pow(2, errorCountRef.current - 1), POLL_INTERVAL_MS * 10)
        : POLL_INTERVAL_MS;
      timeoutRef.current = setTimeout(fetchPrices, backoff);
    };

    // Initial fetch
    fetchPrices();

    return () => {
      mounted = false;
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [positions, updatePrices, address, tradeSignerMode, sessionWalletPubkey]);
}
