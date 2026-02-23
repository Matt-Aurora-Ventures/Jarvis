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
export async function GET() {
  const rpcConfig = resolveServerRpcConfig();
  const cacheProvider = getCacheProviderDiagnostics();
  const rateLimiterProvider = getRateLimitProviderDiagnostics();
  const xaiConfigured = String(process.env.XAI_API_KEY || '').trim().length > 0;
  const xaiBatchEnabled = String(process.env.XAI_BATCH_ENABLED || 'false').toLowerCase() === 'true';
  const xaiModel = String(process.env.XAI_FRONTIER_MODEL || 'grok-4-1-fast-reasoning').trim();
  const xaiDailyBudget = Number(process.env.XAI_DAILY_BUDGET_USD || 10);
  const keyRatePolicy = {
    qps: Number(process.env.XAI_KEY_RATE_QPS || 0.2),
    qpm: Number(process.env.XAI_KEY_RATE_QPM || 12),
    tpm: Number(process.env.XAI_KEY_RATE_TPM || 120000),
  };
  const autonomyEnabled = String(process.env.AUTONOMY_ENABLED || 'false').toLowerCase() === 'true';
  const autonomyApplyOverrides = String(process.env.AUTONOMY_APPLY_OVERRIDES || 'false').toLowerCase() === 'true';
  const checks = {
    status: 'ok' as 'ok' | 'degraded' | 'error',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
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
