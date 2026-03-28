import { Connection, type SignatureStatus } from '@solana/web3.js';

export type PendingState = 'settling' | 'confirmed' | 'failed' | 'unresolved';

export interface SignatureStatusResult {
  state: PendingState;
  error?: string;
  confirmationStatus?: string | null;
  slot?: number | null;
}

const DEFAULT_MAX_WAIT_MS = 30_000;
const DEFAULT_POLL_MS = 2_500;

function toResult(status: SignatureStatus | null): SignatureStatusResult {
  if (!status) {
    return { state: 'settling' };
  }

  if (status.err) {
    return {
      state: 'failed',
      error: typeof status.err === 'string' ? status.err : JSON.stringify(status.err),
      confirmationStatus: status.confirmationStatus ?? null,
      slot: status.slot ?? null,
    };
  }

  const c = status.confirmationStatus ?? null;
  if (c === 'confirmed' || c === 'finalized') {
    return {
      state: 'confirmed',
      confirmationStatus: c,
      slot: status.slot ?? null,
    };
  }

  return {
    state: 'settling',
    confirmationStatus: c,
    slot: status.slot ?? null,
  };
}

export function mapRpcStatusToPendingState(status: SignatureStatus | null): SignatureStatusResult {
  return toResult(status);
}

/**
 * Race a WebSocket `signatureSubscribe` against HTTP polling for faster confirmation.
 * The WSS subscription pushes confirmation status ~400ms vs 2.5s poll intervals.
 * If WSS fails to connect, polling continues as the sole mechanism.
 */
function raceSignatureSubscribe(
  signature: string,
  maxWaitMs: number,
): { promise: Promise<SignatureStatusResult | null>; cancel: () => void } {
  let ws: WebSocket | null = null;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  let cancelled = false;

  // Use the same WS URL the Connection would use
  const wsUrl =
    typeof window !== 'undefined'
      ? (process.env.NEXT_PUBLIC_SOLANA_WS ||
          process.env.NEXT_PUBLIC_SOLANA_RPC?.replace('https://', 'wss://').replace('http://', 'ws://') ||
          'wss://api.mainnet-beta.solana.com')
      : '';

  const promise = new Promise<SignatureStatusResult | null>((resolve) => {
    if (!wsUrl || typeof WebSocket === 'undefined') {
      resolve(null); // No WSS available, let polling handle it
      return;
    }

    try {
      ws = new WebSocket(wsUrl);
    } catch {
      resolve(null);
      return;
    }

    timeoutId = setTimeout(() => {
      resolve(null);
      ws?.close();
    }, maxWaitMs);

    ws.onopen = () => {
      if (cancelled) { ws?.close(); return; }
      ws?.send(
        JSON.stringify({
          jsonrpc: '2.0',
          id: 1,
          method: 'signatureSubscribe',
          params: [signature, { commitment: 'confirmed' }],
        }),
      );
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string);
        // Subscription confirmation — ignore
        if (msg.result !== undefined && !msg.params) return;
        // Actual notification
        const value = msg.params?.result?.value;
        if (value !== undefined) {
          if (value?.err) {
            resolve({
              state: 'failed',
              error: typeof value.err === 'string' ? value.err : JSON.stringify(value.err),
            });
          } else {
            resolve({ state: 'confirmed', confirmationStatus: 'confirmed' });
          }
          ws?.close();
        }
      } catch {
        // Ignore malformed
      }
    };

    ws.onerror = () => {
      resolve(null); // Let polling handle it
      ws?.close();
    };

    ws.onclose = () => {
      if (!cancelled) resolve(null);
    };
  });

  const cancel = () => {
    cancelled = true;
    if (timeoutId) clearTimeout(timeoutId);
    ws?.close();
  };

  return { promise, cancel };
}

export async function waitForSignatureStatus(
  connection: Connection,
  signature: string,
  options?: {
    maxWaitMs?: number;
    pollMs?: number;
  },
): Promise<SignatureStatusResult> {
  const maxWaitMs = Math.max(1_000, options?.maxWaitMs ?? DEFAULT_MAX_WAIT_MS);
  const pollMs = Math.max(500, options?.pollMs ?? DEFAULT_POLL_MS);

  // Start WSS subscription race (non-blocking — resolves null if WSS unavailable)
  const wssRace = raceSignatureSubscribe(signature, maxWaitMs);

  // Polling loop (existing behavior)
  const pollingPromise = (async (): Promise<SignatureStatusResult> => {
    const startedAt = Date.now();
    while (Date.now() - startedAt < maxWaitMs) {
      const statuses = await connection.getSignatureStatuses([signature], {
        searchTransactionHistory: true,
      });
      const result = toResult(statuses?.value?.[0] ?? null);
      if (result.state === 'confirmed' || result.state === 'failed') return result;
      await new Promise((resolve) => setTimeout(resolve, pollMs));
    }
    return { state: 'unresolved', error: `No final signature status within ${maxWaitMs}ms` };
  })();

  // Race: whichever resolves first with a definitive result wins.
  const wssResult = await Promise.race([
    wssRace.promise,
    pollingPromise.then((r) => {
      wssRace.cancel();
      return r;
    }),
  ]);

  // If WSS gave a definitive answer first, return it
  if (wssResult && (wssResult.state === 'confirmed' || wssResult.state === 'failed')) {
    return wssResult;
  }

  // Otherwise wait for polling result
  return pollingPromise;
}

export async function reconcileSignatureStatuses(
  signatures: string[],
): Promise<Record<string, SignatureStatusResult>> {
  const unique = [...new Set(signatures.map((s) => String(s || '').trim()).filter(Boolean))];
  if (unique.length === 0) return {};

  const res = await fetch('/api/rpc', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: Date.now(),
      method: 'getSignatureStatuses',
      params: [unique, { searchTransactionHistory: true }],
    }),
  });

  if (!res.ok) {
    let retryAfterMs = 0;
    const retry = Number(res.headers.get('retry-after') || 0);
    if (Number.isFinite(retry) && retry > 0) retryAfterMs = retry * 1000;
    const suffix = retryAfterMs > 0 ? ` retryAfterMs=${retryAfterMs}` : '';
    throw new Error(`RPC status ${res.status}${suffix}`);
  }

  const payload = await res.json();
  if (payload?.error) {
    throw new Error(payload.error?.message || 'Signature status RPC error');
  }

  const values = payload?.result?.value;
  const out: Record<string, SignatureStatusResult> = {};
  for (let i = 0; i < unique.length; i++) {
    const sig = unique[i];
    out[sig] = toResult((values?.[i] as SignatureStatus | null) ?? null);
  }
  return out;
}
