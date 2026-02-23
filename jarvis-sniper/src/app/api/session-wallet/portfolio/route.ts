import { NextResponse } from 'next/server';
import { PublicKey } from '@solana/web3.js';
import { ServerCache } from '@/lib/server-cache';
import { apiRateLimiter, getClientIp } from '@/lib/rate-limiter';
import {
  type WalletHoldingsConsensus,
  type WalletConsensusHolding,
  buildWalletHoldingsConsensus,
} from '@/lib/wallet-holdings-consensus';

export const runtime = 'nodejs';

type DexTokenMarket = {
  priceUsd: number;
  symbol?: string;
  name?: string;
  icon?: string;
  website?: string;
  twitter?: string;
  telegram?: string;
};

type WalletPortfolioResponse = WalletHoldingsConsensus & {
  stale?: boolean;
  warning?: string;
};

const DEXSCREENER_TOKENS = 'https://api.dexscreener.com/tokens/v1/solana';
const CACHE_TTL_MS = 45_000;
const STALE_TTL_MS = 5 * 60_000;

const portfolioCache = new ServerCache<WalletPortfolioResponse>();
const staleCache = new ServerCache<WalletPortfolioResponse>();
const inFlight = new Map<string, Promise<WalletPortfolioResponse>>();

function asNumber(v: unknown, fallback = 0): number {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function asString(v: unknown, fallback = ''): string {
  return typeof v === 'string' ? v : fallback;
}

function chunk<T>(arr: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

async function fetchDexMarketByMints(mints: string[]): Promise<Map<string, DexTokenMarket>> {
  const out = new Map<string, DexTokenMarket>();
  const uniqueMints = [...new Set(mints.filter(Boolean))];
  if (uniqueMints.length === 0) return out;

  const batches = chunk(uniqueMints, 30);
  for (const batch of batches) {
    try {
      const res = await fetch(`${DEXSCREENER_TOKENS}/${batch.join(',')}`, {
        headers: { Accept: 'application/json' },
        signal: AbortSignal.timeout(8000),
      });
      if (!res.ok) continue;
      const pairs: any[] = await res.json();
      if (!Array.isArray(pairs)) continue;

      for (const pair of pairs) {
        const baseMint = asString(pair?.baseToken?.address, '');
        if (!baseMint || !batch.includes(baseMint)) continue;
        const liq = asNumber(pair?.liquidity?.usd, 0);
        const priceUsd = asNumber(pair?.priceUsd, 0);
        if (!Number.isFinite(priceUsd) || priceUsd <= 0) continue;

        const prev = out.get(baseMint) as (DexTokenMarket & { _liq?: number }) | undefined;
        const prevLiq = prev ? asNumber(prev._liq, 0) : 0;
        if (prev && prevLiq >= liq) continue;

        const socials: any[] = Array.isArray(pair?.info?.socials) ? pair.info.socials : [];
        const websites: any[] = Array.isArray(pair?.info?.websites) ? pair.info.websites : [];
        const market: DexTokenMarket & { _liq?: number } = {
          priceUsd,
          symbol: asString(pair?.baseToken?.symbol, '') || undefined,
          name: asString(pair?.baseToken?.name, '') || undefined,
          icon: asString(pair?.info?.imageUrl, '') || undefined,
          website: asString(websites.find((w: any) => typeof w?.url === 'string')?.url, '') || undefined,
          twitter: asString(socials.find((s: any) => String(s?.type || '').toLowerCase() === 'twitter')?.url, '') || undefined,
          telegram: asString(socials.find((s: any) => String(s?.type || '').toLowerCase() === 'telegram')?.url, '') || undefined,
          _liq: liq,
        };
        out.set(baseMint, market);
      }
    } catch {
      // best effort
    }
  }

  return out;
}

async function buildPortfolio(wallet: string, forceFullScan: boolean): Promise<WalletPortfolioResponse> {
  const base = await buildWalletHoldingsConsensus(wallet, { forceFullScan });
  const dexByMint = await fetchDexMarketByMints(base.holdings.map((h) => h.mint));

  const enriched: WalletConsensusHolding[] = base.holdings.map((h) => {
    const dex = dexByMint.get(h.mint);
    const priceUsd = dex?.priceUsd ?? h.priceUsd ?? 0;
    const valueUsd = priceUsd > 0 ? h.uiAmount * priceUsd : h.valueUsd;
    return {
      ...h,
      symbol: dex?.symbol || h.symbol,
      name: dex?.name || h.name,
      icon: dex?.icon || h.icon,
      priceUsd,
      valueUsd,
    };
  });

  const pricedCount = enriched.filter((h) => h.priceUsd > 0).length;
  const totalValueUsd = enriched.reduce((sum, h) => sum + (Number.isFinite(h.valueUsd) ? h.valueUsd : 0), 0);

  return {
    ...base,
    fetchedAt: Date.now(),
    holdings: enriched.sort((a, b) => b.valueUsd - a.valueUsd || b.uiAmount - a.uiAmount),
    summary: {
      tokenCount: enriched.length,
      totalValueUsd: Number(totalValueUsd.toFixed(2)),
      pricedCount,
      unpricedCount: Math.max(0, enriched.length - pricedCount),
    },
  };
}

export async function GET(request: Request) {
  const ip = getClientIp(request);
  const limit = await apiRateLimiter.check(ip);
  if (!limit.allowed) {
    return NextResponse.json(
      { error: 'Too many requests', retryAfterMs: limit.retryAfterMs },
      { status: 429 },
    );
  }

  const url = new URL(request.url);
  const wallet = (url.searchParams.get('wallet') || '').trim();
  const forceFullScan =
    ['1', 'true', 'yes'].includes((url.searchParams.get('fullScan') || '').toLowerCase()) ||
    ['1', 'true', 'yes'].includes((url.searchParams.get('force') || '').toLowerCase());

  if (!wallet) {
    return NextResponse.json({ error: 'Missing wallet query parameter' }, { status: 400 });
  }
  try {
    new PublicKey(wallet);
  } catch {
    return NextResponse.json({ error: 'Invalid wallet address' }, { status: 400 });
  }

  const cacheKey = `portfolio:${wallet}`;
  if (!forceFullScan) {
    const cached = portfolioCache.get(cacheKey);
    if (cached) {
      return NextResponse.json(cached, {
        headers: {
          'X-Cache': 'HIT',
          'Cache-Control': 'private, max-age=10, stale-while-revalidate=30',
        },
      });
    }
  }

  if (!forceFullScan) {
    const running = inFlight.get(cacheKey);
    if (running) {
      const shared = await running;
      return NextResponse.json(shared, {
        headers: {
          'X-Cache': 'INFLIGHT',
          'Cache-Control': 'private, max-age=10, stale-while-revalidate=30',
        },
      });
    }
  }

  const task = buildPortfolio(wallet, forceFullScan);
  if (!forceFullScan) inFlight.set(cacheKey, task);

  try {
    const data = await task;
    portfolioCache.set(cacheKey, data, CACHE_TTL_MS);
    staleCache.set(cacheKey, data, STALE_TTL_MS);
    return NextResponse.json(data, {
      headers: {
        'X-Cache': forceFullScan ? 'FORCE' : 'MISS',
        'Cache-Control': 'private, max-age=10, stale-while-revalidate=30',
      },
    });
  } catch (error) {
    const stale = staleCache.get(cacheKey);
    if (stale) {
      return NextResponse.json(
        {
          ...stale,
          stale: true,
          warning: 'Portfolio sync degraded; served cached snapshot.',
        },
        {
          headers: {
            'X-Cache': 'STALE',
            'Cache-Control': 'private, max-age=5',
          },
        },
      );
    }

    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json(
      { error: 'Failed to sync wallet portfolio', detail: message },
      { status: 502 },
    );
  } finally {
    if (!forceFullScan) inFlight.delete(cacheKey);
  }
}

