import { createHash } from 'crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import type { HistoricalDataSet, OHLCVSource } from '@/lib/historical-data';

export type DatasetFamily =
  | 'memecoin'
  | 'bags'
  | 'bluechip'
  | 'xstock'
  | 'prestock'
  | 'index'
  | 'xstock_index';

interface DatasetManifestFile {
  manifestId: string;
  family: DatasetFamily;
  createdAt: string;
  dataScale: 'fast' | 'thorough';
  sourcePolicy: 'gecko_only' | 'allow_birdeye_fallback';
  lookbackHours: number;
  attempted: number;
  succeeded: number;
  skipped: number;
  datasetCount: number;
  hash: string;
}

interface DatasetIndexRow {
  mintAddress: string;
  tokenSymbol: string;
  pairAddress?: string;
  source: OHLCVSource;
  candlesFile: string;
  fetchedAt: number;
}

interface DatasetIndexFile {
  manifestId: string;
  family: DatasetFamily;
  rows: DatasetIndexRow[];
}

const ROOT = join(process.cwd(), '.jarvis-cache', 'backtest-datasets');

function safeFamily(family: DatasetFamily): string {
  return family.replace(/[^a-z0-9_]/gi, '_').toLowerCase();
}

function familyDir(manifestId: string, family: DatasetFamily): string {
  return join(ROOT, manifestId, safeFamily(family));
}

function hashDatasets(datasets: HistoricalDataSet[]): string {
  const h = createHash('sha256');
  for (const ds of datasets) {
    h.update(`${ds.mintAddress}|${ds.tokenSymbol}|${ds.source}|${ds.pairAddress || ''};`, 'utf8');
    for (const c of ds.candles) {
      h.update(`${c.timestamp},${c.open},${c.high},${c.low},${c.close},${c.volume};`, 'utf8');
    }
  }
  return h.digest('hex');
}

export function persistFamilyDatasetManifest(args: {
  manifestId: string;
  family: DatasetFamily;
  dataScale: 'fast' | 'thorough';
  sourcePolicy: 'gecko_only' | 'allow_birdeye_fallback';
  lookbackHours: number;
  attempted: number;
  succeeded: number;
  skipped: number;
  datasets: HistoricalDataSet[];
}): { path: string; datasetCount: number } {
  const dir = familyDir(args.manifestId, args.family);
  const candlesDir = join(dir, 'candles');
  if (!existsSync(candlesDir)) mkdirSync(candlesDir, { recursive: true });

  const rows: DatasetIndexRow[] = [];
  for (const ds of args.datasets) {
    const mint = (ds.mintAddress || ds.tokenSymbol || 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
    const fileName = `${mint}.json`;
    const candlesFile = join(candlesDir, fileName);
    writeFileSync(candlesFile, JSON.stringify(ds.candles), 'utf8');
    rows.push({
      mintAddress: ds.mintAddress,
      tokenSymbol: ds.tokenSymbol,
      pairAddress: ds.pairAddress,
      source: ds.source,
      candlesFile: fileName,
      fetchedAt: ds.fetchedAt,
    });
  }

  const index: DatasetIndexFile = {
    manifestId: args.manifestId,
    family: args.family,
    rows,
  };
  const manifest: DatasetManifestFile = {
    manifestId: args.manifestId,
    family: args.family,
    createdAt: new Date().toISOString(),
    dataScale: args.dataScale,
    sourcePolicy: args.sourcePolicy,
    lookbackHours: args.lookbackHours,
    attempted: args.attempted,
    succeeded: args.succeeded,
    skipped: args.skipped,
    datasetCount: args.datasets.length,
    hash: hashDatasets(args.datasets),
  };

  writeFileSync(join(dir, 'datasets.index.json'), JSON.stringify(index, null, 2), 'utf8');
  writeFileSync(join(dir, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');

  return { path: dir, datasetCount: args.datasets.length };
}

export function loadFamilyDatasetManifest(
  manifestId: string,
  family: DatasetFamily,
): {
  datasets: HistoricalDataSet[];
  manifest: {
    attempted: number;
    succeeded: number;
    skipped: number;
    datasetCount: number;
    sourcePolicy: 'gecko_only' | 'allow_birdeye_fallback';
    lookbackHours: number;
    dataScale: 'fast' | 'thorough';
  };
} | null {
  try {
    const dir = familyDir(manifestId, family);
    const manifestPath = join(dir, 'manifest.json');
    const indexPath = join(dir, 'datasets.index.json');
    if (!existsSync(manifestPath) || !existsSync(indexPath)) return null;

    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8')) as DatasetManifestFile;
    const index = JSON.parse(readFileSync(indexPath, 'utf8')) as DatasetIndexFile;
    const datasets: HistoricalDataSet[] = [];

    for (const row of index.rows || []) {
      const candlesPath = join(dir, 'candles', row.candlesFile);
      if (!existsSync(candlesPath)) continue;
      const candles = JSON.parse(readFileSync(candlesPath, 'utf8')) as HistoricalDataSet['candles'];
      datasets.push({
        mintAddress: row.mintAddress,
        tokenSymbol: row.tokenSymbol,
        pairAddress: row.pairAddress || '',
        source: row.source,
        candles,
        fetchedAt: row.fetchedAt,
      });
    }

    return {
      datasets,
      manifest: {
        attempted: manifest.attempted,
        succeeded: manifest.succeeded,
        skipped: manifest.skipped,
        datasetCount: manifest.datasetCount,
        sourcePolicy: manifest.sourcePolicy,
        lookbackHours: manifest.lookbackHours,
        dataScale: manifest.dataScale,
      },
    };
  } catch {
    return null;
  }
}
