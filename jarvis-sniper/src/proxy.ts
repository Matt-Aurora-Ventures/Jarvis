import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Production security middleware for multi-user hosted deployment.
 *
 * Applies security headers, CORS controls, and basic request validation
 * to all routes. Critical for a Solana trading app handling real money.
 */
export function proxy(request: NextRequest) {
  const response = NextResponse.next();

  // ─── Security Headers ───
  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('X-XSS-Protection', '1; mode=block');
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  response.headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');

  // Strict Transport Security (HTTPS only in production)
  if (process.env.NODE_ENV === 'production') {
    response.headers.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  }

  // ─── API Route Protection ───
  if (request.nextUrl.pathname.startsWith('/api/')) {
    // CORS: only allow same-origin requests to API routes
    const origin = request.headers.get('origin');
    const host = request.headers.get('host');
    const allowedOrigins = process.env.ALLOWED_ORIGINS?.split(',') || [];

    if (origin) {
      // Allow same-origin or explicitly allowed origins
      const originHost = new URL(origin).host;
      if (originHost === host || allowedOrigins.includes(origin)) {
        response.headers.set('Access-Control-Allow-Origin', origin);
        response.headers.set('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
        response.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');
      }
    }

    // Handle preflight
    if (request.method === 'OPTIONS') {
      return new NextResponse(null, { status: 204, headers: response.headers });
    }

    // Rate limit header hint (actual limiting is in route handlers)
    response.headers.set('X-RateLimit-Policy', 'sliding-window');
  }

  return response;
}

export const config = {
  matcher: [
    // Apply to all routes except static assets and Next.js internals
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
};
