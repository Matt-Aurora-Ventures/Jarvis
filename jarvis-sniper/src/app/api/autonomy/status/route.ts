import { NextResponse } from 'next/server';
import { loadAutonomyState } from '@/lib/autonomy/audit-store';
import { getStrategyOverrideSnapshot } from '@/lib/autonomy/override-store';

export const runtime = 'nodejs';

function asBoolEnv(value: string | undefined, fallback = false): boolean {
  if (value == null) return fallback;
  return String(value).trim().toLowerCase() === 'true';
}

export async function GET() {
  try {
    const [state, override] = await Promise.all([
      loadAutonomyState(),
      getStrategyOverrideSnapshot(),
    ]);

    const latestCycleId = state.latestCompletedCycleId || state.latestCycleId || null;
    const latestReasonCode = latestCycleId
      ? (state.cycles?.[latestCycleId]?.reasonCode || null)
      : null;

    return NextResponse.json({
      autonomyEnabled: asBoolEnv(process.env.AUTONOMY_ENABLED, false),
      applyOverridesEnabled: asBoolEnv(process.env.AUTONOMY_APPLY_OVERRIDES, false),
      xaiConfigured: String(process.env.XAI_API_KEY || '').trim().length > 0,
      latestCycleId,
      latestReasonCode,
      overrideVersion: Number.isFinite(Number(override?.version)) ? Number(override?.version) : 0,
      overrideUpdatedAt: override?.updatedAt || null,
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Failed to load autonomy status',
      },
      { status: 500 },
    );
  }
}
