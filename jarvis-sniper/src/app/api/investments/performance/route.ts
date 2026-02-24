import { proxyInvestmentsGet } from '@/lib/investments/proxy';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

function requestedHours(request: Request): number {
  const raw = Number(new URL(request.url).searchParams.get('hours') || 24);
  if (!Number.isFinite(raw) || raw <= 0) return 24;
  return Math.floor(raw);
}

export async function GET(request: Request) {
  const upstream = await proxyInvestmentsGet('/performance', request);
  if (upstream.status < 500) return upstream;

  return NextResponse.json(
    {
      basket_id: 'alpha',
      hours: requestedHours(request),
      points: [],
      change_pct: 0,
      _fallback: true,
      _fallbackReason: 'investments_upstream_unavailable',
    },
    { status: 200 },
  );
}
