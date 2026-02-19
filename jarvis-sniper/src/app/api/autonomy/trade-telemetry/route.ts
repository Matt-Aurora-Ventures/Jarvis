import { NextResponse } from 'next/server';
import { appendTradeTelemetryEvent } from '@/lib/autonomy/trade-telemetry-store';
import type { TradeTelemetryEvent } from '@/lib/autonomy/trade-telemetry-client';
import { autonomyRateLimiter, getClientIp } from '@/lib/rate-limiter';
import { requireAutonomyAuth } from '@/lib/autonomy/auth';
import { upsertTradeEvidence } from '@/lib/execution/evidence';
import type { TradeEvidenceV2 } from '@/lib/data-plane/types';

export const runtime = 'nodejs';

const MAX_TELEMETRY_BODY_BYTES = 16 * 1024;

function badRequest(message: string) {
  return NextResponse.json({ ok: false, error: message }, { status: 400 });
}

function toFiniteNumber(value: unknown): number | null {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function toTradeSurface(value: unknown): TradeEvidenceV2['surface'] {
  const text = String(value || '').trim().toLowerCase();
  if (text === 'main' || text === 'bags' || text === 'tradfi') return text;
  return 'unknown';
}

function toMevRiskTag(value: unknown): TradeEvidenceV2['mevRiskTag'] {
  const text = String(value || '').trim().toLowerCase();
  if (text === 'low' || text === 'medium' || text === 'high') return text;
  return 'unknown';
}

function toOutcome(values: unknown[]): TradeEvidenceV2['outcome'] {
  for (const value of values) {
    const text = String(value || '').trim().toLowerCase();
    if (!text) continue;
    if (text === 'confirmed' || text === 'success' || text === 'succeeded' || text === 'closed') return 'confirmed';
    if (text === 'failed' || text === 'failure' || text === 'error' || text === 'rejected') return 'failed';
    if (text === 'no_route' || text === 'noroute' || text === 'route_missing' || text === 'missing_route') return 'no_route';
    if (text === 'unresolved' || text === 'pending' || text === 'submitted' || text === 'inflight') return 'unresolved';
  }
  return 'unresolved';
}

function toStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((v) => String(v || '').trim()).filter(Boolean);
  }
  const text = String(value || '').trim();
  return text ? [text] : [];
}

function toTradeId(raw: Record<string, unknown>, positionId: string): string {
  const candidates = [
    raw.tradeId,
    raw.sellTxHash,
    raw.buyTxHash,
    raw.transactionHash,
    positionId,
  ];
  for (const candidate of candidates) {
    const text = String(candidate || '').trim();
    if (text) return text.slice(0, 160);
  }
  return `telemetry-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function toDecisionTs(raw: Record<string, unknown>, fallbackIso: string): string {
  const candidate = String(raw.decisionTs || raw.timestamp || '').trim();
  if (candidate) {
    const parsed = new Date(candidate);
    if (!Number.isNaN(parsed.valueOf())) return parsed.toISOString();
  }
  return fallbackIso;
}

function buildEvidence(
  raw: Record<string, unknown>,
  normalized: {
    positionId: string;
    mint: string;
    status: string;
    strategyId?: string | null;
    receivedAt: string;
    eventType?: string;
    executionOutcome?: string;
    failureCode?: string | null;
    failureReason?: string | null;
    sellTxHash?: string | null;
    buyTxHash?: string | null;
    trustLevel: string;
  },
): TradeEvidenceV2 {
  const strategyId = String(raw.strategyId || normalized.strategyId || 'unknown').trim() || 'unknown';
  const route = String(raw.route || 'autonomy_trade_telemetry').trim() || 'autonomy_trade_telemetry';

  return {
    tradeId: toTradeId(raw, normalized.positionId),
    surface: toTradeSurface(raw.surface),
    strategyId,
    decisionTs: toDecisionTs(raw, normalized.receivedAt),
    route,
    expectedPrice: toFiniteNumber(raw.expectedPrice),
    executedPrice: toFiniteNumber(raw.executedPrice),
    slippageBps: toFiniteNumber(raw.slippageBps),
    priorityFeeLamports: toFiniteNumber(raw.priorityFeeLamports),
    jitoUsed: Boolean(raw.jitoUsed),
    mevRiskTag: toMevRiskTag(raw.mevRiskTag),
    datasetRefs: toStringArray(raw.datasetRefs),
    outcome: toOutcome([
      raw.executionOutcome,
      raw.outcome,
      normalized.executionOutcome,
      raw.status,
      normalized.status,
    ]),
    metadata: {
      positionId: normalized.positionId,
      mint: normalized.mint,
      status: normalized.status,
      eventType: normalized.eventType || 'unknown',
      trustLevel: normalized.trustLevel,
      failureCode: normalized.failureCode || null,
      failureReason: normalized.failureReason || null,
      sellTxHash: normalized.sellTxHash || null,
      buyTxHash: normalized.buyTxHash || null,
    },
  };
}

export async function POST(request: Request) {
  const ip = getClientIp(request);
  const limit = await autonomyRateLimiter.check(ip);
  if (!limit.allowed) {
    return NextResponse.json(
      { ok: false, error: 'Rate limit exceeded. Try again shortly.' },
      {
        status: 429,
        headers: {
          'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)),
        },
      },
    );
  }

  const authError = requireAutonomyAuth(request, {
    envKeys: ['AUTONOMY_TELEMETRY_TOKEN', 'AUTONOMY_JOB_TOKEN'],
    allowWhenUnconfigured: false,
  });
  if (authError) return authError;

  const contentLength = Number(request.headers.get('content-length') || 0);
  if (Number.isFinite(contentLength) && contentLength > MAX_TELEMETRY_BODY_BYTES) {
    return NextResponse.json(
      { ok: false, error: `Telemetry payload too large (max ${MAX_TELEMETRY_BODY_BYTES} bytes)` },
      { status: 413 },
    );
  }

  try {
    const body = await request.json() as Partial<TradeTelemetryEvent> | null;
    if (!body || typeof body !== 'object') {
      return badRequest('Invalid telemetry payload');
    }

    const raw = body as unknown as Record<string, unknown>;
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
      trustLevel: 'trusted',
    } as TradeTelemetryEvent);

    const evidence = buildEvidence(raw, {
      positionId: saved.positionId,
      mint: saved.mint,
      status: saved.status,
      strategyId: saved.strategyId,
      receivedAt: saved.receivedAt,
      eventType: saved.eventType,
      executionOutcome: saved.executionOutcome,
      failureCode: saved.failureCode,
      failureReason: saved.failureReason,
      sellTxHash: saved.sellTxHash,
      buyTxHash: saved.buyTxHash,
      trustLevel: saved.trustLevel,
    });

    try {
      await upsertTradeEvidence(evidence);
    } catch {
      // best effort
    }

    return NextResponse.json({
      ok: true,
      receivedAt: saved.receivedAt,
      eventType: saved.eventType,
      trustLevel: saved.trustLevel,
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
