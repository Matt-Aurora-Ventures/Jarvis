import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('backtest CORS allowlist', () => {
  beforeEach(() => {
    vi.resetModules();
    delete process.env.ALLOWED_ORIGINS;
    delete process.env.NEXT_PUBLIC_CANONICAL_ORIGIN;
  });

  it('allows official production domains', async () => {
    const { withBacktestCors } = await import('@/lib/backtest-cors');

    for (const origin of [
      'https://kr8tiv.web.app',
      'https://kr8tiv.firebaseapp.com',
      'https://jarvislife.cloud',
      'https://www.jarvislife.cloud',
    ]) {
      const req = new Request('http://localhost/api/backtest', { headers: { origin } });
      const res = withBacktestCors(req, new Response('ok'));
      expect(res.headers.get('Access-Control-Allow-Origin')).toBe(origin);
    }
  });

  it('rejects unknown origins', async () => {
    const { withBacktestCors } = await import('@/lib/backtest-cors');
    const req = new Request('http://localhost/api/backtest', {
      headers: { origin: 'https://evil.example' },
    });
    const res = withBacktestCors(req, new Response('ok'));

    expect(res.headers.get('Access-Control-Allow-Origin')).toBeNull();
  });

  it('includes runtime env origins from ALLOWED_ORIGINS and NEXT_PUBLIC_CANONICAL_ORIGIN', async () => {
    process.env.ALLOWED_ORIGINS = 'https://custom.one, https://custom.two';
    process.env.NEXT_PUBLIC_CANONICAL_ORIGIN = 'https://canonical.example';
    const { withBacktestCors } = await import('@/lib/backtest-cors');

    for (const origin of ['https://custom.one', 'https://custom.two', 'https://canonical.example']) {
      const req = new Request('http://localhost/api/backtest', { headers: { origin } });
      const res = withBacktestCors(req, new Response('ok'));
      expect(res.headers.get('Access-Control-Allow-Origin')).toBe(origin);
    }
  });
});

