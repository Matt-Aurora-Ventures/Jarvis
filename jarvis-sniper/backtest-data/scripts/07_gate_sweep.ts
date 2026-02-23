/**
 * Phase 7: Gate Sweep (Post-Backtest)
 *
 * Purpose:
 * - Use the existing simulated trade dataset to search for better *entry gates*
 *   (score/liquidity/momentum/vol-liq/age) that improve profitability and
 *   rolling-window consistency.
 *
 * Why post-backtest?
 * - Gates are deterministic filters on already-generated trades. Tightening
 *   gates should match live behavior (scanner skips low-quality candidates)
 *   without requiring another candle fetch.
 *
 * Run:
 *   npx tsx backtest-data/scripts/07_gate_sweep.ts
 *
 * Optional env:
 *   GATE_SWEEP_ALGOS=momentum,hybrid_b,let_it_ride
 *   GATE_SWEEP_MIN_TRADES=200
 *   GATE_SWEEP_REQUIRE_PF=1
 */

import {
  log, logError, readJSON, writeJSON, ensureDir, dataPath,
} from './shared/utils';
import { CURRENT_ALGO_IDS, type AlgoId } from './shared/algo-ids';
import type { ScoredToken, TradeResult } from './shared/types';
import * as fs from 'fs';

type WindowSize = 10 | 25 | 50 | 100 | 250 | 500 | 1000;
const WINDOWS: WindowSize[] = [10, 25, 50, 100, 250, 500, 1000];

interface Gate {
  minScore: number;
  minLiquidityUsd: number;
  minMomentum1h: number;
  minVolLiqRatio: number;
  /** Max token age (hours) at sweep time; Infinity disables. */
  maxTokenAgeHours: number;
}

interface GateMetrics {
  trades: number;
  winRate: number;
  profitFactor: number;
  expectancyPct: number;
  totalReturnPct: number;
  /** Rolling-window fraction of windows with positive sum pnl%. */
  posFracByWindow: Partial<Record<WindowSize, number>>;
  /** Worst rolling-window sum pnl% (most negative) per window size. */
  minSumByWindow: Partial<Record<WindowSize, number>>;
  /** Consistency score: minimum posFrac across computed windows. */
  minPosFrac: number;
  /** Avg posFrac across computed windows. */
  avgPosFrac: number;
}

interface GateCandidate extends Gate {
  metrics: GateMetrics;
  score: number;
}

function envNum(name: string, fallback: number): number {
  const raw = process.env[name];
  const n = raw ? Number(raw) : NaN;
  return Number.isFinite(n) ? n : fallback;
}

function parseAlgoList(): AlgoId[] {
  const raw = String(process.env.GATE_SWEEP_ALGOS || '').trim();
  if (!raw) {
    // Default: focus on known underperformers + disabled TradFi (most urgent).
    return [
      'let_it_ride',
      'established_breakout',
      'momentum',
      'hybrid_b',
      'bags_momentum',
      'volume_spike',
      'xstock_intraday',
      'xstock_swing',
      'prestock_speculative',
      'index_intraday',
      'index_leveraged',
    ];
  }

  const wanted = raw.split(',').map(s => s.trim()).filter(Boolean);
  const set = new Set(wanted);
  return CURRENT_ALGO_IDS.filter(id => set.has(id));
}

function computeProfitFactor(pnls: number[]): number {
  let grossWin = 0;
  let grossLoss = 0;
  for (const p of pnls) {
    if (p > 0) grossWin += p;
    else grossLoss += -p;
  }
  if (grossLoss <= 0) return grossWin > 0 ? 999 : 0;
  return grossWin / grossLoss;
}

function rollingWindowStats(pnls: number[], window: number): { posFrac: number; minSum: number } | null {
  if (pnls.length < window) return null;
  let sum = 0;
  for (let i = 0; i < window; i++) sum += pnls[i];
  let pos = sum > 0 ? 1 : 0;
  let minSum = sum;
  let windows = 1;

  for (let i = window; i < pnls.length; i++) {
    sum += pnls[i] - pnls[i - window];
    windows += 1;
    if (sum > 0) pos += 1;
    if (sum < minSum) minSum = sum;
  }

  return { posFrac: pos / windows, minSum };
}

function computeMetrics(trades: TradeResult[]): GateMetrics {
  const n = trades.length;
  const pnls = trades.map(t => t.pnl_percent);
  const wins = pnls.filter(p => p > 0).length;
  const total = pnls.reduce((s, p) => s + p, 0);

  // Sort trades by time for rolling windows.
  const sortedPnls = trades
    .slice()
    .sort((a, b) => a.entry_timestamp - b.entry_timestamp)
    .map(t => t.pnl_percent);

  const posFracByWindow: GateMetrics['posFracByWindow'] = {};
  const minSumByWindow: GateMetrics['minSumByWindow'] = {};
  const computed: number[] = [];

  for (const w of WINDOWS) {
    const st = rollingWindowStats(sortedPnls, w);
    if (!st) continue;
    posFracByWindow[w] = +st.posFrac.toFixed(3);
    minSumByWindow[w] = +st.minSum.toFixed(2);
    computed.push(st.posFrac);
  }

  const minPosFrac = computed.length ? Math.min(...computed) : 0;
  const avgPosFrac = computed.length ? computed.reduce((s, v) => s + v, 0) / computed.length : 0;

  return {
    trades: n,
    winRate: n > 0 ? +(wins / n * 100).toFixed(1) : 0,
    profitFactor: +computeProfitFactor(pnls).toFixed(3),
    expectancyPct: n > 0 ? +(total / n).toFixed(3) : 0,
    totalReturnPct: +total.toFixed(2),
    posFracByWindow,
    minSumByWindow,
    minPosFrac: +minPosFrac.toFixed(3),
    avgPosFrac: +avgPosFrac.toFixed(3),
  };
}

function scoreCandidate(m: GateMetrics): number {
  // Prioritize consistency first, then profitability.
  // Scale factors keep scores in a human-ish range.
  return (
    m.minPosFrac * 1000 +
    m.avgPosFrac * 100 +
    Math.min(10, m.profitFactor) * 10 +
    m.expectancyPct * 5 +
    Math.log10(Math.max(1, m.trades)) * 10
  );
}

function gateKey(g: Gate): string {
  const age = Number.isFinite(g.maxTokenAgeHours) ? g.maxTokenAgeHours : 999999;
  return `S${g.minScore}-L${g.minLiquidityUsd}-M${g.minMomentum1h}-V${g.minVolLiqRatio}-A${age}`;
}

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 7: Gate Sweep (Entry Filters Optimization)');
  log('═══════════════════════════════════════════════════════');

  ensureDir('results');

  const minTrades = Math.max(10, Math.floor(envNum('GATE_SWEEP_MIN_TRADES', 200)));
  const requirePf = envNum('GATE_SWEEP_REQUIRE_PF', 1.0);
  const topK = Math.max(1, Math.floor(envNum('GATE_SWEEP_TOP_K', 8)));
  const algos = parseAlgoList();
  log(`Config: algos=${algos.length} | minTrades=${minTrades} | requirePF>=${requirePf} | topK=${topK}`);

  // Optional: join token ages from scored universe (for maxTokenAge gate).
  const scored = readJSON<ScoredToken[]>('universe/universe_scored.json') || [];
  const metaByMint = new Map<string, { creation_timestamp: number }>();
  for (const t of scored) metaByMint.set(t.mint, { creation_timestamp: t.creation_timestamp });
  const nowSec = Date.now() / 1000;

  // Candidate grids (coarse on purpose; tighten later if needed).
  const SCORE_GRID = [0, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70];
  const LIQ_GRID = [0, 3000, 5000, 10_000, 20_000, 50_000, 100_000, 200_000];
  const MOM_GRID = [-20, -10, 0, 2, 5, 10, 20];
  const VLR_GRID = [0, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0];
  const AGE_GRID = [Infinity, 24, 48, 72, 100, 150, 200, 336, 500, 720, 8760];

  const bestByAlgo: Partial<Record<AlgoId, GateCandidate>> = {};
  const topByAlgo: Partial<Record<AlgoId, GateCandidate[]>> = {};
  const baselineByAlgo: Partial<Record<AlgoId, GateMetrics>> = {};

  function pushTop(list: GateCandidate[], c: GateCandidate): void {
    list.push(c);
    list.sort((a, b) => b.score - a.score);
    if (list.length > topK) list.length = topK;
  }

  for (const algoId of algos) {
    const trades = readJSON<TradeResult[]>(`results/results_${algoId}.json`) || [];
    if (trades.length === 0) {
      log(`  ${algoId}: no trades found (missing results file), skipping`);
      continue;
    }

    const algoMinTrades = trades.length < minTrades
      ? Math.max(10, Math.floor(trades.length * 0.8))
      : minTrades;
    if (algoMinTrades !== minTrades) {
      log(`\nNOTE: ${algoId} has only ${trades.length} trades; lowering minTrades to ${algoMinTrades} for this sweep`);
    }

    const baseline = computeMetrics(trades);
    baselineByAlgo[algoId] = baseline;
    log(`\n─── ${algoId} baseline ───`);
    log(`Trades ${baseline.trades} | WR ${baseline.winRate}% | PF ${baseline.profitFactor} | Exp ${baseline.expectancyPct}% | minPos ${baseline.minPosFrac} | avgPos ${baseline.avgPosFrac}`);

    // Determine which gates are meaningful for this algo (bags has 0 liq/vlr).
    const hasLiq = trades.some(t => t.liquidity_at_entry > 0);
    const hasVlr = trades.some(t => t.vol_liq_ratio_at_entry > 0);

    const topAny: GateCandidate[] = [];
    const topProfitable: GateCandidate[] = [];
    const seen = new Set<string>();

    for (const minScore of SCORE_GRID) {
      for (const minLiquidityUsd of (hasLiq ? LIQ_GRID : [0])) {
        for (const minMomentum1h of MOM_GRID) {
          for (const minVolLiqRatio of (hasVlr ? VLR_GRID : [0])) {
            for (const maxTokenAgeHours of AGE_GRID) {
              const g: Gate = { minScore, minLiquidityUsd, minMomentum1h, minVolLiqRatio, maxTokenAgeHours };
              const key = gateKey(g);
              if (seen.has(key)) continue;
              seen.add(key);

              const filtered = trades.filter(t => {
                if (t.score_at_entry < g.minScore) return false;
                if (hasLiq && t.liquidity_at_entry < g.minLiquidityUsd) return false;
                if (t.momentum_1h_at_entry < g.minMomentum1h) return false;
                if (hasVlr && t.vol_liq_ratio_at_entry < g.minVolLiqRatio) return false;

                if (Number.isFinite(g.maxTokenAgeHours)) {
                  const meta = metaByMint.get(t.mint);
                  const created = meta?.creation_timestamp || 0;
                  const ageH = created > 0 ? (nowSec - created) / 3600 : Infinity;
                  if (ageH > g.maxTokenAgeHours) return false;
                }
                return true;
              });

              if (filtered.length < algoMinTrades) continue;

              const m = computeMetrics(filtered);
              const score = scoreCandidate(m);
              const cand: GateCandidate = { ...g, metrics: m, score };
              pushTop(topAny, cand);
              if (m.profitFactor >= requirePf) pushTop(topProfitable, cand);
            }
          }
        }
      }
    }

    const top = topProfitable.length > 0 ? topProfitable : topAny;
    const best = top[0];

    if (!best) {
      log(`  ${algoId}: no gate combo met constraints (minTrades>=${algoMinTrades})`);
      continue;
    }

    bestByAlgo[algoId] = best;
    topByAlgo[algoId] = top;

    log(`\n✓ ${algoId} best gates (score=${best.score.toFixed(1)})`);
    log(`  minScore=${best.minScore} minLiq=$${best.minLiquidityUsd} minMom1h=${best.minMomentum1h}% minVLR=${best.minVolLiqRatio} maxAge=${Number.isFinite(best.maxTokenAgeHours) ? best.maxTokenAgeHours + 'h' : 'off'}`);
    log(`  Trades ${best.metrics.trades} | WR ${best.metrics.winRate}% | PF ${best.metrics.profitFactor} | Exp ${best.metrics.expectancyPct}% | minPos ${best.metrics.minPosFrac} | avgPos ${best.metrics.avgPosFrac}`);

    if (topProfitable.length === 0 && requirePf > 0) {
      log(`  WARNING: No combo achieved PF>=${requirePf}. Showing best available (may be losing).`);
    }
  }

  writeJSON('results/gate_sweep_best.json', bestByAlgo);
  writeJSON('results/gate_sweep_top.json', topByAlgo);

  // ─── Markdown report ───
  const reportLines: string[] = [];
  reportLines.push('# Gate Sweep Report');
  reportLines.push('');
  reportLines.push(`Generated: ${new Date().toISOString()}`);
  reportLines.push('');
  reportLines.push(`Config: algos=${algos.length}, minTrades=${minTrades}, requirePF>=${requirePf}, topK=${topK}`);
  reportLines.push('');
  reportLines.push('| Algo | Base PF | Base Exp | Base WR | Base N | Best PF | Best Exp | Best WR | Best N | minPos | avgPos | pos10 | pos100 | pos500 | pos1000 | Gates |');
  reportLines.push('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|');

  const fmt = (v: unknown, digits = 2): string => {
    if (v === null || v === undefined || v === '') return '';
    const n = typeof v === 'number' ? v : Number(v);
    if (!Number.isFinite(n)) return '';
    return n.toFixed(digits);
  };

  for (const algoId of algos) {
    const base = baselineByAlgo[algoId];
    const best = bestByAlgo[algoId];
    if (!base || !best) continue;

    const pos = best.metrics.posFracByWindow;
    const gates = [
      `score>=${best.minScore}`,
      `liq>=${best.minLiquidityUsd}`,
      `mom1h>=${best.minMomentum1h}`,
      `vlr>=${best.minVolLiqRatio}`,
      Number.isFinite(best.maxTokenAgeHours) ? `age<=${best.maxTokenAgeHours}h` : 'age=off',
    ].join(', ');

    reportLines.push(
      `| ${algoId} | ${fmt(base.profitFactor, 2)} | ${fmt(base.expectancyPct, 3)} | ${fmt(base.winRate, 1)} | ${base.trades} | ` +
      `${fmt(best.metrics.profitFactor, 2)} | ${fmt(best.metrics.expectancyPct, 3)} | ${fmt(best.metrics.winRate, 1)} | ${best.metrics.trades} | ` +
      `${fmt(best.metrics.minPosFrac, 3)} | ${fmt(best.metrics.avgPosFrac, 3)} | ` +
      `${fmt(pos[10] ?? '', 3)} | ${fmt(pos[100] ?? '', 3)} | ${fmt(pos[500] ?? '', 3)} | ${fmt(pos[1000] ?? '', 3)} | ` +
      `${gates} |`,
    );
  }

  const reportPath = dataPath('results/gate_sweep_report.md');
  fs.writeFileSync(reportPath, reportLines.join('\n'), 'utf-8');
  log(`  → results/gate_sweep_report.md`);

  log('\n✓ Gate sweep complete');
  log('  → results/gate_sweep_best.json');
  log('  → results/gate_sweep_top.json');
}

main().catch(err => {
  logError('Fatal error in gate sweep', err);
  process.exit(1);
});
