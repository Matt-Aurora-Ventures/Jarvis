import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockActivate = vi.fn();
const mockCancel = vi.fn();
const mockPreflight = vi.fn();
const mockReconcile = vi.fn();

vi.mock('@/lib/execution/spot-protection', () => ({
  activateSpotProtection: mockActivate,
  cancelSpotProtection: mockCancel,
  preflightSpotProtection: mockPreflight,
  reconcileSpotProtection: mockReconcile,
}));

describe('POST /api/execution/protection', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it('returns 400 for missing action', async () => {
    const route = await import('@/app/api/execution/protection/route');
    const res = await route.POST(new Request('http://localhost/api/execution/protection', {
      method: 'POST',
      body: JSON.stringify({}),
      headers: { 'Content-Type': 'application/json' },
    }));

    const body = await res.json();
    expect(res.status).toBe(400);
    expect(body.ok).toBe(false);
    expect(String(body.error || '')).toContain('action is required');
  });

  it('routes preflight action and returns 200 on success', async () => {
    mockPreflight.mockResolvedValue({
      ok: true,
      provider: 'local',
      checkedAt: Date.now(),
    });
    const route = await import('@/app/api/execution/protection/route');
    const res = await route.POST(new Request('http://localhost/api/execution/protection', {
      method: 'POST',
      body: JSON.stringify({ action: 'preflight' }),
      headers: { 'Content-Type': 'application/json' },
    }));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.ok).toBe(true);
    expect(mockPreflight).toHaveBeenCalledTimes(1);
  });

  it('routes activate/cancel/reconcile actions and forwards payload fields', async () => {
    mockActivate.mockResolvedValue({
      ok: true,
      provider: 'local',
      status: 'active',
      tpOrderKey: 'tp-key',
      slOrderKey: 'sl-key',
    });
    mockCancel.mockResolvedValue({
      ok: true,
      provider: 'local',
      positionId: 'pos-1',
      status: 'cancelled',
    });
    mockReconcile.mockResolvedValue({
      ok: true,
      provider: 'local',
      records: [{ positionId: 'pos-1', status: 'active' }],
    });

    const route = await import('@/app/api/execution/protection/route');

    const activateRes = await route.POST(new Request('http://localhost/api/execution/protection', {
      method: 'POST',
      body: JSON.stringify({
        action: 'activate',
        payload: { positionId: 'pos-1', walletAddress: 'wallet-1' },
      }),
      headers: { 'Content-Type': 'application/json' },
    }));
    expect(activateRes.status).toBe(200);
    expect(mockActivate).toHaveBeenCalledWith(expect.objectContaining({ positionId: 'pos-1' }));

    const cancelRes = await route.POST(new Request('http://localhost/api/execution/protection', {
      method: 'POST',
      body: JSON.stringify({
        action: 'cancel',
        positionId: 'pos-1',
        reason: 'closed',
      }),
      headers: { 'Content-Type': 'application/json' },
    }));
    expect(cancelRes.status).toBe(200);
    expect(mockCancel).toHaveBeenCalledWith('pos-1', 'closed');

    const reconcileRes = await route.POST(new Request('http://localhost/api/execution/protection', {
      method: 'POST',
      body: JSON.stringify({
        action: 'reconcile',
        positionIds: ['pos-1', 'pos-2'],
      }),
      headers: { 'Content-Type': 'application/json' },
    }));
    expect(reconcileRes.status).toBe(200);
    expect(mockReconcile).toHaveBeenCalledWith(['pos-1', 'pos-2']);
  });
});

