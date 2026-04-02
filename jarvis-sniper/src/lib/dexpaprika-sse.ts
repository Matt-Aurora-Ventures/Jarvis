/**
 * DexPaprika SSE reader using fetch + ReadableStream.
 *
 * Uses the POST endpoint to subscribe to multiple tokens in a single connection.
 * SSE via POST can't use native EventSource (GET only), so we parse the
 * text/event-stream format manually from the response body.
 *
 * Security: read-only public data, no API key, no authentication.
 */

import { DEXPAPRIKA_STREAM_URL } from './price-stream-config';

export interface DexPaprikaPriceEvent {
  /** Token mint address */
  address: string;
  /** USD price */
  priceUsd: number;
  /** Event timestamp (unix seconds) */
  timestamp: number;
}

export type PriceCallback = (event: DexPaprikaPriceEvent) => void;
export type StatusCallback = (status: 'connected' | 'disconnected' | 'reconnecting', error?: string) => void;

interface StreamHandle {
  close: () => void;
  updateMints: (mints: string[]) => void;
}

const RECONNECT_BASE_MS = 3_000;
const RECONNECT_MAX_MS = 60_000;

/**
 * Start a DexPaprika SSE stream for the given token mints.
 * Returns a handle to close or update the subscription.
 */
export function startDexPaprikaStream(
  mints: string[],
  onPrice: PriceCallback,
  onStatus?: StatusCallback,
): StreamHandle {
  let controller: AbortController | null = null;
  let currentMints = [...mints];
  let reconnectAttempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  function connect() {
    if (closed || currentMints.length === 0) return;

    controller = new AbortController();
    onStatus?.('reconnecting', reconnectAttempts > 0 ? `attempt ${reconnectAttempts}` : undefined);

    const body = currentMints.map((address) => ({
      chain: 'solana',
      address,
      method: 't_p',
    }));

    fetch(DEXPAPRIKA_STREAM_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok || !res.body) {
          throw new Error(`DexPaprika ${res.status}`);
        }

        reconnectAttempts = 0;
        onStatus?.('connected');

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done || closed) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE: lines separated by \n, events separated by \n\n
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete last line

          for (const line of lines) {
            if (!line.startsWith('data:')) continue;
            const json = line.slice(5).trim();
            if (!json) continue;

            try {
              const data = JSON.parse(json);
              // DexPaprika format: { a: address, c: chain, p: price_string, t: timestamp }
              const address = data.a || data.address;
              const price = parseFloat(data.p || data.price || '0');
              const ts = data.t_p || data.t || Math.floor(Date.now() / 1000);

              if (address && price > 0) {
                onPrice({ address, priceUsd: price, timestamp: ts });
              }
            } catch {
              // Skip malformed events
            }
          }
        }
      })
      .catch((err) => {
        if (closed) return;
        const msg = err instanceof Error ? err.message : 'Unknown error';
        if (msg === 'The user aborted a request.' || msg.includes('abort')) return;
        onStatus?.('disconnected', msg);
        scheduleReconnect();
      });
  }

  function scheduleReconnect() {
    if (closed) return;
    const delay = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, reconnectAttempts),
      RECONNECT_MAX_MS,
    );
    reconnectAttempts++;
    reconnectTimer = setTimeout(connect, delay);
  }

  function close() {
    closed = true;
    controller?.abort();
    controller = null;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  function updateMints(newMints: string[]) {
    const sorted = [...newMints].sort();
    const prevSorted = [...currentMints].sort();
    if (sorted.join(',') === prevSorted.join(',')) return;

    currentMints = [...newMints];
    // Reconnect with new subscription
    controller?.abort();
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    reconnectAttempts = 0;
    if (currentMints.length > 0) {
      connect();
    }
  }

  // Initial connect
  if (mints.length > 0) connect();

  return { close, updateMints };
}
