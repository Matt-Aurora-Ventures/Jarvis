/**
 * Phase 9: Strategy Recommendations + Provenance Pack
 *
 * Consumes pipeline artifacts and emits:
 * - strategy recommendations (strict gate)
 * - source coverage and request log summary
 * - dataset hashes and provenance manifest
 * - evidence report markdown
 */

import * as fs from 'fs';
import {
  dataPath,
  ensureDir,
  log,
  logError,
  readJSON,
  sha256File,
  writeCSV,
  writeJSON,
} from './shared/utils';
import { CURRENT_ALGO_IDS } from './shared/algo-ids';
import type { ConsistencyReportRow, StrategyStatusLabel, WalkforwardSummary } from './shared/types';

type ComparisonRow = {
  algo_id: string;
  total_trades: number;
  win_rate: number;
  profit_factor: number;
  expectancy_pct: number;
  total_return_pct: number;
};

type Recommendation = {
  algo_id: string;
  status_label: StrategyStatusLabel;
  recommendation: 'promote_to_proven' | 'keep_experimental' | 'disable_experimental';
  reason: string;
  gates: {
    pf_gt_1_15: boolean;
    expectancy_gt_0: boolean;
    trades_gte_100: boolean;
    min_pos_frac_gte_0_70: boolean;
    walkforward_pass_rate_gte_0_60: boolean;
  };
  metrics: {
    trades: number;
    win_rate: number;
    profit_factor: number;
    expectancy_pct: number;
    total_return_pct: number;
    min_pos_frac: number;
    walkforward_pass_rate: number;
    sample_band: string;
  };
};

type SourceRequestRow = {
  ts: string;
  method: string;
  provider: string;
  label: string;
  url: string;
  status: string;
  attempt: number;
  retries: number;
  duration_ms: number;
  error: string;
};

function parseCsv(content: string): string[][] {
  const lines = content.split(/\r?\n/).filter(Boolean);
  const rows: string[][] = [];
  for (const line of lines) {
    const out: string[] = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        if (inQuotes && line[i + 1] === '"') {
          current += '"';
          i += 1;
        } else {
          inQuotes = !inQuotes;
        }
        continue;
      }
      if (ch === ',' && !inQuotes) {
        out.push(current);
        current = '';
        continue;
      }
      current += ch;
    }
    out.push(current);
    rows.push(out);
  }
  return rows;
}

function readSourceRequestLog(): SourceRequestRow[] {
  const rel = 'results/source_request_log.csv';
  const full = dataPath(rel);
  if (!fs.existsSync(full)) return [];

  const raw = fs.readFileSync(full, 'utf-8');
  const rows = parseCsv(raw);
  if (rows.length <= 1) return [];
  const header = rows[0];
  const out: SourceRequestRow[] = [];

  for (const row of rows.slice(1)) {
    const record: Record<string, string> = {};
    for (let i = 0; i < header.length; i++) {
      record[header[i]] = row[i] ?? '';
    }
    out.push({
      ts: record.ts || '',
      method: record.method || '',
      provider: record.provider || 'other',
      label: record.label || '',
      url: record.url || '',
      status: record.status || '',
      attempt: Number(record.attempt || 0),
      retries: Number(record.retries || 0),
      duration_ms: Number(record.duration_ms || 0),
      error: record.error || '',
    });
  }

  return out;
}

function hashIfExists(relPath: string): string | null {
  const full = dataPath(relPath);
  if (!fs.existsSync(full)) return null;
  return sha256File(relPath);
}

function statusFromMetrics(
  row: ComparisonRow | null,
  consistency: ConsistencyReportRow | null,
  walkforward: WalkforwardSummary | null,
): Recommendation {
  const trades = row?.total_trades || 0;
  const pf = row?.profit_factor || 0;
  const expectancy = row?.expectancy_pct || 0;
  const minPos = consistency?.min_pos_frac || 0;
  const passRate = walkforward?.pass_rate || 0;

  const gates = {
    pf_gt_1_15: pf > 1.15,
    expectancy_gt_0: expectancy > 0,
    trades_gte_100: trades >= 100,
    min_pos_frac_gte_0_70: minPos >= 0.70,
    walkforward_pass_rate_gte_0_60: passRate >= 0.60,
  };

  const strictPass = Object.values(gates).every(Boolean);

  let status: StrategyStatusLabel = 'EXPERIMENTAL';
  let recommendation: Recommendation['recommendation'] = 'keep_experimental';
  let reason = 'Insufficient robustness for promotion gate';

  if (!row) {
    status = 'EXPERIMENTAL_DISABLED';
    recommendation = 'disable_experimental';
    reason = 'No comparison row generated (missing results)';
  } else if (pf <= 1 || expectancy <= 0) {
    status = 'EXPERIMENTAL_DISABLED';
    recommendation = 'disable_experimental';
    reason = 'Losing or non-positive expectancy';
  } else if (strictPass) {
    status = 'PROVEN';
    recommendation = 'promote_to_proven';
    reason = 'All strict gates passed';
  }

  return {
    algo_id: row?.algo_id || consistency?.algo_id || walkforward?.algo_id || 'unknown',
    status_label: status,
    recommendation,
    reason,
    gates,
    metrics: {
      trades,
      win_rate: row?.win_rate || 0,
      profit_factor: pf,
      expectancy_pct: expectancy,
      total_return_pct: row?.total_return_pct || 0,
      min_pos_frac: minPos,
      walkforward_pass_rate: passRate,
      sample_band: consistency?.sample_band || walkforward?.sample_band || 'THIN',
    },
  };
}

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 9: Recommendations + Provenance');
  log('═══════════════════════════════════════════════════════');

  ensureDir('results');

  const comparison = readJSON<ComparisonRow[]>('results/master_comparison.json') || [];
  const consistency = readJSON<Record<string, ConsistencyReportRow>>('results/consistency_report.json') || {};
  const walkforward = readJSON<Record<string, WalkforwardSummary>>('results/walkforward_report.json') || {};
  const sourceLog = readSourceRequestLog();
  const universe = readJSON<{ source: string }[]>('universe/universe_raw.json') || [];

  const comparisonByAlgo = new Map(comparison.map(row => [row.algo_id, row]));
  const recommendations: Recommendation[] = [];

  for (const algoId of CURRENT_ALGO_IDS) {
    recommendations.push(
      statusFromMetrics(
        comparisonByAlgo.get(algoId) || null,
        consistency[algoId] || null,
        walkforward[algoId] || null,
      ),
    );
  }

  recommendations.sort((a, b) => {
    if (a.status_label === b.status_label) return b.metrics.expectancy_pct - a.metrics.expectancy_pct;
    const rank = (s: StrategyStatusLabel): number => (s === 'PROVEN' ? 3 : s === 'EXPERIMENTAL' ? 2 : 1);
    return rank(b.status_label) - rank(a.status_label);
  });

  const providerCounts: Record<string, number> = {};
  const statusCounts: Record<string, number> = {};
  const providerDurations: Record<string, number> = {};
  for (const row of sourceLog) {
    providerCounts[row.provider] = (providerCounts[row.provider] || 0) + 1;
    statusCounts[row.status] = (statusCounts[row.status] || 0) + 1;
    providerDurations[row.provider] = (providerDurations[row.provider] || 0) + row.duration_ms;
  }

  const requiredProviders = ['gecko', 'dexscreener', 'jupiter', 'birdeye', 'pumpfun', 'helius'];
  const minRequestsPerProvider = Number(process.env.PROVENANCE_MIN_REQUESTS_PER_PROVIDER || 1);
  const missingProviders = requiredProviders.filter(
    (provider) => (providerCounts[provider] || 0) < minRequestsPerProvider,
  );
  const coverageComplete = sourceLog.length > 0 && missingProviders.length === 0;

  const universeSourceCounts = universe.reduce((acc, token) => {
    acc[token.source] = (acc[token.source] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const sourceCoverage = {
    generated_at: new Date().toISOString(),
    requests_total: sourceLog.length,
    coverage_complete: coverageComplete,
    required_providers: requiredProviders,
    missing_providers: missingProviders,
    min_requests_per_provider: minRequestsPerProvider,
    requests_by_provider: providerCounts,
    status_distribution: statusCounts,
    avg_duration_ms_by_provider: Object.fromEntries(
      Object.entries(providerCounts).map(([provider, count]) => [
        provider,
        count > 0 ? +(providerDurations[provider] / count).toFixed(2) : 0,
      ]),
    ),
    universe_tokens_by_source: universeSourceCounts,
  };

  const datasetHashes = {
    generated_at: new Date().toISOString(),
    files: {
      universe_raw_json: hashIfExists('universe/universe_raw.json'),
      universe_scored_json: hashIfExists('universe/universe_scored.json'),
      master_comparison_csv: hashIfExists('results/master_comparison.csv'),
      consistency_report_csv: hashIfExists('results/consistency_report.csv'),
      walkforward_report_csv: hashIfExists('results/walkforward_report.csv'),
      gate_sweep_best_json: hashIfExists('results/gate_sweep_best.json'),
      equity_sweep_best_json: hashIfExists('results/equity_sweep_best.json'),
      source_request_log_csv: hashIfExists('results/source_request_log.csv'),
      data_manifest_json: hashIfExists('results/data_manifest.json'),
    },
  };

  if (!coverageComplete) {
    for (const row of recommendations) {
      if (row.recommendation === 'promote_to_proven') {
        row.recommendation = 'keep_experimental';
        row.status_label = 'EXPERIMENTAL';
        row.reason = `Provenance coverage incomplete (missing: ${missingProviders.join(', ') || 'none'})`;
      }
    }
  }

  const promotionEligibleAfterCoverage = recommendations.filter(
    r => r.recommendation === 'promote_to_proven',
  ).map(r => r.algo_id);

  const provenanceManifest = {
    generated_at: new Date().toISOString(),
    no_synthetic_data_assertion: true,
    strict_gate: {
      profit_factor_gt: 1.15,
      expectancy_gt: 0,
      min_trades_gte: 100,
      min_pos_frac_gte: 0.70,
      walkforward_pass_rate_gte: 0.60,
    },
    run_summary: {
      strategies_total: recommendations.length,
      proven: recommendations.filter(r => r.status_label === 'PROVEN').length,
      experimental: recommendations.filter(r => r.status_label === 'EXPERIMENTAL').length,
      experimental_disabled: recommendations.filter(r => r.status_label === 'EXPERIMENTAL_DISABLED').length,
      promotion_eligible: promotionEligibleAfterCoverage,
      promotion_eligible_count: promotionEligibleAfterCoverage.length,
    },
    sources: sourceCoverage,
    dataset_hashes_ref: 'results/dataset_hashes.json',
  };

  const markdown: string[] = [];
  markdown.push('# Strategy Evidence Report');
  markdown.push('');
  markdown.push(`Generated: ${new Date().toISOString()}`);
  markdown.push('');
  markdown.push('## Gate');
  markdown.push('- Profit factor > 1.15');
  markdown.push('- Expectancy > 0');
  markdown.push('- Trades >= 100');
  markdown.push('- min_pos_frac >= 0.70');
  markdown.push('- walkforward_pass_rate >= 0.60');
  markdown.push('');
  markdown.push('## Source Coverage');
  markdown.push(`- Requests logged: ${sourceCoverage.requests_total}`);
  markdown.push(`- Coverage complete: ${sourceCoverage.coverage_complete}`);
  if (missingProviders.length > 0) {
    markdown.push(`- Missing providers: ${missingProviders.join(', ')}`);
  }
  markdown.push(`- Providers: ${Object.keys(sourceCoverage.requests_by_provider).length}`);
  for (const [provider, count] of Object.entries(sourceCoverage.requests_by_provider)) {
    markdown.push(`- ${provider}: ${count} requests`);
  }
  markdown.push('');
  markdown.push('## Strategy Status');
  markdown.push('| Algo | Status | Rec | PF | Exp% | Trades | MinPos | WF Pass | Band |');
  markdown.push('|---|---|---|---:|---:|---:|---:|---:|---|');
  for (const row of recommendations) {
    markdown.push(
      `| ${row.algo_id} | ${row.status_label} | ${row.recommendation} | ${row.metrics.profit_factor.toFixed(3)} | ` +
      `${row.metrics.expectancy_pct.toFixed(3)} | ${row.metrics.trades} | ${row.metrics.min_pos_frac.toFixed(3)} | ` +
      `${row.metrics.walkforward_pass_rate.toFixed(3)} | ${row.metrics.sample_band} |`,
    );
  }

  writeJSON('results/strategy_recommendations.json', recommendations);
  writeCSV(
    'results/strategy_recommendations.csv',
    recommendations.map(row => ({
      algo_id: row.algo_id,
      status_label: row.status_label,
      recommendation: row.recommendation,
      reason: row.reason,
      trades: row.metrics.trades,
      win_rate: row.metrics.win_rate,
      profit_factor: row.metrics.profit_factor,
      expectancy_pct: row.metrics.expectancy_pct,
      total_return_pct: row.metrics.total_return_pct,
      min_pos_frac: row.metrics.min_pos_frac,
      walkforward_pass_rate: row.metrics.walkforward_pass_rate,
      sample_band: row.metrics.sample_band,
      gate_pf_gt_1_15: row.gates.pf_gt_1_15,
      gate_expectancy_gt_0: row.gates.expectancy_gt_0,
      gate_trades_gte_100: row.gates.trades_gte_100,
      gate_min_pos_frac_gte_0_70: row.gates.min_pos_frac_gte_0_70,
      gate_walkforward_pass_rate_gte_0_60: row.gates.walkforward_pass_rate_gte_0_60,
    })),
  );
  fs.writeFileSync(dataPath('results/strategy_recommendations.md'), markdown.join('\n') + '\n', 'utf-8');
  writeJSON('results/source_coverage.json', sourceCoverage);
  writeJSON('results/dataset_hashes.json', datasetHashes);
  writeJSON('results/provenance_manifest.json', provenanceManifest);
  fs.writeFileSync(dataPath('results/evidence_report.md'), markdown.join('\n') + '\n', 'utf-8');

  log('\n✓ Phase 9 complete');
  log('  → results/strategy_recommendations.json');
  log('  → results/strategy_recommendations.md');
  log('  → results/source_coverage.json');
  log('  → results/dataset_hashes.json');
  log('  → results/provenance_manifest.json');
  log('  → results/evidence_report.md');
}

main().catch((err) => {
  logError('Fatal error in recommendations/provenance', err);
  process.exit(1);
});
