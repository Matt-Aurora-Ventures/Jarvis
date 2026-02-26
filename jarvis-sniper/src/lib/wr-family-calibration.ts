export type WrCalibrationFamily =
  | 'memecoin'
  | 'bags'
  | 'bluechip'
  | 'xstock'
  | 'prestock'
  | 'index';

export interface CalibrationRow {
  strategyId: string;
  trades: number;
  winRatePct: number;
}

export interface WrFamilyRecommendation {
  primaryPct: number;
  fallbackPct: number;
  minTrades: number;
  weightedWinRatePct: number;
  sampleTrades: number;
  strategyCount: number;
}

export interface WrFamilyCalibrationOptions {
  minFamilyTrades?: number;
  primaryMarginPct?: number;
  fallbackGapPct?: number;
}

function toFinite(value: unknown, fallback = 0): number {
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function round1(value: number): number {
  return Math.round(value * 10) / 10;
}

export function strategyFamilyFromId(strategyId: string): WrCalibrationFamily {
  const sid = String(strategyId || '').trim().toLowerCase();
  if (sid.startsWith('bags_')) return 'bags';
  if (sid.startsWith('bluechip_')) return 'bluechip';
  if (sid.startsWith('xstock_')) return 'xstock';
  if (sid.startsWith('prestock_')) return 'prestock';
  if (sid.startsWith('index_')) return 'index';
  return 'memecoin';
}

export function calibrateWrFamilyThresholds(
  rows: CalibrationRow[],
  options: WrFamilyCalibrationOptions = {},
): Partial<Record<WrCalibrationFamily, WrFamilyRecommendation>> {
  const minFamilyTrades = Math.max(1, Math.floor(toFinite(options.minFamilyTrades, 400)));
  const primaryMarginPct = clamp(toFinite(options.primaryMarginPct, 4), 0, 20);
  const fallbackGapPct = clamp(toFinite(options.fallbackGapPct, 12), 1, 30);
  const byFamily = new Map<WrCalibrationFamily, CalibrationRow[]>();

  for (const rawRow of rows || []) {
    const trades = Math.max(0, Math.floor(toFinite(rawRow?.trades, 0)));
    const winRatePct = clamp(toFinite(rawRow?.winRatePct, Number.NaN), 0, 100);
    if (!Number.isFinite(winRatePct) || trades <= 0) continue;
    const row: CalibrationRow = {
      strategyId: String(rawRow?.strategyId || '').trim(),
      trades,
      winRatePct,
    };
    const family = strategyFamilyFromId(row.strategyId);
    const existing = byFamily.get(family);
    if (existing) existing.push(row);
    else byFamily.set(family, [row]);
  }

  const out: Partial<Record<WrCalibrationFamily, WrFamilyRecommendation>> = {};
  for (const [family, familyRows] of byFamily.entries()) {
    if (familyRows.length === 0) continue;
    const sampleTrades = familyRows.reduce((sum, row) => sum + row.trades, 0);
    if (sampleTrades < minFamilyTrades) continue;

    const weightedWinRatePct = familyRows.reduce(
      (sum, row) => sum + (row.winRatePct * row.trades),
      0,
    ) / Math.max(1, sampleTrades);
    const primaryPct = round1(clamp(weightedWinRatePct - primaryMarginPct, 35, 70));
    const fallbackPct = round1(clamp(primaryPct - fallbackGapPct, 30, primaryPct));
    const minTrades = Math.floor(
      clamp(sampleTrades / Math.max(8, familyRows.length * 3), 40, 1000),
    );

    out[family] = {
      primaryPct,
      fallbackPct,
      minTrades,
      weightedWinRatePct: round1(weightedWinRatePct),
      sampleTrades,
      strategyCount: familyRows.length,
    };
  }

  return out;
}
