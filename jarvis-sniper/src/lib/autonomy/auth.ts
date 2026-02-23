import { NextResponse } from 'next/server';

export interface AutonomyAuthOptions {
  envKeys?: string[];
  allowWhenUnconfigured?: boolean;
  unauthorizedMessage?: string;
  unconfiguredMessage?: string;
  unconfiguredStatus?: number;
}

export interface AutonomyAuthCheckResult {
  authorized: boolean;
  configured: boolean;
  matchedEnvKey: string | null;
}

function normalizeEnvKeys(envKeys?: string[]): string[] {
  const keys = Array.isArray(envKeys) && envKeys.length > 0 ? envKeys : ['AUTONOMY_JOB_TOKEN'];
  return keys
    .map((k) => String(k || '').trim())
    .filter(Boolean);
}

function resolveExpectedToken(envKeys: string[]): { token: string | null; matchedEnvKey: string | null } {
  for (const key of envKeys) {
    const token = String(process.env[key] || '').trim();
    if (token) {
      return { token, matchedEnvKey: key };
    }
  }
  return { token: null, matchedEnvKey: null };
}

export function extractBearerToken(request: Request): string | null {
  const auth = String(request.headers.get('authorization') || '').trim();
  if (!auth.toLowerCase().startsWith('bearer ')) return null;
  const token = auth.slice(7).trim();
  return token || null;
}

export function checkAutonomyAuth(
  request: Request,
  options: AutonomyAuthOptions = {},
): AutonomyAuthCheckResult {
  const envKeys = normalizeEnvKeys(options.envKeys);
  const { token: expected, matchedEnvKey } = resolveExpectedToken(envKeys);
  if (!expected) {
    return {
      authorized: false,
      configured: false,
      matchedEnvKey,
    };
  }

  const actual = extractBearerToken(request);
  return {
    authorized: !!actual && actual === expected,
    configured: true,
    matchedEnvKey,
  };
}

export function requireAutonomyAuth(
  request: Request,
  options: AutonomyAuthOptions = {},
): NextResponse | null {
  const result = checkAutonomyAuth(request, options);
  if (result.configured && result.authorized) return null;
  if (!result.configured && (options.allowWhenUnconfigured ?? false)) return null;

  if (!result.configured) {
    return NextResponse.json(
      {
        error: options.unconfiguredMessage || 'Autonomy auth token is not configured',
      },
      { status: options.unconfiguredStatus ?? 503 },
    );
  }

  return NextResponse.json(
    {
      error: options.unauthorizedMessage || 'Unauthorized',
    },
    { status: 401 },
  );
}