import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import type {
  SpotProtectionActivationInput,
  SpotProtectionActivationResult,
  SpotProtectionCancelResult,
  SpotProtectionPreflightResult,
  SpotProtectionProvider,
  SpotProtectionRecord,
  SpotProtectionReconcileResult,
} from './spot-protection-types';

type SpotProtectionStore = Record<string, SpotProtectionRecord>;

interface ProviderResponse {
  ok: boolean;
  status?: string;
  tpOrderKey?: string;
  slOrderKey?: string;
  reason?: string;
  records?: SpotProtectionRecord[];
}

function nowMs(): number {
  return Date.now();
}

function toBool(v: string | undefined): boolean {
  return String(v || '').trim().toLowerCase() === 'true';
}

function providerUrl(): string {
  return String(process.env.SPOT_PROTECTION_PROVIDER_URL || '').trim().replace(/\/+$/, '');
}

function providerPath(): string {
  const raw = String(process.env.SPOT_PROTECTION_PROVIDER_PATH || '/api/spot-protection').trim();
  if (!raw) return '/api/spot-protection';
  return raw.startsWith('/') ? raw : `/${raw}`;
}

function providerToken(): string {
  return String(process.env.SPOT_PROTECTION_PROVIDER_TOKEN || '').trim();
}

function providerTimeoutMs(): number {
  const raw = Number(process.env.SPOT_PROTECTION_PROVIDER_TIMEOUT_MS || 3000);
  if (!Number.isFinite(raw)) return 3000;
  return Math.max(250, Math.min(20_000, Math.floor(raw)));
}

function allowLocalAdapter(): boolean {
  if (toBool(process.env.SPOT_PROTECTION_LOCAL_MODE)) return true;
  return process.env.NODE_ENV === 'test';
}

function recordsRoot(): string {
  const configured = String(process.env.JARVIS_SPOT_PROTECTION_ROOT || '').trim();
  if (configured) return configured;
  return join(process.cwd(), '.jarvis-cache', 'spot-protection');
}

function recordsPath(): string {
  return join(recordsRoot(), 'records.json');
}

function ensureRoot(): void {
  const root = recordsRoot();
  if (!existsSync(root)) mkdirSync(root, { recursive: true });
}

function readStore(): SpotProtectionStore {
  ensureRoot();
  const path = recordsPath();
  if (!existsSync(path)) return {};
  try {
    const parsed = JSON.parse(readFileSync(path, 'utf8')) as SpotProtectionStore;
    if (!parsed || typeof parsed !== 'object') return {};
    return parsed;
  } catch {
    return {};
  }
}

function writeStore(next: SpotProtectionStore): void {
  ensureRoot();
  writeFileSync(recordsPath(), JSON.stringify(next, null, 2), 'utf8');
}

function sanitizeKey(input: string): string {
  return String(input || '').trim().replace(/[^a-zA-Z0-9:_-]/g, '_').slice(0, 120);
}

function normalizeInput(input: SpotProtectionActivationInput): SpotProtectionActivationInput {
  return {
    ...input,
    positionId: sanitizeKey(input.positionId),
    walletAddress: String(input.walletAddress || '').trim(),
    mint: String(input.mint || '').trim(),
    symbol: String(input.symbol || '').trim() || 'UNKNOWN',
    entryPriceUsd: Number(input.entryPriceUsd || 0),
    quantity: Number(input.quantity || 0),
    tpPercent: Number(input.tpPercent || 0),
    slPercent: Number(input.slPercent || 0),
    strategyId: String(input.strategyId || '').trim() || undefined,
    surface: String(input.surface || '').trim() || undefined,
    idempotencyKey: String(input.idempotencyKey || '').trim() || undefined,
  };
}

function validateInput(input: SpotProtectionActivationInput): string | null {
  if (!input.positionId) return 'positionId is required';
  if (!input.walletAddress) return 'walletAddress is required';
  if (!input.mint) return 'mint is required';
  if (!Number.isFinite(input.entryPriceUsd) || input.entryPriceUsd <= 0) return 'entryPriceUsd must be > 0';
  if (!Number.isFinite(input.quantity) || input.quantity <= 0) return 'quantity must be > 0';
  if (!Number.isFinite(input.tpPercent) || input.tpPercent <= 0) return 'tpPercent must be > 0';
  if (!Number.isFinite(input.slPercent) || input.slPercent <= 0) return 'slPercent must be > 0';
  return null;
}

async function callProvider(payload: Record<string, unknown>): Promise<ProviderResponse> {
  const url = providerUrl();
  if (!url) {
    return { ok: false, reason: 'SPOT_PROTECTION_PROVIDER_URL is not configured' };
  }
  const token = providerToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), providerTimeoutMs());
  try {
    const res = await fetch(`${url}${providerPath()}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal,
      cache: 'no-store',
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      return {
        ok: false,
        reason: String(body?.error || body?.reason || `Provider HTTP ${res.status}`),
      };
    }
    return {
      ok: Boolean(body?.ok),
      status: String(body?.status || ''),
      tpOrderKey: body?.tpOrderKey ? String(body.tpOrderKey) : undefined,
      slOrderKey: body?.slOrderKey ? String(body.slOrderKey) : undefined,
      reason: body?.reason ? String(body.reason) : undefined,
      records: Array.isArray(body?.records) ? (body.records as SpotProtectionRecord[]) : undefined,
    };
  } catch (err) {
    return {
      ok: false,
      reason: err instanceof Error ? err.message : 'Spot protection provider call failed',
    };
  } finally {
    clearTimeout(timeout);
  }
}

function resolveProvider(): SpotProtectionProvider {
  if (providerUrl()) return 'upstream';
  if (allowLocalAdapter()) return 'local';
  return 'none';
}

export async function preflightSpotProtection(): Promise<SpotProtectionPreflightResult> {
  const provider = resolveProvider();
  const checkedAt = nowMs();
  if (provider === 'none') {
    return {
      ok: false,
      provider,
      checkedAt,
      reason: 'No protection adapter configured (set SPOT_PROTECTION_PROVIDER_URL, or SPOT_PROTECTION_LOCAL_MODE=true for internal testing).',
    };
  }
  if (provider === 'local') {
    return {
      ok: true,
      provider,
      checkedAt,
      reason: 'Using local internal protection adapter.',
    };
  }

  const upstream = await callProvider({ action: 'preflight' });
  if (!upstream.ok) {
    return {
      ok: false,
      provider,
      checkedAt,
      reason: upstream.reason || 'Upstream protection preflight failed',
    };
  }
  return {
    ok: true,
    provider,
    checkedAt,
  };
}

function buildLocalOrderKeys(positionId: string): { tpOrderKey: string; slOrderKey: string } {
  const base = sanitizeKey(positionId) || 'position';
  const nonce = nowMs();
  return {
    tpOrderKey: `local-tp:${base}:${nonce}`,
    slOrderKey: `local-sl:${base}:${nonce}`,
  };
}

export async function activateSpotProtection(inputRaw: SpotProtectionActivationInput): Promise<SpotProtectionActivationResult> {
  const input = normalizeInput(inputRaw);
  const validationError = validateInput(input);
  const provider = resolveProvider();
  if (validationError) {
    return {
      ok: false,
      provider,
      status: 'failed',
      reason: validationError,
    };
  }

  const store = readStore();
  const existing = store[input.positionId];
  if (existing?.status === 'active' && existing.tpOrderKey && existing.slOrderKey) {
    return {
      ok: true,
      provider: existing.provider,
      status: 'active',
      tpOrderKey: existing.tpOrderKey,
      slOrderKey: existing.slOrderKey,
      record: existing,
    };
  }

  if (provider === 'none') {
    return {
      ok: false,
      provider,
      status: 'failed',
      reason: 'No protection adapter configured for activation.',
    };
  }

  let tpOrderKey = '';
  let slOrderKey = '';
  let failureReason: string | undefined;
  let resolvedProvider: SpotProtectionProvider = provider;

  if (provider === 'upstream') {
    const upstream = await callProvider({
      action: 'activate',
      payload: input,
    });
    if (!upstream.ok) {
      failureReason = upstream.reason || 'Upstream protection activation failed';
    } else {
      tpOrderKey = String(upstream.tpOrderKey || '').trim();
      slOrderKey = String(upstream.slOrderKey || '').trim();
      if (!tpOrderKey || !slOrderKey) {
        failureReason = 'Upstream response missing tpOrderKey/slOrderKey';
      }
    }
  } else {
    const local = buildLocalOrderKeys(input.positionId);
    tpOrderKey = local.tpOrderKey;
    slOrderKey = local.slOrderKey;
    resolvedProvider = 'local';
  }

  const ts = nowMs();
  const status = failureReason ? 'failed' : 'active';
  const record: SpotProtectionRecord = {
    positionId: input.positionId,
    walletAddress: input.walletAddress,
    mint: input.mint,
    symbol: input.symbol,
    entryPriceUsd: input.entryPriceUsd,
    quantity: input.quantity,
    tpPercent: input.tpPercent,
    slPercent: input.slPercent,
    status,
    tpOrderKey: tpOrderKey || undefined,
    slOrderKey: slOrderKey || undefined,
    failureReason,
    provider: resolvedProvider,
    strategyId: input.strategyId,
    surface: input.surface,
    createdAt: existing?.createdAt || ts,
    updatedAt: ts,
  };

  store[input.positionId] = record;
  writeStore(store);

  return {
    ok: !failureReason,
    provider: resolvedProvider,
    status,
    tpOrderKey: record.tpOrderKey,
    slOrderKey: record.slOrderKey,
    record,
    reason: failureReason,
  };
}

export async function cancelSpotProtection(
  positionIdRaw: string,
  reasonRaw?: string,
): Promise<SpotProtectionCancelResult> {
  const positionId = sanitizeKey(positionIdRaw);
  const reason = String(reasonRaw || '').trim() || undefined;
  const provider = resolveProvider();
  const store = readStore();
  const existing = store[positionId];

  if (!positionId) {
    return { ok: false, provider, positionId, status: 'failed', reason: 'positionId is required' };
  }

  let failureReason: string | undefined;
  let resolvedProvider: SpotProtectionProvider = existing?.provider || provider;
  if (existing?.provider === 'upstream' || (provider === 'upstream' && !existing)) {
    const upstream = await callProvider({
      action: 'cancel',
      positionId,
      reason,
    });
    if (!upstream.ok) {
      failureReason = upstream.reason || 'Upstream cancel failed';
    }
    resolvedProvider = 'upstream';
  } else if (provider === 'none' && !existing) {
    return {
      ok: false,
      provider,
      positionId,
      status: 'failed',
      reason: 'No protection adapter configured and record not found',
    };
  }

  const ts = nowMs();
  const cancelled: SpotProtectionRecord = {
    ...(existing || {
      positionId,
      walletAddress: '',
      mint: '',
      symbol: '',
      entryPriceUsd: 0,
      quantity: 0,
      tpPercent: 0,
      slPercent: 0,
      createdAt: ts,
    }),
    status: 'cancelled',
    provider: resolvedProvider,
    failureReason: failureReason || reason,
    updatedAt: ts,
    cancelledAt: ts,
  };

  store[positionId] = cancelled;
  writeStore(store);
  return {
    ok: !failureReason,
    provider: resolvedProvider,
    positionId,
    status: cancelled.status,
    record: cancelled,
    reason: failureReason,
  };
}

export async function reconcileSpotProtection(positionIdsRaw?: string[]): Promise<SpotProtectionReconcileResult> {
  const provider = resolveProvider();
  const store = readStore();
  const requestedIds = Array.isArray(positionIdsRaw)
    ? positionIdsRaw.map((id) => sanitizeKey(id)).filter(Boolean)
    : [];
  const records = Object.values(store);
  const scope = requestedIds.length > 0
    ? records.filter((record) => requestedIds.includes(record.positionId))
    : records;

  if (provider === 'none') {
    return {
      ok: false,
      provider,
      records: scope,
      reason: 'No protection adapter configured for reconciliation.',
    };
  }

  if (provider === 'local') {
    return { ok: true, provider, records: scope };
  }

  const upstream = await callProvider({
    action: 'reconcile',
    positionIds: requestedIds.length > 0 ? requestedIds : records.map((r) => r.positionId),
  });
  if (!upstream.ok || !Array.isArray(upstream.records)) {
    return {
      ok: false,
      provider,
      records: scope,
      reason: upstream.reason || 'Upstream reconcile failed',
    };
  }

  const next = { ...store };
  const ts = nowMs();
  for (const upstreamRecord of upstream.records) {
    const positionId = sanitizeKey(upstreamRecord.positionId);
    if (!positionId) continue;
    const prev = next[positionId];
    if (!prev) continue;
    next[positionId] = {
      ...prev,
      status: upstreamRecord.status,
      tpOrderKey: upstreamRecord.tpOrderKey || prev.tpOrderKey,
      slOrderKey: upstreamRecord.slOrderKey || prev.slOrderKey,
      failureReason: upstreamRecord.failureReason || prev.failureReason,
      updatedAt: ts,
    };
  }
  writeStore(next);

  const refreshed = Object.values(next);
  const out = requestedIds.length > 0
    ? refreshed.filter((record) => requestedIds.includes(record.positionId))
    : refreshed;
  return {
    ok: true,
    provider,
    records: out,
  };
}
