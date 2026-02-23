import { NextResponse } from 'next/server';
import { getLatestAuditBundle } from '@/lib/autonomy/hourly-cycle';
import { autonomyRateLimiter, getClientIp } from '@/lib/rate-limiter';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  const ip = getClientIp(request);
  const limit = autonomyRateLimiter.check(ip);
  if (!limit.allowed) {
    return NextResponse.json(
      { error: 'Rate limit exceeded. Try again shortly.' },
      {
        status: 429,
        headers: {
          'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)),
        },
      },
    );
  }
  try {
    const latest = await getLatestAuditBundle();
    if (!latest.cycleId || !latest.bundle) {
      return NextResponse.json(
        {
          cycleId: null,
          bundle: null,
          message: 'No autonomy audit artifacts found yet.',
        },
        { status: 404 },
      );
    }
    return NextResponse.json({
      cycleId: latest.cycleId,
      bundle: latest.bundle,
      latestCycleId: latest.state.latestCycleId || null,
      latestCompletedCycleId: latest.state.latestCompletedCycleId || null,
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to load latest autonomy audit' },
      { status: 500 },
    );
  }
}
