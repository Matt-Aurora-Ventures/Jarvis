import { proxyPerpsGet } from '@/lib/perps/proxy';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  const upstream = await proxyPerpsGet('/prices', request);
  if (upstream.status < 500) return upstream;

  return NextResponse.json(
    {
      'SOL-USD': { price: 0 },
      'BTC-USD': { price: 0 },
      'ETH-USD': { price: 0 },
      _fallback: true,
      _fallbackReason: 'perps_upstream_unavailable',
    },
    { status: 200 },
  );
}
