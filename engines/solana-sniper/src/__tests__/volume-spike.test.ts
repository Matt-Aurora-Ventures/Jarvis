import { describe, it, expect } from 'vitest';
import { scoreVolumeSpike, type VolumeSpikeSignal } from '../analysis/volume-spike-detector.js';

describe('Volume Spike Detector', () => {
  it('should return neutral score for null spike', () => {
    const score = scoreVolumeSpike(null);
    expect(score).toBe(0.5);
  });

  it('should return higher score for strong spike', () => {
    const spike: VolumeSpikeSignal = {
      mint: 'test',
      symbol: 'TEST',
      severity: 'MAJOR',
      currentVolume5m: 50000,
      baselineVolume5m: 5000,
      spikeMultiple: 10,
      buyPressure: 0.8,
      uniqueBuyers: 50,
      priceChange5m: 15,
      signalScore: 0.85,
      detectedAt: Date.now(),
    };
    const score = scoreVolumeSpike(spike);
    expect(score).toBeGreaterThan(0.8);
    expect(score).toBeLessThanOrEqual(1);
  });

  it('should return moderate score for micro spike', () => {
    const spike: VolumeSpikeSignal = {
      mint: 'test',
      symbol: 'TEST',
      severity: 'MICRO',
      currentVolume5m: 10000,
      baselineVolume5m: 5000,
      spikeMultiple: 2,
      buyPressure: 0.6,
      uniqueBuyers: 10,
      priceChange5m: 3,
      signalScore: 0.3,
      detectedAt: Date.now(),
    };
    const score = scoreVolumeSpike(spike);
    expect(score).toBeGreaterThan(0.5);
    expect(score).toBeLessThan(0.8);
  });

  it('should classify spike severities correctly', () => {
    const makeSpike = (multiple: number, score: number): VolumeSpikeSignal => ({
      mint: 'test', symbol: 'TEST',
      severity: multiple >= 10 ? 'EXTREME' : multiple >= 5 ? 'MAJOR' : multiple >= 3 ? 'MEDIUM' : 'MICRO',
      currentVolume5m: 10000, baselineVolume5m: 10000 / multiple,
      spikeMultiple: multiple, buyPressure: 0.7, uniqueBuyers: 20,
      priceChange5m: 5, signalScore: score, detectedAt: Date.now(),
    });

    const extreme = scoreVolumeSpike(makeSpike(15, 0.95));
    const major = scoreVolumeSpike(makeSpike(7, 0.7));
    const micro = scoreVolumeSpike(makeSpike(2, 0.3));

    expect(extreme).toBeGreaterThan(major);
    expect(major).toBeGreaterThan(micro);
  });

  it('should score within valid range', () => {
    const spike: VolumeSpikeSignal = {
      mint: 'test', symbol: 'TEST', severity: 'EXTREME',
      currentVolume5m: 100000, baselineVolume5m: 1000,
      spikeMultiple: 100, buyPressure: 1.0, uniqueBuyers: 200,
      priceChange5m: 50, signalScore: 1.0, detectedAt: Date.now(),
    };
    const score = scoreVolumeSpike(spike);
    expect(score).toBeGreaterThanOrEqual(0.5);
    expect(score).toBeLessThanOrEqual(1);
  });
});
