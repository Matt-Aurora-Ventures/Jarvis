import { proxyPerpsGet } from '@/lib/perps/proxy';
import { fallbackPricesPayload } from '@/lib/perps/fallback-runtime';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  const upstream = await proxyPerpsGet('/prices', request);
  if (upstream.status < 500) return upstream;

  return NextResponse.json(fallbackPricesPayload(), { status: 200 });
}
