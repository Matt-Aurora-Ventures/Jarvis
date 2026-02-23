/**
 * Phase 6: Generate Reports
 * 
 * Produces per-algo summaries, master comparison, master all-trades,
 * and data manifest with SHA256 checksums.
 * 
 * Input:  results/results_{algo_id}.json
 * Output: results/summary_{algo_id}.json, master_comparison.csv,
 *         master_all_trades.csv, data_manifest.json
 * 
 * Run: npx tsx backtest-data/scripts/06_generate_reports.ts
 */

import * as fs from 'fs';
import {
  log, logError, readJSON, writeJSON, writeCSV, sha256File,
  ensureDir, dataPath,
} from './shared/utils';
import { CURRENT_ALGO_IDS } from './shared/algo-ids';
import type { TradeResult, AlgoSummary, ExitReason, DataManifest } from './shared/types';

// ─── Compute Algo Summary ───

function computeSummary(algoId: string, trades: TradeResult[]): AlgoSummary {
  const wins = trades.filter(t => t.pnl_percent > 0);
  const losses = trades.filter(t => t.pnl_percent <= 0);

  const winPnls = wins.map(t => t.pnl_percent);
  const lossPnls = losses.map(t => t.pnl_percent);

  const avgWin = winPnls.length > 0 ? winPnls.reduce((s, v) => s + v, 0) / winPnls.length : 0;
  const avgLoss = lossPnls.length > 0 ? lossPnls.reduce((s, v) => s + v, 0) / lossPnls.length : 0;
  const maxWin = winPnls.length > 0 ? Math.max(...winPnls) : 0;
  const maxLoss = lossPnls.length > 0 ? Math.min(...lossPnls) : 0;

  const durations = trades.map(t => t.trade_duration_hours).sort((a, b) => a - b);
  const avgDuration = durations.length > 0 ? durations.reduce((s, v) => s + v, 0) / durations.length : 0;
  const medianDuration = durations.length > 0 ? durations[Math.floor(durations.length / 2)] : 0;

  // Profit factor = gross wins / |gross losses|
  const grossWin = winPnls.reduce((s, v) => s + v, 0);
  const grossLoss = Math.abs(lossPnls.reduce((s, v) => s + v, 0));
  const profitFactor = grossLoss > 0 ? grossWin / grossLoss : grossWin > 0 ? Infinity : 0;

  // Expectancy per trade
  const totalPnl = trades.reduce((s, t) => s + t.pnl_percent, 0);
  const expectancy = trades.length > 0 ? totalPnl / trades.length : 0;

  // Sharpe ratio (annualized, simplified)
  const pnls = trades.map(t => t.pnl_percent);
  const mean = pnls.reduce((s, v) => s + v, 0) / pnls.length;
  const variance = pnls.reduce((s, v) => s + (v - mean) ** 2, 0) / pnls.length;
  const stdDev = Math.sqrt(variance);
  const sharpe = stdDev > 0 ? (mean / stdDev) * Math.sqrt(252) : 0; // annualized

  // Max drawdown (sequential trades equity curve)
  let equity = 100;
  let peak = 100;
  let maxDD = 0;
  for (const t of trades) {
    equity += t.pnl_usd;
    if (equity > peak) peak = equity;
    const dd = ((peak - equity) / peak) * 100;
    if (dd > maxDD) maxDD = dd;
  }

  // Exit distribution
  const exitDist: Record<ExitReason, number> = {
    sl_hit: 0, tp_hit: 0, trail_stop: 0, expired: 0, end_of_data: 0,
  };
  for (const t of trades) {
    exitDist[t.exit_reason]++;
  }

  const dualTriggerBars = trades.reduce((s, t) => s + (t.dual_trigger_bar ? 1 : 0), 0);
  const expiryExitsBelowEntry = trades.filter(
    t => t.exit_reason === 'expired' && t.exit_price_usd < t.entry_price_usd,
  ).length;

  // Monthly breakdown
  const monthlyMap = new Map<string, { trades: number; pnl: number; wins: number }>();
  for (const t of trades) {
    const d = new Date(t.entry_timestamp * 1000);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    const m = monthlyMap.get(key) || { trades: 0, pnl: 0, wins: 0 };
    m.trades++;
    m.pnl += t.pnl_percent;
    if (t.pnl_percent > 0) m.wins++;
    monthlyMap.set(key, m);
  }
  const monthlyBreakdown = Array.from(monthlyMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, m]) => ({
      month,
      trades: m.trades,
      pnl_pct: +m.pnl.toFixed(2),
      win_rate: +(m.wins / m.trades * 100).toFixed(1),
    }));

  // Best/worst day
  const dailyMap = new Map<string, number>();
  for (const t of trades) {
    const d = new Date(t.entry_timestamp * 1000).toISOString().slice(0, 10);
    dailyMap.set(d, (dailyMap.get(d) || 0) + t.pnl_percent);
  }
  let bestDay = '', worstDay = '';
  let bestDayPnl = -Infinity, worstDayPnl = Infinity;
  for (const [day, pnl] of dailyMap) {
    if (pnl > bestDayPnl) { bestDayPnl = pnl; bestDay = day; }
    if (pnl < worstDayPnl) { worstDayPnl = pnl; worstDay = day; }
  }

  return {
    algo_id: algoId,
    total_trades: trades.length,
    wins: wins.length,
    losses: losses.length,
    win_rate: +(wins.length / trades.length * 100).toFixed(1),
    avg_win_pct: +avgWin.toFixed(2),
    avg_loss_pct: +avgLoss.toFixed(2),
    max_win_pct: +maxWin.toFixed(2),
    max_loss_pct: +maxLoss.toFixed(2),
    avg_trade_duration_hours: +avgDuration.toFixed(2),
    median_trade_duration_hours: +medianDuration.toFixed(2),
    profit_factor: profitFactor === Infinity ? 999 : +profitFactor.toFixed(2),
    expectancy_per_trade_pct: +expectancy.toFixed(2),
    total_return_pct: +totalPnl.toFixed(2),
    sharpe_ratio: +sharpe.toFixed(2),
    max_drawdown_pct: +(-maxDD).toFixed(2),
    dual_trigger_bars: dualTriggerBars,
    expiry_exits_below_entry: expiryExitsBelowEntry,
    exit_distribution: exitDist,
    monthly_breakdown: monthlyBreakdown,
    best_day: bestDay,
    worst_day: worstDay,
  };
}

// ─── Collect File Checksums ───

function collectFileChecksums(dir: string, pattern: RegExp): { path: string; rows?: number; sha256: string }[] {
  const fullDir = dataPath(dir);
  if (!fs.existsSync(fullDir)) return [];

  const files = fs.readdirSync(fullDir).filter(f => pattern.test(f));
  return files.map(f => {
    const relPath = `${dir}/${f}`;
    const sha = sha256File(relPath);
    let rows: number | undefined;

    if (f.endsWith('.json')) {
      try {
        const data = readJSON<unknown[]>(relPath);
        if (Array.isArray(data)) rows = data.length;
      } catch { /* ignore */ }
    } else if (f.endsWith('.csv')) {
      try {
        const content = fs.readFileSync(dataPath(relPath), 'utf-8');
        rows = content.split('\n').length - 1; // minus header
      } catch { /* ignore */ }
    }

    return { path: relPath, rows, sha256: sha };
  });
}

// ─── Main ───

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 6: Generate Reports');
  log('═══════════════════════════════════════════════════════');

  ensureDir('results');

  const allSummaries: AlgoSummary[] = [];
  const allTrades: TradeResult[] = [];

  for (const algoId of CURRENT_ALGO_IDS) {
    const trades = readJSON<TradeResult[]>(`results/results_${algoId}.json`);

    if (!trades || trades.length === 0) {
      log(`  ${algoId}: No trade results, skipping.`);
      continue;
    }

    const summary = computeSummary(algoId, trades);
    allSummaries.push(summary);
    allTrades.push(...trades);

    writeJSON(`results/summary_${algoId}.json`, summary);

    log(`  ${algoId}: WR ${summary.win_rate}% | PF ${summary.profit_factor} | Exp ${summary.expectancy_per_trade_pct}% | ${summary.total_trades} trades`);
  }

  // ─── Master Comparison ───
  log('\n─── Master Comparison ───');

  const comparisonRows = allSummaries.map(s => ({
    algo_id: s.algo_id,
    total_trades: s.total_trades,
    win_rate: s.win_rate,
    avg_win_pct: s.avg_win_pct,
    avg_loss_pct: s.avg_loss_pct,
    max_win_pct: s.max_win_pct,
    max_loss_pct: s.max_loss_pct,
    profit_factor: s.profit_factor,
    expectancy_pct: s.expectancy_per_trade_pct,
    total_return_pct: s.total_return_pct,
    sharpe_ratio: s.sharpe_ratio,
    max_drawdown_pct: s.max_drawdown_pct,
    avg_duration_hours: s.avg_trade_duration_hours,
    median_duration_hours: s.median_trade_duration_hours,
    sl_hits: s.exit_distribution.sl_hit,
    tp_hits: s.exit_distribution.tp_hit,
    trail_stops: s.exit_distribution.trail_stop,
    expired: s.exit_distribution.expired,
    end_of_data: s.exit_distribution.end_of_data,
    dual_trigger_bars: s.dual_trigger_bars,
    expiry_exits_below_entry: s.expiry_exits_below_entry,
    best_day: s.best_day,
    worst_day: s.worst_day,
  }));

  // Sort by expectancy descending
  comparisonRows.sort((a, b) => b.expectancy_pct - a.expectancy_pct);

  writeCSV('results/master_comparison.csv', comparisonRows);
  writeJSON('results/master_comparison.json', comparisonRows);

  // ─── Master All Trades ───
  log('─── Master All Trades ───');
  allTrades.sort((a, b) => a.entry_timestamp - b.entry_timestamp);
  writeCSV('results/master_all_trades.csv', allTrades as unknown as Record<string, unknown>[]);
  log(`Master all trades: ${allTrades.length} rows`);

  // ─── Token Universe CSV Copy ───
  const scoredPath = dataPath('universe/universe_scored.csv');
  const universeDestPath = dataPath('results/token_universe.csv');
  if (fs.existsSync(scoredPath)) {
    fs.copyFileSync(scoredPath, universeDestPath);
    log('Copied token_universe.csv to results/');
  }

  // ─── Data Manifest ───
  log('\n─── Data Manifest ───');

  const manifest: DataManifest = {
    created_at: new Date().toISOString(),
    pipeline_version: '1.0.0',
    phases: {
      universe: {
        completed_at: new Date().toISOString(),
        files: collectFileChecksums('universe', /\.(json|csv)$/),
      },
      qualified: {
        completed_at: new Date().toISOString(),
        files: collectFileChecksums('qualified', /\.(json|csv)$/),
      },
      results: {
        completed_at: new Date().toISOString(),
        files: collectFileChecksums('results', /\.(json|csv)$/),
      },
    },
  };

  writeJSON('results/data_manifest.json', manifest);

  // ─── Final Summary ───
  log('');
  log('═══════════════════════════════════════════════════════');
  log('BACKTEST PIPELINE COMPLETE');
  log('═══════════════════════════════════════════════════════');
  log('');

  // Rank algos
  log('Top 10 Algos by Expectancy:');
  for (let i = 0; i < Math.min(10, comparisonRows.length); i++) {
    const r = comparisonRows[i];
    log(`  ${i + 1}. ${r.algo_id.padEnd(25)} WR: ${String(r.win_rate).padStart(5)}% | PF: ${String(r.profit_factor).padStart(5)} | Exp: ${String(r.expectancy_pct).padStart(6)}% | Trades: ${r.total_trades}`);
  }

  log('');
  log('Bottom 5 Algos by Expectancy:');
  for (let i = Math.max(0, comparisonRows.length - 5); i < comparisonRows.length; i++) {
    const r = comparisonRows[i];
    log(`  ${comparisonRows.length - i}. ${r.algo_id.padEnd(25)} WR: ${String(r.win_rate).padStart(5)}% | PF: ${String(r.profit_factor).padStart(5)} | Exp: ${String(r.expectancy_pct).padStart(6)}% | Trades: ${r.total_trades}`);
  }

  log('');
  log(`Total trades across all algos: ${allTrades.length}`);
  log(`Algos with results: ${allSummaries.length}/${CURRENT_ALGO_IDS.length}`);

  const overallWins = allTrades.filter(t => t.pnl_percent > 0).length;
  const overallWR = (overallWins / allTrades.length * 100).toFixed(1);
  const overallAvgPnl = allTrades.reduce((s, t) => s + t.pnl_percent, 0) / allTrades.length;
  log(`Overall win rate: ${overallWR}%`);
  log(`Overall avg PnL: ${overallAvgPnl.toFixed(2)}%`);

  log(`\n✓ Phase 6 complete`);
  log(`  → results/summary_{algo_id}.json (${allSummaries.length} summaries)`);
  log(`  → results/master_comparison.csv`);
  log(`  → results/master_all_trades.csv (${allTrades.length} rows)`);
  log(`  → results/data_manifest.json`);
}

main().catch(err => {
  logError('Fatal error in report generation', err);
  process.exit(1);
});
