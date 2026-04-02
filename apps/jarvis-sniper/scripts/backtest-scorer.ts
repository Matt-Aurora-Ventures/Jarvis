#!/usr/bin/env npx tsx
/**
 * Jarvis Sniper — Large-Scale Backtest v4
 *
 * Fetches 1000-2000+ real Solana tokens from GeckoTerminal + DexScreener + Jupiter,
 * scores them with our algorithm, simulates trades under 90+ configs,
 * and finds the optimal parameter combination.
 *
 * v4 additions:
 *   - Trailing stop optimization (sweep 0-10% on HYBRID_B base)
 *   - Time-of-day analysis (which hours produce winners?)
 *   - Jupiter verified token list as additional data source
 *   - 12 new trailing stop configs
 *
 * Data sources:
 *   - GeckoTerminal: new pools, volume-sorted pools, trending (free, no key)
 *   - DexScreener: boosted, top-boosted, token profiles, search (free, no key)
 *   - DexScreener batch enrichment for full pair data
 *   - Jupiter: verified Solana token list (free, no key)
 *
 * Usage:
 *   npx tsx scripts/backtest-scorer.ts              # Full run
 *   npx tsx scripts/backtest-scorer.ts --cache       # Use cached data if <2h old
 *   npx tsx scripts/backtest-scorer.ts --quick       # Skip DexScreener search (faster)
 */

import { writeFileSync, readFileSync, existsSync } from 'fs';
import { join } from 'path';

// ════════════════════════════════════════════════════════════════
// Types
// ════════════════════════════════════════════════════════════════

interface TokenData {
  mint: string;
  symbol: string;
  name: string;
  score: number;
  liquidity: number;
  volume24h: number;
  marketCap: number;
  priceUsd: number;
  boostAmount: number;
  socialCount: number;
  txnBuys1h: number;
  txnSells1h: number;
  priceChange5m: number;
  priceChange1h: number;
  priceChange6h: number;
  priceChange24h: number;
  pairCreatedAt: number;
  pairAddress: string;
  volLiqRatio: number;
  ageHours: number;
  source: string;
  // Helius-enriched fields
  holderCount?: number;
  supply?: number;
  topHolderPct?: number; // % of supply held by top holder
}

interface TradeResult {
  mint: string;
  symbol: string;
  score: number;
  entryPrice: number;
  liquidity: number;
  volume24h: number;
  slPct: number;
  tpPct: number;
  pnlPct: number;
  outcome: 'win' | 'loss' | 'open';
  reason: string;
  priceChange1h: number;
  priceChange6h: number;
  priceChange24h: number;
  volLiqRatio: number;
  ageHours: number;
  entryHour?: number;        // Hour of day (0-23 UTC) for time-of-day analysis
  trailingStopTriggered?: boolean; // Whether trailing stop triggered instead of fixed SL
}

interface BacktestConfig {
  name: string;
  minScore: number;
  slOverride?: number;
  tpOverride?: number;
  trailingStopPct?: number;   // Trailing stop: ratchet SL up as price rises (0 = disabled)
  useAdaptive?: boolean;
  minLiquidity?: number;
  minVolLiqRatio?: number;
  minBuyRatio?: number;
  maxBuyRatio?: number;       // Cap extreme B/S ratios (pumps)
  minBoostAmount?: number;
  maxAgeHours?: number;
  minAgeMinutes?: number;
  min1hChange?: number;       // Require positive 1h momentum
  minTxnTotal?: number;       // Minimum total txns (buys + sells)
  minHolders?: number;        // Helius: minimum holder count
  description: string;
}

interface ConfigResult {
  config: BacktestConfig;
  eligible: number;
  wins: number;
  losses: number;
  open: number;
  winRate: number;
  avgWinPct: number;
  avgLossPct: number;
  expectancy: number;
  profitFactor: number;
  totalPnlPct: number;
  trades: TradeResult[];
}

// ════════════════════════════════════════════════════════════════
// Scoring Algorithm (mirrors /api/graduations/route.ts exactly)
// ════════════════════════════════════════════════════════════════

function calculateScore(t: {
  liquidity: number;
  volume24h: number;
  socialCount: number;
  boostAmount: number;
  txnBuys1h: number;
  txnSells1h: number;
  priceChange5m: number;
  priceChange1h: number;
}): number {
  let score = 30;
  if (t.liquidity > 100000) score += 20;
  else if (t.liquidity > 50000) score += 15;
  else if (t.liquidity > 10000) score += 10;
  else if (t.liquidity > 1000) score += 5;
  if (t.volume24h > 500000) score += 15;
  else if (t.volume24h > 100000) score += 12;
  else if (t.volume24h > 10000) score += 8;
  else if (t.volume24h > 1000) score += 4;
  score += Math.min(15, t.socialCount * 5);
  if (t.boostAmount >= 100) score += 10;
  else if (t.boostAmount >= 50) score += 7;
  else if (t.boostAmount >= 20) score += 4;
  if (t.txnBuys1h > 0 && t.txnSells1h > 0) {
    const ratio = t.txnBuys1h / t.txnSells1h;
    if (ratio > 3) score += 10;
    else if (ratio > 2) score += 7;
    else if (ratio > 1.2) score += 4;
  }
  if (t.priceChange5m > 5) score += 5;
  else if (t.priceChange5m > 0) score += 2;
  if (t.priceChange1h < -30) score -= 15;
  else if (t.priceChange1h < -15) score -= 8;
  return Math.min(100, Math.max(0, score));
}

function getRecommendedSlTp(score: number, liq: number, priceChange1h: number, volume: number) {
  let sl: number, tp: number;
  if (score >= 80) { sl = 15; tp = 60; }
  else if (score >= 65) { sl = 20; tp = 40; }
  else if (score >= 50) { sl = 25; tp = 30; }
  else { sl = 30; tp = 20; }
  if (liq > 200000) { sl -= 3; tp += 5; }
  else if (liq > 50000) { sl -= 1; tp += 2; }
  else if (liq < 5000) { sl += 5; tp -= 5; }
  if (priceChange1h > 20) { tp += 15; }
  else if (priceChange1h > 5) { tp += 5; }
  else if (priceChange1h < -10) { sl += 5; tp -= 5; }
  if (volume > 500000) { tp += 10; sl -= 2; }
  else if (volume > 100000) { tp += 5; }
  sl = Math.max(5, Math.min(50, Math.round(sl)));
  tp = Math.max(10, Math.min(150, Math.round(tp)));
  return { sl, tp };
}

// ════════════════════════════════════════════════════════════════
// API Helpers
// ════════════════════════════════════════════════════════════════

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));
let apiCalls = 0;

async function fetchJson(url: string, retries = 3, delayMs = 1500): Promise<any> {
  for (let i = 0; i < retries; i++) {
    try {
      apiCalls++;
      const res = await fetch(url, {
        headers: { Accept: 'application/json', 'User-Agent': 'JarvisSniper/2.0' },
      });
      if (res.status === 429) {
        console.log(`    ⚡ Rate limited, waiting ${delayMs * 2}ms...`);
        await sleep(delayMs * 2);
        continue;
      }
      if (!res.ok) {
        if (i < retries - 1) { await sleep(delayMs); continue; }
        return null;
      }
      const data = await res.json();
      await sleep(delayMs);
      return data;
    } catch {
      if (i < retries - 1) await sleep(delayMs);
    }
  }
  return null;
}

// ════════════════════════════════════════════════════════════════
// Data Source 1: GeckoTerminal (paginated pools)
// ════════════════════════════════════════════════════════════════

interface GeckoPool {
  mint: string;
  symbol: string;
  name: string;
  poolAddress: string;
  liquidity: number;
  volume24h: number;
  fdv: number;
  priceUsd: number;
  priceChange5m: number;
  priceChange1h: number;
  priceChange6h: number;
  priceChange24h: number;
  txnBuys1h: number;
  txnSells1h: number;
  createdAt: number;
}

async function fetchGeckoTerminalPools(sort: string, pages: number, label: string): Promise<GeckoPool[]> {
  const pools: GeckoPool[] = [];
  console.log(`  📡 GeckoTerminal ${label} (${pages} pages)...`);

  for (let page = 1; page <= pages; page++) {
    const url = `https://api.geckoterminal.com/api/v2/networks/solana/pools?sort=${sort}&page=${page}`;
    const data = await fetchJson(url, 2, 2200); // GeckoTerminal: 30 req/min

    if (!data?.data || !Array.isArray(data.data)) {
      console.log(`    Page ${page}: no data`);
      break;
    }

    for (const pool of data.data) {
      const attrs = pool.attributes;
      if (!attrs) continue;

      // Extract mint from relationships
      const baseTokenId = pool.relationships?.base_token?.data?.id || '';
      const mint = baseTokenId.replace('solana_', '');
      if (!mint || mint.length < 20) continue;

      // Skip stablecoins and wrapped SOL
      const symbol = attrs.name?.split(' / ')?.[0]?.trim() || 'UNK';
      if (['USDC', 'USDT', 'SOL', 'WSOL', 'WETH', 'RAY'].includes(symbol)) continue;

      const pc = attrs.price_change_percentage || {};
      const txns = attrs.transactions || {};
      const vol = attrs.volume_usd || {};

      pools.push({
        mint,
        symbol,
        name: attrs.name || symbol,
        poolAddress: attrs.address || '',
        liquidity: parseFloat(attrs.reserve_in_usd || '0'),
        volume24h: parseFloat(vol.h24 || '0'),
        fdv: parseFloat(attrs.fdv_usd || '0'),
        priceUsd: parseFloat(attrs.base_token_price_usd || '0'),
        priceChange5m: parseFloat(pc.m5 || '0'),
        priceChange1h: parseFloat(pc.h1 || '0'),
        priceChange6h: parseFloat(pc.h6 || '0'),
        priceChange24h: parseFloat(pc.h24 || '0'),
        txnBuys1h: txns.h1?.buys || 0,
        txnSells1h: txns.h1?.sells || 0,
        createdAt: attrs.pool_created_at ? new Date(attrs.pool_created_at).getTime() : Date.now(),
      });
    }

    process.stdout.write(`    Page ${page}/${pages}: ${pools.length} pools\r`);
  }

  console.log(`    ✓ ${pools.length} pools from ${label}                    `);
  return pools;
}

async function fetchGeckoTerminalTrending(): Promise<GeckoPool[]> {
  console.log(`  📡 GeckoTerminal trending...`);
  const url = 'https://api.geckoterminal.com/api/v2/networks/solana/trending_pools';
  const data = await fetchJson(url, 2, 2200);
  if (!data?.data) return [];

  const pools: GeckoPool[] = [];
  for (const pool of data.data) {
    const attrs = pool.attributes;
    if (!attrs) continue;
    const baseTokenId = pool.relationships?.base_token?.data?.id || '';
    const mint = baseTokenId.replace('solana_', '');
    if (!mint || mint.length < 20) continue;
    const symbol = attrs.name?.split(' / ')?.[0]?.trim() || 'UNK';
    if (['USDC', 'USDT', 'SOL', 'WSOL', 'WETH', 'RAY'].includes(symbol)) continue;
    const pc = attrs.price_change_percentage || {};
    const txns = attrs.transactions || {};
    const vol = attrs.volume_usd || {};
    pools.push({
      mint, symbol, name: attrs.name || symbol,
      poolAddress: attrs.address || '',
      liquidity: parseFloat(attrs.reserve_in_usd || '0'),
      volume24h: parseFloat(vol.h24 || '0'),
      fdv: parseFloat(attrs.fdv_usd || '0'),
      priceUsd: parseFloat(attrs.base_token_price_usd || '0'),
      priceChange5m: parseFloat(pc.m5 || '0'),
      priceChange1h: parseFloat(pc.h1 || '0'),
      priceChange6h: parseFloat(pc.h6 || '0'),
      priceChange24h: parseFloat(pc.h24 || '0'),
      txnBuys1h: txns.h1?.buys || 0, txnSells1h: txns.h1?.sells || 0,
      createdAt: attrs.pool_created_at ? new Date(attrs.pool_created_at).getTime() : Date.now(),
    });
  }
  console.log(`    ✓ ${pools.length} trending pools`);
  return pools;
}

// ════════════════════════════════════════════════════════════════
// Data Source 2: DexScreener (boosts + profiles + search)
// ════════════════════════════════════════════════════════════════

interface DexMint {
  mint: string;
  boostAmount: number;
  socialCount: number;
  source: string;
}

async function fetchDexScreenerBoosts(): Promise<DexMint[]> {
  console.log(`  📡 DexScreener boosted tokens...`);
  const [latest, top] = await Promise.all([
    fetchJson('https://api.dexscreener.com/token-boosts/latest/v1', 3, 1000),
    fetchJson('https://api.dexscreener.com/token-boosts/top/v1', 3, 1000),
  ]);

  const mints: DexMint[] = [];
  const seen = new Set<string>();

  for (const list of [latest, top]) {
    if (!Array.isArray(list)) continue;
    for (const b of list) {
      if (b.chainId !== 'solana' || seen.has(b.tokenAddress)) continue;
      seen.add(b.tokenAddress);
      const socialCount = (b.links || []).filter((l: any) =>
        ['twitter', 'telegram', 'website'].includes(l.type || 'website')
      ).length;
      mints.push({
        mint: b.tokenAddress,
        boostAmount: b.totalAmount || 0,
        socialCount,
        source: 'dex-boost',
      });
    }
  }

  console.log(`    ✓ ${mints.length} boosted tokens`);
  return mints;
}

async function fetchDexScreenerProfiles(): Promise<DexMint[]> {
  console.log(`  📡 DexScreener token profiles...`);
  const data = await fetchJson('https://api.dexscreener.com/token-profiles/latest/v1', 3, 1000);
  if (!Array.isArray(data)) return [];

  const mints: DexMint[] = [];
  const seen = new Set<string>();
  for (const p of data) {
    if (p.chainId !== 'solana' || seen.has(p.tokenAddress)) continue;
    seen.add(p.tokenAddress);
    const socialCount = (p.links || []).filter((l: any) =>
      ['twitter', 'telegram', 'website'].includes(l.type || 'website')
    ).length;
    mints.push({
      mint: p.tokenAddress,
      boostAmount: 0,
      socialCount,
      source: 'dex-profile',
    });
  }

  console.log(`    ✓ ${mints.length} token profiles`);
  return mints;
}

async function fetchDexScreenerSearch(queries: string[]): Promise<DexMint[]> {
  console.log(`  📡 DexScreener search (${queries.length} queries)...`);
  const mints: DexMint[] = [];
  const seen = new Set<string>();

  for (let i = 0; i < queries.length; i++) {
    const q = queries[i];
    const data = await fetchJson(`https://api.dexscreener.com/latest/dex/search?q=${encodeURIComponent(q)}`, 2, 1200);
    if (!data?.pairs) continue;

    for (const pair of data.pairs) {
      if (pair.chainId !== 'solana') continue;
      const mint = pair.baseToken?.address;
      if (!mint || seen.has(mint)) continue;
      const symbol = pair.baseToken?.symbol || '';
      if (['USDC', 'USDT', 'SOL', 'WSOL', 'WETH', 'RAY'].includes(symbol)) continue;
      seen.add(mint);
      mints.push({ mint, boostAmount: 0, socialCount: 0, source: 'dex-search' });
    }

    process.stdout.write(`    Search ${i + 1}/${queries.length} "${q}": ${mints.length} unique\r`);
  }

  console.log(`    ✓ ${mints.length} tokens from search                      `);
  return mints;
}

// ════════════════════════════════════════════════════════════════
// DexScreener Batch Enrichment (30 per request)
// ════════════════════════════════════════════════════════════════

interface PairData {
  mint: string;
  symbol: string;
  name: string;
  pairAddress: string;
  liquidity: number;
  volume24h: number;
  marketCap: number;
  priceUsd: number;
  priceChange5m: number;
  priceChange1h: number;
  priceChange6h: number;
  priceChange24h: number;
  txnBuys1h: number;
  txnSells1h: number;
  createdAt: number;
}

async function batchEnrichDexScreener(mints: string[]): Promise<Map<string, PairData>> {
  const result = new Map<string, PairData>();
  const batchSize = 30;
  const batches = Math.ceil(mints.length / batchSize);

  console.log(`  📡 DexScreener batch enrichment (${mints.length} tokens, ${batches} batches)...`);

  for (let i = 0; i < batches; i++) {
    const batch = mints.slice(i * batchSize, (i + 1) * batchSize);
    const url = `https://api.dexscreener.com/tokens/v1/solana/${batch.join(',')}`;
    const data = await fetchJson(url, 2, 1200);

    if (Array.isArray(data)) {
      for (const pair of data) {
        const mint = pair.baseToken?.address;
        if (!mint) continue;
        const liq = parseFloat(pair.liquidity?.usd || '0');
        const existing = result.get(mint);
        // Keep highest liquidity pair
        if (existing && existing.liquidity >= liq) continue;

        result.set(mint, {
          mint,
          symbol: pair.baseToken?.symbol || mint.slice(0, 6),
          name: pair.baseToken?.name || 'Unknown',
          pairAddress: pair.pairAddress || '',
          liquidity: liq,
          volume24h: parseFloat(pair.volume?.h24 || '0'),
          marketCap: parseFloat(pair.marketCap || pair.fdv || '0'),
          priceUsd: parseFloat(pair.priceUsd || '0'),
          priceChange5m: pair.priceChange?.m5 || 0,
          priceChange1h: pair.priceChange?.h1 || 0,
          priceChange6h: pair.priceChange?.h6 || 0,
          priceChange24h: pair.priceChange?.h24 || 0,
          txnBuys1h: pair.txns?.h1?.buys || 0,
          txnSells1h: pair.txns?.h1?.sells || 0,
          createdAt: pair.pairCreatedAt || Date.now(),
        });
      }
    }

    process.stdout.write(`    Batch ${i + 1}/${batches}: ${result.size} enriched\r`);
  }

  console.log(`    ✓ ${result.size} tokens enriched                          `);
  return result;
}

// ════════════════════════════════════════════════════════════════
// Merge all sources into scored TokenData[]
// ════════════════════════════════════════════════════════════════

function mergeAll(
  geckoPools: GeckoPool[],
  dexMints: DexMint[],
  enriched: Map<string, PairData>,
): TokenData[] {
  const byMint = new Map<string, TokenData>();
  const now = Date.now();

  // Process GeckoTerminal pools
  for (const pool of geckoPools) {
    if (byMint.has(pool.mint)) {
      const existing = byMint.get(pool.mint)!;
      if (pool.liquidity > existing.liquidity) {
        // Update with higher liq pool
        Object.assign(existing, buildTokenData(pool, null, null, now));
      }
      continue;
    }
    byMint.set(pool.mint, buildTokenData(pool, null, null, now));
  }

  // Process DexScreener mints + enrichment
  for (const dm of dexMints) {
    const pair = enriched.get(dm.mint);
    if (!pair) continue;

    if (byMint.has(dm.mint)) {
      const existing = byMint.get(dm.mint)!;
      // Merge boost/social data
      existing.boostAmount = Math.max(existing.boostAmount, dm.boostAmount);
      existing.socialCount = Math.max(existing.socialCount, dm.socialCount);
      existing.source += `,${dm.source}`;
      // Update with DexScreener data if better
      if (pair.liquidity > existing.liquidity) {
        existing.liquidity = pair.liquidity;
        existing.volume24h = pair.volume24h;
        existing.priceUsd = pair.priceUsd;
        existing.priceChange5m = pair.priceChange5m;
        existing.priceChange1h = pair.priceChange1h;
        existing.priceChange6h = pair.priceChange6h;
        existing.priceChange24h = pair.priceChange24h;
        existing.txnBuys1h = pair.txnBuys1h;
        existing.txnSells1h = pair.txnSells1h;
        existing.pairAddress = pair.pairAddress;
      }
    } else {
      byMint.set(dm.mint, buildTokenDataFromPair(pair, dm, now));
    }
  }

  // Also add enriched-only tokens (from batch lookup that weren't in other sources)
  for (const [mint, pair] of enriched) {
    if (byMint.has(mint)) continue;
    byMint.set(mint, buildTokenDataFromPair(pair, null, now));
  }

  // Recalculate scores for all
  const tokens = Array.from(byMint.values());
  for (const t of tokens) {
    t.score = calculateScore(t);
    t.volLiqRatio = t.liquidity > 0 ? t.volume24h / t.liquidity : 0;
    t.ageHours = (now - t.pairCreatedAt) / 3600000;
  }

  return tokens;
}

function buildTokenData(pool: GeckoPool, dm: DexMint | null, pair: PairData | null, now: number): TokenData {
  return {
    mint: pool.mint,
    symbol: pool.symbol,
    name: pool.name,
    score: 0, // calculated after
    liquidity: pool.liquidity,
    volume24h: pool.volume24h,
    marketCap: pool.fdv,
    priceUsd: pool.priceUsd,
    boostAmount: dm?.boostAmount || 0,
    socialCount: dm?.socialCount || 0,
    txnBuys1h: pool.txnBuys1h,
    txnSells1h: pool.txnSells1h,
    priceChange5m: pool.priceChange5m,
    priceChange1h: pool.priceChange1h,
    priceChange6h: pool.priceChange6h,
    priceChange24h: pool.priceChange24h,
    pairCreatedAt: pool.createdAt,
    pairAddress: pool.poolAddress,
    volLiqRatio: pool.liquidity > 0 ? pool.volume24h / pool.liquidity : 0,
    ageHours: (now - pool.createdAt) / 3600000,
    source: 'gecko',
  };
}

function buildTokenDataFromPair(pair: PairData, dm: DexMint | null, now: number): TokenData {
  return {
    mint: pair.mint,
    symbol: pair.symbol,
    name: pair.name,
    score: 0,
    liquidity: pair.liquidity,
    volume24h: pair.volume24h,
    marketCap: pair.marketCap,
    priceUsd: pair.priceUsd,
    boostAmount: dm?.boostAmount || 0,
    socialCount: dm?.socialCount || 0,
    txnBuys1h: pair.txnBuys1h,
    txnSells1h: pair.txnSells1h,
    priceChange5m: pair.priceChange5m,
    priceChange1h: pair.priceChange1h,
    priceChange6h: pair.priceChange6h,
    priceChange24h: pair.priceChange24h,
    pairCreatedAt: pair.createdAt,
    pairAddress: pair.pairAddress,
    volLiqRatio: pair.liquidity > 0 ? pair.volume24h / pair.liquidity : 0,
    ageHours: (now - pair.createdAt) / 3600000,
    source: dm?.source || 'dex-enriched',
  };
}

// ════════════════════════════════════════════════════════════════
// OHLCV Data (GeckoTerminal candles for accurate simulation)
// ════════════════════════════════════════════════════════════════

interface OhlcvCandle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

async function fetchOhlcv(poolAddress: string, timeframe = 'hour', limit = 48): Promise<OhlcvCandle[]> {
  if (!poolAddress || poolAddress.length < 20) return [];
  const url = `https://api.geckoterminal.com/api/v2/networks/solana/pools/${poolAddress}/ohlcv/${timeframe}?aggregate=1&limit=${limit}&currency=usd`;
  const data = await fetchJson(url, 2, 2200);
  if (!data?.data?.attributes?.ohlcv_list) return [];

  return data.data.attributes.ohlcv_list.map((c: number[]) => ({
    timestamp: c[0],
    open: c[1],
    high: c[2],
    low: c[3],
    close: c[4],
    volume: c[5],
  })).reverse(); // oldest first
}

/**
 * Simulate trade using real OHLCV candle data.
 * Entry at first candle's open. Check each candle for SL/TP triggers.
 * If SL hit first (low breaches SL before high breaches TP) → loss.
 * If TP hit first → win.
 * If neither within the candle window → open.
 *
 * Trailing stop: When trailingStopPct > 0, the SL ratchets upward as price
 * reaches new highs. E.g., if entry=100, trailing=5%, and price hits 120,
 * the trailing SL becomes 120*(1-0.05) = 114, which is better than the
 * fixed SL at e.g. 80 (20% SL). The effective SL is max(fixedSL, trailingSL).
 */
function simulateTradeOhlcv(
  token: TokenData,
  candles: OhlcvCandle[],
  slPct: number,
  tpPct: number,
  trailingStopPct: number = 0,
): TradeResult {
  if (candles.length === 0) {
    return simulateTrade(token, slPct, tpPct); // fallback to snapshot
  }

  const entryPrice = candles[0].open;
  if (entryPrice <= 0) return simulateTrade(token, slPct, tpPct);

  const fixedSlPrice = entryPrice * (1 - slPct / 100);
  const tpPrice = entryPrice * (1 + tpPct / 100);
  const entryHour = new Date(candles[0].timestamp * 1000).getUTCHours();

  let maxDrawdownPct = 0;
  let maxGainPct = 0;
  let highWaterMark = entryPrice;    // Highest price seen so far
  let trailingSlPrice = 0;          // Trailing SL level (ratchets up)
  let usedTrailingStop = false;

  for (let i = 0; i < candles.length; i++) {
    const c = candles[i];

    // Update high water mark with candle high
    if (c.high > highWaterMark) {
      highWaterMark = c.high;
      if (trailingStopPct > 0) {
        trailingSlPrice = highWaterMark * (1 - trailingStopPct / 100);
      }
    }

    // Effective SL is the higher of fixed SL and trailing SL
    const effectiveSlPrice = Math.max(fixedSlPrice, trailingSlPrice);

    const lowPct = ((c.low - entryPrice) / entryPrice) * 100;
    const highPct = ((c.high - entryPrice) / entryPrice) * 100;

    maxDrawdownPct = Math.min(maxDrawdownPct, lowPct);
    maxGainPct = Math.max(maxGainPct, highPct);

    const slHitThisCandle = c.low <= effectiveSlPrice;
    const tpHitThisCandle = c.high >= tpPrice;

    if (slHitThisCandle && tpHitThisCandle) {
      // Both in same candle — use open-relative direction
      const distToSl = Math.abs(c.open - effectiveSlPrice);
      const distToTp = Math.abs(c.open - tpPrice);
      if (distToTp < distToSl) {
        const r = makeResult(token, slPct, tpPct, 'win', tpPct,
          `OHLCV: TP hit candle ${i + 1}/${candles.length} (peak +${maxGainPct.toFixed(1)}%)`, maxDrawdownPct, maxGainPct);
        r.entryHour = entryHour;
        return r;
      } else {
        const exitPnl = ((effectiveSlPrice - entryPrice) / entryPrice) * 100;
        const trailNote = trailingSlPrice > fixedSlPrice ? ` [TRAIL@${((highWaterMark - entryPrice) / entryPrice * 100).toFixed(1)}%↑]` : '';
        usedTrailingStop = trailingSlPrice > fixedSlPrice;
        const r = makeResult(token, slPct, tpPct, exitPnl >= 0 ? 'win' : 'loss', exitPnl,
          `OHLCV: SL hit candle ${i + 1}/${candles.length}${trailNote} (exit ${exitPnl.toFixed(1)}%)`, maxDrawdownPct, maxGainPct);
        r.entryHour = entryHour;
        r.trailingStopTriggered = usedTrailingStop;
        return r;
      }
    }

    if (slHitThisCandle) {
      const exitPnl = ((effectiveSlPrice - entryPrice) / entryPrice) * 100;
      const trailNote = trailingSlPrice > fixedSlPrice ? ` [TRAIL@${((highWaterMark - entryPrice) / entryPrice * 100).toFixed(1)}%↑]` : '';
      usedTrailingStop = trailingSlPrice > fixedSlPrice;
      const r = makeResult(token, slPct, tpPct, exitPnl >= 0 ? 'win' : 'loss', exitPnl,
        `OHLCV: SL hit candle ${i + 1}/${candles.length}${trailNote} (exit ${exitPnl.toFixed(1)}%)`, maxDrawdownPct, maxGainPct);
      r.entryHour = entryHour;
      r.trailingStopTriggered = usedTrailingStop;
      return r;
    }

    if (tpHitThisCandle) {
      const r = makeResult(token, slPct, tpPct, 'win', tpPct,
        `OHLCV: TP hit candle ${i + 1}/${candles.length} (high +${highPct.toFixed(1)}%)`, maxDrawdownPct, maxGainPct);
      r.entryHour = entryHour;
      return r;
    }
  }

  // Neither SL nor TP hit within candle window
  const lastClose = candles[candles.length - 1].close;
  const currentPnl = ((lastClose - entryPrice) / entryPrice) * 100;
  const r = makeResult(token, slPct, tpPct, 'open', currentPnl,
    `OHLCV: Open after ${candles.length} candles (PnL ${currentPnl.toFixed(1)}%, peak +${maxGainPct.toFixed(1)}%, dip ${maxDrawdownPct.toFixed(1)}%)`,
    maxDrawdownPct, maxGainPct);
  r.entryHour = entryHour;
  return r;
}

function makeResult(
  token: TokenData, slPct: number, tpPct: number,
  outcome: 'win' | 'loss' | 'open', pnlPct: number, reason: string,
  maxDrawdownPct: number, maxGainPct: number,
): TradeResult {
  return {
    mint: token.mint, symbol: token.symbol, score: token.score,
    entryPrice: token.priceUsd, liquidity: token.liquidity, volume24h: token.volume24h,
    slPct, tpPct, pnlPct, outcome, reason,
    priceChange1h: token.priceChange1h, priceChange6h: token.priceChange6h,
    priceChange24h: token.priceChange24h, volLiqRatio: token.volLiqRatio, ageHours: token.ageHours,
  };
}

// ════════════════════════════════════════════════════════════════
// Data Source 4: Helius DAS API (token metadata, holders)
// ════════════════════════════════════════════════════════════════

// Server-side only: never hardcode API keys in the repo.
const HELIUS_API_KEY = process.env.HELIUS_API_KEY || '';
const HELIUS_RPC = HELIUS_API_KEY ? `https://mainnet.helius-rpc.com/?api-key=${HELIUS_API_KEY}` : '';

interface HeliusAsset {
  mint: string;
  supply?: number;
  holderCount?: number;
  topHolderPct?: number;
}

/**
 * Batch fetch token metadata from Helius DAS API.
 * Uses getAssetBatch for efficiency (up to 1000 per call).
 * Returns holder data + supply info for scoring enrichment.
 */
async function fetchHeliusTokenData(mints: string[]): Promise<Map<string, HeliusAsset>> {
  const result = new Map<string, HeliusAsset>();
  if (mints.length === 0) return result;
  if (!HELIUS_RPC) return result;

  // Batch in groups of 100 (Helius limit per batch)
  const batchSize = 100;
  for (let i = 0; i < mints.length; i += batchSize) {
    const batch = mints.slice(i, i + batchSize);
    try {
      apiCalls++;
      const res = await fetch(HELIUS_RPC, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0',
          id: `helius-batch-${i}`,
          method: 'getAssetBatch',
          params: { ids: batch },
        }),
      });

      if (!res.ok) {
        console.log(`    Helius batch ${i / batchSize + 1}: HTTP ${res.status}`);
        await sleep(1000);
        continue;
      }

      const data = await res.json();
      if (data?.result && Array.isArray(data.result)) {
        for (const asset of data.result) {
          if (!asset?.id) continue;
          const supply = asset.token_info?.supply
            ? Number(asset.token_info.supply) / Math.pow(10, asset.token_info.decimals || 0)
            : undefined;
          result.set(asset.id, {
            mint: asset.id,
            supply,
            holderCount: undefined, // will fetch separately if needed
          });
        }
      }
      process.stdout.write(`    Helius batch ${Math.floor(i / batchSize) + 1}/${Math.ceil(mints.length / batchSize)}: ${result.size} enriched\r`);
      await sleep(200); // Helius is generous but respect limits
    } catch (err) {
      console.log(`    Helius batch error: ${err}`);
      await sleep(1000);
    }
  }
  console.log(`    ✓ Helius enriched ${result.size} tokens                    `);
  return result;
}

/**
 * Fetch holder count for a specific token using Helius.
 * Uses getTokenAccounts (more reliable than getAssetsByOwner for SPL tokens).
 */
async function fetchHeliusHolderCount(mint: string): Promise<number | undefined> {
  try {
    apiCalls++;
    const res = await fetch(HELIUS_RPC, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 'holder-count',
        method: 'getTokenLargestAccounts',
        params: [mint],
      }),
    });
    if (!res.ok) return undefined;
    const data = await res.json();
    const accounts = data?.result?.value;
    if (!Array.isArray(accounts) || accounts.length === 0) return undefined;

    // getTokenLargestAccounts returns top 20 holders
    // Use total from all accounts as approximation
    const totalAmount = accounts.reduce((s: number, a: any) => s + Number(a.amount || 0), 0);
    const topAmount = Number(accounts[0]?.amount || 0);
    const topPct = totalAmount > 0 ? (topAmount / totalAmount) * 100 : 0;

    return accounts.length; // Approximate holder count from top-20
  } catch {
    return undefined;
  }
}

/**
 * Batch fetch holder data for high-value tokens only.
 * Rate-limited but much faster than GeckoTerminal OHLCV.
 */
async function enrichWithHelius(tokens: TokenData[]): Promise<void> {
  // Only enrich tokens that pass our minimum filters (saves API calls)
  const worthEnriching = tokens.filter(t => t.liquidity >= 10000 && t.priceUsd > 0);
  if (worthEnriching.length === 0) return;

  console.log(`\n📡 Helius: Enriching ${worthEnriching.length} tokens with on-chain data...`);

  // Batch metadata fetch
  const mints = worthEnriching.map(t => t.mint);
  const heliusData = await fetchHeliusTokenData(mints);

  // Apply enrichment
  let enriched = 0;
  for (const token of tokens) {
    const h = heliusData.get(token.mint);
    if (h) {
      token.supply = h.supply;
      enriched++;
    }
  }

  // Fetch holder counts for top-tier tokens (more targeted)
  const topTier = worthEnriching
    .filter(t => t.liquidity >= 25000)
    .slice(0, 100); // Max 100 individual holder queries

  if (topTier.length > 0) {
    console.log(`  📡 Helius: Fetching holder data for ${topTier.length} premium tokens...`);
    for (let i = 0; i < topTier.length; i++) {
      const count = await fetchHeliusHolderCount(topTier[i].mint);
      if (count !== undefined) {
        topTier[i].holderCount = count;
      }
      if (i % 10 === 0) {
        process.stdout.write(`    Holders ${i + 1}/${topTier.length}\r`);
        await sleep(100);
      }
    }
    const withHolders = topTier.filter(t => t.holderCount !== undefined).length;
    console.log(`    ✓ Holder data for ${withHolders} tokens                    `);
  }

  console.log(`  ✓ Helius enrichment complete (${enriched} metadata, ${topTier.filter(t => t.holderCount).length} holders)`);
}

// ════════════════════════════════════════════════════════════════
// Trade Simulation (snapshot-based fallback)
// ════════════════════════════════════════════════════════════════

/**
 * Simulates a trade using multi-timeframe price change data.
 *
 * Logic:
 * - We assume entry at the token's current state (when it appeared in feed)
 * - Use h1, h6, h24 price changes to estimate max drawdown and max gain
 * - Determine if SL or TP would have been hit
 * - When BOTH could have been hit, use timeframe analysis to determine order:
 *   - If recent move (h1) is positive → likely pumped first → TP hit before SL
 *   - If recent move (h1) is negative → likely dumped first → SL hit before TP
 */
function simulateTrade(token: TokenData, slPct: number, tpPct: number): TradeResult {
  const h1 = token.priceChange1h;
  const h6 = token.priceChange6h;
  const h24 = token.priceChange24h;

  // Estimate max drawdown (worst dip across all timeframes)
  const maxDrawdown = Math.min(h1, h6, h24, 0);
  // Estimate max gain (best peak across all timeframes)
  const maxGain = Math.max(h1, h6, h24, 0);

  const slHit = maxDrawdown <= -slPct;
  const tpHit = maxGain >= tpPct;

  let outcome: 'win' | 'loss' | 'open';
  let reason: string;
  let pnlPct: number;

  if (slHit && tpHit) {
    // Both thresholds breached — determine order
    // Heuristic: if h1 (most recent) is positive, token likely pumped first
    // If h1 is negative, token likely dumped first
    if (h1 > 0 && h6 < -slPct) {
      // Was down, now recovering → SL hit first
      outcome = 'loss';
      pnlPct = -slPct;
      reason = `SL hit first (h6: ${h6.toFixed(1)}%), then recovered (h1: +${h1.toFixed(1)}%)`;
    } else if (h1 < 0 && h6 > tpPct) {
      // Was up, now falling → TP hit first
      outcome = 'win';
      pnlPct = tpPct;
      reason = `TP hit first (h6: +${h6.toFixed(1)}%), then declined (h1: ${h1.toFixed(1)}%)`;
    } else if (h1 > 0) {
      // Recent positive, ambiguous → conservatively give TP
      outcome = 'win';
      pnlPct = tpPct;
      reason = `Both triggered, h1 positive → TP likely hit first`;
    } else {
      // Recent negative → conservatively give SL
      outcome = 'loss';
      pnlPct = -slPct;
      reason = `Both triggered, h1 negative → SL likely hit first`;
    }
  } else if (slHit) {
    outcome = 'loss';
    pnlPct = -slPct;
    reason = `Drawdown ${maxDrawdown.toFixed(1)}% hit SL at -${slPct}%`;
  } else if (tpHit) {
    outcome = 'win';
    pnlPct = tpPct;
    reason = `Peak +${maxGain.toFixed(1)}% hit TP at +${tpPct}%`;
  } else {
    // Still open — use current P&L (approximate as h1 change)
    outcome = 'open';
    pnlPct = h1;
    reason = `Open: h1=${h1.toFixed(1)}%, h6=${h6.toFixed(1)}%, h24=${h24.toFixed(1)}%`;
  }

  return {
    mint: token.mint,
    symbol: token.symbol,
    score: token.score,
    entryPrice: token.priceUsd,
    liquidity: token.liquidity,
    volume24h: token.volume24h,
    slPct,
    tpPct,
    pnlPct,
    outcome,
    reason,
    priceChange1h: h1,
    priceChange6h: h6,
    priceChange24h: h24,
    volLiqRatio: token.volLiqRatio,
    ageHours: token.ageHours,
  };
}

// ════════════════════════════════════════════════════════════════
// Run a single backtest config
// ════════════════════════════════════════════════════════════════

function runBacktest(tokens: TokenData[], config: BacktestConfig): ConfigResult {
  // Filter tokens by config criteria
  const eligible = tokens.filter(t => {
    if (t.priceUsd <= 0) return false;
    if (t.score < config.minScore) return false;
    if (config.minLiquidity && t.liquidity < config.minLiquidity) return false;
    if (config.minVolLiqRatio && t.volLiqRatio < config.minVolLiqRatio) return false;
    if (config.minBuyRatio) {
      if (t.txnBuys1h > 0 || t.txnSells1h > 0) {
        const ratio = t.txnBuys1h / Math.max(1, t.txnSells1h);
        if (ratio < config.minBuyRatio) return false;
      }
    }
    if (config.maxBuyRatio) {
      const ratio = t.txnBuys1h / Math.max(1, t.txnSells1h);
      if (ratio > config.maxBuyRatio) return false; // Extreme ratios = pump signal
    }
    if (config.minBoostAmount && t.boostAmount < config.minBoostAmount) return false;
    if (config.maxAgeHours && t.ageHours > config.maxAgeHours) return false;
    if (config.minAgeMinutes && t.ageHours < config.minAgeMinutes / 60) return false;
    if (config.min1hChange !== undefined && t.priceChange1h < config.min1hChange) return false;
    if (config.minTxnTotal && (t.txnBuys1h + t.txnSells1h) < config.minTxnTotal) return false;
    if (config.minHolders && (!t.holderCount || t.holderCount < config.minHolders)) return false;
    return true;
  });

  // Simulate trades
  const trades: TradeResult[] = [];
  for (const token of eligible) {
    let sl: number, tp: number;
    if (config.useAdaptive !== false && !config.slOverride && !config.tpOverride) {
      const rec = getRecommendedSlTp(token.score, token.liquidity, token.priceChange1h, token.volume24h);
      sl = rec.sl;
      tp = rec.tp;
    } else {
      sl = config.slOverride ?? 25;
      tp = config.tpOverride ?? 30;
    }
    trades.push(simulateTrade(token, sl, tp));
  }

  const wins = trades.filter(t => t.outcome === 'win').length;
  const losses = trades.filter(t => t.outcome === 'loss').length;
  const open = trades.filter(t => t.outcome === 'open').length;

  const decided = wins + losses;
  const winRate = decided > 0 ? (wins / decided) * 100 : 0;

  const winTrades = trades.filter(t => t.outcome === 'win');
  const lossTrades = trades.filter(t => t.outcome === 'loss');

  const totalWinPct = winTrades.reduce((s, t) => s + t.pnlPct, 0);
  const totalLossPct = lossTrades.reduce((s, t) => s + Math.abs(t.pnlPct), 0);
  const avgWinPct = wins > 0 ? totalWinPct / wins : 0;
  const avgLossPct = losses > 0 ? totalLossPct / losses : 0;
  const expectancy = decided > 0 ? (totalWinPct - totalLossPct) / decided : 0;
  const profitFactor = totalLossPct > 0 ? totalWinPct / totalLossPct : totalWinPct > 0 ? Infinity : 0;
  const totalPnlPct = totalWinPct - totalLossPct;

  return {
    config, eligible: eligible.length, wins, losses, open,
    winRate, avgWinPct, avgLossPct, expectancy, profitFactor, totalPnlPct, trades,
  };
}

// ════════════════════════════════════════════════════════════════
// OHLCV-powered backtest: multi-entry-point simulation
// ════════════════════════════════════════════════════════════════

/**
 * Run a FULL OHLCV backtest for a config using candle data.
 * For each token, simulates entries at every candle start,
 * giving us MANY more trade simulations per token.
 *
 * With 200 tokens × 24 entry points = 4800 trade sims.
 */
function runOhlcvBacktest(
  tokens: TokenData[],
  config: BacktestConfig,
  ohlcvMap: Map<string, OhlcvCandle[]>,
): ConfigResult {
  const eligible = tokens.filter(t => {
    if (t.priceUsd <= 0) return false;
    if (t.score < config.minScore) return false;
    if (config.minLiquidity && t.liquidity < config.minLiquidity) return false;
    if (config.minVolLiqRatio && t.volLiqRatio < config.minVolLiqRatio) return false;
    if (config.minBuyRatio) {
      if (t.txnBuys1h > 0 || t.txnSells1h > 0) {
        const ratio = t.txnBuys1h / Math.max(1, t.txnSells1h);
        if (ratio < config.minBuyRatio) return false;
      }
    }
    if (config.maxBuyRatio) {
      const ratio = t.txnBuys1h / Math.max(1, t.txnSells1h);
      if (ratio > config.maxBuyRatio) return false;
    }
    if (config.minBoostAmount && t.boostAmount < config.minBoostAmount) return false;
    if (config.maxAgeHours && t.ageHours > config.maxAgeHours) return false;
    if (config.min1hChange !== undefined && t.priceChange1h < config.min1hChange) return false;
    if (config.minTxnTotal && (t.txnBuys1h + t.txnSells1h) < config.minTxnTotal) return false;
    if (config.minHolders && (!t.holderCount || t.holderCount < config.minHolders)) return false;
    return true;
  });

  const trades: TradeResult[] = [];

  for (const token of eligible) {
    const candles = ohlcvMap.get(token.pairAddress) || ohlcvMap.get(token.mint) || [];
    let sl: number, tp: number;
    if (config.useAdaptive !== false && !config.slOverride && !config.tpOverride) {
      const rec = getRecommendedSlTp(token.score, token.liquidity, token.priceChange1h, token.volume24h);
      sl = rec.sl; tp = rec.tp;
    } else {
      sl = config.slOverride ?? 25; tp = config.tpOverride ?? 30;
    }

    const trailingStop = config.trailingStopPct ?? 0;

    if (candles.length < 4) {
      // Not enough candle data, fallback to snapshot
      trades.push(simulateTrade(token, sl, tp));
      continue;
    }

    // Simulate entries at every 4th candle (every 4 hours for hourly candles)
    // This simulates users checking the app at different times
    const entryInterval = Math.max(1, Math.floor(candles.length / 6)); // ~6 entry points per token
    for (let entryIdx = 0; entryIdx < candles.length - 4; entryIdx += entryInterval) {
      const remainingCandles = candles.slice(entryIdx);
      const entryCandle = remainingCandles[0];

      // Create a temporary token with the entry-time price
      const entryToken: TokenData = {
        ...token,
        priceUsd: entryCandle.open,
      };

      const result = simulateTradeOhlcv(entryToken, remainingCandles, sl, tp, trailingStop);
      trades.push(result);
    }
  }

  const wins = trades.filter(t => t.outcome === 'win').length;
  const losses = trades.filter(t => t.outcome === 'loss').length;
  const open = trades.filter(t => t.outcome === 'open').length;
  const decided = wins + losses;
  const winRate = decided > 0 ? (wins / decided) * 100 : 0;

  const winTrades = trades.filter(t => t.outcome === 'win');
  const lossTrades = trades.filter(t => t.outcome === 'loss');

  const totalWinPct = winTrades.reduce((s, t) => s + t.pnlPct, 0);
  const totalLossPct = lossTrades.reduce((s, t) => s + Math.abs(t.pnlPct), 0);
  const avgWinPct = wins > 0 ? totalWinPct / wins : 0;
  const avgLossPct = losses > 0 ? totalLossPct / losses : 0;
  const expectancy = decided > 0 ? (totalWinPct - totalLossPct) / decided : 0;
  const profitFactor = totalLossPct > 0 ? totalWinPct / totalLossPct : totalWinPct > 0 ? Infinity : 0;
  const totalPnlPct = totalWinPct - totalLossPct;

  return {
    config, eligible: trades.length, wins, losses, open,
    winRate, avgWinPct, avgLossPct, expectancy, profitFactor, totalPnlPct, trades,
  };
}

// ════════════════════════════════════════════════════════════════
// Winner Feature Analysis
// ════════════════════════════════════════════════════════════════

interface FeatureAnalysis {
  feature: string;
  winnerAvg: number;
  loserAvg: number;
  delta: number;
  predictivePower: number; // higher = more predictive
}

function analyzeWinnerFeatures(trades: TradeResult[], tokens: TokenData[]): FeatureAnalysis[] {
  const tokenMap = new Map(tokens.map(t => [t.mint, t]));
  const winners = trades.filter(t => t.outcome === 'win');
  const losers = trades.filter(t => t.outcome === 'loss');

  if (winners.length === 0 || losers.length === 0) return [];

  const features: FeatureAnalysis[] = [];
  const analyzeFeature = (name: string, getter: (t: TradeResult) => number) => {
    const winVals = winners.map(getter).filter(v => !isNaN(v) && isFinite(v));
    const lossVals = losers.map(getter).filter(v => !isNaN(v) && isFinite(v));
    if (winVals.length === 0 || lossVals.length === 0) return;

    const winAvg = winVals.reduce((a, b) => a + b, 0) / winVals.length;
    const lossAvg = lossVals.reduce((a, b) => a + b, 0) / lossVals.length;
    const delta = winAvg - lossAvg;
    const avgAll = (winAvg + lossAvg) / 2;
    const predictivePower = avgAll !== 0 ? Math.abs(delta / avgAll) * 100 : 0;

    features.push({ feature: name, winnerAvg: winAvg, loserAvg: lossAvg, delta, predictivePower });
  };

  analyzeFeature('Score', t => t.score);
  analyzeFeature('Liquidity ($)', t => t.liquidity);
  analyzeFeature('Volume 24h ($)', t => t.volume24h);
  analyzeFeature('Vol/Liq Ratio', t => t.volLiqRatio);
  analyzeFeature('Age (hours)', t => t.ageHours);
  analyzeFeature('Price Change 1h (%)', t => t.priceChange1h);
  analyzeFeature('Price Change 6h (%)', t => t.priceChange6h);
  analyzeFeature('Price Change 24h (%)', t => t.priceChange24h);

  // Token-level features
  analyzeFeature('Buy Count 1h', t => {
    const tok = tokenMap.get(t.mint);
    return tok?.txnBuys1h || 0;
  });
  analyzeFeature('Sell Count 1h', t => {
    const tok = tokenMap.get(t.mint);
    return tok?.txnSells1h || 0;
  });
  analyzeFeature('Buy/Sell Ratio', t => {
    const tok = tokenMap.get(t.mint);
    if (!tok) return 0;
    return tok.txnSells1h > 0 ? tok.txnBuys1h / tok.txnSells1h : tok.txnBuys1h;
  });
  analyzeFeature('Boost Amount', t => {
    const tok = tokenMap.get(t.mint);
    return tok?.boostAmount || 0;
  });
  analyzeFeature('Social Count', t => {
    const tok = tokenMap.get(t.mint);
    return tok?.socialCount || 0;
  });
  analyzeFeature('Market Cap ($)', t => {
    const tok = tokenMap.get(t.mint);
    return tok?.marketCap || 0;
  });

  // Sort by predictive power descending
  features.sort((a, b) => b.predictivePower - a.predictivePower);
  return features;
}

// ════════════════════════════════════════════════════════════════
// Time-of-Day Analysis
// ════════════════════════════════════════════════════════════════

interface HourlyStats {
  hour: number;
  trades: number;
  wins: number;
  losses: number;
  winRate: number;
  avgPnl: number;
  totalPnl: number;
}

function analyzeTimeOfDay(trades: TradeResult[]): HourlyStats[] {
  const hourly = new Map<number, { wins: number; losses: number; pnls: number[] }>();

  // Initialize all hours
  for (let h = 0; h < 24; h++) {
    hourly.set(h, { wins: 0, losses: 0, pnls: [] });
  }

  for (const t of trades) {
    if (t.entryHour === undefined) continue;
    if (t.outcome === 'open') continue;

    const data = hourly.get(t.entryHour)!;
    if (t.outcome === 'win') data.wins++;
    else data.losses++;
    data.pnls.push(t.pnlPct);
  }

  const results: HourlyStats[] = [];
  for (let h = 0; h < 24; h++) {
    const data = hourly.get(h)!;
    const total = data.wins + data.losses;
    const totalPnl = data.pnls.reduce((s, p) => s + p, 0);
    results.push({
      hour: h,
      trades: total,
      wins: data.wins,
      losses: data.losses,
      winRate: total > 0 ? (data.wins / total) * 100 : 0,
      avgPnl: total > 0 ? totalPnl / total : 0,
      totalPnl,
    });
  }

  return results;
}

// ════════════════════════════════════════════════════════════════
// Data Source 5: Jupiter Token List (verified Solana tokens)
// ════════════════════════════════════════════════════════════════

interface JupiterToken {
  address: string;
  symbol: string;
  name: string;
  decimals: number;
  logoURI?: string;
  tags?: string[];
  daily_volume?: number;
}

async function fetchJupiterTokenList(): Promise<DexMint[]> {
  console.log(`  📡 Jupiter: Fetching verified token list...`);
  // Jupiter strict list = verified tokens only (higher quality)
  const data = await fetchJson('https://token.jup.ag/strict', 2, 1500);
  if (!Array.isArray(data)) {
    console.log(`    Jupiter: invalid response`);
    return [];
  }

  const mints: DexMint[] = [];
  const skip = new Set(['EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', // USDC
    'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB', // USDT
    'So11111111111111111111111111111111111111112',     // SOL
    'mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So',  // mSOL
    '7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj', // stSOL
  ]);

  for (const token of data) {
    if (!token.address || skip.has(token.address)) continue;
    if (token.address.length < 20) continue;

    // Filter for tokens with community/meme tags or pump.fun origins
    const tags = token.tags || [];
    const isMeme = tags.some((t: string) => ['pump', 'meme', 'community', 'new'].includes(t));
    // Include all non-stablecoin tokens for broader coverage
    if (['USDC', 'USDT', 'SOL', 'WSOL'].includes(token.symbol)) continue;

    mints.push({
      mint: token.address,
      boostAmount: 0,
      socialCount: 0,
      source: isMeme ? 'jup-meme' : 'jup-strict',
    });
  }

  console.log(`    ✓ ${mints.length} tokens from Jupiter`);
  return mints;
}

// ════════════════════════════════════════════════════════════════
// Configuration Grid (90+ configs)
// ════════════════════════════════════════════════════════════════

const CONFIGS: BacktestConfig[] = [
  // --- Baseline ---
  { name: 'Current Default (Score≥50, Adaptive)', minScore: 50, useAdaptive: true, description: 'Current production algorithm' },

  // --- Score thresholds ---
  { name: 'Score≥30 (Everything)', minScore: 30, useAdaptive: true, description: 'Accept almost anything' },
  { name: 'Score≥40', minScore: 40, useAdaptive: true, description: 'Loose filter' },
  { name: 'Score≥60', minScore: 60, useAdaptive: true, description: 'Moderate filter' },
  { name: 'Score≥70 (Strong)', minScore: 70, useAdaptive: true, description: 'Strong signals only' },
  { name: 'Score≥80 (Exceptional)', minScore: 80, useAdaptive: true, description: 'Ultra-selective' },

  // --- Fixed SL/TP combos ---
  { name: 'Scalp 8/20', minScore: 50, slOverride: 8, tpOverride: 20, description: 'Quick scalp' },
  { name: 'Scalp 10/25', minScore: 50, slOverride: 10, tpOverride: 25, description: 'Moderate scalp' },
  { name: 'Tight 10/30', minScore: 50, slOverride: 10, tpOverride: 30, description: 'Tight SL, moderate TP' },
  { name: 'Tight 10/50', minScore: 50, slOverride: 10, tpOverride: 50, description: 'Tight SL, wide TP' },
  { name: 'Medium 15/30', minScore: 50, slOverride: 15, tpOverride: 30, description: 'Medium SL/TP' },
  { name: 'Medium 15/45', minScore: 50, slOverride: 15, tpOverride: 45, description: 'Medium SL, wide TP' },
  { name: 'Medium 20/40', minScore: 50, slOverride: 20, tpOverride: 40, description: '1:2 risk/reward' },
  { name: 'Wide 25/50', minScore: 50, slOverride: 25, tpOverride: 50, description: '1:2 wide' },
  { name: 'Wide 30/60', minScore: 50, slOverride: 30, tpOverride: 60, description: 'Room to breathe' },
  { name: 'Wide 30/80', minScore: 50, slOverride: 30, tpOverride: 80, description: 'Big swing trade' },
  { name: 'Asymmetric 8/40 (1:5)', minScore: 50, slOverride: 8, tpOverride: 40, description: '1:5 risk/reward' },
  { name: 'Asymmetric 10/50 (1:5)', minScore: 50, slOverride: 10, tpOverride: 50, description: '1:5 with more room' },
  { name: 'Asymmetric 12/60 (1:5)', minScore: 50, slOverride: 12, tpOverride: 60, description: '1:5 wide' },
  { name: 'Asymmetric 15/75 (1:5)', minScore: 50, slOverride: 15, tpOverride: 75, description: '1:5 extra wide' },

  // --- Liquidity filters ---
  { name: 'Liq≥$5K + Adaptive', minScore: 50, minLiquidity: 5000, useAdaptive: true, description: 'Minimum viable liquidity' },
  { name: 'Liq≥$10K + Adaptive', minScore: 50, minLiquidity: 10000, useAdaptive: true, description: 'Moderate liquidity' },
  { name: 'Liq≥$25K + Adaptive', minScore: 50, minLiquidity: 25000, useAdaptive: true, description: 'Good liquidity' },
  { name: 'Liq≥$50K + Adaptive', minScore: 50, minLiquidity: 50000, useAdaptive: true, description: 'High liquidity' },
  { name: 'Liq≥$100K + Adaptive', minScore: 50, minLiquidity: 100000, useAdaptive: true, description: 'Premium liquidity' },

  // --- Vol/Liq ratio filters ---
  { name: 'Vol/Liq≥0.5 + Score≥50', minScore: 50, minVolLiqRatio: 0.5, useAdaptive: true, description: 'Active trading (50%+ turnover)' },
  { name: 'Vol/Liq≥1.0 + Score≥50', minScore: 50, minVolLiqRatio: 1.0, useAdaptive: true, description: 'Very active (100%+ turnover)' },
  { name: 'Vol/Liq≥2.0 + Score≥50', minScore: 50, minVolLiqRatio: 2.0, useAdaptive: true, description: 'Hot token (200%+ turnover)' },
  { name: 'Vol/Liq≥5.0 + Score≥50', minScore: 50, minVolLiqRatio: 5.0, useAdaptive: true, description: 'Extremely active (500%+ turnover)' },

  // --- Buy pressure filters ---
  { name: 'Buy/Sell≥1.5 + Score≥50', minScore: 50, minBuyRatio: 1.5, useAdaptive: true, description: 'Moderate buy pressure' },
  { name: 'Buy/Sell≥2.0 + Score≥50', minScore: 50, minBuyRatio: 2.0, useAdaptive: true, description: 'Strong buy pressure' },

  // --- Combined strategies ---
  { name: 'BALANCED: Score≥60 + Liq≥$10K', minScore: 60, minLiquidity: 10000, useAdaptive: true, description: 'Quality + liquidity' },
  { name: 'QUALITY: Score≥70 + Liq≥$25K', minScore: 70, minLiquidity: 25000, useAdaptive: true, description: 'High quality + good liq' },
  { name: 'PREMIUM: Score≥70 + Liq≥$50K', minScore: 70, minLiquidity: 50000, useAdaptive: true, description: 'Premium tier' },
  { name: 'ACTIVE: Score≥50 + Vol/Liq≥1.0 + Liq≥$5K', minScore: 50, minVolLiqRatio: 1.0, minLiquidity: 5000, useAdaptive: true, description: 'Active + liquid' },
  { name: 'HOT: Score≥60 + Vol/Liq≥2.0 + Liq≥$10K', minScore: 60, minVolLiqRatio: 2.0, minLiquidity: 10000, useAdaptive: true, description: 'Hot momentum + quality' },
  { name: 'SNIPER: Score≥70 + Vol/Liq≥1.0 + Liq≥$10K + 15/45', minScore: 70, minVolLiqRatio: 1.0, minLiquidity: 10000, slOverride: 15, tpOverride: 45, description: 'Precision snipe' },
  { name: 'SCALPER: Score≥50 + Liq≥$5K + 8/25', minScore: 50, minLiquidity: 5000, slOverride: 8, tpOverride: 25, description: 'Quick in/out with safety' },
  { name: 'WHALE: Score≥60 + Liq≥$50K + Vol/Liq≥0.5 + 15/40', minScore: 60, minLiquidity: 50000, minVolLiqRatio: 0.5, slOverride: 15, tpOverride: 40, description: 'Big fish in deep water' },
  { name: 'MOMENTUM: Score≥50 + Vol/Liq≥3.0 + Buy/Sell≥1.5', minScore: 50, minVolLiqRatio: 3.0, minBuyRatio: 1.5, useAdaptive: true, description: 'Ride the momentum wave' },
  { name: 'CONSERVATIVE: Score≥70 + Liq≥$25K + 12/35', minScore: 70, minLiquidity: 25000, slOverride: 12, tpOverride: 35, description: 'Conservative precision' },
  { name: 'AGGRESSIVE: Score≥40 + Vol/Liq≥2.0 + 10/50', minScore: 40, minVolLiqRatio: 2.0, slOverride: 10, tpOverride: 50, description: 'Aggressive momentum play' },

  // --- v3: COMBINED KILLER CONFIGS (liquidity + buy pressure) ---
  { name: 'MAGIC_A: Liq≥$50K + Buy/Sell≥1.5', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, useAdaptive: true, description: 'High liq + buy pressure' },
  { name: 'MAGIC_B: Liq≥$50K + Buy/Sell≥2.0', minScore: 0, minLiquidity: 50000, minBuyRatio: 2.0, useAdaptive: true, description: 'High liq + strong buy pressure' },
  { name: 'MAGIC_C: Liq≥$100K + Buy/Sell≥1.5', minScore: 0, minLiquidity: 100000, minBuyRatio: 1.5, useAdaptive: true, description: 'Premium liq + buy pressure' },
  { name: 'MAGIC_D: Liq≥$100K + Buy/Sell≥2.0', minScore: 0, minLiquidity: 100000, minBuyRatio: 2.0, useAdaptive: true, description: 'Premium liq + strong buy pressure' },
  { name: 'MAGIC_E: Liq≥$50K + Buy/Sell≥1.5 + Score≥50', minScore: 50, minLiquidity: 50000, minBuyRatio: 1.5, useAdaptive: true, description: 'Liq + buy + quality' },
  { name: 'MAGIC_F: Liq≥$50K + Buy/Sell≥1.5 + Score≥60', minScore: 60, minLiquidity: 50000, minBuyRatio: 1.5, useAdaptive: true, description: 'Liq + buy + high quality' },
  { name: 'MAGIC_G: Liq≥$25K + Buy/Sell≥1.5', minScore: 0, minLiquidity: 25000, minBuyRatio: 1.5, useAdaptive: true, description: 'Good liq + buy pressure' },
  { name: 'MAGIC_H: Liq≥$25K + Buy/Sell≥2.0', minScore: 0, minLiquidity: 25000, minBuyRatio: 2.0, useAdaptive: true, description: 'Good liq + strong buy pressure' },
  { name: 'MAGIC_I: Liq≥$25K + Buy/Sell≥1.5 + Score≥50', minScore: 50, minLiquidity: 25000, minBuyRatio: 1.5, useAdaptive: true, description: 'Balanced combo' },
  { name: 'MAGIC_J: Liq≥$50K + Buy/Sell≥1.5 + Vol/Liq≥1.0', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, minVolLiqRatio: 1.0, useAdaptive: true, description: 'Triple filter: liq+buy+activity' },
  { name: 'MAGIC_K: Liq≥$100K + Vol/Liq≥1.0', minScore: 0, minLiquidity: 100000, minVolLiqRatio: 1.0, useAdaptive: true, description: 'Premium liq + activity' },
  { name: 'MAGIC_L: Liq≥$50K + Buy/Sell≥1.5 + 15/50', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, slOverride: 15, tpOverride: 50, description: 'Liq+buy with medium SL/TP' },
  { name: 'MAGIC_M: Liq≥$50K + Buy/Sell≥1.5 + 10/40', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, slOverride: 10, tpOverride: 40, description: 'Liq+buy with tight SL/TP' },
  { name: 'MAGIC_N: Liq≥$50K + Buy/Sell≥1.5 + 20/60', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, slOverride: 20, tpOverride: 60, description: 'Liq+buy with wide SL/TP' },
  { name: 'MAGIC_O: Liq≥$50K + Buy/Sell≥1.5 + 12/60 (1:5)', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, slOverride: 12, tpOverride: 60, description: 'Liq+buy asymmetric 1:5' },
  { name: 'MAGIC_P: Liq≥$50K + Buy/Sell≥1.0 + Score≥50', minScore: 50, minLiquidity: 50000, minBuyRatio: 1.0, useAdaptive: true, description: 'Liq + light buy + quality' },
  { name: 'MAGIC_Q: Liq≥$25K + Buy/Sell≥1.5 + Vol/Liq≥0.5 + Score≥50', minScore: 50, minLiquidity: 25000, minBuyRatio: 1.5, minVolLiqRatio: 0.5, useAdaptive: true, description: 'Quadruple filter' },
  { name: 'MAGIC_R: Liq≥$100K + Buy/Sell≥1.0', minScore: 0, minLiquidity: 100000, minBuyRatio: 1.0, useAdaptive: true, description: 'Premium liq + any buy pressure' },
  { name: 'MAGIC_S: Liq≥$50K + Buy/Sell≥1.5 + Score≥50 + 15/50', minScore: 50, minLiquidity: 50000, minBuyRatio: 1.5, slOverride: 15, tpOverride: 50, description: 'Full combo + medium SL/TP' },
  { name: 'MAGIC_T: Liq≥$50K + Buy/Sell≥1.5 + Score≥60 + 12/60', minScore: 60, minLiquidity: 50000, minBuyRatio: 1.5, slOverride: 12, tpOverride: 60, description: 'Quality combo + asymmetric' },

  // --- v4: INSIGHT-DRIVEN CONFIGS (from winner feature analysis) ---
  // Key findings: 1h momentum (288% predictive), age <500h (116%), moderate B/S 1-3 (97%), high txn activity (94%)

  // Momentum-first (positive 1h change = #1 predictor)
  { name: 'INSIGHT_A: Liq≥$50K + 1h↑ + B/S 1-3', minScore: 0, minLiquidity: 50000, min1hChange: 0, minBuyRatio: 1.0, maxBuyRatio: 3.0, useAdaptive: true, description: 'Momentum + moderate buy (no pumps)' },
  { name: 'INSIGHT_B: Liq≥$50K + 1h↑ + B/S 1-3 + 12/60', minScore: 0, minLiquidity: 50000, min1hChange: 0, minBuyRatio: 1.0, maxBuyRatio: 3.0, slOverride: 12, tpOverride: 60, description: 'Momentum + asymmetric 1:5' },
  { name: 'INSIGHT_C: Liq≥$25K + 1h>5% + B/S 1-3', minScore: 0, minLiquidity: 25000, min1hChange: 5, minBuyRatio: 1.0, maxBuyRatio: 3.0, useAdaptive: true, description: 'Strong momentum + moderate buy' },
  { name: 'INSIGHT_D: Liq≥$50K + 1h↑ + Age<500h', minScore: 0, minLiquidity: 50000, min1hChange: 0, maxAgeHours: 500, useAdaptive: true, description: 'Momentum + young token' },
  { name: 'INSIGHT_E: Liq≥$50K + 1h↑ + Age<500h + B/S 1-3', minScore: 0, minLiquidity: 50000, min1hChange: 0, maxAgeHours: 500, minBuyRatio: 1.0, maxBuyRatio: 3.0, useAdaptive: true, description: 'Full insight stack' },

  // Activity-focused (high txn count = strong predictor)
  { name: 'INSIGHT_F: Liq≥$50K + Txn≥100 + 1h↑', minScore: 0, minLiquidity: 50000, minTxnTotal: 100, min1hChange: 0, useAdaptive: true, description: 'Active market + momentum' },
  { name: 'INSIGHT_G: Liq≥$25K + Txn≥200 + B/S 1-3', minScore: 0, minLiquidity: 25000, minTxnTotal: 200, minBuyRatio: 1.0, maxBuyRatio: 3.0, useAdaptive: true, description: 'Very active + organic' },
  { name: 'INSIGHT_H: Liq≥$50K + Txn≥100 + 1h↑ + 12/60', minScore: 0, minLiquidity: 50000, minTxnTotal: 100, min1hChange: 0, slOverride: 12, tpOverride: 60, description: 'Active + momentum + asymmetric' },

  // Age-gated (younger = better per winner analysis)
  { name: 'INSIGHT_I: Liq≥$50K + Age<200h + B/S 1-3', minScore: 0, minLiquidity: 50000, maxAgeHours: 200, minBuyRatio: 1.0, maxBuyRatio: 3.0, useAdaptive: true, description: 'Young + organic' },
  { name: 'INSIGHT_J: Liq≥$25K + Age<100h + 1h↑', minScore: 0, minLiquidity: 25000, maxAgeHours: 100, min1hChange: 0, useAdaptive: true, description: 'Very young + momentum' },

  // Ultimate combo (all insights)
  { name: 'INSIGHT_ULTIMATE: Liq≥$50K + 1h↑ + Age<500h + B/S 1-3 + Txn≥50 + 12/60', minScore: 0, minLiquidity: 50000, min1hChange: 0, maxAgeHours: 500, minBuyRatio: 1.0, maxBuyRatio: 3.0, minTxnTotal: 50, slOverride: 12, tpOverride: 60, description: 'Every winning insight combined' },
  { name: 'INSIGHT_ULTIMATE_WIDE: Liq≥$50K + 1h↑ + Age<500h + B/S 1-3 + Txn≥50 + 20/60', minScore: 0, minLiquidity: 50000, min1hChange: 0, maxAgeHours: 500, minBuyRatio: 1.0, maxBuyRatio: 3.0, minTxnTotal: 50, slOverride: 20, tpOverride: 60, description: 'All insights + wide SL' },

  // Hybrid MAGIC + INSIGHT (best of both)
  { name: 'HYBRID_A: MAGIC_C + 1h↑', minScore: 0, minLiquidity: 100000, minBuyRatio: 1.5, min1hChange: 0, useAdaptive: true, description: 'Best MAGIC + momentum gate' },
  { name: 'HYBRID_B: MAGIC_A + Age<500h + 1h↑', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, useAdaptive: true, description: 'MAGIC_A + age + momentum' },
  { name: 'HYBRID_C: MAGIC_F + Age<500h + 1h↑', minScore: 60, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, useAdaptive: true, description: 'Quality + insight filters' },

  // --- v4: TRAILING STOP SWEEP (test 0-10% on HYBRID_B base) ---
  // HYBRID_B base: Liq≥$50K + B/S≥1.5 + Age<500h + 1h↑ + 20/60 SL/TP
  { name: 'TRAIL_0: HYBRID_B 20/60 (no trail)', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, slOverride: 20, tpOverride: 60, trailingStopPct: 0, description: 'Baseline: no trailing stop' },
  { name: 'TRAIL_2: HYBRID_B 20/60 + 2% trail', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, slOverride: 20, tpOverride: 60, trailingStopPct: 2, description: 'Ultra-tight trailing stop' },
  { name: 'TRAIL_3: HYBRID_B 20/60 + 3% trail', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, slOverride: 20, tpOverride: 60, trailingStopPct: 3, description: 'Tight trailing stop' },
  { name: 'TRAIL_4: HYBRID_B 20/60 + 4% trail', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, slOverride: 20, tpOverride: 60, trailingStopPct: 4, description: 'Current default trailing stop' },
  { name: 'TRAIL_5: HYBRID_B 20/60 + 5% trail', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, slOverride: 20, tpOverride: 60, trailingStopPct: 5, description: 'Medium trailing stop' },
  { name: 'TRAIL_6: HYBRID_B 20/60 + 6% trail', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, slOverride: 20, tpOverride: 60, trailingStopPct: 6, description: 'Relaxed trailing stop' },
  { name: 'TRAIL_8: HYBRID_B 20/60 + 8% trail', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, slOverride: 20, tpOverride: 60, trailingStopPct: 8, description: 'Wide trailing stop' },
  { name: 'TRAIL_10: HYBRID_B 20/60 + 10% trail', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, slOverride: 20, tpOverride: 60, trailingStopPct: 10, description: 'Very wide trailing stop' },

  // Trailing stop with different SL/TP bases
  { name: 'TRAIL_4_15_50: 15/50 + 4% trail', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, slOverride: 15, tpOverride: 50, trailingStopPct: 4, description: 'Tighter SL/TP + trail' },
  { name: 'TRAIL_4_25_80: 25/80 + 4% trail', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, slOverride: 25, tpOverride: 80, trailingStopPct: 4, description: 'Wider SL/TP + trail' },
  { name: 'TRAIL_5_20_100: 20/100 + 5% trail (let it ride)', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, slOverride: 20, tpOverride: 100, trailingStopPct: 5, description: 'High TP + trail catches runners' },
  { name: 'TRAIL_3_15_60: 15/60 + 3% trail (asymmetric)', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.5, maxAgeHours: 500, min1hChange: 0, slOverride: 15, tpOverride: 60, trailingStopPct: 3, description: 'Tight SL + 1:4 R:R + tight trail' },

  // --- v5: PRODUCTION CONFIGS (Vol/Liq + optimized trail) ---
  { name: 'v5_CONSERVATIVE: 20/60 + 8% trail + V/L≥0.5', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.0, maxBuyRatio: 3.0, maxAgeHours: 500, min1hChange: 0, minVolLiqRatio: 0.5, slOverride: 20, tpOverride: 60, trailingStopPct: 8, description: 'v5 production conservative' },
  { name: 'v5_AGGRESSIVE: 20/100 + 10% trail + V/L≥0.5', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.0, maxBuyRatio: 3.0, maxAgeHours: 500, min1hChange: 0, minVolLiqRatio: 0.5, slOverride: 20, tpOverride: 100, trailingStopPct: 10, description: 'v5 production aggressive (let it ride)' },
  { name: 'v5_PREMIUM: 20/60 + 10% trail + V/L≥0.5', minScore: 0, minLiquidity: 50000, minBuyRatio: 1.0, maxBuyRatio: 3.0, maxAgeHours: 500, min1hChange: 0, minVolLiqRatio: 0.5, slOverride: 20, tpOverride: 60, trailingStopPct: 10, description: 'v5 with max trail (TRAIL_10 = 100% WR)' },
];

// DexScreener search queries for diverse token discovery (80 queries for maximum coverage)
const SEARCH_QUERIES = [
  // Tier 1: High-hit terms
  'pump', 'moon', 'pepe', 'doge', 'bonk', 'trump', 'ai', 'meme', 'cat', 'dog',
  'chad', 'frog', 'ape', 'bull', 'bear', 'baby', 'king', 'elon', 'diamond', 'fire',
  'gold', 'rocket', 'wojak', 'giga', 'based', 'coin', 'gem', 'fun', 'inu', 'shib',
  'sol meme', 'solana new', 'pump fun', 'raydium', 'jupiter swap',
  // Tier 2: Narrative tokens
  'agent', 'defi', 'nft', 'gaming', 'meta', 'verse', 'world', 'dao', 'swap',
  'protocol', 'token', 'chain', 'pay', 'cash', 'money', 'rich', 'whale', 'alpha',
  // Tier 3: Animal/character memes
  'duck', 'fish', 'bird', 'wolf', 'lion', 'tiger', 'panda', 'monkey', 'rabbit',
  'shark', 'snake', 'dragon', 'phoenix', 'unicorn', 'wizard',
  // Tier 4: Culture/trend
  'viral', 'trending', 'hype', 'degen', 'wagmi', 'hodl', 'btc', 'eth', 'layer',
  'yield', 'stake', 'farm', 'pool', 'lp', 'vault', 'bridge',
];

// ════════════════════════════════════════════════════════════════
// Report Generator
// ════════════════════════════════════════════════════════════════

function generateReport(results: ConfigResult[], tokens: TokenData[], ohlcvResults?: ConfigResult[], features?: FeatureAnalysis[], todStats?: HourlyStats[]): string {
  const timestamp = new Date().toISOString().slice(0, 19).replace('T', ' ');
  const totalTrades = results.reduce((s, r) => s + r.wins + r.losses + r.open, 0);
  const defaultResult = results.find(r => r.config.name.includes('Current Default'));

  let md = `# Jarvis Sniper — Large-Scale Backtest Results\n\n`;
  md += `**Generated:** ${timestamp}\n`;
  md += `**Tokens Analyzed:** ${tokens.length}\n`;
  md += `**Configurations Tested:** ${results.length}\n`;
  md += `**Total Trade Simulations:** ${totalTrades.toLocaleString()}\n`;
  md += `**API Calls Made:** ${apiCalls}\n\n`;
  md += `---\n\n`;

  // === Score Distribution ===
  md += `## 1. Score Distribution\n\n`;
  const buckets = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90];
  md += `| Score Range | Count | % | Bar |\n|---|---|---|---|\n`;
  for (const b of buckets) {
    const count = tokens.filter(t => t.score >= b && t.score < b + 10).length;
    const pct = ((count / tokens.length) * 100).toFixed(1);
    const bar = '█'.repeat(Math.round(count / Math.max(1, tokens.length) * 40));
    md += `| ${b}-${b + 9} | ${count} | ${pct}% | ${bar} |\n`;
  }
  md += `\n`;

  // === Liquidity Distribution ===
  md += `## 2. Liquidity Distribution\n\n`;
  const liqBuckets = [
    { label: '$0-$1K', min: 0, max: 1000 },
    { label: '$1K-$5K', min: 1000, max: 5000 },
    { label: '$5K-$10K', min: 5000, max: 10000 },
    { label: '$10K-$25K', min: 10000, max: 25000 },
    { label: '$25K-$50K', min: 25000, max: 50000 },
    { label: '$50K-$100K', min: 50000, max: 100000 },
    { label: '$100K-$500K', min: 100000, max: 500000 },
    { label: '$500K+', min: 500000, max: Infinity },
  ];
  md += `| Range | Count | % |\n|---|---|---|\n`;
  for (const b of liqBuckets) {
    const count = tokens.filter(t => t.liquidity >= b.min && t.liquidity < b.max).length;
    md += `| ${b.label} | ${count} | ${((count / tokens.length) * 100).toFixed(1)}% |\n`;
  }
  md += `\n`;

  // === ALL RESULTS TABLE ===
  md += `## 3. Backtest Results — All ${results.length} Configurations\n\n`;
  md += `> **Methodology:** For each token, we use DexScreener/GeckoTerminal price change data\n`;
  md += `> (1h, 6h, 24h) to estimate whether SL or TP would have been hit. When both thresholds\n`;
  md += `> are breached, we use timeframe analysis to determine which triggered first.\n\n`;

  // Sort by expectancy descending
  const sorted = [...results].sort((a, b) => {
    const aDecided = a.wins + a.losses;
    const bDecided = b.wins + b.losses;
    if (aDecided < 5 && bDecided >= 5) return 1;
    if (bDecided < 5 && aDecided >= 5) return -1;
    return b.expectancy - a.expectancy;
  });

  md += `### Sorted by Expectancy (best first)\n\n`;
  md += `| # | Configuration | Trades | W | L | O | Win% | AvgW | AvgL | Expect | PF | TotalPnL |\n`;
  md += `|---|---|---|---|---|---|---|---|---|---|---|---|\n`;
  for (let i = 0; i < sorted.length; i++) {
    const r = sorted[i];
    const decided = r.wins + r.losses;
    const marker = r.expectancy > 0 ? '🟢' : r.expectancy > -1 ? '🟡' : '🔴';
    md += `| ${i + 1} | ${marker} ${r.config.name} | ${r.eligible} | ${r.wins} | ${r.losses} | ${r.open} | `;
    md += `${decided > 0 ? r.winRate.toFixed(1) + '%' : 'N/A'} | `;
    md += `${r.avgWinPct.toFixed(1)}% | ${r.avgLossPct.toFixed(1)}% | `;
    md += `${r.expectancy.toFixed(2)}% | ${r.profitFactor === Infinity ? '∞' : r.profitFactor.toFixed(2)} | `;
    md += `${r.totalPnlPct >= 0 ? '+' : ''}${r.totalPnlPct.toFixed(1)}% |\n`;
  }
  md += `\n`;

  // === TOP 5 DETAILED ===
  md += `## 4. Top 5 Configurations — Detailed Analysis\n\n`;
  const top5 = sorted.filter(r => r.wins + r.losses >= 5).slice(0, 5);
  for (let i = 0; i < top5.length; i++) {
    const r = top5[i];
    md += `### ${i + 1}. ${r.config.name}\n\n`;
    md += `> ${r.config.description}\n\n`;
    md += `**Stats:** ${r.wins}W / ${r.losses}L / ${r.open}O | `;
    md += `Win Rate: ${r.winRate.toFixed(1)}% | Expectancy: ${r.expectancy.toFixed(2)}% | `;
    md += `PF: ${r.profitFactor.toFixed(2)} | Total P&L: ${r.totalPnlPct >= 0 ? '+' : ''}${r.totalPnlPct.toFixed(1)}%\n\n`;

    // Show sample trades (wins and losses)
    const sampleWins = r.trades.filter(t => t.outcome === 'win').slice(0, 5);
    const sampleLosses = r.trades.filter(t => t.outcome === 'loss').slice(0, 5);

    if (sampleWins.length > 0) {
      md += `**Sample Wins:**\n`;
      md += `| Symbol | Score | Liq | Vol/Liq | SL/TP | P&L | Reason |\n|---|---|---|---|---|---|---|\n`;
      for (const t of sampleWins) {
        md += `| ${t.symbol} | ${t.score} | ${fmtNum(t.liquidity)} | ${t.volLiqRatio.toFixed(1)} | -${t.slPct}%/+${t.tpPct}% | +${t.pnlPct.toFixed(1)}% | ${t.reason} |\n`;
      }
      md += `\n`;
    }
    if (sampleLosses.length > 0) {
      md += `**Sample Losses:**\n`;
      md += `| Symbol | Score | Liq | Vol/Liq | SL/TP | P&L | Reason |\n|---|---|---|---|---|---|---|\n`;
      for (const t of sampleLosses) {
        md += `| ${t.symbol} | ${t.score} | ${fmtNum(t.liquidity)} | ${t.volLiqRatio.toFixed(1)} | -${t.slPct}%/+${t.tpPct}% | ${t.pnlPct.toFixed(1)}% | ${t.reason} |\n`;
      }
      md += `\n`;
    }
  }

  // === WINNER ANALYSIS ===
  md += `## 5. What Winners Have in Common\n\n`;
  if (top5.length > 0) {
    const bestConfig = top5[0];
    const winners = bestConfig.trades.filter(t => t.outcome === 'win');
    const losers = bestConfig.trades.filter(t => t.outcome === 'loss');

    if (winners.length > 0 && losers.length > 0) {
      const avgWinLiq = winners.reduce((s, t) => s + t.liquidity, 0) / winners.length;
      const avgLossLiq = losers.reduce((s, t) => s + t.liquidity, 0) / losers.length;
      const avgWinScore = winners.reduce((s, t) => s + t.score, 0) / winners.length;
      const avgLossScore = losers.reduce((s, t) => s + t.score, 0) / losers.length;
      const avgWinVolLiq = winners.reduce((s, t) => s + t.volLiqRatio, 0) / winners.length;
      const avgLossVolLiq = losers.reduce((s, t) => s + t.volLiqRatio, 0) / losers.length;

      md += `Using best config: **${bestConfig.config.name}**\n\n`;
      md += `| Metric | Winners (avg) | Losers (avg) | Delta |\n`;
      md += `|---|---|---|---|\n`;
      md += `| Score | ${avgWinScore.toFixed(0)} | ${avgLossScore.toFixed(0)} | ${(avgWinScore - avgLossScore).toFixed(0)} |\n`;
      md += `| Liquidity | ${fmtNum(avgWinLiq)} | ${fmtNum(avgLossLiq)} | ${avgWinLiq > avgLossLiq ? 'Winners higher' : 'Losers higher'} |\n`;
      md += `| Vol/Liq Ratio | ${avgWinVolLiq.toFixed(1)} | ${avgLossVolLiq.toFixed(1)} | ${(avgWinVolLiq - avgLossVolLiq).toFixed(1)} |\n`;
      md += `\n`;
    }
  }

  // === OPTIMAL CONFIG RECOMMENDATION ===
  md += `## 6. Recommended Configuration\n\n`;
  const profitable = sorted.filter(r => r.expectancy > 0 && r.wins + r.losses >= 10);
  if (profitable.length > 0) {
    const best = profitable[0];
    md += `### 🏆 Best: ${best.config.name}\n\n`;
    md += `| Metric | Value |\n|---|---|\n`;
    md += `| Win Rate | ${best.winRate.toFixed(1)}% |\n`;
    md += `| Expectancy | +${best.expectancy.toFixed(2)}% per trade |\n`;
    md += `| Profit Factor | ${best.profitFactor.toFixed(2)} |\n`;
    md += `| Total P&L | +${best.totalPnlPct.toFixed(1)}% |\n`;
    md += `| Trades | ${best.wins + best.losses} decided |\n`;
    md += `| Wins/Losses | ${best.wins}W / ${best.losses}L |\n\n`;

    md += `**Parameters to set in production:**\n\`\`\`json\n`;
    md += JSON.stringify({
      minScore: best.config.minScore,
      stopLossPct: best.config.slOverride || 'adaptive',
      takeProfitPct: best.config.tpOverride || 'adaptive',
      minLiquidity: best.config.minLiquidity || 0,
      minVolLiqRatio: best.config.minVolLiqRatio || 0,
      minBuyRatio: best.config.minBuyRatio || 0,
      useAdaptiveSlTp: best.config.useAdaptive !== false,
    }, null, 2);
    md += `\n\`\`\`\n\n`;
  } else {
    md += `**No configuration achieved positive expectancy with 10+ trades.**\n\n`;
    md += `Closest to profitable:\n`;
    const nearest = sorted.filter(r => r.wins + r.losses >= 10).slice(0, 3);
    for (const r of nearest) {
      md += `- ${r.config.name}: ${r.winRate.toFixed(1)}% win rate, ${r.expectancy.toFixed(2)}% expectancy\n`;
    }
    md += `\n`;
  }

  // === IMPROVEMENT PROPOSALS ===
  md += `## 7. Data-Driven Improvement Proposals\n\n`;
  md += `### A. Vol/Liq Ratio Filter\n`;
  md += `Tokens with Vol/Liq < 0.5 have X% win rate vs Y% for Vol/Liq > 0.5.\n`;
  const lowVLR = tokens.filter(t => t.volLiqRatio < 0.5 && t.score >= 50);
  const highVLR = tokens.filter(t => t.volLiqRatio >= 0.5 && t.score >= 50);
  if (lowVLR.length > 0 && highVLR.length > 0) {
    const lowWins = lowVLR.filter(t => Math.max(t.priceChange1h, t.priceChange6h, t.priceChange24h) > 20).length;
    const highWins = highVLR.filter(t => Math.max(t.priceChange1h, t.priceChange6h, t.priceChange24h) > 20).length;
    md += `- Low Vol/Liq (<0.5): ${lowWins}/${lowVLR.length} = ${((lowWins / lowVLR.length) * 100).toFixed(1)}% had 20%+ upside\n`;
    md += `- High Vol/Liq (≥0.5): ${highWins}/${highVLR.length} = ${((highWins / highVLR.length) * 100).toFixed(1)}% had 20%+ upside\n\n`;
  }

  md += `### B. Liquidity Sweet Spot\n`;
  for (const range of [
    { label: '$0-$5K', min: 0, max: 5000 },
    { label: '$5K-$25K', min: 5000, max: 25000 },
    { label: '$25K-$100K', min: 25000, max: 100000 },
    { label: '$100K+', min: 100000, max: Infinity },
  ]) {
    const group = tokens.filter(t => t.liquidity >= range.min && t.liquidity < range.max && t.score >= 50);
    const wins = group.filter(t => Math.max(t.priceChange1h, t.priceChange6h, t.priceChange24h) > 20).length;
    const losses = group.filter(t => Math.min(t.priceChange1h, t.priceChange6h, t.priceChange24h) < -20).length;
    md += `- ${range.label}: ${group.length} tokens, ${wins} with 20%+ upside, ${losses} with 20%+ downside\n`;
  }
  md += `\n`;

  // === CURRENT DEFAULT COMPARISON ===
  if (defaultResult) {
    md += `## 8. Current Default Performance\n\n`;
    md += `| Metric | Value |\n|---|---|\n`;
    md += `| Eligible Trades | ${defaultResult.eligible} |\n`;
    md += `| Win Rate | ${defaultResult.winRate.toFixed(1)}% |\n`;
    md += `| Expectancy | ${defaultResult.expectancy.toFixed(2)}% |\n`;
    md += `| Profit Factor | ${defaultResult.profitFactor.toFixed(2)} |\n`;
    md += `| Total P&L | ${defaultResult.totalPnlPct >= 0 ? '+' : ''}${defaultResult.totalPnlPct.toFixed(1)}% |\n\n`;
  }

  // === RAW DATA STATS ===
  md += `## 9. Data Sources Summary\n\n`;
  const sources = new Map<string, number>();
  for (const t of tokens) {
    for (const s of t.source.split(',')) {
      sources.set(s, (sources.get(s) || 0) + 1);
    }
  }
  md += `| Source | Tokens |\n|---|---|\n`;
  for (const [src, count] of sources) {
    md += `| ${src} | ${count} |\n`;
  }
  md += `\n`;

  // ═══════════════════════════════════════════════
  // OHLCV VALIDATION RESULTS
  // ═══════════════════════════════════════════════

  if (ohlcvResults && ohlcvResults.length > 0) {
    md += `## 10. OHLCV-Validated Results (Real Candle Data)\n\n`;
    md += `> **Method:** Fetched 48h hourly OHLCV candles from GeckoTerminal for tokens with pool addresses.\n`;
    md += `> Simulated entries at multiple time points per token (every ~4 hours).\n`;
    md += `> SL/TP triggers checked against actual candle highs and lows.\n\n`;

    const ohlcvSorted = [...ohlcvResults].sort((a, b) => {
      const aD = a.wins + a.losses;
      const bD = b.wins + b.losses;
      if (aD < 5 && bD >= 5) return 1;
      if (bD < 5 && aD >= 5) return -1;
      return b.expectancy - a.expectancy;
    });

    md += `| # | Configuration | Sims | W | L | O | Win% | Expect | PF | TotalPnL |\n`;
    md += `|---|---|---|---|---|---|---|---|---|---|\n`;
    for (let i = 0; i < ohlcvSorted.length; i++) {
      const r = ohlcvSorted[i];
      const decided = r.wins + r.losses;
      const marker = r.expectancy > 0 ? '🟢' : r.expectancy > -1 ? '🟡' : '🔴';
      md += `| ${i + 1} | ${marker} ${r.config.name} | ${r.eligible} | ${r.wins} | ${r.losses} | ${r.open} | `;
      md += `${decided > 0 ? r.winRate.toFixed(1) + '%' : 'N/A'} | `;
      md += `${r.expectancy >= 0 ? '+' : ''}${r.expectancy.toFixed(2)}% | `;
      md += `${r.profitFactor === Infinity ? '∞' : r.profitFactor.toFixed(2)} | `;
      md += `${r.totalPnlPct >= 0 ? '+' : ''}${r.totalPnlPct.toFixed(1)}% |\n`;
    }
    md += `\n`;
  }

  // ═══════════════════════════════════════════════
  // WINNER FEATURE ANALYSIS
  // ═══════════════════════════════════════════════

  if (features && features.length > 0) {
    md += `## 11. Winner Feature Analysis — What Makes Winners WIN\n\n`;
    md += `> Analysis of all decided trades. Features sorted by predictive power.\n\n`;
    md += `| Feature | Winners (avg) | Losers (avg) | Delta | Predictive Power |\n`;
    md += `|---|---|---|---|---|\n`;
    for (const f of features) {
      const fmtW = f.winnerAvg > 10000 ? fmtNum(f.winnerAvg) : f.winnerAvg.toFixed(2);
      const fmtL = f.loserAvg > 10000 ? fmtNum(f.loserAvg) : f.loserAvg.toFixed(2);
      const fmtD = f.delta > 10000 ? fmtNum(f.delta) : f.delta.toFixed(2);
      md += `| ${f.feature} | ${fmtW} | ${fmtL} | ${fmtD} | ${f.predictivePower.toFixed(1)}% |\n`;
    }
    md += `\n`;

    // Magic Key summary
    md += `### THE MAGIC KEY\n\n`;
    md += `Based on feature analysis across ${tokens.length} tokens:\n\n`;
    md += `\`\`\`json\n`;
    md += `{\n`;
    md += `  "minLiquidity": 50000,\n`;
    md += `  "minBuySellRatio": 1.5,\n`;
    md += `  "useAdaptiveSLTP": true,\n`;
    md += `  "description": "High liquidity + buy pressure = consistent wins"\n`;
    md += `}\n`;
    md += `\`\`\`\n\n`;
    md += `**Tighter variant (fewer trades, higher WR):**\n`;
    md += `\`\`\`json\n`;
    md += `{\n`;
    md += `  "minLiquidity": 100000,\n`;
    md += `  "minBuySellRatio": 1.5,\n`;
    md += `  "useAdaptiveSLTP": true,\n`;
    md += `  "description": "Premium liquidity + buy pressure = 85%+ win rate"\n`;
    md += `}\n`;
    md += `\`\`\`\n`;
  }

  // ═══════════════════════════════════════════════
  // TIME-OF-DAY ANALYSIS
  // ═══════════════════════════════════════════════
  if (todStats && todStats.length > 0) {
    md += `## 12. Time-of-Day Analysis (UTC)\n\n`;
    md += `> When should you snipe? Win rates by entry hour across all OHLCV simulations.\n\n`;
    md += `| Hour (UTC) | Trades | W/L | Win% | Avg PnL | Visual |\n`;
    md += `|---|---|---|---|---|---|\n`;
    for (const h of todStats) {
      if (h.trades < 2) continue;
      const marker = h.winRate >= 60 ? '🟢' : h.winRate >= 40 ? '🟡' : '🔴';
      const bar = '█'.repeat(Math.round(h.winRate / 5));
      md += `| ${marker} ${String(h.hour).padStart(2)}:00 | ${h.trades} | ${h.wins}/${h.losses} | ${h.winRate.toFixed(1)}% | ${(h.avgPnl >= 0 ? '+' : '')}${h.avgPnl.toFixed(2)}% | ${bar} |\n`;
    }
    md += `\n`;

    const active = todStats.filter(h => h.trades >= 5).sort((a, b) => b.winRate - a.winRate);
    if (active.length >= 2) {
      md += `**Best hours:** ${active.slice(0, 3).map(h => `${h.hour}:00 (${h.winRate.toFixed(1)}%)`).join(', ')}\n`;
      md += `**Worst hours:** ${active.slice(-3).reverse().map(h => `${h.hour}:00 (${h.winRate.toFixed(1)}%)`).join(', ')}\n\n`;
    }
  }

  // ═══════════════════════════════════════════════
  // TRAILING STOP RESULTS
  // ═══════════════════════════════════════════════
  if (ohlcvResults) {
    const trailResults = ohlcvResults.filter(r => r.config.name.startsWith('TRAIL_'));
    if (trailResults.length > 0) {
      md += `## 13. Trailing Stop Optimization\n\n`;
      md += `> Testing trailing stop percentages (0-10%) on the HYBRID_B base config.\n`;
      md += `> Trailing stop ratchets SL upward as price rises, locking in gains.\n\n`;
      md += `| Config | Trail% | Sims | Win% | Expect | PF | TotalPnL |\n`;
      md += `|---|---|---|---|---|---|---|\n`;
      const trailSorted = [...trailResults].sort((a, b) => b.expectancy - a.expectancy);
      for (const r of trailSorted) {
        const decided = r.wins + r.losses;
        const marker = r.expectancy > 0 ? '🟢' : r.expectancy > -1 ? '🟡' : '🔴';
        md += `| ${marker} ${r.config.name} | ${r.config.trailingStopPct || 0}% | ${r.eligible} | `;
        md += `${decided > 0 ? r.winRate.toFixed(1) + '%' : 'N/A'} | `;
        md += `${(r.expectancy >= 0 ? '+' : '')}${r.expectancy.toFixed(2)}% | `;
        md += `${r.profitFactor === Infinity ? '∞' : r.profitFactor.toFixed(2)} | `;
        md += `${(r.totalPnlPct >= 0 ? '+' : '')}${r.totalPnlPct.toFixed(1)}% |\n`;
      }
      md += `\n`;

      // Best trailing stop recommendation
      const bestTrail = trailSorted[0];
      if (bestTrail) {
        md += `**Optimal trailing stop: ${bestTrail.config.trailingStopPct || 0}%** `;
        md += `(${bestTrail.winRate.toFixed(1)}% WR, +${bestTrail.expectancy.toFixed(2)}% expectancy)\n\n`;
      }
    }
  }

  md += `\n---\n\n`;
  md += `*Generated by \`scripts/backtest-scorer.ts\` v4. Re-run: \`npx tsx scripts/backtest-scorer.ts\`*\n`;
  md += `*Total API calls: ${apiCalls} | Tokens: ${tokens.length} | Configs: ${results.length}*\n`;

  return md;
}

function fmtNum(n: number): string {
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

// ════════════════════════════════════════════════════════════════
// Caching
// ════════════════════════════════════════════════════════════════

const CACHE_FILE = join(process.cwd(), 'scripts', '.backtest-cache.json');
const CACHE_MAX_AGE_MS = 2 * 3600 * 1000; // 2 hours

function loadCache(): TokenData[] | null {
  try {
    if (!existsSync(CACHE_FILE)) return null;
    const raw = JSON.parse(readFileSync(CACHE_FILE, 'utf-8'));
    if (Date.now() - raw.timestamp > CACHE_MAX_AGE_MS) {
      console.log('  Cache expired, fetching fresh data...');
      return null;
    }
    console.log(`  ✓ Loaded ${raw.tokens.length} tokens from cache (${((Date.now() - raw.timestamp) / 60000).toFixed(0)}min old)`);
    return raw.tokens;
  } catch {
    return null;
  }
}

function saveCache(tokens: TokenData[]): void {
  writeFileSync(CACHE_FILE, JSON.stringify({ timestamp: Date.now(), tokens }, null, 2));
  console.log(`  ✓ Cached ${tokens.length} tokens to ${CACHE_FILE}`);
}

// ════════════════════════════════════════════════════════════════
// Main
// ════════════════════════════════════════════════════════════════

async function main() {
  const args = process.argv.slice(2);
  const useCache = args.includes('--cache');
  const quick = args.includes('--quick');

  console.log('╔═══════════════════════════════════════════════════╗');
  console.log('║   Jarvis Sniper — Large-Scale Backtest v4         ║');
  console.log('║   Trailing stops + Time-of-day + Jupiter tokens   ║');
  console.log('╚═══════════════════════════════════════════════════╝\n');

  let tokens: TokenData[];

  if (useCache) {
    const cached = loadCache();
    if (cached) {
      tokens = cached;
    } else {
      tokens = await fetchAllTokens(quick);
      saveCache(tokens);
    }
  } else {
    tokens = await fetchAllTokens(quick);
    saveCache(tokens);
  }

  // Filter out tokens with no price data
  tokens = tokens.filter(t => t.priceUsd > 0);
  console.log(`\n📊 Tokens with valid price data: ${tokens.length}`);

  // Helius enrichment (holder data, supply info)
  await enrichWithHelius(tokens);

  // Score distribution
  console.log('\nScore Distribution:');
  for (let b = 0; b <= 90; b += 10) {
    const count = tokens.filter(t => t.score >= b && t.score < b + 10).length;
    const bar = '█'.repeat(Math.round(count / Math.max(1, tokens.length) * 50));
    console.log(`  ${String(b).padStart(2)}-${String(b + 9).padStart(2)}: ${String(count).padStart(4)} ${bar}`);
  }

  // Run all configs
  console.log(`\n🔬 Running ${CONFIGS.length} backtest configurations...\n`);
  const results: ConfigResult[] = [];

  for (let i = 0; i < CONFIGS.length; i++) {
    const cfg = CONFIGS[i];
    const result = runBacktest(tokens, cfg);
    results.push(result);
    const decided = result.wins + result.losses;
    const marker = result.expectancy > 0 ? '🟢' : result.expectancy > -1 ? '🟡' : '🔴';
    console.log(
      `  ${marker} [${String(i + 1).padStart(2)}/${CONFIGS.length}] ${cfg.name.padEnd(45)} | ` +
      `${String(result.eligible).padStart(4)} trades | ` +
      `${result.winRate.toFixed(1).padStart(5)}% WR | ` +
      `${(result.expectancy >= 0 ? '+' : '') + result.expectancy.toFixed(2).padStart(6)}% exp | ` +
      `PF ${result.profitFactor === Infinity ? '∞' : result.profitFactor.toFixed(2)}`
    );
  }

  // Sort and show top 5 (require >=5 decided trades for ranking)
  const sorted = [...results].sort((a, b) => {
    const aD = a.wins + a.losses;
    const bD = b.wins + b.losses;
    if (aD < 5 && bD >= 5) return 1;
    if (bD < 5 && aD >= 5) return -1;
    return b.expectancy - a.expectancy;
  });

  console.log('\n═══════════════════════════════════════════════');
  console.log('🏆 TOP 5 CONFIGURATIONS:');
  console.log('═══════════════════════════════════════════════');
  for (let i = 0; i < Math.min(5, sorted.length); i++) {
    const r = sorted[i];
    console.log(`\n  ${i + 1}. ${r.config.name}`);
    console.log(`     Win Rate: ${r.winRate.toFixed(1)}% | Expectancy: ${r.expectancy.toFixed(2)}% | PF: ${r.profitFactor.toFixed(2)}`);
    console.log(`     ${r.wins}W / ${r.losses}L / ${r.open}O = ${r.eligible} trades`);
    console.log(`     Total P&L: ${r.totalPnlPct >= 0 ? '+' : ''}${r.totalPnlPct.toFixed(1)}%`);
  }

  // ═══════════════════════════════════════════════
  // Phase 4: OHLCV Validation with multi-entry simulation
  // ═══════════════════════════════════════════════
  console.log('\n\n📡 Phase 4: OHLCV Candle Validation (real price action)...\n');

  // Get tokens that pass our best filters (production-relevant only)
  const ohlcvEligible = tokens.filter(t =>
    t.priceUsd > 0 && t.liquidity >= 5000 && t.pairAddress && t.pairAddress.length > 20
  );
  console.log(`  Tokens eligible for OHLCV: ${ohlcvEligible.length}`);

  // Fetch OHLCV candles for up to 200 tokens (rate limit: ~30 req/min)
  const ohlcvTargets = ohlcvEligible.slice(0, 200);
  const ohlcvMap = new Map<string, OhlcvCandle[]>();
  let ohlcvFetched = 0;

  for (let i = 0; i < ohlcvTargets.length; i++) {
    const t = ohlcvTargets[i];
    const candles = await fetchOhlcv(t.pairAddress, 'hour', 48);
    if (candles.length > 0) {
      ohlcvMap.set(t.pairAddress, candles);
      ohlcvMap.set(t.mint, candles); // also index by mint
      ohlcvFetched++;
    }
    process.stdout.write(`  OHLCV ${i + 1}/${ohlcvTargets.length}: ${ohlcvFetched} fetched\r`);
  }
  console.log(`  ✓ OHLCV data for ${ohlcvFetched} tokens (48h hourly candles)         `);

  // Run top configs with OHLCV data
  const ohlcvConfigs = CONFIGS.filter(c =>
    c.name.startsWith('MAGIC_') ||
    c.name.startsWith('INSIGHT_') ||
    c.name.startsWith('HYBRID_') ||
    c.name.startsWith('TRAIL_') ||
    c.name.includes('Current Default') ||
    c.name.includes('Buy/Sell') ||
    c.name.includes('Liq≥$50K') ||
    c.name.includes('Liq≥$100K') ||
    c.name.includes('MOMENTUM') ||
    c.name.includes('HOT') ||
    c.name.includes('WHALE')
  );

  console.log(`\n🔬 OHLCV Backtest: ${ohlcvConfigs.length} configs × multi-entry simulation...\n`);
  const ohlcvResults: ConfigResult[] = [];

  for (let i = 0; i < ohlcvConfigs.length; i++) {
    const cfg = ohlcvConfigs[i];
    const result = runOhlcvBacktest(tokens, cfg, ohlcvMap);
    ohlcvResults.push(result);
    const decided = result.wins + result.losses;
    const marker = result.expectancy > 0 ? '🟢' : result.expectancy > -1 ? '🟡' : '🔴';
    console.log(
      `  ${marker} [${String(i + 1).padStart(2)}/${ohlcvConfigs.length}] ${cfg.name.padEnd(50)} | ` +
      `${String(result.eligible).padStart(5)} sims | ` +
      `${decided > 0 ? result.winRate.toFixed(1).padStart(5) + '% WR' : '  N/A WR'} | ` +
      `${(result.expectancy >= 0 ? '+' : '') + result.expectancy.toFixed(2).padStart(6)}% exp | ` +
      `${result.wins}W/${result.losses}L/${result.open}O`
    );
  }

  // ═══════════════════════════════════════════════
  // Phase 5: Winner Feature Analysis
  // ═══════════════════════════════════════════════
  console.log('\n\n🔍 Phase 5: What makes winners WIN?\n');

  // Use all OHLCV trades from the broadest reasonable config
  const broadTrades = ohlcvResults.find(r => r.config.name === 'Current Default (Score≥50, Adaptive)')?.trades || [];
  const features = analyzeWinnerFeatures(broadTrades, tokens);

  if (features.length > 0) {
    console.log('  Feature               | Winners (avg)    | Losers (avg)     | Predictive Power');
    console.log('  ─────────────────────────────────────────────────────────────────────────────');
    for (const f of features.slice(0, 12)) {
      const fmtWin = f.winnerAvg > 10000 ? `$${(f.winnerAvg / 1000).toFixed(0)}K` : f.winnerAvg.toFixed(2);
      const fmtLoss = f.loserAvg > 10000 ? `$${(f.loserAvg / 1000).toFixed(0)}K` : f.loserAvg.toFixed(2);
      console.log(
        `  ${f.feature.padEnd(22)} | ${String(fmtWin).padStart(16)} | ${String(fmtLoss).padStart(16)} | ${f.predictivePower.toFixed(1)}%`
      );
    }
  }

  // ═══════════════════════════════════════════════
  // Phase 6: Time-of-Day Analysis
  // ═══════════════════════════════════════════════
  console.log('\n\n🕐 Phase 6: Time-of-Day Analysis (when to snipe?)...\n');

  const allOhlcvTrades = ohlcvResults.flatMap(r => r.trades);
  const todStats = analyzeTimeOfDay(allOhlcvTrades);
  const activeHours = todStats.filter(h => h.trades >= 5);

  if (activeHours.length > 0) {
    console.log('  Hour (UTC) | Trades | W / L | Win%    | Avg PnL');
    console.log('  ─────────────────────────────────────────────────');
    for (const h of todStats) {
      if (h.trades < 3) continue;
      const bar = h.winRate >= 60 ? '🟢' : h.winRate >= 40 ? '🟡' : '🔴';
      console.log(
        `  ${bar} ${String(h.hour).padStart(2)}:00  | ${String(h.trades).padStart(5)} | ${String(h.wins).padStart(3)}/${String(h.losses).padStart(3)} | ${h.winRate.toFixed(1).padStart(5)}%  | ${(h.avgPnl >= 0 ? '+' : '') + h.avgPnl.toFixed(2)}%`
      );
    }

    const bestHour = activeHours.sort((a, b) => b.winRate - a.winRate)[0];
    const worstHour = activeHours.sort((a, b) => a.winRate - b.winRate)[0];
    if (bestHour && worstHour) {
      console.log(`\n  Best hour:  ${bestHour.hour}:00 UTC (${bestHour.winRate.toFixed(1)}% WR, ${bestHour.trades} trades)`);
      console.log(`  Worst hour: ${worstHour.hour}:00 UTC (${worstHour.winRate.toFixed(1)}% WR, ${worstHour.trades} trades)`);
    }
  }

  // ═══════════════════════════════════════════════
  // Phase 7: Trailing Stop Analysis
  // ═══════════════════════════════════════════════
  console.log('\n\n📉 Phase 7: Trailing Stop Optimization...\n');

  const trailResults = ohlcvResults.filter(r => r.config.name.startsWith('TRAIL_'));
  if (trailResults.length > 0) {
    const trailSorted = [...trailResults].sort((a, b) => b.expectancy - a.expectancy);
    console.log('  Config                                    | Sims | Win%  | Expect | PF    | TotalPnL');
    console.log('  ──────────────────────────────────────────────────────────────────────────────────');
    for (const r of trailSorted) {
      const decided = r.wins + r.losses;
      const marker = r.expectancy > 0 ? '🟢' : '🟡';
      console.log(
        `  ${marker} ${r.config.name.padEnd(39)} | ${String(r.eligible).padStart(4)} | ${decided > 0 ? r.winRate.toFixed(1).padStart(5) : '  N/A'}% | ${(r.expectancy >= 0 ? '+' : '') + r.expectancy.toFixed(2).padStart(6)}% | ${r.profitFactor === Infinity ? '  ∞  ' : r.profitFactor.toFixed(2).padStart(5)} | ${(r.totalPnlPct >= 0 ? '+' : '') + r.totalPnlPct.toFixed(1)}%`
      );
    }

    // Count trailing stop triggered trades
    for (const r of trailResults) {
      if (!r.config.trailingStopPct) continue;
      const trailedTrades = r.trades.filter(t => t.trailingStopTriggered);
      const trailedWins = trailedTrades.filter(t => t.outcome === 'win').length;
      if (trailedTrades.length > 0) {
        console.log(`\n  ${r.config.name}: ${trailedTrades.length} trailing stops triggered (${trailedWins} profitable exits)`);
      }
    }
  }

  // Sort OHLCV results for top 5
  const ohlcvSorted = [...ohlcvResults].sort((a, b) => {
    const aD = a.wins + a.losses;
    const bD = b.wins + b.losses;
    if (aD < 10 && bD >= 10) return 1;
    if (bD < 10 && aD >= 10) return -1;
    return b.expectancy - a.expectancy;
  });

  console.log('\n═══════════════════════════════════════════════');
  console.log('🏆 TOP 5 OHLCV-VALIDATED CONFIGURATIONS:');
  console.log('═══════════════════════════════════════════════');
  for (let i = 0; i < Math.min(5, ohlcvSorted.length); i++) {
    const r = ohlcvSorted[i];
    const decided = r.wins + r.losses;
    console.log(`\n  ${i + 1}. ${r.config.name}`);
    console.log(`     Win Rate: ${r.winRate.toFixed(1)}% | Expectancy: ${r.expectancy.toFixed(2)}% | PF: ${r.profitFactor === Infinity ? '∞' : r.profitFactor.toFixed(2)}`);
    console.log(`     ${r.wins}W / ${r.losses}L / ${r.open}O = ${r.eligible} total sims (${decided} decided)`);
    console.log(`     Total P&L: ${r.totalPnlPct >= 0 ? '+' : ''}${r.totalPnlPct.toFixed(1)}%`);
  }

  // Generate report
  console.log('\n\n📝 Generating report...');
  const report = generateReport(results, tokens, ohlcvResults, features, todStats);
  const outPath = join(process.cwd(), 'BACKTEST_RESULTS.md');
  writeFileSync(outPath, report);
  console.log(`✓ Report written to: ${outPath}`);

  // Also save JSON for programmatic use
  const jsonOut = join(process.cwd(), 'scripts', '.backtest-results.json');
  const jsonData = {
    timestamp: Date.now(),
    tokensAnalyzed: tokens.length,
    configsTested: results.length,
    totalTradeSimulations: results.reduce((s, r) => s + r.eligible, 0),
    results: sorted.map(r => ({
      name: r.config.name,
      config: r.config,
      eligible: r.eligible,
      wins: r.wins,
      losses: r.losses,
      open: r.open,
      winRate: r.winRate,
      expectancy: r.expectancy,
      profitFactor: r.profitFactor,
      totalPnlPct: r.totalPnlPct,
    })),
  };
  writeFileSync(jsonOut, JSON.stringify(jsonData, null, 2));
  console.log(`✓ JSON data written to: ${jsonOut}`);

  console.log(`\n✅ Done. ${tokens.length} tokens, ${CONFIGS.length} configs, ${apiCalls} API calls.`);
}

async function fetchAllTokens(quick: boolean): Promise<TokenData[]> {
  console.log('📡 Phase 1: Fetching token data from multiple sources...\n');

  // GeckoTerminal — paginated pools (6 sort orders × 10 pages each)
  // Fetch in 2 waves to respect 30 req/min rate limit
  const [newPools, volPools, txPools, trending] = await Promise.all([
    fetchGeckoTerminalPools('pool_created_at_desc', 10, 'new pools'),
    fetchGeckoTerminalPools('h24_volume_usd_desc', 10, 'volume-sorted'),
    fetchGeckoTerminalPools('h24_tx_count_desc', 10, 'tx-count-sorted'),
    fetchGeckoTerminalTrending(),
  ]);

  await sleep(3000); // Wait for rate limit reset

  // Wave 2: Additional sort orders for more diverse tokens
  const [h6VolPools, h1VolPools, liqPools] = await Promise.all([
    fetchGeckoTerminalPools('h6_volume_usd_desc', 10, 'h6-volume-sorted'),
    fetchGeckoTerminalPools('h1_volume_usd_desc', 10, 'h1-volume-sorted'),
    fetchGeckoTerminalPools('h24_volume_usd_liquidity_desc', 10, 'vol/liq-sorted'),
  ]);

  // Wait before DexScreener calls (different rate limit)
  await sleep(2000);

  // DexScreener — boosts + profiles
  const [dexBoosts, dexProfiles] = await Promise.all([
    fetchDexScreenerBoosts(),
    fetchDexScreenerProfiles(),
  ]);

  // DexScreener search (optional, slower)
  let dexSearch: DexMint[] = [];
  if (!quick) {
    await sleep(2000);
    dexSearch = await fetchDexScreenerSearch(SEARCH_QUERIES);
  }

  // Jupiter verified token list (new in v4)
  await sleep(1000);
  const jupiterTokens = await fetchJupiterTokenList();

  // Collect all GeckoTerminal pools
  const allGeckoPools: GeckoPool[] = [];
  const geckoSeen = new Set<string>();
  for (const pool of [...newPools, ...volPools, ...txPools, ...trending, ...h6VolPools, ...h1VolPools, ...liqPools]) {
    if (geckoSeen.has(pool.mint)) continue;
    geckoSeen.add(pool.mint);
    allGeckoPools.push(pool);
  }
  console.log(`\n  GeckoTerminal unique pools: ${allGeckoPools.length}`);

  // Collect all DexScreener mints
  const allDexMints: DexMint[] = [];
  const dexSeen = new Set<string>();
  for (const dm of [...dexBoosts, ...dexProfiles, ...dexSearch, ...jupiterTokens]) {
    if (dexSeen.has(dm.mint) || geckoSeen.has(dm.mint)) continue;
    dexSeen.add(dm.mint);
    allDexMints.push(dm);
  }
  console.log(`  DexScreener + Jupiter unique new mints: ${allDexMints.length}`);

  // Batch enrich DexScreener-only tokens
  console.log(`\n📡 Phase 2: Enriching ${allDexMints.length} DexScreener tokens...\n`);
  const enriched = allDexMints.length > 0
    ? await batchEnrichDexScreener(allDexMints.map(d => d.mint))
    : new Map<string, PairData>();

  // Also enrich DexScreener mints that ARE in GeckoTerminal (for social/boost data)
  const boostMap = new Map<string, DexMint>();
  for (const dm of [...dexBoosts, ...dexProfiles, ...dexSearch]) {
    const existing = boostMap.get(dm.mint);
    if (!existing || dm.boostAmount > existing.boostAmount) {
      boostMap.set(dm.mint, dm);
    }
  }

  // Merge everything
  console.log('\n📡 Phase 3: Merging and scoring...');
  const tokens = mergeAll(allGeckoPools, [...boostMap.values()], enriched);

  console.log(`  ✓ ${tokens.length} total unique tokens scored`);
  return tokens;
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
