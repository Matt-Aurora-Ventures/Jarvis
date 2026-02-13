import type { AutonomyState } from '@/lib/autonomy/types';

const DEFAULT_DAILY_BUDGET_USD = 10;
const DEFAULT_HOURLY_MAX_INPUT_TOKENS = 150_000;
const DEFAULT_HOURLY_MAX_OUTPUT_TOKENS = 30_000;
const DEFAULT_INPUT_COST_PER_1M = 5;
const DEFAULT_OUTPUT_COST_PER_1M = 15;

export interface XaiBudgetConfig {
  dailyBudgetUsd: number;
  hourlyMaxInputTokens: number;
  hourlyMaxOutputTokens: number;
  inputCostPer1MUsd: number;
  outputCostPer1MUsd: number;
}

export interface BudgetCheckResult {
  ok: boolean;
  reasonCode?: 'AUTONOMY_NOOP_BUDGET_CAP' | 'AUTONOMY_NOOP_ACTIVE_CYCLE_LIMIT';
  estimatedCostUsd: number;
}

function safeNum(raw: string | undefined, fallback: number): number {
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return n;
}

export function getBudgetConfig(): XaiBudgetConfig {
  return {
    dailyBudgetUsd: safeNum(process.env.XAI_DAILY_BUDGET_USD, DEFAULT_DAILY_BUDGET_USD),
    hourlyMaxInputTokens: Math.floor(
      safeNum(process.env.XAI_HOURLY_MAX_INPUT_TOKENS, DEFAULT_HOURLY_MAX_INPUT_TOKENS),
    ),
    hourlyMaxOutputTokens: Math.floor(
      safeNum(process.env.XAI_HOURLY_MAX_OUTPUT_TOKENS, DEFAULT_HOURLY_MAX_OUTPUT_TOKENS),
    ),
    inputCostPer1MUsd: safeNum(process.env.XAI_EST_INPUT_COST_PER_1M_USD, DEFAULT_INPUT_COST_PER_1M),
    outputCostPer1MUsd: safeNum(process.env.XAI_EST_OUTPUT_COST_PER_1M_USD, DEFAULT_OUTPUT_COST_PER_1M),
  };
}

function usageDateKey(isoNow: string): string {
  return isoNow.slice(0, 10);
}

export function estimateCostUsd(inputTokens: number, outputTokens: number, cfg = getBudgetConfig()): number {
  const inCost = (Math.max(0, inputTokens) / 1_000_000) * cfg.inputCostPer1MUsd;
  const outCost = (Math.max(0, outputTokens) / 1_000_000) * cfg.outputCostPer1MUsd;
  return Number((inCost + outCost).toFixed(6));
}

export function checkBudgetAndQuota(args: {
  state: AutonomyState;
  cycleId: string;
  estimatedInputTokens: number;
  estimatedOutputTokens: number;
  nowIso?: string;
}): BudgetCheckResult {
  const cfg = getBudgetConfig();
  const nowIso = args.nowIso || new Date().toISOString();
  const todayKey = usageDateKey(nowIso);
  const estInput = Math.max(0, Math.floor(args.estimatedInputTokens));
  const estOutput = Math.max(0, Math.floor(args.estimatedOutputTokens));

  if (
    args.state.pendingBatch &&
    args.state.pendingBatch.cycleId === args.cycleId
  ) {
    return {
      ok: false,
      reasonCode: 'AUTONOMY_NOOP_ACTIVE_CYCLE_LIMIT',
      estimatedCostUsd: 0,
    };
  }

  if (estInput > cfg.hourlyMaxInputTokens || estOutput > cfg.hourlyMaxOutputTokens) {
    return {
      ok: false,
      reasonCode: 'AUTONOMY_NOOP_BUDGET_CAP',
      estimatedCostUsd: estimateCostUsd(estInput, estOutput, cfg),
    };
  }

  const dayUsage = args.state.budgetUsageByDay[todayKey] || {
    estimatedCostUsd: 0,
    inputTokens: 0,
    outputTokens: 0,
    cycles: 0,
  };
  const projected = dayUsage.estimatedCostUsd + estimateCostUsd(estInput, estOutput, cfg);
  if (projected > cfg.dailyBudgetUsd) {
    return {
      ok: false,
      reasonCode: 'AUTONOMY_NOOP_BUDGET_CAP',
      estimatedCostUsd: estimateCostUsd(estInput, estOutput, cfg),
    };
  }

  return {
    ok: true,
    estimatedCostUsd: estimateCostUsd(estInput, estOutput, cfg),
  };
}

export function recordUsage(
  state: AutonomyState,
  args: {
    inputTokens: number;
    outputTokens: number;
    estimatedCostUsd?: number;
    nowIso?: string;
  },
): AutonomyState {
  const nowIso = args.nowIso || new Date().toISOString();
  const key = usageDateKey(nowIso);
  const next = { ...state, budgetUsageByDay: { ...state.budgetUsageByDay } };
  const prev = next.budgetUsageByDay[key] || {
    estimatedCostUsd: 0,
    inputTokens: 0,
    outputTokens: 0,
    cycles: 0,
  };
  const est = typeof args.estimatedCostUsd === 'number'
    ? args.estimatedCostUsd
    : estimateCostUsd(args.inputTokens, args.outputTokens);
  next.budgetUsageByDay[key] = {
    estimatedCostUsd: Number((prev.estimatedCostUsd + Math.max(0, est)).toFixed(6)),
    inputTokens: prev.inputTokens + Math.max(0, Math.floor(args.inputTokens)),
    outputTokens: prev.outputTokens + Math.max(0, Math.floor(args.outputTokens)),
    cycles: prev.cycles + 1,
  };
  next.updatedAt = nowIso;
  return next;
}

