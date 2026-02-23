import { NextResponse } from 'next/server';
import { resolveServerRpcConfig } from '@/lib/server-rpc-config';
import { getCacheProviderDiagnostics } from '@/lib/cache-provider';
import { getRateLimitProviderDiagnostics } from '@/lib/rate-limit-provider';

/**
 * Health check endpoint for production monitoring.
 * Returns service status and environment readiness.
 *
 * GET /api/health
 */
function deriveCloudRunTagUrl(request: Request): string | null {
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
    const withoutScheme = first.replace(/^https?:\/\//i, '').trim();
    const hostOnly = withoutScheme.split('/')[0]?.trim() || '';
    const hostname = hostOnly.includes(':') ? hostOnly.split(':')[0] : hostOnly;
    if (hostname.endsWith('.a.run.app')) {
      return `https://${hostname}`;
    }
  }

  return null;
}

export async function GET(request: Request) {
  const rpcConfig = resolveServerRpcConfig();
  const cacheProvider = getCacheProviderDiagnostics();
  const rateLimiterProvider = getRateLimitProviderDiagnostics();
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
    distributedState: {
      cacheProvider,
      rateLimiterProvider,
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
  if (cacheProvider.warning || rateLimiterProvider.warning) {
    checks.status = 'degraded';
  }

  return NextResponse.json(checks);
}
