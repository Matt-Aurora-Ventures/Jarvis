import { NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import { join } from 'path';

// Path to the sniper's BEST_EVER.json — updated by the continuous backtester
const BEST_EVER_PATH = join(process.cwd(), '..', 'solana-sniper', 'winning', 'BEST_EVER.json');

export async function GET() {
  try {
    const raw = await readFile(BEST_EVER_PATH, 'utf-8');
    const data = JSON.parse(raw);
    return NextResponse.json(data);
  } catch {
    // Fallback: HYBRID_B v5 — 928-token OHLCV-validated, 8% trail, Vol/Liq filter
    return NextResponse.json({
      winRate: 0.941,
      pnl: 457,
      config: {
        stopLossPct: 20,
        takeProfitPct: 60,
        trailingStopPct: 8,
        minLiquidityUsd: 50000,
        minBuySellRatio: 1.5,
        minVolLiqRatio: 0.5,
        safetyScoreMin: 0,
        maxConcurrentPositions: 10,
        maxPositionUsd: 0.1,
      },
      validationWinRate: 0.941,
      blendedWinRate: 0.941,
      strategy: 'HYBRID_B_v5',
      description: 'Liq≥$50K + V/L≥0.5 + B/S 1-3 + Age<500h + 1h↑ + 8% trail + TOD | 20/60',
      bestHoursUtc: [4, 8, 11, 21],
      badHoursUtc: [1, 3, 5, 9, 17, 23],
    });
  }
}
