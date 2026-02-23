import { NextResponse } from 'next/server';
import { getClientIp, autonomyRateLimiter } from '@/lib/rate-limiter';
import { runHourlyAutonomyCycle } from '@/lib/autonomy/hourly-cycle';
import { requireAutonomyAuth } from '@/lib/autonomy/auth';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  const ip = getClientIp(request);
  const limit = await autonomyRateLimiter.check(ip);
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

  const authError = requireAutonomyAuth(request, {
    envKeys: ['AUTONOMY_JOB_TOKEN'],
    allowWhenUnconfigured: false,
    unconfiguredStatus: 401,
  });
  if (authError) return authError;

  try {
    const result = await runHourlyAutonomyCycle();
    return NextResponse.json({
      ok: result.ok,
      cycleId: result.cycleId,
      reasonCode: result.reasonCode || null,
      latestCycleId: result.state.latestCycleId || null,
      latestCompletedCycleId: result.state.latestCompletedCycleId || null,
      pendingBatchCycleId: result.state.pendingBatch?.cycleId || null,
      pendingBatchId: result.state.pendingBatch?.batchId || null,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Hourly autonomy cycle failed';
    return NextResponse.json(
      {
        ok: false,
        error: message,
      },
      { status: 500 },
    );
  }
}

