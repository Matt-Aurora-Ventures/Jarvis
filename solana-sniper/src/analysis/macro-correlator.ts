import axios from 'axios';
import fs from 'fs';
import path from 'path';
import { createModuleLogger } from '../utils/logger.js';

const log = createModuleLogger('macro-correlator');

// ─── Cache ───────────────────────────────────────────────────
const CACHE_DIR = path.resolve(process.cwd(), 'data');
const MACRO_CACHE_FILE = path.join(CACHE_DIR, 'macro-snapshot.json');
const CACHE_TTL_MS = 3 * 60 * 1000; // 3 minutes

export interface MacroSnapshot {
  btc: { price: number; change24h: number; change7d: number };
  eth: { price: number; change24h: number };
  sol: { price: number; change24h: number };
  // DXY & Gold (may be null if API unavailable)
  dxy: { value: number; change24h: number } | null;
  gold: { price: number; change24h: number } | null;
  // Derived signals
  regime: 'risk_on' | 'risk_off' | 'neutral';
  btcTrend: 'pumping' | 'dumping' | 'flat';
  memeExposureMultiplier: number; // 0.3-1.5x -- how much to allocate to memes
  fetchedAt: number;
}

/**
 * Determine the current macro regime:
 * - risk_on: BTC rising + DXY falling (or just BTC strongly rising)
 * - risk_off: BTC dumping + DXY rising
 * - neutral: mixed signals
 */
function computeRegime(btcChange: number, dxyChange: number | null): MacroSnapshot['regime'] {
  const btcStrong = btcChange > 3;
  const btcWeak = btcChange < -3;
  const dxyUp = dxyChange != null && dxyChange > 0.3;
  const dxyDown = dxyChange != null && dxyChange < -0.3;

  if (btcStrong && (dxyDown || dxyChange == null)) return 'risk_on';
  if (btcWeak && (dxyUp || dxyChange == null)) return 'risk_off';
  if (btcStrong) return 'risk_on';
  if (btcWeak) return 'risk_off';
  return 'neutral';
}

function computeBtcTrend(change24h: number): MacroSnapshot['btcTrend'] {
  if (change24h > 2) return 'pumping';
  if (change24h < -2) return 'dumping';
  return 'flat';
}

/**
 * How much to allocate to memecoins given macro conditions:
 * - BTC dumping hard: reduce to 0.3x (capital preservation)
 * - BTC flat: normal 1.0x
 * - BTC pumping: increase to 1.3x (rising tide)
 * - Risk off + DXY surging: drop to 0.5x
 */
function computeMemeExposure(btcChange: number, regime: MacroSnapshot['regime']): number {
  if (regime === 'risk_off' && btcChange < -5) return 0.3;
  if (regime === 'risk_off') return 0.5;
  if (regime === 'risk_on' && btcChange > 5) return 1.3;
  if (regime === 'risk_on') return 1.1;
  return 1.0;
}

// ─── Data Fetchers ───────────────────────────────────────────

async function fetchCoinGecko(): Promise<{
  btc: { price: number; change24h: number; change7d: number };
  eth: { price: number; change24h: number };
  sol: { price: number; change24h: number };
}> {
  const url = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true&include_market_cap=true';

  const res = await axios.get(url, { timeout: 10000 });
  const d = res.data;

  return {
    btc: {
      price: d.bitcoin?.usd || 0,
      change24h: d.bitcoin?.usd_24h_change || 0,
      change7d: 0, // CoinGecko simple endpoint doesn't give 7d
    },
    eth: {
      price: d.ethereum?.usd || 0,
      change24h: d.ethereum?.usd_24h_change || 0,
    },
    sol: {
      price: d.solana?.usd || 0,
      change24h: d.solana?.usd_24h_change || 0,
    },
  };
}

async function fetchDxy(): Promise<{ value: number; change24h: number } | null> {
  // Try Twelve Data first (requires API key in env)
  const apiKey = process.env.TWELVE_DATA_API_KEY;
  if (apiKey) {
    try {
      const res = await axios.get(
        `https://api.twelvedata.com/time_series?symbol=DXY&interval=1day&outputsize=2&apikey=${apiKey}`,
        { timeout: 10000 }
      );
      const values = res.data?.values;
      if (values && values.length >= 2) {
        const current = parseFloat(values[0].close);
        const prev = parseFloat(values[1].close);
        return {
          value: current,
          change24h: ((current - prev) / prev) * 100,
        };
      }
    } catch { /* fall through */ }
  }

  // Fallback: synthetic DXY from forex pairs (no key needed)
  try {
    const res = await axios.get('https://api.exchangerate-api.com/v4/latest/USD', { timeout: 8000 });
    // Create a simplified DXY proxy from EUR/USD (EUR has ~58% weight in DXY)
    const eurRate = res.data?.rates?.EUR;
    if (eurRate) {
      // DXY is inversely correlated with EUR/USD
      // This is a rough approximation
      const syntheticDxy = 1 / eurRate * 100;
      return { value: syntheticDxy, change24h: 0 }; // Can't get change without history
    }
  } catch { /* ignore */ }

  return null;
}

async function fetchGold(): Promise<{ price: number; change24h: number } | null> {
  // Try gold-api.com (requires key)
  try {
    const res = await axios.get('https://www.goldapi.io/api/XAU/USD', {
      headers: { 'x-access-token': process.env.GOLD_API_KEY || '' },
      timeout: 8000,
    });
    if (res.data?.price) {
      return {
        price: res.data.price,
        change24h: res.data.ch || 0,
      };
    }
  } catch { /* fall through */ }

  // Fallback: use CoinGecko for gold (they have PAX Gold as proxy)
  try {
    const res = await axios.get(
      'https://api.coingecko.com/api/v3/simple/price?ids=pax-gold&vs_currencies=usd&include_24hr_change=true',
      { timeout: 8000 }
    );
    const d = res.data?.['pax-gold'];
    if (d?.usd) {
      return {
        price: d.usd,
        change24h: d.usd_24h_change || 0,
      };
    }
  } catch { /* ignore */ }

  return null;
}

// ─── Main API ────────────────────────────────────────────────

function readMacroCache(): MacroSnapshot | null {
  try {
    if (!fs.existsSync(MACRO_CACHE_FILE)) return null;
    const data: MacroSnapshot = JSON.parse(fs.readFileSync(MACRO_CACHE_FILE, 'utf8'));
    if (Date.now() - data.fetchedAt < CACHE_TTL_MS) return data;
  } catch { /* ignore */ }
  return null;
}

function writeMacroCache(snapshot: MacroSnapshot): void {
  try {
    if (!fs.existsSync(CACHE_DIR)) fs.mkdirSync(CACHE_DIR, { recursive: true });
    fs.writeFileSync(MACRO_CACHE_FILE, JSON.stringify(snapshot, null, 2));
  } catch { /* ignore */ }
}

/**
 * Fetch the current macro environment snapshot.
 * Uses cache (3 min TTL) to avoid rate limiting.
 */
export async function getMacroSnapshot(): Promise<MacroSnapshot> {
  const cached = readMacroCache();
  if (cached) return cached;

  // Fetch all data sources in parallel
  const [crypto, dxy, gold] = await Promise.all([
    fetchCoinGecko().catch(() => ({
      btc: { price: 0, change24h: 0, change7d: 0 },
      eth: { price: 0, change24h: 0 },
      sol: { price: 0, change24h: 0 },
    })),
    fetchDxy().catch(() => null),
    fetchGold().catch(() => null),
  ]);

  const regime = computeRegime(crypto.btc.change24h, dxy?.change24h ?? null);
  const btcTrend = computeBtcTrend(crypto.btc.change24h);
  const memeExposureMultiplier = computeMemeExposure(crypto.btc.change24h, regime);

  const snapshot: MacroSnapshot = {
    ...crypto,
    dxy,
    gold,
    regime,
    btcTrend,
    memeExposureMultiplier,
    fetchedAt: Date.now(),
  };

  writeMacroCache(snapshot);

  log.info('Macro snapshot fetched', {
    btc: `$${crypto.btc.price.toFixed(0)} (${crypto.btc.change24h > 0 ? '+' : ''}${crypto.btc.change24h.toFixed(1)}%)`,
    regime,
    btcTrend,
    memeMultiplier: memeExposureMultiplier.toFixed(2),
    dxy: dxy ? `${dxy.value.toFixed(1)} (${dxy.change24h > 0 ? '+' : ''}${dxy.change24h.toFixed(2)}%)` : 'N/A',
    gold: gold ? `$${gold.price.toFixed(0)}` : 'N/A',
  });

  return snapshot;
}

/**
 * Compute the correlation-adjusted score modifier for a token.
 * Returns -0.3 to +0.3 adjustment to apply to the token's safety/buy score.
 *
 * Logic:
 * - BTC dumping hard -> penalize all tokens (-0.15 to -0.30)
 * - BTC pumping -> bonus for momentum tokens (+0.05 to +0.15)
 * - DXY surging -> penalize risk assets (-0.10)
 * - Gold surging -> mixed signal for crypto (slight penalty -0.05)
 * - Risk off regime -> penalize fresh/meme tokens more, veterans less
 */
export function getCorrelationAdjustment(
  macro: MacroSnapshot,
  tokenAge: 'fresh' | 'young' | 'established' | 'veteran',
  isXStock: boolean,
): number {
  let adj = 0;

  // BTC trend impact (strongest factor)
  if (macro.btcTrend === 'dumping') {
    adj -= 0.15;
    // Fresh tokens suffer more in dumps
    if (tokenAge === 'fresh') adj -= 0.10;
    else if (tokenAge === 'young') adj -= 0.05;
    // xStocks are somewhat insulated from crypto-specific dumps
    if (isXStock) adj += 0.08;
  } else if (macro.btcTrend === 'pumping') {
    adj += 0.08;
    // Fresh tokens benefit most from BTC pumps (rising tide)
    if (tokenAge === 'fresh') adj += 0.05;
  }

  // DXY impact
  if (macro.dxy) {
    if (macro.dxy.change24h > 0.5) adj -= 0.05; // Strong dollar = crypto bearish
    if (macro.dxy.change24h < -0.5) adj += 0.03; // Weak dollar = crypto bullish
  }

  // Gold impact (gold up = fear indicator, but gold and crypto can move together)
  if (macro.gold) {
    if (macro.gold.change24h > 2) adj -= 0.03; // Gold surge = flight to safety
  }

  // Regime override
  if (macro.regime === 'risk_off') {
    adj -= 0.05;
    if (isXStock) adj += 0.05; // xStocks less affected
  }

  return Math.max(-0.30, Math.min(0.30, adj));
}

/**
 * Estimate BTC correlation coefficient for a token based on
 * whether its price moved in the same direction as BTC.
 * Returns -1 to 1 (positive = moves with BTC, negative = inverse).
 *
 * This is a rough estimation based on 24h price changes.
 * A proper correlation would need OHLCV time series.
 */
export function estimateBtcCorrelation(
  tokenChange24h: number,
  btcChange24h: number,
): number {
  if (Math.abs(btcChange24h) < 0.5) return 0; // BTC flat = no signal

  // Simple directional correlation
  const sameDirection = (tokenChange24h > 0 && btcChange24h > 0) || (tokenChange24h < 0 && btcChange24h < 0);
  const magnitude = Math.min(1, Math.abs(tokenChange24h) / Math.max(1, Math.abs(btcChange24h)));

  return sameDirection ? magnitude * 0.8 : -magnitude * 0.8;
}
