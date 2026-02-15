import { NextResponse } from 'next/server';
import { STRATEGY_SEED_META } from '@/lib/strategy-seed-meta';

/**
 * Build/version fingerprint for deploy verification.
 *
 * GET /api/version
 */
export async function GET() {
  const gitSha = String(process.env.NEXT_PUBLIC_BUILD_SHA || process.env.GITHUB_SHA || '').trim() || null;
  const builtAt = String(process.env.NEXT_PUBLIC_BUILT_AT || '').trim() || null;

  return NextResponse.json(
    {
      gitSha,
      builtAt,
      strategySeedRevision: STRATEGY_SEED_META.strategyRevision,
      seedVersion: STRATEGY_SEED_META.seedVersion,
    },
    { headers: { 'Cache-Control': 'no-store' } },
  );
}

