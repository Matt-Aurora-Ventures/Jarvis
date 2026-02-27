import { proxyPerpsPost } from '@/lib/perps/proxy';
import { fallbackArm } from '@/lib/perps/fallback-runtime';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  const payload = await request.clone().json().catch(() => ({}));
  const normalizedPayload =
    payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};

  const upstream = await proxyPerpsPost('/arm', request);
  if (upstream.status < 500) return upstream;

  const fallback = fallbackArm(normalizedPayload);
  const status = fallback.ok ? 200 : Number(fallback.status || 400);
  return NextResponse.json(fallback, { status });
}
