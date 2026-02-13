import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';

export type CampaignPhase =
  | 'preflight'
  | 'smoke'
  | 'baseline'
  | 'expansion'
  | 'optimization'
  | 'promotion'
  | 'audit'
  | 'done'
  | 'failed';

export type StrategyFamily =
  | 'memecoin'
  | 'bags'
  | 'bluechip'
  | 'xstock'
  | 'prestock'
  | 'index'
  | 'unknown';

export interface StrategyCampaignEntry {
  strategyId: string;
  family: StrategyFamily;
  targetTrades: number;
  achievedTrades: number;
  cumulativeTrades: number;
  passes: number;
  promoted: boolean;
  promotionReason?: string;
  insufficiencyReason?: string;
}

export interface RunAttemptRecord {
  runId: string;
  strategyId: string;
  startedAt: string;
  endedAt?: string;
  status: 'running' | 'completed' | 'failed' | 'stalled' | 'timeout';
  sourcePolicy: 'gecko_only' | 'allow_birdeye_fallback';
  maxTokens: number;
  mode: 'quick' | 'full' | 'grid';
  dataScale: 'fast' | 'thorough';
  progress?: number;
  error?: string;
  diagnostics?: Record<string, unknown>;
}

export interface CampaignDefaults {
  strictNoSynthetic: true;
  includeEvidence: true;
  sourceTierPolicy: string;
  targetTradesPerStrategy: number;
  cohort: string;
  lookbackHours: number;
}

export interface CampaignArtifactRef {
  runId: string;
  evidenceRunId?: string;
  manifestPath?: string;
  evidencePath?: string;
  reportPath?: string;
  tradesCsvPath?: string;
}

export interface BacktestCampaignLedger {
  campaignId: string;
  startedAt: string;
  updatedAt: string;
  phase: CampaignPhase;
  defaults: CampaignDefaults;
  strategies: StrategyCampaignEntry[];
  runsByStrategy: Record<string, string[]>;
  attemptsByRunId: Record<string, RunAttemptRecord>;
  completedRunIds: string[];
  failedRunIds: string[];
  insufficientStrategies: string[];
  artifactIndex: CampaignArtifactRef[];
}

export function defaultLedgerRoot(): string {
  return join(process.cwd(), '.jarvis-cache', 'backtest-campaign');
}

export function campaignDir(campaignId: string, root = defaultLedgerRoot()): string {
  return join(root, campaignId);
}

export function campaignStatePath(campaignId: string, root = defaultLedgerRoot()): string {
  return join(campaignDir(campaignId, root), 'campaign-state.json');
}

export function ensureCampaignDir(campaignId: string, root = defaultLedgerRoot()): string {
  const dir = campaignDir(campaignId, root);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

export function createCampaignLedger(input: {
  campaignId: string;
  defaults: CampaignDefaults;
  strategies: StrategyCampaignEntry[];
}): BacktestCampaignLedger {
  const now = new Date().toISOString();
  return {
    campaignId: input.campaignId,
    startedAt: now,
    updatedAt: now,
    phase: 'preflight',
    defaults: input.defaults,
    strategies: input.strategies,
    runsByStrategy: Object.fromEntries(input.strategies.map((s) => [s.strategyId, []])),
    attemptsByRunId: {},
    completedRunIds: [],
    failedRunIds: [],
    insufficientStrategies: [],
    artifactIndex: [],
  };
}

export function saveCampaignLedger(
  ledger: BacktestCampaignLedger,
  root = defaultLedgerRoot(),
): void {
  ensureCampaignDir(ledger.campaignId, root);
  ledger.updatedAt = new Date().toISOString();
  writeFileSync(campaignStatePath(ledger.campaignId, root), JSON.stringify(ledger, null, 2), 'utf8');
}

export function loadCampaignLedger(
  campaignId: string,
  root = defaultLedgerRoot(),
): BacktestCampaignLedger | null {
  const p = campaignStatePath(campaignId, root);
  if (!existsSync(p)) return null;
  try {
    return JSON.parse(readFileSync(p, 'utf8')) as BacktestCampaignLedger;
  } catch {
    return null;
  }
}

export function upsertAttempt(
  ledger: BacktestCampaignLedger,
  attempt: RunAttemptRecord,
): BacktestCampaignLedger {
  ledger.attemptsByRunId[attempt.runId] = attempt;
  const arr = ledger.runsByStrategy[attempt.strategyId] || [];
  if (!arr.includes(attempt.runId)) {
    ledger.runsByStrategy[attempt.strategyId] = [...arr, attempt.runId];
  }
  return ledger;
}

export function markAttemptResult(
  ledger: BacktestCampaignLedger,
  runId: string,
  status: RunAttemptRecord['status'],
  extra?: Partial<RunAttemptRecord>,
): BacktestCampaignLedger {
  const attempt = ledger.attemptsByRunId[runId];
  if (!attempt) return ledger;
  attempt.status = status;
  attempt.endedAt = new Date().toISOString();
  if (extra) Object.assign(attempt, extra);
  if (status === 'completed') {
    if (!ledger.completedRunIds.includes(runId)) ledger.completedRunIds.push(runId);
    ledger.failedRunIds = ledger.failedRunIds.filter((id) => id !== runId);
  } else if (!ledger.failedRunIds.includes(runId)) {
    ledger.failedRunIds.push(runId);
  }
  return ledger;
}

export function updateStrategyProgress(
  ledger: BacktestCampaignLedger,
  strategyId: string,
  metrics: {
    achievedTrades?: number;
    cumulativeTrades?: number;
    promoted?: boolean;
    promotionReason?: string;
    insufficiencyReason?: string;
  },
): BacktestCampaignLedger {
  const entry = ledger.strategies.find((s) => s.strategyId === strategyId);
  if (!entry) return ledger;
  if (typeof metrics.achievedTrades === 'number') {
    entry.achievedTrades = Math.max(entry.achievedTrades, metrics.achievedTrades);
  }
  if (typeof metrics.cumulativeTrades === 'number') {
    entry.cumulativeTrades = metrics.cumulativeTrades;
  }
  if (typeof metrics.promoted === 'boolean') entry.promoted = metrics.promoted;
  if (typeof metrics.promotionReason === 'string') entry.promotionReason = metrics.promotionReason;
  if (typeof metrics.insufficiencyReason === 'string') entry.insufficiencyReason = metrics.insufficiencyReason;
  return ledger;
}

export function appendArtifactRef(
  ledger: BacktestCampaignLedger,
  ref: CampaignArtifactRef,
): BacktestCampaignLedger {
  const key = `${ref.runId}:${ref.evidenceRunId || ''}`;
  const seen = ledger.artifactIndex.some((a) => `${a.runId}:${a.evidenceRunId || ''}` === key);
  if (!seen) ledger.artifactIndex.push(ref);
  return ledger;
}

export function artifactRefComplete(ref: CampaignArtifactRef): boolean {
  const required = [ref.manifestPath, ref.evidencePath, ref.reportPath, ref.tradesCsvPath];
  if (required.some((p) => !p)) return false;
  return required.every((p) => existsSync(String(p)));
}

export function setCampaignPhase(
  ledger: BacktestCampaignLedger,
  phase: CampaignPhase,
): BacktestCampaignLedger {
  ledger.phase = phase;
  return ledger;
}

export function markInsufficient(
  ledger: BacktestCampaignLedger,
  strategyId: string,
  reason: string,
): BacktestCampaignLedger {
  if (!ledger.insufficientStrategies.includes(strategyId)) {
    ledger.insufficientStrategies.push(strategyId);
  }
  updateStrategyProgress(ledger, strategyId, { insufficiencyReason: reason, promoted: false });
  return ledger;
}
