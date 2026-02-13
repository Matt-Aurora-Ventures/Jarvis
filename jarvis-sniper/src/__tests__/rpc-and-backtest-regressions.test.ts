import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'fs';
import { join } from 'path';
import {
  createBacktestRunStatus,
  getBacktestRunStatus,
  heartbeatBacktestRun,
} from '@/lib/backtest-run-registry';

function listFilesRecursive(root: string): string[] {
  const out: string[] = [];
  const stack = [root];
  while (stack.length > 0) {
    const cur = stack.pop()!;
    for (const entry of readdirSync(cur)) {
      const full = join(cur, entry);
      const st = statSync(full);
      if (st.isDirectory()) {
        if (entry === '.next' || entry === 'node_modules') continue;
        stack.push(full);
      } else {
        out.push(full);
      }
    }
  }
  return out;
}

describe('rpc-url runtime safety', () => {
  it('returns absolute browser URL for web3 Connection compatibility', async () => {
    const previousWindow = (globalThis as any).window;
    Object.defineProperty(globalThis, 'window', {
      value: { location: { origin: 'http://127.0.0.1:3001' } },
      configurable: true,
      writable: true,
    });
    try {
      const { getRpcUrl } = await import('@/lib/rpc-url');
      expect(getRpcUrl()).toBe('http://127.0.0.1:3001/api/rpc');
      expect(getRpcUrl().startsWith('http://') || getRpcUrl().startsWith('https://')).toBe(true);
    } finally {
      Object.defineProperty(globalThis, 'window', {
        value: previousWindow,
        configurable: true,
        writable: true,
      });
    }
  });
});

describe('no relative RPC Connection regression', () => {
  it('contains no new Connection("/api/rpc") literal usage in src', () => {
    const srcRoot = join(process.cwd(), 'src');
    const files = listFilesRecursive(srcRoot)
      .filter((f) => /\.(ts|tsx)$/.test(f))
      .filter((f) => !f.endsWith('rpc-and-backtest-regressions.test.ts'));
    const banned = [
      /new\s+Connection\(\s*['"]\/api\/rpc['"]/g,
      /const\s+RPC_URL\s*=\s*['"]\/api\/rpc['"]/g,
    ];
    const offenders: string[] = [];

    for (const file of files) {
      const text = readFileSync(file, 'utf8');
      if (banned.some((r) => r.test(text))) offenders.push(file);
    }

    expect(offenders).toEqual([]);
  });
});

describe('backtest run heartbeat', () => {
  it('updates heartbeat and activity in run status', () => {
    const runId = `test-heartbeat-${Date.now()}`;
    createBacktestRunStatus({
      runId,
      strategyIds: ['bluechip_trend_follow'],
      strictNoSynthetic: true,
      targetTradesPerStrategy: 5000,
      sourceTierPolicy: 'adaptive_tiered',
      cohort: 'baseline_90d',
    });

    const before = getBacktestRunStatus(runId);
    expect(before).not.toBeNull();
    const beforeUpdatedAt = before!.updatedAt;

    heartbeatBacktestRun(runId, 'Testing heartbeat activity');
    const after = getBacktestRunStatus(runId);
    expect(after).not.toBeNull();
    expect(after!.currentActivity).toBe('Testing heartbeat activity');
    expect(typeof after!.heartbeatAt).toBe('number');
    expect(after!.updatedAt).toBeGreaterThanOrEqual(beforeUpdatedAt);
  });
});
