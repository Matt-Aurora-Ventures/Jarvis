import { proxyInvestmentsGet } from '@/lib/investments/proxy';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  const upstream = await proxyInvestmentsGet('/basket', request);
  if (upstream.status < 500) return upstream;

  return NextResponse.json(
    {
      tokens: {},
      total_nav: 0,
      nav_per_share: 0,
      _fallback: true,
      _fallbackReason: 'investments_upstream_unavailable',
    },
    { status: 200 },
  );
}
