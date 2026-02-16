import { NextResponse } from 'next/server';

const ALLOWED_ORIGINS = new Set([
  'https://kr8tiv.web.app',
  'https://kr8tiv.firebaseapp.com',
  'http://localhost:3000',
  'http://127.0.0.1:3000',
  'http://localhost:3001',
  'http://127.0.0.1:3001',
]);

function resolveAllowedOrigin(origin: string | null): string | null {
  if (!origin) return null;
  const trimmed = origin.trim();
  if (!trimmed) return null;
  return ALLOWED_ORIGINS.has(trimmed) ? trimmed : null;
}

export function withBacktestCors<T extends Response>(request: Request, response: T): T {
  const origin = resolveAllowedOrigin(request.headers.get('origin'));
  if (!origin) return response;

  // Next.js route-handler responses have mutable headers.
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
