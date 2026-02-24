import { proxyInvestmentsGet } from '@/lib/investments/proxy';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  const upstream = await proxyInvestmentsGet('/decisions', request);
  if (upstream.status < 500) return upstream;

  return NextResponse.json([], {
    status: 200,
    headers: { 'x-jarvis-fallback': '1' },
  });
}
