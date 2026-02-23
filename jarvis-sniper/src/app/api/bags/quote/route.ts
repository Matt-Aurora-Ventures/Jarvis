/**
 * Server-side Bags SDK proxy — Quote endpoint
 * Bypasses CORS by running SDK on the server.
 *
 * Rate limiting: 30 req/min per IP (most expensive upstream call).
 * Caching: 3-second TTL per unique quote key to deduplicate identical requests.
 */
import { NextResponse } from 'next/server';
import { BagsSDK } from '@bagsfm/bags-sdk';
import { Connection, PublicKey } from '@solana/web3.js';
import { quoteCache } from '@/lib/server-cache';
import { quoteRateLimiter, getClientIp } from '@/lib/rate-limiter';
import { resolveServerRpcConfig } from '@/lib/server-rpc-config';

function readBagsApiKey(): string {
  // Secret Manager values can sometimes include trailing newlines/whitespace; Node will reject
  // such values when used as HTTP header content (x-api-key). Sanitize defensively.
  return String(process.env.BAGS_API_KEY || '')
    .replace(/[\x00-\x20\x7f]/g, '')
    .trim();
}

const BAGS_API_KEY = readBagsApiKey();

let _sdk: BagsSDK | null = null;
let _connection: Connection | null = null;
let _rpcUrl: string | null = null;

function getConnection(rpcUrl: string): Connection {
  if (!_connection || _rpcUrl !== rpcUrl) {
    _connection = new Connection(rpcUrl, 'confirmed');
    _rpcUrl = rpcUrl;
    _sdk = null;
  }
  return _connection;
}

function getSDK(connection: Connection): BagsSDK {
  if (!_sdk) {
    if (!BAGS_API_KEY) throw new Error('BAGS_API_KEY not configured');
    _sdk = new BagsSDK(BAGS_API_KEY, connection);
  }
  return _sdk;
}

const QUOTE_TTL_MS = 3_000; // 3 seconds — quotes are time-sensitive

export async function POST(request: Request) {
  try {
    // Rate limit — quote is the most expensive upstream call
    const ip = getClientIp(request);
    const limit = await quoteRateLimiter.check(ip);
    if (!limit.allowed) {
      return NextResponse.json(
        { error: 'Rate limit exceeded. Try again shortly.' },
        {
          status: 429,
          headers: {
            'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)),
            'X-RateLimit-Remaining': '0',
          },
        },
      );
    }

    const { inputMint, outputMint, amount, slippageBps } = await request.json();

    if (!inputMint || !outputMint || !amount) {
      return NextResponse.json({ error: 'Missing required parameters' }, { status: 400 });
    }

    const rpcConfig = resolveServerRpcConfig();
    if (!rpcConfig.ok || !rpcConfig.url) {
      return NextResponse.json(
        {
          code: 'RPC_PROVIDER_UNAVAILABLE',
          error: 'RPC provider unavailable',
          diagnostic: rpcConfig.diagnostic,
          source: rpcConfig.source,
        },
        { status: 503 },
      );
    }

    // Cache key: same pair + amount = same quote (within TTL)
    const cacheKey = `quote:${inputMint}:${outputMint}:${amount}:${slippageBps || 'auto'}`;
    const cached = await quoteCache.get(cacheKey);
    if (cached) {
      return NextResponse.json(cached, {
        headers: {
          'X-Cache': 'HIT',
          'X-RateLimit-Remaining': String(limit.remaining),
        },
      });
    }

    const connection = getConnection(rpcConfig.url);
    const sdk = getSDK(connection);
    const quote = await sdk.trade.getQuote({
      inputMint: new PublicKey(inputMint),
      outputMint: new PublicKey(outputMint),
      amount: Number(amount),
      slippageMode: slippageBps ? 'manual' : 'auto',
      ...(slippageBps ? { slippageBps: Number(slippageBps) } : {}),
    });

    const responseData = { quote };
    await quoteCache.set(cacheKey, responseData, QUOTE_TTL_MS);

    return NextResponse.json(responseData, {
      headers: {
        'X-Cache': 'MISS',
        'X-RateLimit-Remaining': String(limit.remaining),
      },
    });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Quote failed';
    console.error('[API /bags/quote]', msg);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
