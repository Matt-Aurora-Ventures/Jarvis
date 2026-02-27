import { proxyPerpsGet } from '@/lib/perps/proxy';
import { fallbackStatusPayload } from '@/lib/perps/fallback-runtime';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  const upstream = await proxyPerpsGet('/status', request);
  if (upstream.status < 500) return upstream;

  return NextResponse.json(fallbackStatusPayload(), { status: 200 });
}
