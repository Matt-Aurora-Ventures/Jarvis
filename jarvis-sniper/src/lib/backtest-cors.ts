import { NextResponse } from 'next/server';

const STATIC_ALLOWED_ORIGINS = new Set([
  'https://kr8tiv.web.app',
  'https://kr8tiv.firebaseapp.com',
  'https://jarvislife.cloud',
  'https://www.jarvislife.cloud',
  'http://localhost:3000',
  'http://127.0.0.1:3000',
  'http://localhost:3001',
  'http://127.0.0.1:3001',
]);

function normalizeOrigin(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const trimmed = String(raw).trim();
  if (!trimmed) return null;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null;
    return `${parsed.protocol}//${parsed.host}`;
  } catch {
    return null;
  }
}

function buildAllowedOrigins(): Set<string> {
  const allow = new Set<string>(STATIC_ALLOWED_ORIGINS);

  const extra = String(process.env.ALLOWED_ORIGINS || '')
    .split(',')
    .map((x) => normalizeOrigin(x))
    .filter((x): x is string => !!x);
  for (const o of extra) allow.add(o);

  const canonical = normalizeOrigin(process.env.NEXT_PUBLIC_CANONICAL_ORIGIN);
  if (canonical) allow.add(canonical);

  return allow;
}

function resolveAllowedOrigin(origin: string | null): string | null {
  const normalized = normalizeOrigin(origin);
  if (!normalized) return null;
  const allow = buildAllowedOrigins();
  return allow.has(normalized) ? normalized : null;
}

export function withBacktestCors<T extends Response>(request: Request, response: T): T {
  const origin = resolveAllowedOrigin(request.headers.get('origin'));
  if (!origin) return response;

  // In Next.js route handlers, the Response headers are mutable.
  response.headers.set('Access-Control-Allow-Origin', origin);
  response.headers.set('Vary', 'Origin');
  response.headers.set('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  response.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  response.headers.set('Access-Control-Max-Age', '86400');
  return response;
}

export function backtestCorsOptions(request: Request): NextResponse {
  return withBacktestCors(request, new NextResponse(null, { status: 204 }));
}

