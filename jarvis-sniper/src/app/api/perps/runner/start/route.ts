import { proxyPerpsPost } from '@/lib/perps/proxy';
import { fallbackStartRunner } from '@/lib/perps/fallback-runtime';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  const upstream = await proxyPerpsPost('/runner/start', request);
  if (upstream.status < 500) return upstream;

  return NextResponse.json(fallbackStartRunner(), { status: 200 });
}
