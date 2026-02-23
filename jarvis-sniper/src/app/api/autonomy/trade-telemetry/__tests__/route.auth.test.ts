import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockAppendTradeTelemetryEvent = vi.fn();
const mockAutonomyLimiterCheck = vi.fn();
const mockUpsertTradeEvidence = vi.fn();

vi.mock('@/lib/autonomy/trade-telemetry-store', () => ({
  appendTradeTelemetryEvent: mockAppendTradeTelemetryEvent,
}));

vi.mock('@/lib/rate-limiter', () => ({
  autonomyRateLimiter: { check: mockAutonomyLimiterCheck },
  getClientIp: vi.fn().mockReturnValue('127.0.0.1'),
}));

vi.mock('@/lib/execution/evidence', () => ({
  upsertTradeEvidence: mockUpsertTradeEvidence,
}));

describe('POST /api/autonomy/trade-telemetry auth', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    process.env.AUTONOMY_TELEMETRY_TOKEN = 'telemetry-token';
    mockAutonomyLimiterCheck.mockReturnValue({ allowed: true });
    mockUpsertTradeEvidence.mockResolvedValue(undefined);
    mockAppendTradeTelemetryEvent.mockResolvedValue({
      schemaVersion: 1,
      positionId: 'pos-1',
      mint: 'mint-1',
      status: 'open',
      trustLevel: 'trusted',
      eventType: 'sell_attempt',
      receivedAt: new Date().toISOString(),
      receivedAtMs: Date.now(),
    });
  });

  it('returns 401 without telemetry token', async () => {
    const route = await import('@/app/api/autonomy/trade-telemetry/route');
    const req = new Request('http://localhost/api/autonomy/trade-telemetry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ positionId: 'p', mint: 'm', status: 'open' }),
    });
    const res = await route.POST(req);
    expect(res.status).toBe(401);
  });

  it('returns 429 when telemetry rate limit exceeded', async () => {
    mockAutonomyLimiterCheck.mockReturnValue({ allowed: false, retryAfterMs: 12_000 });
    const route = await import('@/app/api/autonomy/trade-telemetry/route');
    const req = new Request('http://localhost/api/autonomy/trade-telemetry', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer telemetry-token',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ positionId: 'p', mint: 'm', status: 'open' }),
    });
    const res = await route.POST(req);
    expect(res.status).toBe(429);
  });

  it('accepts valid signed request', async () => {
    const route = await import('@/app/api/autonomy/trade-telemetry/route');
    const req = new Request('http://localhost/api/autonomy/trade-telemetry', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer telemetry-token',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        positionId: 'pos-1',
        mint: 'mint-1',
        status: 'open',
        eventType: 'sell_attempt',
      }),
    });
    const res = await route.POST(req);
    const body = await res.json();
    expect(res.status).toBe(202);
    expect(body.ok).toBe(true);
    expect(mockUpsertTradeEvidence).toHaveBeenCalled();
  });
});
