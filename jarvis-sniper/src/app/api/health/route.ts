import { NextResponse } from 'next/server';

/**
 * Health check endpoint for production monitoring.
 * Returns service status and environment readiness.
 *
 * GET /api/health
 */
export async function GET() {
  const checks = {
    status: 'ok' as 'ok' | 'degraded' | 'error',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    env: {
      rpcPublic: !!process.env.NEXT_PUBLIC_SOLANA_RPC,
      rpcServer: !!process.env.SOLANA_RPC_URL,
      bagsApiKey: !!process.env.BAGS_API_KEY,
      bagsReferral: !!process.env.BAGS_REFERRAL_ACCOUNT,
    },
    memory: {
      heapUsedMB: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
      rssUsedMB: Math.round(process.memoryUsage().rss / 1024 / 1024),
    },
  };

  // Degraded if missing critical env vars
  if (!checks.env.bagsApiKey) {
    checks.status = 'degraded';
  }

  return NextResponse.json(checks);
}
