import { NextResponse } from 'next/server';
import { swapRateLimiter, getClientIp } from '@/lib/rate-limiter';

const JITO_BLOCK_ENGINE_URL = 'https://mainnet.block-engine.jito.wtf/api/v1/bundles';

/**
 * Proxy for Jito Block Engine (avoids CORS from browser).
 * Accepts an array of signed, base64-encoded VersionedTransactions.
 */
export async function POST(request: Request) {
  try {
    // Rate limit (uses swap limiter: 20 req/min — Jito is transaction-heavy)
    const ip = getClientIp(request);
    const limit = await swapRateLimiter.check(ip);
    if (!limit.allowed) {
      return NextResponse.json(
        { error: 'Rate limit exceeded' },
        {
          status: 429,
          headers: {
            'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)),
            'X-RateLimit-Remaining': '0',
          },
        },
      );
    }

    const { transactions } = await request.json();

    if (!Array.isArray(transactions) || transactions.length === 0) {
      return NextResponse.json({ error: 'Empty bundle' }, { status: 400 });
    }

    if (transactions.length > 5) {
      return NextResponse.json({ error: 'Max 5 transactions per bundle' }, { status: 400 });
    }

    console.log(`[Jito] Submitting bundle of ${transactions.length} txs...`);

    const payload = {
      jsonrpc: '2.0',
      id: 1,
      method: 'sendBundle',
      params: [transactions],
    };

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15_000); // 15s timeout
    const res = await fetch(JITO_BLOCK_ENGINE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    clearTimeout(timer);

    const data = await res.json();

    if (data.error) {
      console.error('[Jito] Error:', data.error);
      return NextResponse.json({ error: JSON.stringify(data.error) }, { status: 502 });
    }

    console.log(`[Jito] Bundle accepted: ${data.result}`);
    return NextResponse.json({ bundleId: data.result });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Jito bundle submission failed';
    console.error('[Jito Proxy Error]', message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
