import { NextResponse } from 'next/server';
import { resolveServerRpcConfig } from '@/lib/server-rpc-config';

/**
 * Health check endpoint for production monitoring.
 * Returns service status and environment readiness.
 *
 * GET /api/health
 */
export async function GET() {
  const rpcConfig = resolveServerRpcConfig();
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
    },
    rpc: {
      configured: rpcConfig.ok,
      source: rpcConfig.source,
      productionMode: rpcConfig.isProduction,
      url: rpcConfig.sanitizedUrl,
      diagnostic: rpcConfig.diagnostic,
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

  return NextResponse.json(checks);
}
