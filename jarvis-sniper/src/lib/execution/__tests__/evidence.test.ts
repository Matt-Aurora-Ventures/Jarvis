import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mkdtempSync, rmSync } from 'fs';
import { join } from 'path';
import os from 'os';
import type { TradeEvidenceV2 } from '@/lib/data-plane/types';

function mkEvidence(partial: Partial<TradeEvidenceV2> & { tradeId: string }): TradeEvidenceV2 {
  return {
    tradeId: partial.tradeId,
    surface: partial.surface || 'bags',
    strategyId: partial.strategyId || 'strat-a',
    decisionTs: partial.decisionTs || new Date().toISOString(),
    route: partial.route || 'bags_sdk_proxy',
    expectedPrice: partial.expectedPrice ?? null,
    executedPrice: partial.executedPrice ?? null,
    slippageBps: partial.slippageBps ?? null,
    priorityFeeLamports: partial.priorityFeeLamports ?? null,
    jitoUsed: partial.jitoUsed ?? false,
    mevRiskTag: partial.mevRiskTag || 'unknown',
    datasetRefs: partial.datasetRefs || [],
    outcome: partial.outcome || 'unresolved',
    metadata: partial.metadata,
  };
}

describe('execution evidence store', () => {
  const originalCwd = process.cwd();
  let tempCwd = '';

  beforeEach(() => {
    vi.resetModules();
    tempCwd = mkdtempSync(join(os.tmpdir(), 'jarvis-evidence-'));
    process.chdir(tempCwd);
    delete process.env.DATA_PLANE_AUDIT_BUCKET;
    delete process.env.AUTONOMY_AUDIT_BUCKET;
    process.env.DATA_PLANE_FIRESTORE_ENABLED = 'false';
  });

  afterEach(() => {
    process.chdir(originalCwd);
    if (tempCwd) rmSync(tempCwd, { recursive: true, force: true });
  });

  it('upserts and retrieves trade evidence by tradeId', async () => {
    const mod = await import('@/lib/execution/evidence');
    const row = mkEvidence({
      tradeId: 'trade-abc',
      outcome: 'confirmed',
      slippageBps: 7,
      priorityFeeLamports: 1200,
    });

    await mod.upsertTradeEvidence(row);
    const found = mod.getTradeEvidence('trade-abc');

    expect(found).toBeTruthy();
    expect(found?.tradeId).toBe('trade-abc');
    expect(found?.outcome).toBe('confirmed');
    expect(found?.slippageBps).toBe(7);
  });

  it('summarizes slippage and outcome counts with filters', async () => {
    const mod = await import('@/lib/execution/evidence');
    await mod.upsertTradeEvidence(mkEvidence({ tradeId: 't1', surface: 'bags', strategyId: 's1', slippageBps: 2, outcome: 'confirmed' }));
    await mod.upsertTradeEvidence(mkEvidence({ tradeId: 't2', surface: 'bags', strategyId: 's1', slippageBps: 4, outcome: 'failed' }));
    await mod.upsertTradeEvidence(mkEvidence({ tradeId: 't3', surface: 'bags', strategyId: 's1', slippageBps: 8, outcome: 'confirmed' }));
    await mod.upsertTradeEvidence(mkEvidence({ tradeId: 't4', surface: 'main', strategyId: 's2', slippageBps: 30, outcome: 'confirmed' }));

    const filtered = mod.summarizeTradeEvidence({ surface: 'bags', strategyId: 's1' });

    expect(filtered.count).toBe(3);
    expect(filtered.medianSlippageBps).toBe(4);
    expect(filtered.p95SlippageBps).toBe(4);
    expect(filtered.byOutcome).toEqual(expect.objectContaining({ confirmed: 2, failed: 1 }));
  });
});
