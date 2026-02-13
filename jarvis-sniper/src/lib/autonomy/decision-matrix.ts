import { STRATEGY_PRESETS } from '@/stores/useSniperStore';
import { fetchGraduations } from '@/lib/bags-api';
import type { AutonomyDecisionMatrix, AutonomyState } from './types';

const DEFAULT_WR_GATE = {
  primaryPct: 70,
  fallbackPct: 50,
  minTrades: 1000,
  method: 'wilson95_lower' as const,
  scope: 'memecoin_bags' as const,
};

function average(nums: number[]): number {
  if (nums.length === 0) return 0;
  return nums.reduce((sum, n) => sum + n, 0) / nums.length;
}

function median(nums: number[]): number {
  if (nums.length === 0) return 0;
  const arr = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(arr.length / 2);
  if (arr.length % 2 === 1) return arr[mid];
  return (arr[mid - 1] + arr[mid]) / 2;
}

function estimateInputTokens(matrix: Omit<AutonomyDecisionMatrix, 'tokenBudget'>): number {
  const bytes = Buffer.byteLength(JSON.stringify(matrix), 'utf8');
  return Math.ceil(bytes / 4);
}

function extractBaseConfig(
  row: Record<string, unknown>,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const key of [
    'stopLossPct',
    'takeProfitPct',
    'trailingStopPct',
    'minScore',
    'minLiquidityUsd',
    'slippageBps',
    'maxTokenAgeHours',
    'minMomentum1h',
    'minVolLiqRatio',
  ]) {
    const value = Number(row[key]);
    if (Number.isFinite(value)) out[key] = value;
  }
  return out;
}

function reliabilityFromState(state: AutonomyState): {
  confirmed: number;
  unresolved: number;
  failed: number;
} {
  let confirmed = 0;
  let unresolved = 0;
  let failed = 0;
  for (const artifact of Object.values(state.cycles || {})) {
    if (artifact.status === 'completed') confirmed++;
    if (artifact.status === 'pending') unresolved++;
    if (artifact.status === 'error' || artifact.status === 'noop') failed++;
  }
  return { confirmed, unresolved, failed };
}

export async function buildDecisionMatrix(args: {
  cycleId: string;
  state: AutonomyState;
}): Promise<AutonomyDecisionMatrix> {
  const generatedAt = new Date().toISOString();
  let feedRows: Array<{ liquidity: number; momentum: number; volLiq: number }> = [];
  try {
    const grads = await fetchGraduations(120);
    feedRows = grads.map((g) => {
      const liq = Number(g.liquidity || 0);
      const vol = Number(g.volume_24h || 0);
      return {
        liquidity: liq,
        momentum: Number(g.price_change_1h || 0),
        volLiq: liq > 0 ? vol / liq : 0,
      };
    });
  } catch {
    feedRows = [];
  }

  const liq = feedRows.map((r) => r.liquidity).filter((n) => Number.isFinite(n) && n >= 0);
  const mom = feedRows.map((r) => r.momentum).filter((n) => Number.isFinite(n));
  const vl = feedRows.map((r) => r.volLiq).filter((n) => Number.isFinite(n) && n >= 0);

  const base = {
    cycleId: args.cycleId,
    generatedAt,
    wrGatePolicy: DEFAULT_WR_GATE,
    strategyRows: STRATEGY_PRESETS.map((p) => ({
      strategyId: p.id,
      assetType: p.assetType || 'memecoin',
      baselineWinRateText: String(p.winRate || 'unknown'),
      baselineTrades: Number(p.trades || 0),
      baseConfig: extractBaseConfig((p.config || {}) as Record<string, unknown>),
    })),
    metrics: {
      liquidityRegime: {
        sampleSize: liq.length,
        avgLiquidityUsd: Number(average(liq).toFixed(2)),
        medianLiquidityUsd: Number(median(liq).toFixed(2)),
        avgMomentum1h: Number(average(mom).toFixed(4)),
        avgVolLiqRatio: Number(average(vl).toFixed(4)),
      },
      thompsonBeliefs: {
        availability: 'unavailable_server_scope' as const,
        reason: 'Thompson beliefs are client-side persisted in browser localStorage and not server-visible.',
        rows: [],
      },
      reliability: reliabilityFromState(args.state),
      realized: {
        totalPnlSol: 0,
        winCount: 0,
        lossCount: 0,
        tradeCount: 0,
        drawdownPct: 0,
      },
    },
  };

  const estimatedInputTokens = estimateInputTokens(base);
  return {
    ...base,
    tokenBudget: {
      maxInputTokens: Number(process.env.XAI_HOURLY_MAX_INPUT_TOKENS || 150000),
      maxOutputTokens: Number(process.env.XAI_HOURLY_MAX_OUTPUT_TOKENS || 30000),
      estimatedInputTokens,
    },
  };
}

export function buildDecisionPrompt(matrix: AutonomyDecisionMatrix): string {
  return [
    'You are an autonomous quant governance model for a Solana sniper app.',
    'Task: produce strict JSON only; choose one decision in {hold,adjust,rollback,disable_strategy}.',
    'Constraints:',
    '- Never change fields outside allowed patch keys.',
    '- Safety first: fail-closed when evidence quality is weak.',
    '- Max one strategy adjustment this cycle.',
    '',
    'Return JSON with keys:',
    'decision, reason, confidence, targets[], evidence[], constraintsCheck, alternativesConsidered',
    '',
    `Cycle: ${matrix.cycleId}`,
    `GeneratedAt: ${matrix.generatedAt}`,
    '',
    'Decision matrix:',
    JSON.stringify(matrix),
  ].join('\n');
}

export function buildSelfCritiquePrompt(matrix: AutonomyDecisionMatrix): string {
  return [
    'Review the decision process for overfitting, regime drift, and risk policy violations.',
    'Return JSON object with keys:',
    '{decision, reason, confidence, targets, evidence, constraintsCheck, alternativesConsidered}',
    'Use "hold" unless there is high-confidence evidence to change parameters.',
    `Cycle: ${matrix.cycleId}`,
    '',
    'Decision matrix:',
    JSON.stringify(matrix),
  ].join('\n');
}

