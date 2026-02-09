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
    // Fallback config if file not found
    return NextResponse.json({
      winRate: 0.83,
      pnl: 59.65,
      config: {
        stopLossPct: 8,
        takeProfitPct: 35,
        trailingStopPct: 4,
        minLiquidityUsd: 7829,
        minBuySellRatio: 0.94,
        safetyScoreMin: 0.2,
        maxConcurrentPositions: 10,
        maxPositionUsd: 3.2,
        partialExitPct: 59,
        source: 'pumpswap',
      },
      validationWinRate: 0.786,
      blendedWinRate: 0.814,
    });
  }
}
