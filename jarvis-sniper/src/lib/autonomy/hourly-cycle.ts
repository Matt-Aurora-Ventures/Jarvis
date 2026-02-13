import { createHash } from 'crypto';
import {
  buildDecisionMatrix,
  buildDecisionPrompt,
  buildSelfCritiquePrompt,
} from './decision-matrix';
import {
  loadAutonomyState,
  readAuditBundle,
  saveAutonomyState,
  writeHourlyArtifact,
} from './audit-store';
import { getStrategyOverrideSnapshot, saveStrategyOverrideSnapshot } from './override-store';
import {
  applyOverrideDecision,
  emptyOverrideSnapshot,
  normalizePatchAgainstBase,
} from './override-policy';
import type {
  AutonomyDecision,
  AutonomyState,
  StrategyOverridePatch,
  StrategyOverrideSnapshot,
} from './types';
import { checkBudgetAndQuota, recordUsage } from '@/lib/xai/budget-rate';
import {
  createBatch,
  getBatch,
  getFileContent,
  uploadBatchInputFile,
} from '@/lib/xai/client';
import { resolveFrontierModel } from '@/lib/xai/model-policy';
import { parseAndValidateAutonomyDecision } from './decision-schema';
import { STRATEGY_PRESETS, type SniperConfig } from '@/stores/useSniperStore';

const ALLOWED_REASON_CODES = new Set([
  'AUTONOMY_NOOP_XAI_UNAVAILABLE',
  'AUTONOMY_NOOP_BUDGET_CAP',
  'AUTONOMY_NOOP_MODEL_POLICY_FAIL',
  'AUTONOMY_NOOP_SCHEMA_INVALID',
  'AUTONOMY_NOOP_CONSTRAINT_BLOCK',
  'AUTONOMY_NOOP_APPLY_DISABLED',
  'AUTONOMY_NOOP_DISABLED',
  'AUTONOMY_PENDING_BATCH',
  'AUTONOMY_COMPLETED',
]);

function hashText(text: string): string {
  return createHash('sha256').update(text).digest('hex');
}

function cycleIdFrom(date = new Date()): string {
  const y = date.getUTCFullYear().toString().padStart(4, '0');
  const m = String(date.getUTCMonth() + 1).padStart(2, '0');
  const d = String(date.getUTCDate()).padStart(2, '0');
  const h = String(date.getUTCHours()).padStart(2, '0');
  return `${y}${m}${d}${h}`;
}

function previousCycleId(current: string): string {
  const y = Number(current.slice(0, 4));
  const m = Number(current.slice(4, 6)) - 1;
  const d = Number(current.slice(6, 8));
  const h = Number(current.slice(8, 10));
  const prev = new Date(Date.UTC(y, m, d, h));
  prev.setUTCHours(prev.getUTCHours() - 1);
  return cycleIdFrom(prev);
}

function maxAdjustmentsPerCycle(): number {
  const n = Number(process.env.AUTONOMY_MAX_ADJUSTMENTS_PER_CYCLE || 1);
  if (!Number.isFinite(n) || n < 1) return 1;
  return Math.floor(n);
}

function isAutonomyEnabled(): boolean {
  return String(process.env.AUTONOMY_ENABLED || 'false').toLowerCase() === 'true';
}

function isApplyOverridesEnabled(): boolean {
  return String(process.env.AUTONOMY_APPLY_OVERRIDES || 'false').toLowerCase() === 'true';
}

function isBatchEnabled(): boolean {
  return String(process.env.XAI_BATCH_ENABLED || 'false').toLowerCase() === 'true';
}

function isXaiConfigured(): boolean {
  return String(process.env.XAI_API_KEY || '').trim().length > 0;
}

function baseConfigForStrategy(strategyId: string): SniperConfig {
  const fallback = {
    stopLossPct: 20,
    takeProfitPct: 80,
    trailingStopPct: 8,
    minScore: 0,
    minLiquidityUsd: 25000,
    slippageBps: 150,
    maxTokenAgeHours: 200,
    minMomentum1h: 5,
    minVolLiqRatio: 1.0,
  };
  const preset = STRATEGY_PRESETS.find((s) => s.id === strategyId);
  return {
    ...(fallback as unknown as SniperConfig),
    ...((preset?.config || {}) as Partial<SniperConfig>),
  } as SniperConfig;
}

function summarizeDecision(
  decision: AutonomyDecision,
  reasonCode: string,
  status: 'completed' | 'noop' | 'pending' | 'error',
  overrides: StrategyOverrideSnapshot | null,
): string {
  const lines: string[] = [];
  lines.push(`# Autonomy Decision Report — ${new Date().toISOString()}`);
  lines.push('');
  lines.push(`- Status: ${status}`);
  lines.push(`- ReasonCode: ${reasonCode}`);
  lines.push(`- Decision: ${decision.decision}`);
  lines.push(`- Confidence: ${decision.confidence}`);
  lines.push(`- Summary: ${decision.reason}`);
  lines.push('');
  lines.push('## Constraint Check');
  lines.push(`- Pass: ${decision.constraintsCheck.pass ? 'yes' : 'no'}`);
  for (const reason of decision.constraintsCheck.reasons) lines.push(`- ${reason}`);
  lines.push('');
  lines.push('## Targets');
  if (!decision.targets.length) {
    lines.push('- (none)');
  } else {
    for (const target of decision.targets) {
      lines.push(`- ${target.strategyId}: ${target.reason} (confidence=${target.confidence})`);
      const patch = target.patch || {};
      for (const [k, v] of Object.entries(patch)) {
        lines.push(`  - ${k}: ${v}`);
      }
    }
  }
  lines.push('');
  lines.push('## Alternatives Considered');
  if (!decision.alternativesConsidered.length) {
    lines.push('- (none)');
  } else {
    for (const alt of decision.alternativesConsidered) {
      lines.push(`- ${alt.option}: ${alt.rejectedBecause}`);
    }
  }
  lines.push('');
  lines.push('## Applied Override Snapshot');
  if (!overrides) {
    lines.push('- none');
  } else {
    lines.push(`- version: ${overrides.version}`);
    lines.push(`- cycleId: ${overrides.cycleId}`);
    lines.push(`- patchCount: ${overrides.patches.length}`);
    lines.push(`- signature: ${overrides.signature}`);
  }
  return lines.join('\n');
}

function makeNoopDecision(reason: string): AutonomyDecision {
  return {
    decision: 'hold',
    reason,
    confidence: 0,
    targets: [],
    evidence: [],
    constraintsCheck: {
      pass: false,
      reasons: [reason],
    },
    alternativesConsidered: [
      { option: 'adjust', rejectedBecause: reason },
    ],
  };
}

function buildBatchJsonl(args: {
  model: string;
  cycleId: string;
  decisionPrompt: string;
  critiquePrompt: string;
}): string {
  const rows = [
    {
      custom_id: `${args.cycleId}:decision`,
      method: 'POST',
      url: '/v1/chat/completions',
      body: {
        model: args.model,
        temperature: 0.1,
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: 'Return valid JSON only.' },
          { role: 'user', content: args.decisionPrompt },
        ],
      },
    },
    {
      custom_id: `${args.cycleId}:self_critique`,
      method: 'POST',
      url: '/v1/chat/completions',
      body: {
        model: args.model,
        temperature: 0.1,
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: 'Return valid JSON only.' },
          { role: 'user', content: args.critiquePrompt },
        ],
      },
    },
  ];
  return rows.map((row) => JSON.stringify(row)).join('\n');
}

function extractDecisionFromBatchOutput(raw: string, cycleId: string): {
  decisionRaw: string;
  critiqueRaw: string;
  inputTokens: number;
  outputTokens: number;
} {
  const lines = raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  let decisionRaw = '';
  let critiqueRaw = '';
  let inputTokens = 0;
  let outputTokens = 0;
  for (const line of lines) {
    let parsed: any = null;
    try {
      parsed = JSON.parse(line);
    } catch {
      continue;
    }
    const customId = String(parsed.custom_id || '');
    const content = parsed?.response?.body?.choices?.[0]?.message?.content;
    const usage = parsed?.response?.body?.usage || {};
    inputTokens += Number(usage.prompt_tokens || 0);
    outputTokens += Number(usage.completion_tokens || 0);
    const text = typeof content === 'string'
      ? content
      : Array.isArray(content)
        ? content.map((c: any) => (typeof c?.text === 'string' ? c.text : '')).join('\n')
        : '';
    if (customId === `${cycleId}:decision`) decisionRaw = text;
    if (customId === `${cycleId}:self_critique`) critiqueRaw = text;
  }
  return { decisionRaw, critiqueRaw, inputTokens, outputTokens };
}

function sanitizeReasonCode(code: string): string {
  if (ALLOWED_REASON_CODES.has(code)) return code;
  return 'AUTONOMY_NOOP_XAI_UNAVAILABLE';
}

async function persistCycleArtifacts(args: {
  cycleId: string;
  matrix: unknown;
  response: unknown;
  reportMarkdown: string;
  appliedOverrides: unknown;
}): Promise<{ matrixHash: string; responseHash: string; decisionHash: string }> {
  const matrixWrite = await writeHourlyArtifact({
    cycleId: args.cycleId,
    fileName: 'decision-matrix.json',
    content: args.matrix,
  });
  const responseWrite = await writeHourlyArtifact({
    cycleId: args.cycleId,
    fileName: 'decision-response.json',
    content: args.response,
  });
  await writeHourlyArtifact({
    cycleId: args.cycleId,
    fileName: 'decision-report.md',
    content: args.reportMarkdown,
  });
  const decisionWrite = await writeHourlyArtifact({
    cycleId: args.cycleId,
    fileName: 'applied-overrides.json',
    content: args.appliedOverrides,
  });
  return {
    matrixHash: matrixWrite.sha256,
    responseHash: responseWrite.sha256,
    decisionHash: decisionWrite.sha256,
  };
}

async function finalizePriorPendingBatch(state: AutonomyState, currentCycleId: string): Promise<AutonomyState> {
  const pending = state.pendingBatch;
  if (!pending) return state;
  if (pending.cycleId === currentCycleId) return state;

  let batch: Awaited<ReturnType<typeof getBatch>>;
  try {
    batch = await getBatch(pending.batchId);
  } catch {
    // Keep pending; we'll try finalization on the next cycle.
    return state;
  }
  if (batch.status !== 'completed') {
    return state;
  }

  let outputText = '';
  try {
    outputText = batch.output_file_id ? await getFileContent(batch.output_file_id) : '';
  } catch {
    // If output fetch fails, keep pending and retry next cycle.
    return state;
  }
  const extracted = extractDecisionFromBatchOutput(outputText, pending.cycleId);
  const validated = parseAndValidateAutonomyDecision(extracted.decisionRaw);
  const critiqueValidated = parseAndValidateAutonomyDecision(extracted.critiqueRaw);

  let reasonCode = 'AUTONOMY_COMPLETED';
  let status: 'completed' | 'noop' = 'completed';
  let currentSnapshot = await getStrategyOverrideSnapshot();
  if (!currentSnapshot) currentSnapshot = emptyOverrideSnapshot();

  if (!validated.ok || !validated.decision) {
    reasonCode = 'AUTONOMY_NOOP_SCHEMA_INVALID';
    status = 'noop';
  } else if (!validated.decision.constraintsCheck.pass) {
    reasonCode = 'AUTONOMY_NOOP_CONSTRAINT_BLOCK';
    status = 'noop';
  }

  let nextSnapshot = currentSnapshot;
  const effectiveDecision = validated.decision || makeNoopDecision('Schema validation failed');
  const applyEnabled = isApplyOverridesEnabled();
  const decisionWantsChanges = effectiveDecision.decision !== 'hold';
  if (status === 'completed' && isAutonomyEnabled() && decisionWantsChanges && !applyEnabled) {
    // Audit-only mode: write artifacts, but do not apply/commit runtime overrides.
    reasonCode = 'AUTONOMY_NOOP_APPLY_DISABLED';
  } else if (status === 'completed' && isAutonomyEnabled()) {
    if (effectiveDecision.decision === 'rollback') {
      const targets = new Set(
        effectiveDecision.targets.map((t) => t.strategyId).filter(Boolean),
      );
      const nextPatches = targets.size === 0
        ? []
        : currentSnapshot.patches.filter((p) => !targets.has(p.strategyId));
      nextSnapshot = applyOverrideDecision(currentSnapshot, {
        cycleId: pending.cycleId,
        patches: nextPatches,
      });
      await saveStrategyOverrideSnapshot(nextSnapshot);
    } else if (effectiveDecision.decision === 'adjust' || effectiveDecision.decision === 'disable_strategy') {
      const allowedTargets = effectiveDecision.targets.slice(0, maxAdjustmentsPerCycle());
      const map = new Map(currentSnapshot.patches.map((p) => [p.strategyId, p] as const));
      const nextPatches: StrategyOverridePatch[] = [];

      for (const target of allowedTargets) {
        const strategyId = String(target.strategyId || '').trim();
        if (!strategyId) continue;
        const rawPatch = target.patch || {};
        if (effectiveDecision.decision === 'disable_strategy' && !('minScore' in rawPatch)) {
          (rawPatch as Record<string, number>).minScore = 100;
        }
        const normalized = normalizePatchAgainstBase(baseConfigForStrategy(strategyId), rawPatch);
        if (Object.keys(normalized.patch).length === 0) continue;
        nextPatches.push({
          strategyId,
          patch: normalized.patch,
          reason: target.reason || effectiveDecision.reason,
          confidence: target.confidence || effectiveDecision.confidence,
          evidence: [...new Set([...(target.evidence || []), ...(normalized.violations || [])])],
          sourceCycleId: pending.cycleId,
          decidedAt: new Date().toISOString(),
        });
      }

      for (const patch of nextPatches) {
        map.set(patch.strategyId, patch);
      }
      nextSnapshot = applyOverrideDecision(currentSnapshot, {
        cycleId: pending.cycleId,
        patches: [...map.values()],
      });
      await saveStrategyOverrideSnapshot(nextSnapshot);
    }
  } else if (!isAutonomyEnabled()) {
    reasonCode = 'AUTONOMY_NOOP_DISABLED';
    status = 'noop';
  }

  const reportMarkdown = summarizeDecision(effectiveDecision, reasonCode, status, nextSnapshot);
  const responsePayload = {
    cycleId: pending.cycleId,
    batchId: pending.batchId,
    outputFileId: batch.output_file_id || null,
    decisionValid: validated.ok,
    critiqueValid: critiqueValidated.ok,
    decisionErrors: validated.errors,
    critiqueErrors: critiqueValidated.errors,
    decisionRawJson: validated.rawJson,
    critiqueRawJson: critiqueValidated.rawJson,
    reasonCode,
  };

  const hashes = await persistCycleArtifacts({
    cycleId: pending.cycleId,
    matrix: pending.matrix,
    response: responsePayload,
    reportMarkdown,
    appliedOverrides: nextSnapshot,
  });

  const nextState = {
    ...state,
    pendingBatch: undefined,
    latestCompletedCycleId: pending.cycleId,
    cycles: {
      ...state.cycles,
      [pending.cycleId]: {
        ...(state.cycles[pending.cycleId] || {
          cycleId: pending.cycleId,
          createdAt: pending.submittedAt,
        }),
        cycleId: pending.cycleId,
        status,
        reasonCode,
        updatedAt: new Date().toISOString(),
        batchId: pending.batchId,
        inputFileId: pending.inputFileId,
        outputFileId: batch.output_file_id || undefined,
        matrixHash: hashes.matrixHash,
        responseHash: hashes.responseHash,
        decisionHash: hashes.decisionHash,
        appliedOverrideVersion: nextSnapshot.version,
      },
    },
  } satisfies AutonomyState;

  return recordUsage(nextState, {
    inputTokens: extracted.inputTokens,
    outputTokens: extracted.outputTokens,
    nowIso: new Date().toISOString(),
  });
}

async function submitCurrentCycle(state: AutonomyState, cycleId: string): Promise<AutonomyState> {
  if (state.cycles[cycleId] && state.cycles[cycleId].status === 'pending') {
    return state;
  }

  const matrix = await buildDecisionMatrix({ cycleId, state });
  const matrixJson = JSON.stringify(matrix);
  const matrixHash = hashText(matrixJson);

  const baseNoop = async (reasonCodeRaw: string): Promise<AutonomyState> => {
    const reasonCode = sanitizeReasonCode(reasonCodeRaw);
    const decision = makeNoopDecision(reasonCode);
    const reportMd = summarizeDecision(decision, reasonCode, 'noop', await getStrategyOverrideSnapshot());
    const hashes = await persistCycleArtifacts({
      cycleId,
      matrix,
      response: {
        cycleId,
        status: 'noop',
        reasonCode,
      },
      reportMarkdown: reportMd,
      appliedOverrides: await getStrategyOverrideSnapshot(),
    });
    return {
      ...state,
      latestCycleId: cycleId,
      cycles: {
        ...state.cycles,
        [cycleId]: {
          cycleId,
          status: 'noop',
          reasonCode,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          matrixHash: hashes.matrixHash,
          responseHash: hashes.responseHash,
          decisionHash: hashes.decisionHash,
        },
      },
    };
  };

  if (!isAutonomyEnabled()) return baseNoop('AUTONOMY_NOOP_DISABLED');
  if (!isBatchEnabled() || !isXaiConfigured()) return baseNoop('AUTONOMY_NOOP_XAI_UNAVAILABLE');

  const budget = checkBudgetAndQuota({
    state,
    cycleId,
    estimatedInputTokens: matrix.tokenBudget.estimatedInputTokens,
    estimatedOutputTokens: matrix.tokenBudget.maxOutputTokens,
  });
  if (!budget.ok) {
    return baseNoop(budget.reasonCode || 'AUTONOMY_NOOP_BUDGET_CAP');
  }

  let frontier: Awaited<ReturnType<typeof resolveFrontierModel>>;
  try {
    frontier = await resolveFrontierModel();
  } catch {
    return baseNoop('AUTONOMY_NOOP_XAI_UNAVAILABLE');
  }
  if (!frontier.ok || !frontier.selectedModel) {
    return baseNoop('AUTONOMY_NOOP_MODEL_POLICY_FAIL');
  }

  const batchJsonl = buildBatchJsonl({
    model: frontier.selectedModel,
    cycleId,
    decisionPrompt: buildDecisionPrompt(matrix),
    critiquePrompt: buildSelfCritiquePrompt(matrix),
  });

  let inputFileId = '';
  let batchId = '';
  try {
    inputFileId = await uploadBatchInputFile(batchJsonl);
    batchId = await createBatch(inputFileId, '/v1/chat/completions', '24h');
  } catch {
    return baseNoop('AUTONOMY_NOOP_XAI_UNAVAILABLE');
  }

  const pendingState = {
    ...state,
    latestCycleId: cycleId,
    pendingBatch: {
      cycleId,
      batchId,
      inputFileId,
      model: frontier.selectedModel,
      submittedAt: new Date().toISOString(),
      matrix,
      matrixHash,
    },
    cycles: {
      ...state.cycles,
      [cycleId]: {
        cycleId,
        status: 'pending',
        reasonCode: 'AUTONOMY_PENDING_BATCH',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        batchId,
        inputFileId,
        matrixHash,
      },
    },
  } satisfies AutonomyState;

  const withUsage = recordUsage(pendingState, {
    inputTokens: matrix.tokenBudget.estimatedInputTokens,
    outputTokens: matrix.tokenBudget.maxOutputTokens,
    estimatedCostUsd: budget.estimatedCostUsd,
  });

  const reportMd = summarizeDecision(
    makeNoopDecision('Batch submitted and pending completion'),
    'AUTONOMY_PENDING_BATCH',
    'pending',
    await getStrategyOverrideSnapshot(),
  );
  const hashes = await persistCycleArtifacts({
    cycleId,
    matrix,
    response: {
      cycleId,
      status: 'pending',
      reasonCode: 'AUTONOMY_PENDING_BATCH',
      batchId,
      inputFileId,
      model: frontier.selectedModel,
      frontierPolicy: frontier,
    },
    reportMarkdown: reportMd,
    appliedOverrides: await getStrategyOverrideSnapshot(),
  });
  withUsage.cycles[cycleId] = {
    ...withUsage.cycles[cycleId],
    responseHash: hashes.responseHash,
    decisionHash: hashes.decisionHash,
  };
  return withUsage;
}

export async function runHourlyAutonomyCycle(): Promise<{
  ok: boolean;
  cycleId: string;
  reasonCode?: string;
  state: AutonomyState;
}> {
  const cycleId = cycleIdFrom(new Date());
  const prevCycleId = previousCycleId(cycleId);
  let state = await loadAutonomyState();
  state = await finalizePriorPendingBatch(state, cycleId);

  if (state.cycles[cycleId]) {
    await saveAutonomyState(state);
    return {
      ok: true,
      cycleId,
      reasonCode: state.cycles[cycleId].reasonCode,
      state,
    };
  }

  if (state.pendingBatch && state.pendingBatch.cycleId !== prevCycleId) {
    // Only allow one unresolved carry-over cycle; if older, mark as noop and continue.
    state.pendingBatch = undefined;
  }

  state = await submitCurrentCycle(state, cycleId);
  await saveAutonomyState(state);
  return {
    ok: true,
    cycleId,
    reasonCode: state.cycles[cycleId]?.reasonCode,
    state,
  };
}

export async function getLatestAuditBundle() {
  const state = await loadAutonomyState();
  const cycleId = state.latestCompletedCycleId || state.latestCycleId;
  if (!cycleId) {
    return {
      cycleId: null,
      bundle: null,
      state,
    };
  }
  return {
    cycleId,
    bundle: await readAuditBundle(cycleId),
    state,
  };
}
