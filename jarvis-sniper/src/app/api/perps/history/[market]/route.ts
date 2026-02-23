import { NextResponse } from 'next/server';
import { isAllowedPerpsMarket, proxyPerpsGet } from '@/lib/perps/proxy';

export const runtime = 'nodejs';

export async function GET(
  request: Request,
  context: { params: Promise<{ market: string }> },
) {
  const { market } = await context.params;
  const normalized = String(market || '').trim().toUpperCase();
  if (!isAllowedPerpsMarket(normalized)) {
    return NextResponse.json(
      {
        error: 'Unknown market. Allowed: SOL-USD, BTC-USD, ETH-USD',
      },
      { status: 404 },
    );
  }
  return proxyPerpsGet(`/history/${normalized}`, request);
}
