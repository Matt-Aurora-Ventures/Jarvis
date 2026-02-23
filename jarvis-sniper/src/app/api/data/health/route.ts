import { NextResponse } from 'next/server';
import { getSourceHealthSummary } from '@/lib/data-plane/health-store';

export const runtime = 'nodejs';

export async function GET() {
  try {
    const summary = getSourceHealthSummary();
    return NextResponse.json({
      ok: true,
      updatedAt: summary.updatedAt,
      totalSources: summary.totalSources,
      healthySources: summary.healthySources,
      degradedSources: summary.degradedSources,
      sources: summary.snapshots,
    });
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        error: error instanceof Error ? error.message : 'Failed to load source health',
      },
      { status: 500 },
    );
  }
}
