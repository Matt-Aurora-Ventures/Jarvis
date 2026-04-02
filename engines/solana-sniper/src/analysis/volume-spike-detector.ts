/**
 * Volume Spike Detector
 *
 * Detects abnormal volume surges that indicate early buying pressure.
 * Compares current volume against rolling baselines to generate spike signals.
 *
 * Spike Types:
 * - MICRO: 2-3x baseline (early interest)
 * - MEDIUM: 3-5x baseline (growing momentum)
 * - MAJOR: 5-10x baseline (breakout potential)
 * - EXTREME: 10x+ baseline (possible viral event)
 */
import axios from 'axios';
import { createModuleLogger } from '../utils/logger.js';

const log = createModuleLogger('volume-spike');

export type SpikeSeverity = 'MICRO' | 'MEDIUM' | 'MAJOR' | 'EXTREME';

export interface VolumeSpikeSignal {
  mint: string;
  symbol: string;
  severity: SpikeSeverity;
  currentVolume5m: number;
  baselineVolume5m: number;
  spikeMultiple: number;
  buyPressure: number; // ratio of buys to total txns (0-1)
  uniqueBuyers: number;
  priceChange5m: number;
  signalScore: number; // 0-1, higher = stronger signal
  detectedAt: number;
}

// ─── Rolling baselines per token ──────────────────────────
const volumeBaselines: Map<string, {
  samples: number[];
  lastUpdated: number;
}> = new Map();

function getBaseline(mint: string): number {
  const entry = volumeBaselines.get(mint);
  if (!entry || entry.samples.length === 0) return 0;
  return entry.samples.reduce((a, b) => a + b, 0) / entry.samples.length;
}

function updateBaseline(mint: string, volume: number): void {
  const entry = volumeBaselines.get(mint) || { samples: [], lastUpdated: 0 };
  entry.samples.push(volume);
  // Keep last 12 samples (1 hour of 5-min windows)
  if (entry.samples.length > 12) entry.samples.shift();
  entry.lastUpdated = Date.now();
  volumeBaselines.set(mint, entry);
}

// ─── Detect volume spike for a token ──────────────────────
export async function detectVolumeSpike(mint: string): Promise<VolumeSpikeSignal | null> {
  try {
    // Fetch from DexScreener for current trading data
    const resp = await axios.get(
      `https://api.dexscreener.com/latest/dex/tokens/${mint}`,
      { timeout: 8000 },
    );

    const pairs = resp.data?.pairs;
    if (!pairs || pairs.length === 0) return null;

    const pair = pairs[0];
    const volume5m = pair.volume?.m5 ?? 0;
    const volumeH1 = pair.volume?.h1 ?? 0;
    const buys5m = pair.txns?.m5?.buys ?? 0;
    const sells5m = pair.txns?.m5?.sells ?? 0;
    const priceChange5m = pair.priceChange?.m5 ?? 0;

    // Update rolling baseline
    updateBaseline(mint, volume5m);
    const baseline = getBaseline(mint);

    // Need at least some baseline data
    if (baseline <= 0 && volumeH1 <= 0) return null;

    // Use hourly volume divided into 12 windows as fallback baseline
    const effectiveBaseline = baseline > 0 ? baseline : (volumeH1 / 12);
    if (effectiveBaseline <= 0) return null;

    const spikeMultiple = volume5m / effectiveBaseline;

    // Classify severity
    let severity: SpikeSeverity;
    if (spikeMultiple >= 10) severity = 'EXTREME';
    else if (spikeMultiple >= 5) severity = 'MAJOR';
    else if (spikeMultiple >= 3) severity = 'MEDIUM';
    else if (spikeMultiple >= 2) severity = 'MICRO';
    else return null; // No spike detected

    const totalTxns = buys5m + sells5m;
    const buyPressure = totalTxns > 0 ? buys5m / totalTxns : 0.5;

    // Signal score: combines spike severity, buy pressure, and price confirmation
    const severityScore = Math.min(1, spikeMultiple / 15);
    const buyPressureScore = buyPressure;
    const priceConfirmation = priceChange5m > 0 ? Math.min(1, priceChange5m / 20) : 0;

    const signalScore = severityScore * 0.4 + buyPressureScore * 0.35 + priceConfirmation * 0.25;

    const signal: VolumeSpikeSignal = {
      mint,
      symbol: pair.baseToken?.symbol ?? mint.slice(0, 6),
      severity,
      currentVolume5m: volume5m,
      baselineVolume5m: effectiveBaseline,
      spikeMultiple,
      buyPressure,
      uniqueBuyers: buys5m, // approximation
      priceChange5m,
      signalScore,
      detectedAt: Date.now(),
    };

    log.info('Volume spike detected!', {
      mint: mint.slice(0, 8),
      severity,
      multiple: spikeMultiple.toFixed(1) + 'x',
      buyPressure: (buyPressure * 100).toFixed(0) + '%',
      priceChange: priceChange5m.toFixed(1) + '%',
      score: signalScore.toFixed(2),
    });

    return signal;
  } catch (err) {
    log.debug('Volume spike detection failed', { mint: mint.slice(0, 8), error: (err as Error).message });
    return null;
  }
}

// ─── Batch scan for volume spikes ─────────────────────────
export async function scanForVolumeSpikes(
  mints: string[],
  concurrency = 3,
): Promise<VolumeSpikeSignal[]> {
  const spikes: VolumeSpikeSignal[] = [];

  for (let i = 0; i < mints.length; i += concurrency) {
    const batch = mints.slice(i, i + concurrency);
    const results = await Promise.allSettled(
      batch.map(mint => detectVolumeSpike(mint)),
    );

    for (const result of results) {
      if (result.status === 'fulfilled' && result.value) {
        spikes.push(result.value);
      }
    }

    // Rate limit between batches
    if (i + concurrency < mints.length) {
      await new Promise(r => setTimeout(r, 500));
    }
  }

  // Sort by signal score (strongest first)
  return spikes.sort((a, b) => b.signalScore - a.signalScore);
}

// ─── Score for integration with backtest ──────────────────
export function scoreVolumeSpike(spike: VolumeSpikeSignal | null): number {
  if (!spike) return 0.5; // neutral when no data
  return 0.5 + spike.signalScore * 0.5; // 0.5 to 1.0 range
}

// ─── Get baseline stats ──────────────────────────────────
export function getBaselineStats(): { tracked: number; withBaseline: number } {
  const tracked = volumeBaselines.size;
  const withBaseline = [...volumeBaselines.values()].filter(b => b.samples.length >= 3).length;
  return { tracked, withBaseline };
}
