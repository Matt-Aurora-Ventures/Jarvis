import { NextResponse } from 'next/server';
import { getStrategyOverrideSnapshot } from '@/lib/autonomy/override-store';
import { requireAutonomyAuth } from '@/lib/autonomy/auth';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  const authError = requireAutonomyAuth(request, {
    envKeys: ['AUTONOMY_READ_TOKEN', 'AUTONOMY_JOB_TOKEN'],
    allowWhenUnconfigured: false,
  });
  if (authError) return authError;

  try {
    const snapshot = await getStrategyOverrideSnapshot();
    return NextResponse.json({
      version: snapshot.version,
      updatedAt: snapshot.updatedAt,
      cycleId: snapshot.cycleId,
      signature: snapshot.signature,
      patches: snapshot.patches,
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Failed to load strategy overrides',
      },
      { status: 500 },
    );
  }
}

