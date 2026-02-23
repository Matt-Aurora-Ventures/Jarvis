import { NextResponse } from 'next/server';
import {
  activateSpotProtection,
  cancelSpotProtection,
  preflightSpotProtection,
  reconcileSpotProtection,
} from '@/lib/execution/spot-protection';
import type { SpotProtectionActivationInput } from '@/lib/execution/spot-protection-types';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  const payload = await request.json().catch(() => ({} as Record<string, unknown>));
  const action = String(payload?.action || '').trim().toLowerCase();

  if (!action) {
    return NextResponse.json(
      {
        ok: false,
        error: 'action is required (preflight|activate|cancel|reconcile)',
      },
      { status: 400 },
    );
  }

  if (action === 'preflight') {
    const result = await preflightSpotProtection();
    return NextResponse.json(result, { status: result.ok ? 200 : 503 });
  }

  if (action === 'activate') {
    const input = (payload?.payload || {}) as SpotProtectionActivationInput;
    const result = await activateSpotProtection(input);
    return NextResponse.json(result, { status: result.ok ? 200 : 422 });
  }

  if (action === 'cancel') {
    const positionId = String(payload?.positionId || '').trim();
    const reason = String(payload?.reason || '').trim() || undefined;
    const result = await cancelSpotProtection(positionId, reason);
    return NextResponse.json(result, { status: result.ok ? 200 : 422 });
  }

  if (action === 'reconcile') {
    const ids = Array.isArray(payload?.positionIds)
      ? (payload.positionIds as unknown[]).map((id) => String(id || '').trim()).filter(Boolean)
      : undefined;
    const result = await reconcileSpotProtection(ids);
    return NextResponse.json(result, { status: result.ok ? 200 : 503 });
  }

  return NextResponse.json(
    {
      ok: false,
      error: `Unsupported action: ${action}`,
    },
    { status: 400 },
  );
}
