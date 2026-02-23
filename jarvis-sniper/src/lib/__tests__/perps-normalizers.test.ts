import { describe, expect, it } from 'vitest';
import { normalizePerpsCandles, normalizePerpsPriceSnapshot } from '@/lib/perps/normalizers';

describe('perps normalizers', () => {
  it('normalizes market-object prices into sol/btc/eth snapshot', () => {
    const snapshot = normalizePerpsPriceSnapshot({
      'SOL-USD': { price: 101.25 },
      'BTC-USD': { price: 95000.5 },
      'ETH-USD': { price: 3100.1 },
    });

    expect(snapshot.sol).toBeCloseTo(101.25);
    expect(snapshot.btc).toBeCloseTo(95000.5);
    expect(snapshot.eth).toBeCloseTo(3100.1);
  });

  it('normalizes candle payloads and drops invalid rows', () => {
    const candles = normalizePerpsCandles({
      candles: [
        { time: 1, open: 1, high: 2, low: 0.5, close: 1.5 },
        { time: 0, open: 1, high: 2, low: 0.5, close: 1.5 },
      ],
    });

    expect(candles).toHaveLength(1);
    expect(candles[0].time).toBe(1);
  });
});
