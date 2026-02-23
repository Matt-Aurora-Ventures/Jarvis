import axios from 'axios';
import fs from 'fs';
import path from 'path';
import { createModuleLogger } from '../utils/logger.js';

const log = createModuleLogger('hyperliquid-data');
const API_URL = 'https://api.hyperliquid.xyz/info';
const CACHE_DIR = path.resolve(process.cwd(), 'data', 'hyperliquid');

export interface HLCandle {
  timestamp: number; // epoch ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface HLCorrelationData {
  sol: HLCandle[];
  btc: HLCandle[];
  eth: HLCandle[];
  // Derived correlations
  solBtcCorrelation: number;  // Pearson correlation coefficient
  solEthCorrelation: number;
  btcVolatility: number;      // 24h realized vol
  solVolatility: number;
  fetchedAt: number;
}

async function fetchCandles(
  coin: string,
  interval: string,
  startTime: number,
  endTime: number,
): Promise<HLCandle[]> {
  try {
    const res = await axios.post(API_URL, {
      type: 'candleSnapshot',
      req: { coin, interval, startTime, endTime },
    }, { timeout: 15000 });

    const raw = res.data;
    if (!Array.isArray(raw)) return [];

    return raw.map((c: any) => ({
      timestamp: c.t || c[0],
      open: parseFloat(c.o || c[1] || '0'),
      high: parseFloat(c.h || c[2] || '0'),
      low: parseFloat(c.l || c[3] || '0'),
      close: parseFloat(c.c || c[4] || '0'),
      volume: parseFloat(c.v || c[5] || '0'),
    })).filter((c: HLCandle) => c.close > 0);
  } catch (err) {
    log.warn(`Failed to fetch ${coin} candles`, { error: (err as Error).message });
    return [];
  }
}

/**
 * Compute Pearson correlation coefficient between two price series.
 * Returns -1 to 1.
 */
function pearsonCorrelation(x: number[], y: number[]): number {
  const n = Math.min(x.length, y.length);
  if (n < 5) return 0;

  const meanX = x.slice(0, n).reduce((a, b) => a + b, 0) / n;
  const meanY = y.slice(0, n).reduce((a, b) => a + b, 0) / n;

  let num = 0, denomX = 0, denomY = 0;
  for (let i = 0; i < n; i++) {
    const dx = x[i] - meanX;
    const dy = y[i] - meanY;
    num += dx * dy;
    denomX += dx * dx;
    denomY += dy * dy;
  }

  const denom = Math.sqrt(denomX * denomY);
  return denom > 0 ? num / denom : 0;
}

/**
 * Compute returns (% change) from candle closes.
 */
function computeReturns(candles: HLCandle[]): number[] {
  const returns: number[] = [];
  for (let i = 1; i < candles.length; i++) {
    const prev = candles[i - 1].close;
    if (prev > 0) {
      returns.push((candles[i].close - prev) / prev * 100);
    }
  }
  return returns;
}

/**
 * Compute realized volatility (annualized standard deviation of hourly returns).
 */
function computeVolatility(candles: HLCandle[]): number {
  const returns = computeReturns(candles);
  if (returns.length < 2) return 0;

  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((s, r) => s + Math.pow(r - mean, 2), 0) / (returns.length - 1);
  const hourlyVol = Math.sqrt(variance);

  // Annualize: hourly vol * sqrt(8760 hours/year)
  return hourlyVol * Math.sqrt(8760);
}

function readCorrelationCache(): HLCorrelationData | null {
  try {
    const cachePath = path.join(CACHE_DIR, 'correlation-cache.json');
    if (!fs.existsSync(cachePath)) return null;
    const data = JSON.parse(fs.readFileSync(cachePath, 'utf8'));
    // Cache for 1 hour
    if (Date.now() - data.fetchedAt < 3600000 && data.sol?.length > 0) return data;
  } catch { /* ignore */ }
  return null;
}

function writeCorrelationCache(data: HLCorrelationData): void {
  try {
    if (!fs.existsSync(CACHE_DIR)) fs.mkdirSync(CACHE_DIR, { recursive: true });
    fs.writeFileSync(
      path.join(CACHE_DIR, 'correlation-cache.json'),
      JSON.stringify(data, null, 2),
    );
  } catch { /* ignore */ }
}

/**
 * Fetch 2 weeks of hourly candle data from Hyperliquid for SOL, BTC, ETH.
 * Compute correlations between SOL and BTC/ETH.
 * Results are cached for 1 hour.
 */
export async function getHyperliquidCorrelations(): Promise<HLCorrelationData> {
  const cached = readCorrelationCache();
  if (cached) {
    log.info('Using cached Hyperliquid correlations', {
      solBtcCorr: cached.solBtcCorrelation.toFixed(3),
      solEthCorr: cached.solEthCorrelation.toFixed(3),
    });
    return cached;
  }

  const endTime = Date.now();
  const startTime = endTime - 14 * 24 * 3600 * 1000; // 2 weeks

  log.info('Fetching Hyperliquid historical data...', {
    startTime: new Date(startTime).toISOString(),
    endTime: new Date(endTime).toISOString(),
  });

  // Fetch all three in parallel
  const [sol, btc, eth] = await Promise.all([
    fetchCandles('SOL', '1h', startTime, endTime),
    fetchCandles('BTC', '1h', startTime, endTime),
    fetchCandles('ETH', '1h', startTime, endTime),
  ]);

  log.info('Hyperliquid candles fetched', {
    solCandles: sol.length,
    btcCandles: btc.length,
    ethCandles: eth.length,
  });

  // Compute returns for correlation
  const solReturns = computeReturns(sol);
  const btcReturns = computeReturns(btc);
  const ethReturns = computeReturns(eth);

  const solBtcCorrelation = pearsonCorrelation(solReturns, btcReturns);
  const solEthCorrelation = pearsonCorrelation(solReturns, ethReturns);
  const btcVolatility = computeVolatility(btc);
  const solVolatility = computeVolatility(sol);

  const result: HLCorrelationData = {
    sol, btc, eth,
    solBtcCorrelation,
    solEthCorrelation,
    btcVolatility,
    solVolatility,
    fetchedAt: Date.now(),
  };

  writeCorrelationCache(result);

  log.info('Hyperliquid correlations computed', {
    solBtcCorr: solBtcCorrelation.toFixed(3),
    solEthCorr: solEthCorrelation.toFixed(3),
    btcVol: btcVolatility.toFixed(1) + '%',
    solVol: solVolatility.toFixed(1) + '%',
    dataPoints: solReturns.length,
  });

  return result;
}

/**
 * For the backtester: fetch longer periods by chaining 2-week chunks.
 * Max 3 months (6 chunks x 2 weeks).
 */
export async function getExtendedHistory(
  months: number = 3,
): Promise<{ sol: HLCandle[]; btc: HLCandle[]; eth: HLCandle[] }> {
  const endTime = Date.now();
  const startTime = endTime - months * 30 * 24 * 3600 * 1000;
  const chunkMs = 14 * 24 * 3600 * 1000; // 2 weeks

  const allSol: HLCandle[] = [];
  const allBtc: HLCandle[] = [];
  const allEth: HLCandle[] = [];

  let cursor = startTime;
  let chunk = 0;

  while (cursor < endTime) {
    const chunkEnd = Math.min(cursor + chunkMs, endTime);
    chunk++;
    log.info(`Fetching chunk ${chunk}...`, {
      from: new Date(cursor).toISOString().slice(0, 10),
      to: new Date(chunkEnd).toISOString().slice(0, 10),
    });

    const [sol, btc, eth] = await Promise.all([
      fetchCandles('SOL', '1h', cursor, chunkEnd),
      fetchCandles('BTC', '1h', cursor, chunkEnd),
      fetchCandles('ETH', '1h', cursor, chunkEnd),
    ]);

    allSol.push(...sol);
    allBtc.push(...btc);
    allEth.push(...eth);

    cursor = chunkEnd;

    // Small delay between chunks to be nice to the API
    if (cursor < endTime) await new Promise(r => setTimeout(r, 500));
  }

  log.info('Extended history fetched', {
    months,
    solCandles: allSol.length,
    btcCandles: allBtc.length,
    ethCandles: allEth.length,
  });

  // Save to disk for reuse
  try {
    const histPath = path.join(CACHE_DIR, `extended-${months}mo.json`);
    fs.writeFileSync(histPath, JSON.stringify({
      sol: allSol, btc: allBtc, eth: allEth,
      fetchedAt: Date.now(),
    }));
    log.info('Extended history saved', { path: histPath });
  } catch { /* ignore */ }

  return { sol: allSol, btc: allBtc, eth: allEth };
}
