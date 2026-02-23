#!/usr/bin/env node
import { existsSync, readdirSync, readFileSync } from 'fs';
import { join } from 'path';

const root = process.cwd();
const disallowedTerms = ['synthetic', 'random', 'simulated', 'client', 'mock'];
const promotable = new Set(['geckoterminal', 'birdeye', 'helius', 'jupiter', 'dexscreener', 'mixed']);

function normalize(v) {
  return String(v || '').trim().toLowerCase().replace(/\s+/g, '_');
}

function isDisallowedSource(v) {
  const n = normalize(v);
  if (!n) return true;
  if (promotable.has(n)) return false;
  return disallowedTerms.some((term) => n.includes(term));
}

function collectJsonFiles(dir, out = []) {
  if (!existsSync(dir)) return out;
  for (const name of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, name.name);
    if (name.isDirectory()) {
      collectJsonFiles(full, out);
      continue;
    }
    if (name.isFile() && name.name.toLowerCase().endsWith('.json')) out.push(full);
  }
  return out;
}

function scanArtifactJson(file, violations) {
  let parsed;
  try {
    parsed = JSON.parse(readFileSync(file, 'utf8'));
  } catch {
    return;
  }

  const datasets = Array.isArray(parsed?.datasets) ? parsed.datasets : [];
  for (const ds of datasets) {
    const source = ds?.source;
    if (isDisallowedSource(source)) {
      violations.push(`${file}: non-promotable dataset source "${source}"`);
    }
  }

  const summary = Array.isArray(parsed?.resultsSummary)
    ? parsed.resultsSummary
    : (Array.isArray(parsed?.results) ? parsed.results : []);

  for (const row of summary) {
    const source = row?.dataSource;
    const validated = row?.validated;
    if (isDisallowedSource(source) && validated !== false) {
      violations.push(`${file}: scored summary row uses non-promotable source "${source}"`);
    }
  }
}

function scanCodeGuards(violations) {
  const apiServer = join(root, 'core', 'api_server.py');
  const coliseum = join(root, 'core', 'trading_coliseum.py');

  if (existsSync(apiServer)) {
    const txt = readFileSync(apiServer, 'utf8');
    if (txt.includes('dexscreener_synthetic')) {
      violations.push('core/api_server.py still contains dexscreener_synthetic fallback');
    }
  }

  if (existsSync(coliseum)) {
    const txt = readFileSync(coliseum, 'utf8');
    if (txt.includes('random.uniform') && !txt.includes('validation_excluded=True')) {
      violations.push('core/trading_coliseum.py has randomized backtests without validation exclusion guard');
    }
  }
}

function main() {
  const violations = [];
  const runsDir = join(root, '.jarvis-cache', 'backtest-runs');
  const evidenceDir = join(root, '.jarvis-cache', 'backtest-evidence');

  for (const file of collectJsonFiles(runsDir)) {
    scanArtifactJson(file, violations);
  }
  for (const file of collectJsonFiles(evidenceDir)) {
    scanArtifactJson(file, violations);
  }

  scanCodeGuards(violations);

  if (violations.length > 0) {
    console.error('[real-data-guard] FAILED');
    for (const v of violations) console.error(` - ${v}`);
    process.exit(1);
  }

  console.log('[real-data-guard] PASS');
}

main();
