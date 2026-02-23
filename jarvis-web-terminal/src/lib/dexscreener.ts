/**
 * DexScreener API Client
 *
 * Searches for Solana token pairs via the DexScreener public API.
 * Used by the TokenSearch component for token discovery.
 */

// ── Types ────────────────────────────────────────────────────────────

export interface DexScreenerToken {
  address: string;
  name: string;
  symbol: string;
}

export interface DexScreenerPair {
  chainId: string;
  dexId: string;
  url: string;
  baseToken: DexScreenerToken;
  quoteToken: DexScreenerToken;
  priceUsd: string;
  priceChange: { h24: number };
  volume: { h24: number };
  liquidity: { usd: number };
  fdv: number;
  pairAddress: string;
}

export interface BoostedToken {
  url: string;
  chainId: string;
  tokenAddress: string;
  icon?: string;
  header?: string;
  openGraph?: string;
  description?: string;
  links?: unknown[];
  amount: number;
  totalAmount?: number;
}

export interface EnrichedTrendingToken {
  address: string;
  name: string;
  symbol: string;
  priceUsd: string;
  priceChange24h: number;
  volume24h: number;
  liquidity: number;
  fdv: number;
  poolAddress: string;
}

// ── Constants ────────────────────────────────────────────────────────

const DEXSCREENER_SEARCH_URL = 'https://api.dexscreener.com/latest/dex/search';
const DEXSCREENER_BOOSTS_URL = 'https://api.dexscreener.com/token-boosts/top/v1';
const DEXSCREENER_TOKENS_URL = 'https://api.dexscreener.com/latest/dex/tokens';
const DEFAULT_MAX_RESULTS = 10;

// ── Functions ────────────────────────────────────────────────────────

/**
 * Search DexScreener for token pairs matching a query string.
 *
 * Returns all pairs (not filtered by chain). Use `filterSolanaPairs`
 * to narrow to Solana only.
 *
 * Returns empty array on any error (never throws).
 *
 * @param query - Search term (token name, symbol, or address)
 * @returns Array of matching pairs
 */
export async function searchDexScreener(
  query: string
): Promise<DexScreenerPair[]> {
  const trimmed = query.trim();
  if (trimmed.length === 0) {
    return [];
  }

  try {
    const url = `${DEXSCREENER_SEARCH_URL}?q=${encodeURIComponent(trimmed)}`;
    const response = await fetch(url);

    if (!response.ok) {
      console.warn(`[DexScreener] API returned ${response.status}`);
      return [];
    }

    const json = await response.json();
    return json.pairs ?? [];
  } catch (error) {
    console.warn('[DexScreener] Search failed:', error);
    return [];
  }
}

/**
 * Filter pairs to only Solana chain, deduplicate by base token address,
 * and limit the number of results.
 *
 * @param pairs      - Raw pairs from DexScreener
 * @param maxResults - Maximum results to return (default 10)
 * @returns Filtered and deduplicated Solana pairs
 */
export function filterSolanaPairs(
  pairs: DexScreenerPair[],
  maxResults: number = DEFAULT_MAX_RESULTS
): DexScreenerPair[] {
  const solanaPairs = pairs.filter((p) => p.chainId === 'solana');

  // Deduplicate by base token address - keep first occurrence
  const seen = new Set<string>();
  const unique: DexScreenerPair[] = [];

  for (const pair of solanaPairs) {
    if (!seen.has(pair.baseToken.address)) {
      seen.add(pair.baseToken.address);
      unique.push(pair);
    }
  }

  return unique.slice(0, maxResults);
}

// ── Trending / Boosted Tokens ───────────────────────────────────────

/**
 * Fetch trending (boosted) tokens from DexScreener.
 *
 * Returns only Solana tokens, deduplicated by address.
 * Returns empty array on any error (never throws).
 */
export async function fetchTrendingTokens(): Promise<BoostedToken[]> {
  try {
    const response = await fetch(DEXSCREENER_BOOSTS_URL);

    if (!response.ok) {
      console.warn(`[DexScreener] Boosts API returned ${response.status}`);
      return [];
    }

    const json = await response.json();

    if (!Array.isArray(json)) {
      console.warn('[DexScreener] Boosts response is not an array');
      return [];
    }

    // Filter to Solana only
    const solanaTokens = json.filter(
      (t: BoostedToken) => t.chainId === 'solana'
    );

    // Deduplicate by tokenAddress
    const seen = new Set<string>();
    const unique: BoostedToken[] = [];
    for (const token of solanaTokens) {
      if (!seen.has(token.tokenAddress)) {
        seen.add(token.tokenAddress);
        unique.push(token);
      }
    }

    return unique;
  } catch (error) {
    console.warn('[DexScreener] Trending fetch failed:', error);
    return [];
  }
}

/**
 * Enrich a list of token addresses with price/volume data from DexScreener.
 *
 * Calls the /tokens/{addresses} endpoint and returns enriched data
 * for each address. Picks the highest-volume Solana pair per token.
 *
 * Returns empty array on any error (never throws).
 *
 * @param addresses - Array of token mint addresses
 * @returns Enriched token data with price, volume, etc.
 */
export async function enrichTrendingTokens(
  addresses: string[]
): Promise<EnrichedTrendingToken[]> {
  if (addresses.length === 0) {
    return [];
  }

  try {
    const joined = addresses.join(',');
    const url = `${DEXSCREENER_TOKENS_URL}/${joined}`;
    const response = await fetch(url);

    if (!response.ok) {
      console.warn(`[DexScreener] Tokens API returned ${response.status}`);
      return [];
    }

    const json = await response.json();
    const pairs: DexScreenerPair[] = json.pairs ?? [];

    // Filter to Solana pairs only
    const solanaPairs = pairs.filter((p) => p.chainId === 'solana');

    // Group by base token address, pick highest volume pair
    const bestByAddress = new Map<string, DexScreenerPair>();

    for (const pair of solanaPairs) {
      const addr = pair.baseToken.address;
      const existing = bestByAddress.get(addr);
      if (!existing || pair.volume.h24 > existing.volume.h24) {
        bestByAddress.set(addr, pair);
      }
    }

    // Convert to enriched format
    const enriched: EnrichedTrendingToken[] = [];
    for (const pair of bestByAddress.values()) {
      enriched.push({
        address: pair.baseToken.address,
        name: pair.baseToken.name,
        symbol: pair.baseToken.symbol,
        priceUsd: pair.priceUsd,
        priceChange24h: pair.priceChange.h24,
        volume24h: pair.volume.h24,
        liquidity: pair.liquidity.usd,
        fdv: pair.fdv,
        poolAddress: pair.pairAddress,
      });
    }

    return enriched;
  } catch (error) {
    console.warn('[DexScreener] Enrich failed:', error);
    return [];
  }
}

/**
 * Format a number into compact dollar notation.
 *
 * @param num - Number to format
 * @returns Formatted string like "$1.5B", "$12.0M", "$350.0K", "$500"
 */
export function formatCompactNumber(num: number): string {
  if (num >= 1e9) return `$${(num / 1e9).toFixed(1)}B`;
  if (num >= 1e6) return `$${(num / 1e6).toFixed(1)}M`;
  if (num >= 1e3) return `$${(num / 1e3).toFixed(1)}K`;
  return `$${Math.round(num)}`;
}
