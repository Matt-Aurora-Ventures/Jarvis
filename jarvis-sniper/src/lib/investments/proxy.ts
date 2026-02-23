import { NextResponse } from 'next/server';

const DEFAULT_INVESTMENTS_BASE_URL = 'http://127.0.0.1:8770';

function baseUrl(): string {
  return String(process.env.INVESTMENTS_SERVICE_BASE_URL || DEFAULT_INVESTMENTS_BASE_URL).trim().replace(/\/+$/, '');
}

function upstreamUrl(path: string, query?: URLSearchParams): string {
  const q = query && query.toString() ? `?${query.toString()}` : '';
  return `${baseUrl()}/api/investments${path}${q}`;
}

function extractBearerToken(request: Request): string | null {
  const raw = String(request.headers.get('authorization') || '').trim();
  if (!raw.toLowerCase().startsWith('bearer ')) return null;
  const token = raw.slice(7).trim();
  return token || null;
}

async function responseFromUpstream(upstream: Response): Promise<NextResponse> {
  const contentType = String(upstream.headers.get('content-type') || '').toLowerCase();
  if (contentType.includes('application/json')) {
    const body = await upstream.json().catch(() => ({}));
    return NextResponse.json(body, { status: upstream.status });
  }
  const text = await upstream.text().catch(() => '');
  return NextResponse.json(
    {
      error: 'Non-JSON upstream response',
      status: upstream.status,
      body: text.slice(0, 2000),
    },
    { status: upstream.status },
  );
}

function networkError(error: unknown): NextResponse {
  const message = error instanceof Error ? error.message : String(error);
  return NextResponse.json(
    {
      error: 'Investments upstream unavailable',
      details: message,
    },
    { status: 502 },
  );
}

export function verifyInvestmentsAdminAuth(request: Request): NextResponse | null {
  const expectedToken = String(process.env.INVESTMENTS_ADMIN_TOKEN || '').trim();
  if (!expectedToken) {
    return NextResponse.json(
      {
        error: 'Investments admin token is not configured',
      },
      { status: 503 },
    );
  }

  const actualToken = extractBearerToken(request);
  if (!actualToken || actualToken !== expectedToken) {
    return NextResponse.json(
      {
        error: 'Unauthorized',
      },
      { status: 401 },
    );
  }

  return null;
}

export async function proxyInvestmentsGet(path: string, request: Request): Promise<NextResponse> {
  try {
    const url = new URL(request.url);
    const token = extractBearerToken(request);
    const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
    const upstream = await fetch(upstreamUrl(path, url.searchParams), {
      method: 'GET',
      headers,
      cache: 'no-store',
    });
    return await responseFromUpstream(upstream);
  } catch (error) {
    return networkError(error);
  }
}

export async function proxyInvestmentsPost(path: string, request: Request): Promise<NextResponse> {
  try {
    const payload = await request.json().catch(() => ({}));
    const token = String(process.env.INVESTMENTS_ADMIN_TOKEN || '').trim();
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
    const upstream = await fetch(upstreamUrl(path), {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      cache: 'no-store',
    });
    return await responseFromUpstream(upstream);
  } catch (error) {
    return networkError(error);
  }
}
