import { mkdtempSync, rmSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { describe, expect, it } from 'vitest';
import {
  appendArtifactRef,
  createCampaignLedger,
  loadCampaignLedger,
  markAttemptResult,
  markInsufficient,
  saveCampaignLedger,
  setCampaignPhase,
  upsertAttempt,
  updateStrategyProgress,
} from '@/lib/backtest-campaign-ledger';
import { aggregateRunSummaries, evaluatePromotion, scoreStrategySet } from '@/lib/backtest-campaign-scorer';

describe('backtest campaign orchestrator ledger', () => {
  it('persists and resumes campaign state with attempts and artifacts', () => {
    const root = mkdtempSync(join(tmpdir(), 'jarvis-campaign-'));
    try {
      const ledger = createCampaignLedger({
        campaignId: 'test-campaign',
        defaults: {
          strictNoSynthetic: true,
          includeEvidence: true,
          sourceTierPolicy: 'adaptive_tiered',
          targetTradesPerStrategy: 5000,
          cohort: 'baseline_90d',
          lookbackHours: 2160,
        },
        strategies: [
          {
            strategyId: 'pump_fresh_tight',
            family: 'memecoin',
            targetTrades: 5000,
            achievedTrades: 0,
            cumulativeTrades: 0,
            passes: 0,
            promoted: false,
          },
        ],
      });

      setCampaignPhase(ledger, 'baseline');
      upsertAttempt(ledger, {
        runId: 'run-1',
        strategyId: 'pump_fresh_tight',
        startedAt: new Date().toISOString(),
        status: 'running',
        sourcePolicy: 'gecko_only',
        maxTokens: 40,
        mode: 'quick',
        dataScale: 'fast',
      });
      markAttemptResult(ledger, 'run-1', 'completed');
      updateStrategyProgress(ledger, 'pump_fresh_tight', { achievedTrades: 1200, cumulativeTrades: 1200 });
      appendArtifactRef(ledger, {
        runId: 'run-1',
        evidenceRunId: 'evidence-1',
        manifestPath: '/abs/manifest.json',
      });
      saveCampaignLedger(ledger, root);

      const loaded = loadCampaignLedger('test-campaign', root);
      expect(loaded).not.toBeNull();
      expect(loaded?.phase).toBe('baseline');
      expect(loaded?.runsByStrategy.pump_fresh_tight).toContain('run-1');
      expect(loaded?.completedRunIds).toContain('run-1');
      expect(loaded?.artifactIndex[0]?.evidenceRunId).toBe('evidence-1');
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it('marks strategy as insufficient with explicit reason', () => {
    const ledger = createCampaignLedger({
      campaignId: 'test-campaign',
      defaults: {
        strictNoSynthetic: true,
        includeEvidence: true,
        sourceTierPolicy: 'adaptive_tiered',
        targetTradesPerStrategy: 5000,
        cohort: 'baseline_90d',
        lookbackHours: 2160,
      },
      strategies: [
        {
          strategyId: 'bluechip_trend_follow',
          family: 'bluechip',
          targetTrades: 5000,
          achievedTrades: 600,
          cumulativeTrades: 1200,
          passes: 2,
          promoted: false,
        },
      ],
    });

    markInsufficient(ledger, 'bluechip_trend_follow', 'Could not reach 5000 trades after expansion ladder');
    expect(ledger.insufficientStrategies).toContain('bluechip_trend_follow');
    expect(ledger.strategies[0].insufficiencyReason).toContain('5000 trades');
    expect(ledger.strategies[0].promoted).toBe(false);
  });
});

describe('backtest campaign scoring', () => {
  it('scores candidates and evaluates promotion gates', () => {
    const aggregate = aggregateRunSummaries('bags_momentum', 'bags', [
      { trades: 3000, winRate: 0.52, expectancy: 0.08, profitFactor: 1.2, maxDrawdownPct: 22, netPnl: 240, sharpe: 1.4 },
      { trades: 2500, winRate: 0.49, expectancy: 0.06, profitFactor: 1.15, maxDrawdownPct: 25, netPnl: 180, sharpe: 1.3 },
    ]);
    expect(aggregate.trades).toBe(5500);

    const ranked = scoreStrategySet([
      aggregate,
      {
        strategyId: 'bags_value',
        family: 'bags',
        trades: 5600,
        winRate: 0.43,
        expectancy: 0.01,
        profitFactor: 1.07,
        maxDrawdownPct: 39,
        netPnl: 60,
        sharpe: 0.7,
      },
    ]);
    expect(ranked.length).toBe(2);
    expect(ranked[0].compositeScore).toBeGreaterThanOrEqual(ranked[1].compositeScore);

    const decision = evaluatePromotion(aggregate);
    expect(decision.promoted).toBe(true);
  });
});

