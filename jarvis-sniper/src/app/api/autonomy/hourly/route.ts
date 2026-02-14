import { NextResponse } from 'next/server';
import { getClientIp, autonomyRateLimiter } from '@/lib/rate-limiter';
import { runHourlyAutonomyCycle } from '@/lib/autonomy/hourly-cycle';

export const runtime = 'nodejs';

function isAuthorized(request: Request): boolean {
  const expected = String(process.env.AUTONOMY_JOB_TOKEN || '').trim();
  if (!expected) return false;
  const auth = String(request.headers.get('authorization') || '').trim();
  if (!auth.toLowerCase().startsWith('bearer ')) return false;
  const token = auth.slice(7).trim();
  return token === expected;
}

export async function POST(request: Request) {
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

  if (!isAuthorized(request)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

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

