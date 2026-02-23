import type {
  SpotProtectionActivationInput,
  SpotProtectionActivationResult,
  SpotProtectionCancelResult,
  SpotProtectionPreflightResult,
  SpotProtectionReconcileResult,
} from './spot-protection-types';

type SpotProtectionApiResponse = {
  ok: boolean;
  error?: string;
  reason?: string;
  [key: string]: unknown;
};

function asString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

async function post(payload: Record<string, unknown>): Promise<SpotProtectionApiResponse> {
  try {
    const res = await fetch('/api/execution/protection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      cache: 'no-store',
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      return {
        ok: false,
        error: String(body?.error || body?.reason || `HTTP ${res.status}`),
      };
    }
    return body as SpotProtectionApiResponse;
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : 'Spot protection request failed',
    };
  }
}

export async function preflightSpotProtectionClient(): Promise<SpotProtectionPreflightResult> {
  const result = await post({ action: 'preflight' });
  return {
    ok: result.ok,
    provider: (result.provider as SpotProtectionPreflightResult['provider']) || 'none',
    checkedAt: Number(result.checkedAt || Date.now()),
    reason: result.reason || result.error,
  };
}

export async function activateSpotProtectionClient(
  input: SpotProtectionActivationInput,
): Promise<SpotProtectionActivationResult> {
  const result = await post({
    action: 'activate',
    payload: input,
  });
  const tpOrderKey = asString(result.tpOrderKey);
  const slOrderKey = asString(result.slOrderKey);
  return {
    ok: result.ok,
    provider: (result.provider as SpotProtectionActivationResult['provider']) || 'none',
    status: (result.status as SpotProtectionActivationResult['status']) || 'failed',
    tpOrderKey,
    slOrderKey,
    record: (result.record as SpotProtectionActivationResult['record']) || undefined,
    reason: result.reason || result.error,
  };
}

export async function cancelSpotProtectionClient(
  positionId: string,
  reason?: string,
): Promise<SpotProtectionCancelResult> {
  const result = await post({
    action: 'cancel',
    positionId,
    reason,
  });
  return {
    ok: result.ok,
    provider: (result.provider as SpotProtectionCancelResult['provider']) || 'none',
    positionId: String(result.positionId || positionId || ''),
    status: (result.status as SpotProtectionCancelResult['status']) || 'failed',
    record: (result.record as SpotProtectionCancelResult['record']) || undefined,
    reason: result.reason || result.error,
  };
}

export async function reconcileSpotProtectionClient(positionIds?: string[]): Promise<SpotProtectionReconcileResult> {
  const result = await post({
    action: 'reconcile',
    positionIds: Array.isArray(positionIds) ? positionIds : undefined,
  });
  return {
    ok: result.ok,
    provider: (result.provider as SpotProtectionReconcileResult['provider']) || 'none',
    records: Array.isArray(result.records) ? result.records : [],
    reason: result.reason || result.error,
  };
}
