import { proxyInvestmentsGet } from '@/lib/investments/proxy';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  const upstream = await proxyInvestmentsGet('/kill-switch', request);
  if (upstream.status < 500) return upstream;

  return NextResponse.json(
    {
      active: false,
      _fallback: true,
      _fallbackReason: 'investments_upstream_unavailable',
    },
    { status: 200 },
  );
}
