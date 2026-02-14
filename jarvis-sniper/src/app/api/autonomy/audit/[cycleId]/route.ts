import { NextResponse } from 'next/server';
import { readAuditBundle } from '@/lib/autonomy/audit-store';
import { autonomyRateLimiter, getClientIp } from '@/lib/rate-limiter';

export const runtime = 'nodejs';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ cycleId: string }> },
) {
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

  const { cycleId } = await params;
  const normalized = String(cycleId || '').trim();
  if (!/^\d{10}$/.test(normalized)) {
    return NextResponse.json(
      { error: 'Invalid cycleId. Expected UTC hour key in YYYYMMDDHH format.' },
      { status: 400 },
    );
  }

  try {
    const bundle = await readAuditBundle(normalized);
    if (!bundle.matrix && !bundle.response && !bundle.reportMarkdown && !bundle.appliedOverrides) {
      return NextResponse.json(
        { error: 'Audit artifact not found for cycleId', cycleId: normalized },
        { status: 404 },
      );
    }
    return NextResponse.json(bundle);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to load audit bundle' },
      { status: 500 },
    );
  }
}
