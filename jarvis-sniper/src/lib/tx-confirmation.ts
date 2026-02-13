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
