import { proxyPerpsGet } from '@/lib/perps/proxy';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  const upstream = await proxyPerpsGet('/status', request);
  if (upstream.status < 500) return upstream;

  return NextResponse.json(
    {
      runner_healthy: false,
      mode: 'disabled',
      arm: {
        stage: 'disarmed',
        last_reason: 'perps_upstream_unavailable',
      },
      _fallback: true,
    },
    { status: 200 },
  );
}
