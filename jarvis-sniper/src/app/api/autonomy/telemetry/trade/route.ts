import { NextResponse } from 'next/server';
import { telemetryRateLimiter, getClientIp } from '@/lib/rate-limiter';
import { writeTradeTelemetry } from '@/lib/autonomy/trade-telemetry-store';
import type { TradeTelemetryIngest } from '@/lib/autonomy/types';

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asNumber(value: unknown): number | null {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return null;
  return n;
}

function isValidStatus(value: unknown): value is TradeTelemetryIngest['status'] {
  return (
    value === 'tp_hit' ||
    value === 'sl_hit' ||
    value === 'trail_stop' ||
    value === 'expired' ||
    value === 'closed'
  );
}

export async function POST(request: Request) {
  const ip = getClientIp(request);
  const limit = telemetryRateLimiter.check(ip);
  if (!limit.allowed) {
    return NextResponse.json(
      { error: 'Rate limit exceeded', code: 'RATE_LIMITED' },
      {
        status: 429,
        headers: {
          'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)),
          'X-RateLimit-Remaining': '0',
        },
      },
    );
  }

  let body: any;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const schemaVersion = asNumber(body?.schemaVersion);
  if (schemaVersion !== 1) {
    return NextResponse.json({ error: 'Unsupported schemaVersion' }, { status: 400 });
  }

  const positionId = asString(body?.positionId).trim();
  const mint = asString(body?.mint).trim();
  const status = body?.status;
  if (!positionId || !mint || !isValidStatus(status)) {
    return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
  }

  const payload: TradeTelemetryIngest = {
    schemaVersion: 1,
    positionId,
    mint,
    status,
    symbol: asString(body?.symbol).trim() || undefined,
    walletAddress: asString(body?.walletAddress).trim() || undefined,
    strategyId: asString(body?.strategyId).trim() || null,
    entrySource: body?.entrySource === 'auto' ? 'auto' : body?.entrySource === 'manual' ? 'manual' : undefined,
    entryTime: asNumber(body?.entryTime) ?? undefined,
    exitTime: asNumber(body?.exitTime) ?? undefined,
    solInvested: asNumber(body?.solInvested) ?? undefined,
    exitSolReceived: asNumber(body?.exitSolReceived),
    pnlSol: asNumber(body?.pnlSol) ?? undefined,
    pnlPercent: asNumber(body?.pnlPercent) ?? undefined,
    buyTxHash: asString(body?.buyTxHash).trim() || null,
    sellTxHash: asString(body?.sellTxHash).trim() || null,
    includedInStats: typeof body?.includedInStats === 'boolean' ? body.includedInStats : undefined,
    manualOnly: typeof body?.manualOnly === 'boolean' ? body.manualOnly : undefined,
    recoveredFrom: asString(body?.recoveredFrom).trim() || null,
    tradeSignerMode: body?.tradeSignerMode === 'session' ? 'session' : body?.tradeSignerMode === 'phantom' ? 'phantom' : undefined,
    sessionWalletPubkey: asString(body?.sessionWalletPubkey).trim() || null,
    activePreset: asString(body?.activePreset).trim() || null,
  };

  try {
    const stored = await writeTradeTelemetry({ payload });
    return NextResponse.json(
      {
        ok: true,
        stored: !!stored,
        key: stored?.key || null,
      },
      { status: 200 },
    );
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Telemetry write failed';
    return NextResponse.json({ ok: false, error: msg }, { status: 500 });
  }
}

