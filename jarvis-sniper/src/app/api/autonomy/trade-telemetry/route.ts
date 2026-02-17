import { NextResponse } from 'next/server';
import { appendTradeTelemetryEvent } from '@/lib/autonomy/trade-telemetry-store';
import type { TradeTelemetryEvent } from '@/lib/autonomy/trade-telemetry-client';

export const runtime = 'nodejs';

function badRequest(message: string) {
  return NextResponse.json({ ok: false, error: message }, { status: 400 });
}

export async function POST(request: Request) {
  try {
    const body = await request.json() as Partial<TradeTelemetryEvent> | null;
    if (!body || typeof body !== 'object') {
      return badRequest('Invalid telemetry payload');
    }

    const positionId = String(body.positionId || '').trim();
    const mint = String(body.mint || '').trim();
    const status = String(body.status || '').trim();
    if (!positionId) return badRequest('positionId is required');
    if (!mint) return badRequest('mint is required');
    if (!status) return badRequest('status is required');

    const saved = await appendTradeTelemetryEvent({
      schemaVersion: Number(body.schemaVersion || 1),
      ...body,
      positionId,
      mint,
      status,
    } as TradeTelemetryEvent);

    return NextResponse.json({
      ok: true,
      receivedAt: saved.receivedAt,
      eventType: saved.eventType,
    }, { status: 202 });
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        error: error instanceof Error ? error.message : 'Failed to persist trade telemetry',
      },
      { status: 500 },
    );
  }
}
