import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

function normalized(input: string | undefined): string | null {
  const value = String(input || '').trim();
  return value.length > 0 ? value : null;
}

export async function GET() {
  const workspaceBuildSha = normalized(process.env.NEXT_PUBLIC_BUILD_SHA) || normalized(process.env.GITHUB_SHA);
  const investmentsServiceSha = normalized(process.env.INVESTMENTS_SERVICE_BUILD_SHA);
  const driftDetected = Boolean(
    workspaceBuildSha &&
    investmentsServiceSha &&
    workspaceBuildSha !== investmentsServiceSha,
  );

  return NextResponse.json(
    {
      workspaceBuildSha,
      investmentsServiceSha,
      driftDetected,
      warning: driftDetected
        ? 'Investments container SHA differs from current workspace build SHA.'
        : null,
    },
    { status: 200 },
  );
}
