import { proxyPerpsGet } from '@/lib/perps/proxy';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  const upstream = await proxyPerpsGet('/audit', request);
  if (upstream.status < 500) return upstream;

  return NextResponse.json(
    {
      events: [],
      _fallback: true,
      _fallbackReason: 'perps_upstream_unavailable',
    },
    { status: 200 },
  );
}
