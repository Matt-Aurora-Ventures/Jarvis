import { proxyPerpsGet } from '@/lib/perps/proxy';
import { fallbackPositionsPayload } from '@/lib/perps/fallback-runtime';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  const upstream = await proxyPerpsGet('/positions', request);
  if (upstream.status < 500) return upstream;

  return NextResponse.json(fallbackPositionsPayload(), { status: 200 });
}
