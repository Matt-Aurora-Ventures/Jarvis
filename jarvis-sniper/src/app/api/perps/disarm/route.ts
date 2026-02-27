import { proxyPerpsPost } from '@/lib/perps/proxy';
import { fallbackDisarm } from '@/lib/perps/fallback-runtime';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  const upstream = await proxyPerpsPost('/disarm', request);
  if (upstream.status < 500) return upstream;

  return NextResponse.json(fallbackDisarm(), { status: 200 });
}
