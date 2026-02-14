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
  addBatchRequests,
  createBatch,
  getBatch,
  getBatchResults,
  XaiApiError,
  type XaiBatchRequest,
  type XaiBatchResult,
} from '@/lib/xai/client';
import { resolveFrontierModel } from '@/lib/xai/model-policy';
import { parseAndValidateAutonomyDecision } from './decision-schema';
import { STRATEGY_PRESETS, type SniperConfig } from '@/stores/useSniperStore';

const ALLOWED_REASON_CODES = new Set([
  'AUTONOMY_NOOP_XAI_UNAVAILABLE',
  'AUTONOMY_NOOP_BUDGET_CAP',
  'AUTONOMY_NOOP_ACTIVE_CYCLE_LIMIT',
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

function buildBatchRequests(args: {
  model: string;
  cycleId: string;
  decisionPrompt: string;
  critiquePrompt: string;
}): { requestIds: [string, string]; requests: XaiBatchRequest[] } {
  const decisionId = `${args.cycleId}:decision`;
  const critiqueId = `${args.cycleId}:self_critique`;
  const decision: XaiBatchRequest = {
    batch_request_id: decisionId,
    completion_request: {
      model: args.model,
      temperature: 0.1,
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: 'Return valid JSON only.' },
        { role: 'user', content: args.decisionPrompt },
      ],
    },
  };
  const critique: XaiBatchRequest = {
    batch_request_id: critiqueId,
    completion_request: {
      model: args.model,
      temperature: 0.1,
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: 'Return valid JSON only.' },
        { role: 'user', content: args.critiquePrompt },
      ],
    },
  };

  return {
    requestIds: [decisionId, critiqueId],
    requests: [decision, critique],
  };
}

function normalizeTextContent(content: unknown): string {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === 'string') return part;
        if (part && typeof part === 'object' && typeof (part as any).text === 'string') {
          return String((part as any).text);
        }
        return '';
      })
      .filter(Boolean)
      .join('\n');
  }
  return '';
}

function extractAssistantTextFromCompletion(body: any): string {
  const direct = normalizeTextContent(body?.choices?.[0]?.message?.content);
  if (direct) return direct;

  const output0 = body?.outputs?.[0];
  const alt = normalizeTextContent(output0?.content ?? output0?.text ?? output0?.message?.content);
  if (alt) return alt;

  if (typeof body?.output_text === 'string') return body.output_text;
  return '';
}

function extractTokenUsageFromCompletion(body: any): { inputTokens: number; outputTokens: number } {
  const usage = body?.usage ?? body?.usage_total ?? null;
  const inputTokens = Number(usage?.prompt_tokens ?? usage?.input_tokens ?? 0) || 0;
  const outputTokens = Number(usage?.completion_tokens ?? usage?.output_tokens ?? 0) || 0;
  return { inputTokens, outputTokens };
}

function extractDecisionFromBatchResults(results: XaiBatchResult[], cycleId: string): {
  decisionRaw: string;
  critiqueRaw: string;
  inputTokens: number;
  outputTokens: number;
} {
  const decisionId = `${cycleId}:decision`;
  const critiqueId = `${cycleId}:self_critique`;
  let decisionRaw = '';
  let critiqueRaw = '';
  let inputTokens = 0;
  let outputTokens = 0;
  for (const result of results) {
    const id = String(result.batch_request_id || '').trim();
    if (!id) continue;

    const responseEnvelope: any = result.response;
    const completionBody = responseEnvelope?.completion_response ?? responseEnvelope ?? null;
    const text = extractAssistantTextFromCompletion(completionBody);
    const usage = extractTokenUsageFromCompletion(completionBody);
    inputTokens += usage.inputTokens;
    outputTokens += usage.outputTokens;

    if (id === decisionId) decisionRaw = text;
    if (id === critiqueId) critiqueRaw = text;
  }
  return { decisionRaw, critiqueRaw, inputTokens, outputTokens };
}

function sanitizeReasonCode(code: string): string {
  if (ALLOWED_REASON_CODES.has(code)) return code;
  return 'AUTONOMY_NOOP_XAI_UNAVAILABLE';
}

function sanitizeXaiErrorMessage(message: string): string {
  // Never leak any token/key-like substring into durable artifacts.
  return String(message || 'xAI error')
    .replace(/Incorrect API key provided:[^.]*(\\.|$)/gi, 'Incorrect API key provided (redacted).')
    .slice(0, 500);
}

function describeXaiError(err: unknown): Record<string, unknown> {
  if (err instanceof XaiApiError) {
    return {
      name: err.name,
      message: sanitizeXaiErrorMessage(err.message),
      status: err.status,
      code: err.code || null,
      correlationId: err.correlationId,
    };
  }
  if (err instanceof Error) {
    return {
      name: err.name,
      message: sanitizeXaiErrorMessage(err.message),
    };
  }
  return { message: 'Unknown xAI error' };
}

function isBatchComplete(batch: { state?: { num_pending?: number; num_requests?: number; num_success?: number; num_error?: number; num_cancelled?: number } }): boolean {
  const pending = Number(batch.state?.num_pending);
  if (Number.isFinite(pending)) {
    return pending <= 0 && Number(batch.state?.num_requests || 0) > 0;
  }
  const total = Number(batch.state?.num_requests || 0);
  if (total <= 0) return false;
  const done = Number(batch.state?.num_success || 0) + Number(batch.state?.num_error || 0) + Number(batch.state?.num_cancelled || 0);
  return done >= total;
}

async function fetchAllBatchResults(batchId: string): Promise<XaiBatchResult[]> {
  const all: XaiBatchResult[] = [];
  let token: string | undefined;
  for (let i = 0; i < 10; i++) {
    const page = await getBatchResults({ batchId, limit: 100, paginationToken: token });
    all.push(...page.results);
    if (!page.pagination_token) break;
    token = page.pagination_token;
  }
  return all;
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
    // Keep the pending batch; we’ll retry on the next hourly cycle.
    return state;
  }
  if (!isBatchComplete(batch)) {
    return state;
  }

  let results: XaiBatchResult[] = [];
  let extracted = { decisionRaw: '', critiqueRaw: '', inputTokens: 0, outputTokens: 0 };
  let fetchFailed = false;
  try {
    results = await fetchAllBatchResults(pending.batchId);
    extracted = extractDecisionFromBatchResults(results, pending.cycleId);
  } catch {
    fetchFailed = true;
  }

  const validated = fetchFailed
    ? { ok: false as const, decision: null, rawJson: null, errors: ['xAI batch results fetch failed'] }
    : parseAndValidateAutonomyDecision(extracted.decisionRaw);
  const critiqueValidated = fetchFailed
    ? { ok: false as const, decision: null, rawJson: null, errors: ['xAI batch results fetch failed'] }
    : parseAndValidateAutonomyDecision(extracted.critiqueRaw);

  let reasonCode = 'AUTONOMY_COMPLETED';
  let status: 'completed' | 'noop' = 'completed';
  let currentSnapshot = await getStrategyOverrideSnapshot();
  if (!currentSnapshot) currentSnapshot = emptyOverrideSnapshot();

  if (fetchFailed) {
    reasonCode = 'AUTONOMY_NOOP_XAI_UNAVAILABLE';
    status = 'noop';
  } else if (!validated.ok || !validated.decision) {
    reasonCode = 'AUTONOMY_NOOP_SCHEMA_INVALID';
    status = 'noop';
  } else if (!validated.decision.constraintsCheck.pass) {
    reasonCode = 'AUTONOMY_NOOP_CONSTRAINT_BLOCK';
    status = 'noop';
  }

  let nextSnapshot = currentSnapshot;
  const effectiveDecision = validated.decision || makeNoopDecision(fetchFailed ? 'xAI batch results fetch failed' : 'Schema validation failed');
  if (status === 'completed' && isAutonomyEnabled()) {
    const canApply = isApplyOverridesEnabled();
    if (effectiveDecision.decision === 'rollback') {
      if (!canApply) {
        reasonCode = 'AUTONOMY_NOOP_APPLY_DISABLED';
        status = 'noop';
      }
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
      if (canApply) await saveStrategyOverrideSnapshot(nextSnapshot);
    } else if (effectiveDecision.decision === 'adjust' || effectiveDecision.decision === 'disable_strategy') {
      if (!canApply) {
        reasonCode = 'AUTONOMY_NOOP_APPLY_DISABLED';
        status = 'noop';
      }
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
      if (canApply) await saveStrategyOverrideSnapshot(nextSnapshot);
    }
  } else if (!isAutonomyEnabled()) {
    reasonCode = 'AUTONOMY_NOOP_DISABLED';
    status = 'noop';
  }

  const reportMarkdown = summarizeDecision(effectiveDecision, reasonCode, status, nextSnapshot);
  const responsePayload = {
    cycleId: pending.cycleId,
    batchId: pending.batchId,
    batchState: batch.state || null,
    resultCount: results.length,
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

  const baseNoop = async (
    reasonCodeRaw: string,
    extraResponse: Record<string, unknown> = {},
  ): Promise<AutonomyState> => {
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
        ...extraResponse,
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

  let frontier: Awaited<ReturnType<typeof resolveFrontierModel>> | null = null;
  try {
    frontier = await resolveFrontierModel();
  } catch (err) {
    return baseNoop('AUTONOMY_NOOP_XAI_UNAVAILABLE', { xaiError: describeXaiError(err) });
  }
  if (!frontier?.ok || !frontier.selectedModel) {
    return baseNoop('AUTONOMY_NOOP_MODEL_POLICY_FAIL');
  }

  const decisionPrompt = buildDecisionPrompt(matrix);
  const critiquePrompt = buildSelfCritiquePrompt(matrix);
  const batchRequests = buildBatchRequests({
    model: frontier.selectedModel,
    cycleId,
    decisionPrompt,
    critiquePrompt,
  });
  const batchName = `jarvis_autonomy_${cycleId}`;

  let batchId = '';
  try {
    batchId = await createBatch(batchName);
    await addBatchRequests(batchId, batchRequests.requests);
  } catch (err) {
    return baseNoop('AUTONOMY_NOOP_XAI_UNAVAILABLE', { xaiError: describeXaiError(err) });
  }

  const pendingState = {
    ...state,
    latestCycleId: cycleId,
    pendingBatch: {
      cycleId,
      batchId,
      batchName,
      requestIds: batchRequests.requestIds,
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
      batchName,
      requestIds: batchRequests.requestIds,
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
