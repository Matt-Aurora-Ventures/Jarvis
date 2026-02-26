import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { join, resolve } from 'path';
import {
  calibrateWrFamilyThresholds,
  strategyFamilyFromId,
  type CalibrationRow,
  type WrCalibrationFamily,
} from '@/lib/wr-family-calibration';

type SourceRow = {
  algo_id?: unknown;
  total_trades?: unknown;
  win_rate?: unknown;
};

const DEFAULT_SOURCE = 'backtest-data/results/master_comparison.json';
const DEFAULT_OUTPUT_DIR = 'artifacts/ops/wr-family-calibration';

function toFinite(value: unknown, fallback = 0): number {
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function loadCalibrationRows(filePath: string): CalibrationRow[] {
  if (!existsSync(filePath)) {
    throw new Error(`Calibration source not found: ${filePath}`);
  }
  const raw = JSON.parse(readFileSync(filePath, 'utf8')) as unknown;
  if (!Array.isArray(raw)) {
    throw new Error(`Calibration source must be a JSON array: ${filePath}`);
  }

  const out: CalibrationRow[] = [];
  for (const row of raw as SourceRow[]) {
    const strategyId = String(row?.algo_id || '').trim();
    if (!strategyId) continue;
    const trades = Math.max(0, Math.floor(toFinite(row?.total_trades, 0)));
    const winRatePct = toFinite(row?.win_rate, Number.NaN);
    if (!Number.isFinite(winRatePct) || trades <= 0) continue;
    out.push({ strategyId, trades, winRatePct });
  }

  return out;
}

function summarizeTradesByFamily(rows: CalibrationRow[]): Record<WrCalibrationFamily, number> {
  const summary: Record<WrCalibrationFamily, number> = {
    memecoin: 0,
    bags: 0,
    bluechip: 0,
    xstock: 0,
    prestock: 0,
    index: 0,
  };

  for (const row of rows) {
    const family = strategyFamilyFromId(row.strategyId);
    summary[family] += row.trades;
  }
  return summary;
}

function toMarkdown(args: {
  sourcePath: string;
  minFamilyTrades: number;
  generatedAtIso: string;
  recommendations: ReturnType<typeof calibrateWrFamilyThresholds>;
  tradeSummary: Record<WrCalibrationFamily, number>;
}): string {
  const lines: string[] = [];
  lines.push('# WR Family Calibration (Read-Only)');
  lines.push('');
  lines.push(`- Generated: ${args.generatedAtIso}`);
  lines.push(`- Source: \`${args.sourcePath}\``);
  lines.push(`- Minimum family trades: ${args.minFamilyTrades}`);
  lines.push('- Auto-apply: disabled (advisory only)');
  lines.push('');
  lines.push('## Recommendations');
  lines.push('');
  lines.push('| Family | Primary | Fallback | Min Trades | Weighted WR | Sample Trades | Strategies |');
  lines.push('|---|---:|---:|---:|---:|---:|---:|');

  const order: WrCalibrationFamily[] = ['memecoin', 'bags', 'bluechip', 'xstock', 'prestock', 'index'];
  for (const family of order) {
    const rec = args.recommendations[family];
    if (!rec) {
      lines.push(`| ${family} | - | - | - | - | ${args.tradeSummary[family]} | - |`);
      continue;
    }
    lines.push(
      `| ${family} | ${rec.primaryPct.toFixed(1)} | ${rec.fallbackPct.toFixed(1)} | ${rec.minTrades} | ${rec.weightedWinRatePct.toFixed(1)} | ${rec.sampleTrades} | ${rec.strategyCount} |`,
    );
  }

  return lines.join('\n');
}

async function main(): Promise<void> {
  const sourcePath = resolve(
    process.cwd(),
    String(process.env.WR_FAMILY_CALIBRATION_SOURCE || DEFAULT_SOURCE),
  );
  const outDir = resolve(
    process.cwd(),
    String(process.env.WR_FAMILY_CALIBRATION_OUTPUT_DIR || DEFAULT_OUTPUT_DIR),
  );
  const minFamilyTrades = Math.max(
    1,
    Math.floor(toFinite(process.env.WR_FAMILY_CALIBRATION_MIN_FAMILY_TRADES, 500)),
  );

  const rows = loadCalibrationRows(sourcePath);
  const recommendations = calibrateWrFamilyThresholds(rows, { minFamilyTrades });
  const tradeSummary = summarizeTradesByFamily(rows);
  const generatedAtIso = new Date().toISOString();

  mkdirSync(outDir, { recursive: true });
  const stamp = Date.now();
  const jsonPath = join(outDir, `wr-family-calibration-${stamp}.json`);
  const mdPath = join(outDir, `wr-family-calibration-${stamp}.md`);

  writeFileSync(
    jsonPath,
    JSON.stringify(
      {
        generatedAt: generatedAtIso,
        sourcePath,
        minFamilyTrades,
        rows: rows.length,
        tradeSummary,
        recommendations,
        autoApply: false,
      },
      null,
      2,
    ),
    'utf8',
  );
  writeFileSync(
    mdPath,
    toMarkdown({
      sourcePath,
      minFamilyTrades,
      generatedAtIso,
      recommendations,
      tradeSummary,
    }),
    'utf8',
  );

  console.log(`[wr-calibration] rows=${rows.length} source=${sourcePath}`);
  console.log(`[wr-calibration] json=${jsonPath}`);
  console.log(`[wr-calibration] md=${mdPath}`);
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`[wr-calibration] fatal=${message}`);
  process.exitCode = 1;
});
