import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockRunHourlyAutonomyCycle = vi.fn();
const mockRateLimiterCheck = vi.fn();

vi.mock('@/lib/autonomy/hourly-cycle', () => ({
  runHourlyAutonomyCycle: mockRunHourlyAutonomyCycle,
}));

vi.mock('@/lib/rate-limiter', async () => {
  const actual = await vi.importActual<typeof import('@/lib/rate-limiter')>('@/lib/rate-limiter');
  return {
    ...actual,
    autonomyRateLimiter: { check: mockRateLimiterCheck },
    getClientIp: vi.fn().mockReturnValue('127.0.0.1'),
  };
});

describe('POST /api/autonomy/hourly', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    process.env.AUTONOMY_JOB_TOKEN = 'test-token';
    mockRateLimiterCheck.mockReturnValue({ allowed: true });
  });

  it('returns 401 when authorization token is missing', async () => {
    const route = await import('@/app/api/autonomy/hourly/route');
    const req = new Request('http://localhost/api/autonomy/hourly', { method: 'POST' });
    const res = await route.POST(req);
    expect(res.status).toBe(401);
  });

  it('returns cycle summary when authorized', async () => {
    mockRunHourlyAutonomyCycle.mockResolvedValue({
      ok: true,
      cycleId: '2026021318',
      reasonCode: 'AUTONOMY_PENDING_BATCH',
      state: {
        latestCycleId: '2026021318',
        latestCompletedCycleId: '2026021317',
        pendingBatch: { cycleId: '2026021318', batchId: 'batch-1' },
      },
    });
    const route = await import('@/app/api/autonomy/hourly/route');
    const req = new Request('http://localhost/api/autonomy/hourly', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer test-token',
        'Content-Type': 'application/json',
      },
      body: '{}',
    });
    const res = await route.POST(req);
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.cycleId).toBe('2026021318');
    expect(body.reasonCode).toBe('AUTONOMY_PENDING_BATCH');
  });
});
