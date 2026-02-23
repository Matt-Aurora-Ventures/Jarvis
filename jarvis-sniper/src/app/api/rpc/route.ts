/**
 * Solana JSON-RPC proxy — routes client requests through the server's
 * paid RPC endpoint (Helius) so the API key stays server-only.
 *
 * Allowed methods are whitelisted to prevent abuse.
 * Rate limited with a dedicated RPC limiter (web3 polling is chatty).
 */
import { NextResponse } from 'next/server';
import { getClientIp, rpcRateLimiter } from '@/lib/rate-limiter';
import { resolveServerRpcConfig } from '@/lib/server-rpc-config';

/** Only proxy safe, read-heavy methods + send/confirm for trading. */
const ALLOWED_METHODS = new Set([
  'getLatestBlockhash',
  'getRecentBlockhash',
  'isBlockhashValid',
  'getBalance',
  'getSignaturesForAddress',
  'getTokenAccountsByOwner',
  'getAccountInfo',
  'getMultipleAccounts',
  'getFeeForMessage',
  'getSignatureStatuses',
  'getTransaction',
  'getSlot',
  'getBlockHeight',
  'getMinimumBalanceForRentExemption',
  'sendTransaction',
  'sendRawTransaction',
  'simulateTransaction',
  'confirmTransaction',
  'getRecentPrioritizationFees',
]);

export async function POST(request: Request) {
  // Rate limit
  const ip = getClientIp(request);
  const limit = await rpcRateLimiter.check(ip);
  if (!limit.allowed) {
    return NextResponse.json(
      { jsonrpc: '2.0', error: { code: 429, message: 'Rate limit exceeded' }, id: null },
      { status: 429, headers: { 'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)) } },
    );
  }

  try {
    const body = await request.json();

    // Validate JSON-RPC structure
    const method = body?.method;
    if (typeof method !== 'string' || !ALLOWED_METHODS.has(method)) {
      return NextResponse.json(
        { jsonrpc: '2.0', error: { code: -32601, message: `Method not allowed: ${method}` }, id: body?.id ?? null },
        { status: 400 },
      );
    }

    const rpcConfig = resolveServerRpcConfig();
    if (!rpcConfig.ok || !rpcConfig.url) {
      return NextResponse.json(
        {
          jsonrpc: '2.0',
          error: {
            code: -32001,
            message: 'RPC provider unavailable',
            data: { diagnostic: rpcConfig.diagnostic, source: rpcConfig.source },
          },
          id: body?.id ?? null,
        },
        { status: 503 },
      );
    }

    // Forward to upstream RPC with bounded retries for transient 429/5xx.
    const maxAttempts = 4;
    let lastStatus = 0;
    let lastText = '';

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      const upstream = await fetch(rpcConfig.url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      lastStatus = upstream.status;
      lastText = await upstream.text();

      if (upstream.ok) {
        try {
          return NextResponse.json(JSON.parse(lastText));
        } catch {
          return NextResponse.json(
            { jsonrpc: '2.0', error: { code: -32700, message: 'Invalid JSON from upstream RPC' }, id: body?.id ?? null },
            { status: 502 },
          );
        }
      }

      const shouldRetry = lastStatus === 429 || (lastStatus >= 500 && lastStatus <= 599);
      if (!shouldRetry || attempt === maxAttempts) break;

      const retryHeader = Number(upstream.headers.get('retry-after') || 0);
      const backoffMs = retryHeader > 0
        ? retryHeader * 1000
        : Math.min(3000, 300 * Math.pow(2, attempt - 1));

      await new Promise((resolve) => setTimeout(resolve, backoffMs));
    }

    // Return sanitized structured error so clients don't spin forever.
    return NextResponse.json(
      {
        jsonrpc: '2.0',
        error: {
          code: -32000,
          message: `Upstream RPC failure (${lastStatus || 'unknown'})`,
        },
        id: body?.id ?? null,
      },
      { status: lastStatus || 502 },
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    console.error('[api/rpc] Proxy error:', msg);
    return NextResponse.json(
      { jsonrpc: '2.0', error: { code: -32000, message: 'RPC proxy error' }, id: null },
      { status: 502 },
    );
  }
}
