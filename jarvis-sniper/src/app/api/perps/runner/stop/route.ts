import { proxyPerpsPost } from '@/lib/perps/proxy';
import { fallbackStopRunner } from '@/lib/perps/fallback-runtime';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  const upstream = await proxyPerpsPost('/runner/stop', request);
  if (upstream.status < 500) return upstream;

  return NextResponse.json(fallbackStopRunner(), { status: 200 });
}
