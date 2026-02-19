import { NextResponse } from 'next/server';
import { getTradeEvidence, summarizeTradeEvidence } from '@/lib/execution/evidence';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  const url = new URL(request.url);
  const tradeId = String(url.searchParams.get('tradeId') || '').trim();
  const surface = String(url.searchParams.get('surface') || '').trim();
  const strategyId = String(url.searchParams.get('strategyId') || '').trim();

  if (tradeId) {
    const evidence = getTradeEvidence(tradeId);
    if (!evidence) {
      return NextResponse.json(
        {
          ok: false,
          error: 'Trade evidence not found',
          tradeId,
        },
        { status: 404 },
      );
    }
    return NextResponse.json({ ok: true, tradeId, evidence });
  }

  const summary = summarizeTradeEvidence({
    surface: surface ? (surface as any) : undefined,
    strategyId: strategyId || undefined,
  });

  return NextResponse.json({
    ok: true,
    summary,
  });
}
