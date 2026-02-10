'use client';

import { useEffect, useRef } from 'react';
import { useSniperStore } from '@/stores/useSniperStore';

const DEXSCREENER_TOKENS = 'https://api.dexscreener.com/tokens/v1/solana';
const POLL_INTERVAL_MS = 3000;

/**
 * Polls DexScreener batch API every 3s to update open position prices.
 * Batches up to 30 token addresses per request (DexScreener limit).
 * Updates the store's positions with currentPrice, pnlPercent, pnlSol.
 */
export function usePnlTracker() {
  const positions = useSniperStore((s) => s.positions);
  const updatePrices = useSniperStore((s) => s.updatePrices);
  const isPollingRef = useRef(false);

  useEffect(() => {
    const openPositions = positions.filter((p) => p.status === 'open');
    if (openPositions.length === 0) return;

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

        for (const batch of batches) {
          try {
            const res = await fetch(`${DEXSCREENER_TOKENS}/${batch.join(',')}`, {
              headers: { Accept: 'application/json' },
            });

            if (!res.ok) continue;

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
            // Silent — don't crash the loop on a single batch failure
          }
        }

        // Fetch current SOL price for accurate SOL-denominated P&L
        let solPriceUsd: number | undefined;
        try {
          const macroRes = await fetch('/api/macro');
          if (macroRes.ok) {
            const macroData = await macroRes.json();
            if (typeof macroData?.solPrice === 'number' && macroData.solPrice > 0) {
              solPriceUsd = macroData.solPrice;
            }
          }
        } catch {
          // SOL price unavailable — P&L will use approximation
        }

        if (Object.keys(priceMap).length > 0) {
          updatePrices(priceMap, solPriceUsd);
        }
      } finally {
        isPollingRef.current = false;
      }
    };

    // Initial fetch
    fetchPrices();

    const interval = setInterval(fetchPrices, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [positions, updatePrices]);
}
