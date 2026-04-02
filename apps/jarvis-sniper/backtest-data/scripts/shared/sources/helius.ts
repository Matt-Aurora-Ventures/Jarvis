import { fetchJSONPost, log, RateLimiter } from '../utils';
import type { TokenRecord } from '../types';

function envInt(name: string, fallback: number): number {
  const raw = process.env[name];
  const n = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

function getHeliusUrl(): string | undefined {
  const explicit = String(process.env.HELIUS_RPC_URL || '').trim();
  if (explicit) return explicit;
  const key = String(process.env.HELIUS_API_KEY || '').trim();
  if (!key) return undefined;
  return `https://mainnet.helius-rpc.com/?api-key=${key}`;
}

interface HeliusAsset {
  id?: string;
  content?: {
    metadata?: {
      name?: string;
      symbol?: string;
    };
    links?: {
      website?: string;
      twitter?: string;
      telegram?: string;
    };
  };
  token_info?: {
    price_info?: {
      price_per_token?: number;
    };
    supply?: number;
  };
}

interface HeliusGetAssetBatchResponse {
  result?: HeliusAsset[];
}

function num(value: unknown, fallback = 0): number {
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function assetToToken(asset: HeliusAsset): TokenRecord | null {
  const mint = asset.id || '';
  if (!mint || mint.length < 32) return null;

  return {
    mint,
    symbol: asset.content?.metadata?.symbol || 'UNKNOWN',
    name: asset.content?.metadata?.name || asset.content?.metadata?.symbol || 'Unknown',
    pool_address: '',
    creation_timestamp: 0,
    liquidity_usd: 0,
    volume_24h_usd: 0,
    price_change_1h: 0,
    price_usd: num(asset.token_info?.price_info?.price_per_token),
    buy_txn_count_24h: 0,
    sell_txn_count_24h: 0,
    holder_count: 0,
    has_twitter: Boolean(asset.content?.links?.twitter),
    has_website: Boolean(asset.content?.links?.website),
    has_telegram: Boolean(asset.content?.links?.telegram),
    source: 'helius',
    source_confidence: 0.65,
    source_details: {
      provider: 'helius',
      endpoint: 'getAssetBatch',
      supply: num(asset.token_info?.supply),
    },
  };
}

export async function fetchHeliusAssetBatch(mints: string[]): Promise<TokenRecord[]> {
  const heliusUrl = getHeliusUrl();
  if (!heliusUrl) {
    log('Helius API key/RPC URL missing; skipping Helius enrichment source');
    return [];
  }

  const filtered = Array.from(new Set(mints.filter((mint) => mint && mint.length >= 32)));
  if (filtered.length === 0) return [];

  const maxMints = envInt('HELIUS_MAX_MINTS', 500);
  const batchSize = Math.min(envInt('HELIUS_BATCH_SIZE', 100), 100);
  const rpm = envInt('HELIUS_RPM', 20);
  const limiter = new RateLimiter(rpm, 60_000);
  const target = filtered.slice(0, maxMints);
  const out: TokenRecord[] = [];

  for (let i = 0; i < target.length; i += batchSize) {
    const batch = target.slice(i, i + batchSize);
    const payload = {
      jsonrpc: '2.0',
      id: `jarvis-helius-${Math.floor(i / batchSize) + 1}`,
      method: 'getAssetBatch',
      params: {
        ids: batch,
      },
    };

    const resp = await fetchJSONPost<HeliusGetAssetBatchResponse>(heliusUrl, payload, {
      rateLimiter: limiter,
      label: `helius:getAssetBatch:b${Math.floor(i / batchSize) + 1}`,
      retries: 3,
    });

    const assets = resp?.result || [];
    const mapped = assets
      .map((asset) => assetToToken(asset))
      .filter((token): token is TokenRecord => token !== null);

    out.push(...mapped);
  }

  log(`  Helius enrichment records: ${out.length}`);
  return out;
}
