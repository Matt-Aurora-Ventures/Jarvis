import { NextResponse } from 'next/server';
import { resolveServerRpcConfig } from '@/lib/server-rpc-config';

/**
 * Health check endpoint for production monitoring.
 * Returns service status and environment readiness.
 *
 * GET /api/health
 */
function normalizeCloudRunTagUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const trimmed = String(raw).trim();
  if (!trimmed) return null;
  const candidate = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;

  try {
    const parsed = new URL(candidate);
    const hostname = String(parsed.hostname || '').trim().toLowerCase();
    if (parsed.protocol !== 'https:') return null;
    if (!hostname.endsWith('.a.run.app')) return null;
    return `https://${hostname}`;
  } catch {
    return null;
  }
}

function deriveCloudRunTagUrl(request: Request): string | null {
  // Preferred explicit source for deterministic backtest bypass in custom-domain setups.
  const fromEnv = normalizeCloudRunTagUrl(process.env.BACKTEST_CLOUD_RUN_TAG_URL);
  if (fromEnv) return fromEnv;

  // Firebase Hosting / App Hosting rewrites to Cloud Run may preserve the original host in
  // forwarded headers, while the direct Cloud Run host remains available as another header.
  // We only return Cloud Run hosts (`*.a.run.app`) to support backtest bypass of Hosting 60s.
  const candidates = [
    request.headers.get('x-fh-requested-host'),
    request.headers.get('host'),
    request.headers.get('x-forwarded-host'),
    request.headers.get('x-original-host'),
  ];

  for (const raw of candidates) {
    if (!raw) continue;
    const first = String(raw).split(',')[0]?.trim() || '';
    if (!first) continue;
    const normalized = normalizeCloudRunTagUrl(first);
    if (normalized) return normalized;
  }

  return null;
}

type UpstreamCheck = {
  configured: boolean;
  baseUrl: string | null;
  ok: boolean | null;
  statusCode: number | null;
  latencyMs: number | null;
  error: string | null;
};

const DEFAULT_UPSTREAM_HEALTH_TIMEOUT_MS = 2500;

function upstreamHealthTimeoutMs(): number {
  const raw = Number(process.env.UPSTREAM_HEALTH_TIMEOUT_MS || DEFAULT_UPSTREAM_HEALTH_TIMEOUT_MS);
  if (!Number.isFinite(raw) || raw <= 0) return DEFAULT_UPSTREAM_HEALTH_TIMEOUT_MS;
  return Math.floor(raw);
}

function normalizeHttpBaseUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const trimmed = String(raw).trim();
  if (!trimmed) return null;
  const candidate = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;
  try {
    const parsed = new URL(candidate);
    if (!/^https?:$/i.test(parsed.protocol)) return null;
    return `${parsed.protocol}//${parsed.host}`;
  } catch {
    return null;
  }
}

async function checkUpstream(base: string | null, path: string): Promise<UpstreamCheck> {
  if (!base) {
    return {
      configured: false,
      baseUrl: null,
      ok: null,
      statusCode: null,
      latencyMs: null,
      error: null,
    };
  }

  const started = Date.now();
  try {
    const signal = AbortSignal.timeout(upstreamHealthTimeoutMs());
    const res = await fetch(`${base}${path}`, {
      method: 'GET',
      cache: 'no-store',
      signal,
    });
    return {
      configured: true,
      baseUrl: base,
      ok: res.ok,
      statusCode: res.status,
      latencyMs: Date.now() - started,
      error: null,
    };
  } catch (error) {
    return {
      configured: true,
      baseUrl: base,
      ok: false,
      statusCode: null,
      latencyMs: Date.now() - started,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

export async function GET(request: Request) {
  const rpcConfig = resolveServerRpcConfig();
  const xaiConfigured = String(process.env.XAI_API_KEY || '').trim().length > 0;
  const xaiBatchEnabled = String(process.env.XAI_BATCH_ENABLED || 'false').toLowerCase() === 'true';
  const xaiModel = String(process.env.XAI_FRONTIER_MODEL || 'grok-4-1-fast-reasoning').trim();
  const xaiDailyBudget = Number(process.env.XAI_DAILY_BUDGET_USD || 10);
  const autonomyEnabled = String(process.env.AUTONOMY_ENABLED || 'false').toLowerCase() === 'true';
  const autonomyApplyOverrides =
    String(process.env.AUTONOMY_APPLY_OVERRIDES || 'false').toLowerCase() === 'true';
  const keyRatePolicy = {
    qps: Number(process.env.XAI_KEY_RATE_QPS || 0.2),
    qpm: Number(process.env.XAI_KEY_RATE_QPM || 12),
    tpm: Number(process.env.XAI_KEY_RATE_TPM || 120000),
  };
  const perpsUpstream = await checkUpstream(normalizeHttpBaseUrl(process.env.PERPS_SERVICE_BASE_URL), '/api/perps/status');
  const investmentsUpstream = await checkUpstream(
    normalizeHttpBaseUrl(process.env.INVESTMENTS_SERVICE_BASE_URL),
    '/api/investments/performance?hours=24',
  );
  const checks = {
    status: 'ok' as 'ok' | 'degraded' | 'error',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    backend: {
      cloudRunTagUrl: deriveCloudRunTagUrl(request),
    },
    env: {
      rpcGatekeeper: !!process.env.HELIUS_GATEKEEPER_RPC_URL,
      rpcPublic: !!process.env.NEXT_PUBLIC_SOLANA_RPC,
      rpcServer: !!process.env.SOLANA_RPC_URL,
      bagsApiKey: !!process.env.BAGS_API_KEY,
      bagsReferral: !!process.env.BAGS_REFERRAL_ACCOUNT,
      solscanApiKey: !!process.env.SOLSCAN_API_KEY,
    },
    rpc: {
      configured: rpcConfig.ok,
      source: rpcConfig.source,
      productionMode: rpcConfig.isProduction,
      url: rpcConfig.sanitizedUrl,
      diagnostic: rpcConfig.diagnostic,
    },
    upstreams: {
      perps: perpsUpstream,
      investments: investmentsUpstream,
    },
    autonomy: {
      enabled: autonomyEnabled,
      applyOverrides: autonomyApplyOverrides,
    },
    xai: {
      configured: xaiConfigured,
      batchEnabled: xaiBatchEnabled,
      modelPolicy: xaiModel,
      dailyBudgetUsd: Number.isFinite(xaiDailyBudget) ? xaiDailyBudget : 10,
      keyRatePolicy,
    },
    memory: {
      heapUsedMB: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
      rssUsedMB: Math.round(process.memoryUsage().rss / 1024 / 1024),
    },
  };

  // Degraded if missing critical env vars
  if (!checks.env.bagsApiKey || !checks.rpc.configured) {
    checks.status = 'degraded';
  }

  if (!perpsUpstream.configured || !investmentsUpstream.configured) {
    checks.status = 'degraded';
  }

  if ((perpsUpstream.configured && !perpsUpstream.ok) || (investmentsUpstream.configured && !investmentsUpstream.ok)) {
    checks.status = 'degraded';
  }

  return NextResponse.json(checks);
}
