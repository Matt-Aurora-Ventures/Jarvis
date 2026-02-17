import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockAppendTradeTelemetryEvent = vi.fn();

vi.mock('@/lib/autonomy/trade-telemetry-store', () => ({
  appendTradeTelemetryEvent: mockAppendTradeTelemetryEvent,
}));

describe('POST /api/autonomy/trade-telemetry', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it('rejects invalid payloads', async () => {
    const route = await import('@/app/api/autonomy/trade-telemetry/route');
    const req = new Request('http://localhost/api/autonomy/trade-telemetry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mint: 'abc', status: 'open' }),
    });
    const res = await route.POST(req);
    const body = await res.json();
    expect(res.status).toBe(400);
    expect(String(body.error || '')).toContain('positionId');
  });

  it('persists sanitized telemetry and returns 202', async () => {
    mockAppendTradeTelemetryEvent.mockResolvedValue({
      schemaVersion: 1,
      positionId: 'pos-1',
      mint: 'mint-1',
      status: 'open',
      receivedAt: '2026-02-17T20:00:00.000Z',
      receivedAtMs: 1763352000000,
      eventType: 'sell_attempt',
    });
    const route = await import('@/app/api/autonomy/trade-telemetry/route');
    const req = new Request('http://localhost/api/autonomy/trade-telemetry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
    expect(body.eventType).toBe('sell_attempt');
    expect(mockAppendTradeTelemetryEvent).toHaveBeenCalled();
  });
});
