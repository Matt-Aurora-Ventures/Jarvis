'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useSniperStore } from '@/stores/useSniperStore';
import { DATA_SOURCE, PUMPFUN_PROGRAM_ID } from '@/lib/data-source-config';
import { getRpcWsUrl } from '@/lib/rpc-url';
import type { BagsGraduation } from '@/lib/bags-api';

/**
 * Secondary real-time token discovery via Helius standard WebSocket `logsSubscribe`.
 *
 * Subscribes to transaction logs mentioning the PumpFun program ID at the validator level.
 * When a "Create" instruction is detected, the mint address is extracted from the
 * base64-encoded `Program data:` log line (per Chainstack guide).
 *
 * This uses STANDARD Solana WebSocket methods — works on all Helius tiers including
 * the $49/mo Developer plan. No Enhanced WebSockets or LaserStream required.
 *
 * Feature-flagged: only active when NEXT_PUBLIC_DATA_SOURCE=logs-subscribe.
 */

const RECONNECT_BASE_MS = 3_000;
const RECONNECT_MAX_MS = 60_000;
const DEDUP_WINDOW_MS = 30_000;

/**
 * Attempt to extract a mint address from PumpFun "Create" instruction log data.
 * The `Program data:` line contains base64-encoded instruction data.
 * The mint public key (32 bytes) starts at byte offset 0 in the decoded data
 * for the PumpFun create instruction (the first account key logged in program data).
 */
function extractMintFromLogs(logs: string[]): string | null {
  const createIdx = logs.findIndex(
    (l) => l.includes('Instruction: Create') || l.includes('Program log: Create'),
  );
  if (createIdx === -1) return null;

  // Look for "Program data:" lines after the Create instruction
  for (let i = createIdx + 1; i < logs.length; i++) {
    const line = logs[i];
    if (line.startsWith('Program data:')) {
      try {
        const b64 = line.slice('Program data: '.length).trim();
        const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
        // PumpFun create log data layout: first 32 bytes are the mint public key
        if (bytes.length >= 32) {
          // Convert 32 bytes to base58 (Solana address format)
          return base58Encode(bytes.slice(0, 32));
        }
      } catch {
        // Skip unparseable data lines
      }
    }
    // Stop if we hit the next instruction
    if (line.includes('Instruction:') && i !== createIdx) break;
  }

  return null;
}

/** Minimal base58 encoder for 32-byte public keys. */
function base58Encode(bytes: Uint8Array): string {
  const ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
  const ZERO = BigInt(0);
  const BASE = BigInt(58);
  const BYTE = BigInt(256);
  let num = ZERO;
  for (const b of bytes) {
    num = num * BYTE + BigInt(b);
  }
  let str = '';
  while (num > ZERO) {
    const rem = Number(num % BASE);
    num = num / BASE;
    str = ALPHABET[rem] + str;
  }
  // Leading zeros
  for (const b of bytes) {
    if (b !== 0) break;
    str = '1' + str;
  }
  return str;
}

export function useLogsSubscribe() {
  const addGraduation = useSniperStore((s) => s.addGraduation);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef(0);
  const seenMints = useRef(new Map<string, number>());
  const isActive = DATA_SOURCE === 'logs-subscribe';

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

    const wsUrl = process.env.NEXT_PUBLIC_HELIUS_WS_URL || getRpcWsUrl();

    const connect = () => {
      cleanup();

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttempts.current = 0;
        console.log('[logs-subscribe] Connected to Helius WSS — subscribing to PumpFun logs');
        ws.send(
          JSON.stringify({
            jsonrpc: '2.0',
            id: 1,
            method: 'logsSubscribe',
            params: [
              { mentions: [PUMPFUN_PROGRAM_ID] },
              { commitment: 'processed' },
            ],
          }),
        );
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data as string);
          const logs: string[] | undefined = msg.params?.result?.value?.logs;
          if (!logs || !Array.isArray(logs)) return;

          const mint = extractMintFromLogs(logs);
          if (!mint) return;

          // Dedup
          const now = Date.now();
          if (seenMints.current.has(mint)) return;
          seenMints.current.set(mint, now);

          if (seenMints.current.size > 500) {
            for (const [m, ts] of seenMints.current) {
              if (now - ts > DEDUP_WINDOW_MS) seenMints.current.delete(m);
            }
          }

          const grad: BagsGraduation = {
            mint,
            symbol: '???',
            name: 'New Token',
            score: 50,
            graduation_time: now / 1000,
            bonding_curve_score: 0,
            holder_distribution_score: 0,
            liquidity_score: 0,
            social_score: 0,
            market_cap: 0,
            price_usd: 0,
            liquidity: 0,
            source: 'helius-logs-subscribe',
          };

          addGraduation(grad);
          console.log(`[logs-subscribe] New PumpFun token: ${mint}`);
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onerror = () => {};

      ws.onclose = () => {
        const delay = Math.min(
          RECONNECT_BASE_MS * Math.pow(2, reconnectAttempts.current),
          RECONNECT_MAX_MS,
        );
        reconnectAttempts.current += 1;
        console.warn(`[logs-subscribe] Disconnected — reconnecting in ${delay}ms`);
        reconnectTimer.current = setTimeout(connect, delay);
      };
    };

    connect();

    return cleanup;
  }, [isActive, addGraduation, cleanup]);

  return { isActive };
}
