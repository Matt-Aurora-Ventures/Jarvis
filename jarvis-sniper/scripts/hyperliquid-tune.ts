#!/usr/bin/env npx tsx
/**
 * Hyperliquid Tuning Runner (Real Data Only)
 *
 * Purpose:
 * - Stage 1 (sanity): broad parameter sweep on a smaller sample (100-300+ trades target)
 * - Stage 2 (stability): re-evaluate top configs on a larger sample (1000+ trades target)
 *
 * Output (best-effort):
 * - `.jarvis-cache/backtest-runs/<runId>/{manifest.json,trades.csv,report.md,evidence.json}`
 *
 * Usage examples:
 *   cd jarvis-sniper
 *   npx tsx scripts/hyperliquid-tune.ts --strategy hl_momentum --interval 5m --days1 7 --days2 30
 *   npx tsx scripts/hyperliquid-tune.ts --coins BTC,ETH,SOL --top 10 --stage2-min-trades 500
 *
 * Notes:
 * - NO synthetic candles. Only Hyperliquid candleSnapshot data.
 * - This script is designed to be run locally; it can take time for large grids.
 */

import { createHash } from 'crypto';
import {
  BacktestEngine,
  breakoutEntry,
  meanReversionEntry,
  momentumEntry,
  squeezeBreakoutEntry,
  trendFollowingEntry,
  type BacktestConfig,
  type BacktestResult,
  type OHLCVCandle,
} from '../src/lib/backtest-engine';
import { persistBacktestArtifacts } from '../src/lib/backtest-artifacts';
import type {
  BacktestEvidenceBundle,
  BacktestEvidenceDataset,
  BacktestEvidenceTradeRow,
} from '../src/lib/backtest-evidence';
import { fetchHyperliquidCandles, type HyperliquidInterval } from '../src/lib/hyperliquid-data';

type StrategyId =
  | 'hl_mean_revert'
  | 'hl_trend_follow'
  | 'hl_breakout'
  | 'hl_momentum'
  | 'hl_squeeze_breakout';

type AggregatedMetrics = {
  totalTrades: number;
  winRate: number;
  profitFactor: number;
  expectancy: number;
  sharpe: number;
  maxDD: number;
  datasets: number;
};

type ParamConfig = Pick<
  BacktestConfig,
  'stopLossPct' | 'takeProfitPct' | 'trailingStopPct' | 'maxHoldCandles'
>;

type Candidate = ParamConfig & {
  metrics: AggregatedMetrics;
};

const HL_ENTRY_SIGNALS: Record<StrategyId, NonNullable<BacktestConfig['entrySignal']>> = {
  hl_mean_revert: meanReversionEntry,
  hl_trend_follow: trendFollowingEntry,
  hl_breakout: breakoutEntry,
  hl_momentum: momentumEntry,
  hl_squeeze_breakout: squeezeBreakoutEntry,
};

const HL_BASE_CONFIG: Record<StrategyId, Omit<BacktestConfig, keyof ParamConfig | 'entrySignal'>> = {
  hl_mean_revert: {
    strategyId: 'hl_mean_revert',
    minScore: 0,
    minLiquidityUsd: 0,
    slippagePct: 0.05,
    feePct: 0.02,
  },
  hl_trend_follow: {
    strategyId: 'hl_trend_follow',
    minScore: 0,
    minLiquidityUsd: 0,
    slippagePct: 0.05,
    feePct: 0.02,
  },
  hl_breakout: {
    strategyId: 'hl_breakout',
    minScore: 0,
    minLiquidityUsd: 0,
    slippagePct: 0.05,
    feePct: 0.02,
  },
  hl_momentum: {
    strategyId: 'hl_momentum',
    minScore: 0,
    minLiquidityUsd: 0,
    slippagePct: 0.05,
    feePct: 0.02,
  },
  hl_squeeze_breakout: {
    strategyId: 'hl_squeeze_breakout',
    minScore: 0,
    minLiquidityUsd: 0,
    slippagePct: 0.05,
    feePct: 0.02,
  },
};

const DEFAULT_COINS = [
  'BTC',
  'ETH',
  'SOL',
  'DOGE',
  'AVAX',
  'ARB',
  'OP',
  'SUI',
  'APT',
  'LINK',
  'XRP',
  'BNB',
  'LTC',
  'BCH',
  'ADA',
  'DOT',
  'ATOM',
  'NEAR',
  'ETC',
  'MATIC',
];

function getArg(flag: string): string | null {
  const i = process.argv.indexOf(flag);
  if (i === -1) return null;
  const v = process.argv[i + 1];
  if (!v || v.startsWith('--')) return null;
  return v;
}

function getArgNumber(flag: string, fallback: number): number {
  const raw = getArg(flag);
  if (!raw) return fallback;
  const n = Number.parseFloat(raw);
  return Number.isFinite(n) ? n : fallback;
}

function parseCoins(raw: string | null): string[] {
  if (!raw) return [...DEFAULT_COINS];
  if (raw.trim().toLowerCase() === 'all') return ['__ALL__'];
  const list = raw
    .split(',')
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);
  return list.length > 0 ? list : [...DEFAULT_COINS];
}

async function fetchHyperliquidUniverseCoins(limit = 80): Promise<string[]> {
  try {
    const res = await fetch('https://api.hyperliquid.xyz/info', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'User-Agent': 'JarvisSniper/1.0',
      },
      body: JSON.stringify({ type: 'meta' }),
    });
    if (!res.ok) return [...DEFAULT_COINS].slice(0, Math.max(1, limit));
    const json = (await res.json()) as { universe?: Array<{ name?: string }> };
    const names = Array.isArray(json?.universe)
      ? json.universe
          .map((u) => (u?.name || '').trim().toUpperCase())
          .filter((n) => n.length > 0)
      : [];
    const unique = [...new Set(names)];
    if (unique.length === 0) return [...DEFAULT_COINS].slice(0, Math.max(1, limit));
    return unique.slice(0, Math.max(1, limit));
  } catch {
    return [...DEFAULT_COINS].slice(0, Math.max(1, limit));
  }
}

function makeRunId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function hashCandlesHex(candles: OHLCVCandle[]): string {
  const h = createHash('sha256');
  for (const c of candles) {
    h.update(`${c.timestamp},${c.open},${c.high},${c.low},${c.close},${c.volume};`, 'utf8');
  }
  return h.digest('hex');
}

function cartesianGrid(values: {
  stopLossPcts: number[];
  takeProfitPcts: number[];
  trailingStopPcts: number[];
  maxHoldCandles: number[];
}): ParamConfig[] {
  const out: ParamConfig[] = [];
  for (const sl of values.stopLossPcts) {
    for (const tp of values.takeProfitPcts) {
      for (const trail of values.trailingStopPcts) {
        for (const maxHold of values.maxHoldCandles) {
          out.push({
            stopLossPct: sl,
            takeProfitPct: tp,
            trailingStopPct: trail,
            maxHoldCandles: maxHold,
          });
        }
      }
    }
  }
  return out;
}

function evaluateConfigAcrossDatasets(
  sid: StrategyId,
  cfg: ParamConfig,
  datasets: { coin: string; candles: OHLCVCandle[] }[],
): AggregatedMetrics {
  const entrySignal = HL_ENTRY_SIGNALS[sid];
  const base = HL_BASE_CONFIG[sid];

  let totalTrades = 0;
  let estWins = 0;
  let pfWeightedSum = 0;
  let expWeightedSum = 0;
  let sharpeWeightedSum = 0;
  let maxDD = 0;
  let datasetsUsed = 0;

  for (const d of datasets) {
    const fullConfig: BacktestConfig = {
      ...base,
      ...cfg,
      entrySignal,
    };
    const engine = new BacktestEngine(d.candles, fullConfig);
    const r = engine.run(d.coin);
    if (r.totalTrades <= 0) continue;

    datasetsUsed += 1;
    totalTrades += r.totalTrades;
    estWins += r.winRate * r.totalTrades;
    pfWeightedSum += r.profitFactor * r.totalTrades;
    expWeightedSum += r.expectancy * r.totalTrades;
    sharpeWeightedSum += r.sharpeRatio * r.totalTrades;
    maxDD = Math.max(maxDD, r.maxDrawdownPct);
  }

  const winRate = totalTrades > 0 ? estWins / totalTrades : 0;
  const profitFactor = totalTrades > 0 ? pfWeightedSum / totalTrades : 0;
  const expectancy = totalTrades > 0 ? expWeightedSum / totalTrades : 0;
  const sharpe = totalTrades > 0 ? sharpeWeightedSum / totalTrades : 0;

  return {
    totalTrades,
    winRate,
    profitFactor,
    expectancy,
    sharpe,
    maxDD,
    datasets: datasetsUsed,
  };
}

async function fetchDatasets(
  coins: string[],
  interval: HyperliquidInterval,
  startTime: number,
  endTime: number,
  concurrency: number,
  minCandles: number,
): Promise<{ coin: string; candles: OHLCVCandle[]; dataHash: string }[]> {
  const out: { coin: string; candles: OHLCVCandle[]; dataHash: string }[] = [];
  const queue = [...coins];
  let active = 0;

  await new Promise<void>((resolve) => {
    const pump = () => {
      if (queue.length === 0 && active === 0) return resolve();

      while (active < concurrency && queue.length > 0) {
        const coin = queue.shift()!;
        active += 1;

        fetchHyperliquidCandles({
          coin,
          interval,
          startTime,
          endTime,
        })
          .then((candles) => {
            if (!Array.isArray(candles) || candles.length < minCandles) return;
            out.push({ coin, candles, dataHash: hashCandlesHex(candles) });
          })
          .catch(() => {
            // ignore missing/unsupported coins
          })
          .finally(() => {
            active -= 1;
            pump();
          });
      }
    };

    pump();
  });

  out.sort((a, b) => a.coin.localeCompare(b.coin));
  return out;
}

function mdTableRow(cols: (string | number)[]): string {
  return `| ${cols.map((c) => String(c)).join(' | ')} |`;
}

function formatPct(x: number): string {
  if (!Number.isFinite(x)) return 'n/a';
  return `${(x * 100).toFixed(1)}%`;
}

function formatNum(x: number, digits: number): string {
  if (!Number.isFinite(x)) return 'n/a';
  return x.toFixed(digits);
}

async function main() {
  const strategy = (getArg('--strategy') || 'hl_momentum') as StrategyId;
  if (!(strategy in HL_ENTRY_SIGNALS)) {
    // eslint-disable-next-line no-console
    console.error(`Unknown --strategy ${strategy}`);
    process.exit(1);
  }

  const interval = (getArg('--interval') || '5m') as HyperliquidInterval;
  const maxCoins = Math.floor(getArgNumber('--max-coins', 80));
  const coinsArg = getArg('--coins');
  let coins = parseCoins(coinsArg);
  if (coins.length === 1 && coins[0] === '__ALL__') {
    coins = await fetchHyperliquidUniverseCoins(maxCoins);
  } else if (coins.length > maxCoins) {
    coins = coins.slice(0, maxCoins);
  }

  const days1 = getArgNumber('--days1', 7);
  const days2 = getArgNumber('--days2', 30);
  const topK = Math.floor(getArgNumber('--top', 20));
  const stage1MinTrades = Math.floor(getArgNumber('--stage1-min-trades', 200));
  const stage2MinTrades = Math.floor(getArgNumber('--stage2-min-trades', 1000));
  const concurrency = Math.max(1, Math.min(12, Math.floor(getArgNumber('--concurrency', 6))));
  const minCandles = Math.max(12, Math.floor(getArgNumber('--min-candles', 50)));

  // Stage 1 grid: keep it moderate; widening is easy once we have a winner.
  const grid = cartesianGrid({
    stopLossPcts: [1.2, 1.8, 2.5, 3.5, 5],
    takeProfitPcts: [2.5, 4, 6, 8, 10, 15],
    trailingStopPcts: [0, 0.8, 1.2, 1.8, 2.5, 3.5],
    maxHoldCandles: [12, 24, 36, 48, 72, 120],
  });

  const now = Date.now();
  const stage1Start = now - Math.floor(days1 * 24 * 60 * 60 * 1000);
  const stage2Start = now - Math.floor(days2 * 24 * 60 * 60 * 1000);

  const runId = makeRunId(`hl-tune-${strategy}`);

  // eslint-disable-next-line no-console
  console.log(`[${runId}] Hyperliquid tune starting`);
  // eslint-disable-next-line no-console
  console.log(`strategy=${strategy} interval=${interval} coins=${coins.length} stage1Days=${days1} stage2Days=${days2}`);
  // eslint-disable-next-line no-console
  console.log(`gridConfigs=${grid.length} topK=${topK} stage1MinTrades=${stage1MinTrades} stage2MinTrades=${stage2MinTrades} concurrency=${concurrency}`);

  // Stage 1: fetch smaller sample.
  // eslint-disable-next-line no-console
  console.log(`[${runId}] Stage 1: fetching candles...`);
  const stage1Datasets = await fetchDatasets(coins, interval, stage1Start, now, concurrency, minCandles);
  if (stage1Datasets.length === 0) {
    // eslint-disable-next-line no-console
    console.error(`[${runId}] No datasets fetched. Check coins/interval.`);
    process.exit(1);
  }
  // eslint-disable-next-line no-console
  console.log(`[${runId}] Stage 1: datasets=${stage1Datasets.length}`);

  // Stage 1: evaluate full grid (heuristic aggregation).
  // eslint-disable-next-line no-console
  console.log(`[${runId}] Stage 1: evaluating grid...`);
  const stage1Candidates: Candidate[] = [];
  for (let i = 0; i < grid.length; i++) {
    const cfg = grid[i];
    const metrics = evaluateConfigAcrossDatasets(
      strategy,
      cfg,
      stage1Datasets.map((d) => ({ coin: d.coin, candles: d.candles })),
    );
    if (metrics.totalTrades < stage1MinTrades) continue;
    stage1Candidates.push({ ...cfg, metrics });

    if ((i + 1) % 150 === 0) {
      // eslint-disable-next-line no-console
      console.log(`[${runId}] Stage 1 progress: ${i + 1}/${grid.length} (kept=${stage1Candidates.length})`);
    }
  }

  stage1Candidates.sort((a, b) => b.metrics.expectancy - a.metrics.expectancy);
  const stage1Top = stage1Candidates.slice(0, Math.max(1, topK));

  if (stage1Top.length === 0) {
    // eslint-disable-next-line no-console
    console.error(`[${runId}] Stage 1 produced 0 candidates meeting trade threshold. Try lowering --stage1-min-trades or widening --coins/--days1.`);
    process.exit(1);
  }

  // Stage 2: fetch larger sample.
  // eslint-disable-next-line no-console
  console.log(`[${runId}] Stage 2: fetching candles...`);
  const stage2Datasets = await fetchDatasets(coins, interval, stage2Start, now, concurrency, minCandles);
  // eslint-disable-next-line no-console
  console.log(`[${runId}] Stage 2: datasets=${stage2Datasets.length}`);
  if (stage2Datasets.length === 0) {
    // eslint-disable-next-line no-console
    console.error(`[${runId}] Stage 2 datasets empty. Aborting.`);
    process.exit(1);
  }

  // Stage 2: re-evaluate top configs on bigger sample.
  // eslint-disable-next-line no-console
  console.log(`[${runId}] Stage 2: evaluating top configs...`);
  const stage2Top: Candidate[] = [];
  for (const cfg of stage1Top) {
    const metrics = evaluateConfigAcrossDatasets(
      strategy,
      cfg,
      stage2Datasets.map((d) => ({ coin: d.coin, candles: d.candles })),
    );
    stage2Top.push({ ...cfg, metrics });
  }
  stage2Top.sort((a, b) => b.metrics.expectancy - a.metrics.expectancy);
  const best = stage2Top[0];

  // Stage 2: if trade count still low, we still persist artifacts but mark it clearly.
  const meetsStage2Trades = best.metrics.totalTrades >= stage2MinTrades;

  // Build a report + evidence for the BEST config only (full trades).
  const entrySignal = HL_ENTRY_SIGNALS[strategy];
  const base = HL_BASE_CONFIG[strategy];
  const tunedParams: ParamConfig = {
    stopLossPct: best.stopLossPct,
    takeProfitPct: best.takeProfitPct,
    trailingStopPct: best.trailingStopPct,
    maxHoldCandles: best.maxHoldCandles,
  };
  const tunedConfig: BacktestConfig = { ...base, ...tunedParams, entrySignal };

  const evidenceDatasets: BacktestEvidenceDataset[] = [];
  const evidenceTrades: BacktestEvidenceTradeRow[] = [];

  // eslint-disable-next-line no-console
  console.log(`[${runId}] Building evidence for best config (this can take a bit)...`);
  for (const d of stage2Datasets) {
    const engine = new BacktestEngine(d.candles, tunedConfig);
    const r: BacktestResult = engine.run(d.coin);
    if (r.totalTrades <= 0) continue;

    evidenceDatasets.push({
      tokenSymbol: d.coin,
      mintAddress: d.coin,
      pairAddress: '',
      candles: d.candles.length,
      dataHash: d.dataHash,
      dataStartTime: d.candles[0]?.timestamp ?? 0,
      dataEndTime: d.candles[d.candles.length - 1]?.timestamp ?? 0,
      fetchedAt: now,
      source: `hyperliquid:candleSnapshot:${interval}`,
    });

    for (const t of r.trades) {
      evidenceTrades.push({
        strategyId: strategy,
        mode: 'tune_stage2',
        tokenSymbol: d.coin,
        resultTokenSymbol: r.tokenSymbol,
        mintAddress: d.coin,
        pairAddress: '',
        source: `hyperliquid:candleSnapshot:${interval}`,
        entryTime: t.entryTime,
        exitTime: t.exitTime,
        entryPrice: t.entryPrice,
        exitPrice: t.exitPrice,
        pnlPct: t.pnlPct,
        pnlNet: t.pnlNet,
        exitReason: t.exitReason,
        holdCandles: t.holdCandles,
        highWaterMark: t.highWaterMark,
        lowWaterMark: t.lowWaterMark,
        maxDrawdownPct: t.maxDrawdownPct,
        stopLossPct: tunedConfig.stopLossPct,
        takeProfitPct: tunedConfig.takeProfitPct,
        trailingStopPct: tunedConfig.trailingStopPct,
        maxHoldCandles: tunedConfig.maxHoldCandles,
        slippagePct: tunedConfig.slippagePct,
        feePct: tunedConfig.feePct,
        minScore: tunedConfig.minScore,
        minLiquidityUsd: tunedConfig.minLiquidityUsd,
      });
    }
  }

  const report: string[] = [];
  report.push(`# Hyperliquid Tune Report`);
  report.push('');
  report.push(`**Run ID:** \`${runId}\``);
  report.push(`**Generated:** ${new Date(now).toISOString()}`);
  report.push(`**Strategy:** ${strategy}`);
  report.push(`**Interval:** ${interval}`);
  report.push(`**Coins requested:** ${coins.length}`);
  report.push(`**Coins used (stage1/stage2):** ${stage1Datasets.length} / ${stage2Datasets.length}`);
  report.push('');
  report.push('## Stage 1 (Sanity Sweep)');
  report.push('');
  report.push(`- Window: last ${days1} days`);
  report.push(`- Trade threshold: ${stage1MinTrades}+`);
  report.push(`- Grid size: ${grid.length} configs`);
  report.push('');
  report.push(mdTableRow(['Rank', 'SL%', 'TP%', 'Trail%', 'MaxHold', 'Trades', 'WR', 'PF', 'Exp', 'Sharpe', 'MaxDD']));
  report.push(mdTableRow(['---', '---', '---', '---', '---', '---', '---', '---', '---', '---', '---']));
  stage1Top.slice(0, 10).forEach((c, idx) => {
    report.push(
      mdTableRow([
        idx + 1,
        c.stopLossPct,
        c.takeProfitPct,
        c.trailingStopPct,
        c.maxHoldCandles,
        c.metrics.totalTrades,
        formatPct(c.metrics.winRate),
        formatNum(c.metrics.profitFactor, 2),
        formatNum(c.metrics.expectancy, 4),
        formatNum(c.metrics.sharpe, 2),
        `${c.metrics.maxDD.toFixed(1)}%`,
      ]),
    );
  });
  report.push('');
  report.push('## Stage 2 (Stability Re-Test)');
  report.push('');
  report.push(`- Window: last ${days2} days`);
  report.push(`- Trade threshold (goal): ${stage2MinTrades}+`);
  report.push('');
  report.push(mdTableRow(['Rank', 'SL%', 'TP%', 'Trail%', 'MaxHold', 'Trades', 'WR', 'PF', 'Exp', 'Sharpe', 'MaxDD']));
  report.push(mdTableRow(['---', '---', '---', '---', '---', '---', '---', '---', '---', '---', '---']));
  stage2Top.slice(0, 10).forEach((c, idx) => {
    report.push(
      mdTableRow([
        idx + 1,
        c.stopLossPct,
        c.takeProfitPct,
        c.trailingStopPct,
        c.maxHoldCandles,
        c.metrics.totalTrades,
        formatPct(c.metrics.winRate),
        formatNum(c.metrics.profitFactor, 2),
        formatNum(c.metrics.expectancy, 4),
        formatNum(c.metrics.sharpe, 2),
        `${c.metrics.maxDD.toFixed(1)}%`,
      ]),
    );
  });
  report.push('');
  report.push('## Selected Config');
  report.push('');
  report.push(`- SL/TP/Trail: **${best.stopLossPct}% / ${best.takeProfitPct}% / ${best.trailingStopPct}%**`);
  report.push(`- Max hold: **${best.maxHoldCandles} candles**`);
  report.push(`- Stage 2 trades: **${best.metrics.totalTrades}** (${meetsStage2Trades ? 'meets' : 'below'} threshold)`);
  report.push(`- Stage 2 expectancy: **${formatNum(best.metrics.expectancy, 4)}**`);
  report.push('');
  report.push('## Evidence');
  report.push('');
  report.push('- Trade-level timestamps are included in `trades.csv`.');
  report.push('- Dataset hashes are included in `manifest.json` for reproducibility (same candles => same hash).');
  report.push('');

  const bundle: BacktestEvidenceBundle = {
    runId,
    generatedAt: new Date(now).toISOString(),
    request: {
      strategy,
      interval,
      coins,
      stage1: { days: days1, minTrades: stage1MinTrades, gridConfigs: grid.length, topK },
      stage2: { days: days2, minTrades: stage2MinTrades, topK: stage1Top.length },
    },
    meta: {
      strategy,
      interval,
      coinsRequested: coins.length,
      coinsUsedStage1: stage1Datasets.length,
      coinsUsedStage2: stage2Datasets.length,
      stage1MinTrades,
      stage2MinTrades,
      selectedConfig: {
        stopLossPct: tunedConfig.stopLossPct,
        takeProfitPct: tunedConfig.takeProfitPct,
        trailingStopPct: tunedConfig.trailingStopPct,
        maxHoldCandles: tunedConfig.maxHoldCandles,
        slippagePct: tunedConfig.slippagePct,
        feePct: tunedConfig.feePct,
      },
      stage2MeetsTradeThreshold: meetsStage2Trades,
    },
    datasets: evidenceDatasets,
    trades: evidenceTrades,
    reportMd: report.join('\n'),
    resultsSummary: [
      {
        stage: 1,
        top: stage1Top.slice(0, 20).map((c) => ({
          ...c,
          metrics: c.metrics,
        })),
      },
      {
        stage: 2,
        top: stage2Top.slice(0, 20).map((c) => ({
          ...c,
          metrics: c.metrics,
        })),
      },
    ],
  };

  persistBacktestArtifacts(bundle);

  // eslint-disable-next-line no-console
  console.log(`[${runId}] Done.`);
  // eslint-disable-next-line no-console
  console.log(`[${runId}] Artifacts: .jarvis-cache/backtest-runs/${runId}/`);
  // eslint-disable-next-line no-console
  console.log(`[${runId}] Datasets=${bundle.datasets.length} trades=${bundle.trades.length}`);
  if (!meetsStage2Trades) {
    // eslint-disable-next-line no-console
    console.log(`[${runId}] WARNING: stage2 trades below threshold. Increase --coins or --days2, or lower --stage2-min-trades.`);
  }
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  process.exit(1);
});
