'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useSniperStore } from '@/stores/useSniperStore';
import { DATA_SOURCE, PUMPPORTAL_WS_URL } from '@/lib/data-source-config';
import type { BagsGraduation } from '@/lib/bags-api';

/**
 * Real-time token discovery via PumpPortal WebSocket.
 *
 * Connects to wss://pumpportal.fun/api/data and subscribes to `subscribeNewToken`.
 * Each new PumpFun token is fed into the graduation store with minimal metadata.
 * DexScreener enrichment (pairs, scoring, icon) happens asynchronously via the
 * existing polling loop — this hook just ensures the token appears FAST (~1-3s
 * instead of ~30s from REST polling alone).
 *
 * Feature-flagged: only active when NEXT_PUBLIC_DATA_SOURCE=pumpportal.
 * Includes auto-reconnect with exponential backoff.
 *
 * Based on VoxForge conversation (27 Mar 2026) — this is what roostar.vercel.app uses.
 */

const RECONNECT_BASE_MS = 3_000;
const RECONNECT_MAX_MS = 60_000;
const DEDUP_WINDOW_MS = 30_000;

export function usePumpPortalStream() {
  const addGraduation = useSniperStore((s) => s.addGraduation);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef(0);
  const seenMints = useRef(new Map<string, number>());
  const isActive = DATA_SOURCE === 'pumpportal';

  const cleanup = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!isActive) return;

    const connect = () => {
      cleanup();

      const ws = new WebSocket(PUMPPORTAL_WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttempts.current = 0;
        console.log('[pump-stream] Connected to PumpPortal WSS');
        ws.send(JSON.stringify({ method: 'subscribeNewToken' }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string);

          // PumpPortal subscribeNewToken sends objects with mint, name, symbol, etc.
          const mint: string | undefined = data.mint;
          if (!mint || typeof mint !== 'string') return;

          // Dedup: skip mints seen in the last 30s
          const now = Date.now();
          if (seenMints.current.has(mint)) return;
          seenMints.current.set(mint, now);

          // Prune dedup map periodically
          if (seenMints.current.size > 500) {
            for (const [m, ts] of seenMints.current) {
              if (now - ts > DEDUP_WINDOW_MS) seenMints.current.delete(m);
            }
          }

          // Build a minimal BagsGraduation entry.
          // Required fields get safe defaults — the existing enrichment pipeline
          // (DexScreener batch fetch in /api/graduations) fills in the rest.
          const grad: BagsGraduation = {
            mint,
            symbol: data.symbol || '???',
            name: data.name || 'New Token',
            score: 50,
            graduation_time: now / 1000,
            bonding_curve_score: 0,
            holder_distribution_score: 0,
            liquidity_score: 0,
            social_score: 0,
            market_cap: 0,
            price_usd: 0,
            liquidity: 0,
            source: 'pumpportal-ws',
          };

          addGraduation(grad);
        } catch {
          // Ignore malformed messages (e.g. subscription confirmations)
        }
      };

      ws.onerror = () => {
        // onclose will fire after this — reconnect handled there
      };

      ws.onclose = () => {
        const delay = Math.min(
          RECONNECT_BASE_MS * Math.pow(2, reconnectAttempts.current),
          RECONNECT_MAX_MS,
        );
        reconnectAttempts.current += 1;
        console.warn(`[pump-stream] Disconnected — reconnecting in ${delay}ms`);
        reconnectTimer.current = setTimeout(connect, delay);
      };
    };

    connect();

    return cleanup;
  }, [isActive, addGraduation, cleanup]);

  return { isActive };
}
