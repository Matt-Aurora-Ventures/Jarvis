import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { describe, expect, it } from 'vitest';
import { artifactRefComplete } from '@/lib/backtest-campaign-ledger';

describe('backtest artifact integrity', () => {
  it('requires manifest, evidence, report, and trades csv', () => {
    const root = mkdtempSync(join(tmpdir(), 'jarvis-artifacts-'));
    try {
      const runDir = join(root, 'run-1');
      const manifestPath = join(runDir, 'manifest.json');
      const evidencePath = join(runDir, 'evidence.json');
      const reportPath = join(runDir, 'report.md');
      const tradesCsvPath = join(runDir, 'trades.csv');

      // create all files
      mkdirSync(runDir, { recursive: true });
      writeFileSync(manifestPath, '{"ok":true}', 'utf8');
      writeFileSync(evidencePath, '{"ok":true}', 'utf8');
      writeFileSync(reportPath, '# Report', 'utf8');
      writeFileSync(tradesCsvPath, 'a,b\n1,2\n', 'utf8');

      expect(
        artifactRefComplete({
          runId: 'run-1',
          evidenceRunId: 'ev-1',
          manifestPath,
          evidencePath,
          reportPath,
          tradesCsvPath,
        }),
      ).toBe(true);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it('fails integrity when any required artifact path is missing', () => {
    expect(
      artifactRefComplete({
        runId: 'run-2',
        manifestPath: '/tmp/missing-manifest.json',
        evidencePath: '/tmp/missing-evidence.json',
        reportPath: '/tmp/missing-report.md',
      }),
    ).toBe(false);
  });
});
