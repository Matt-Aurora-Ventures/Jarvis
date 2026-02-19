export type DataPlaneSource =
  | 'geckoterminal'
  | 'dexscreener'
  | 'birdeye'
  | 'jupiter'
  | 'helius'
  | 'tradingview'
  | 'internal';

export interface DataPointProvenance {
  source: DataPlaneSource | string;
  fetchedAt: string;
  latencyMs: number | null;
  httpStatus: number | null;
  schemaVersion: 'v2';
  reliabilityScore: number;
  rawHash: string;
}

export interface SourceHealthSnapshot {
  source: DataPlaneSource | string;
  checkedAt: string;
  ok: boolean;
  freshnessMs: number;
  latencyMs: number | null;
  httpStatus: number | null;
  reliabilityScore: number;
  errorBudgetBurn: number;
  redundancyState: 'healthy' | 'degraded' | 'single_source';
  message?: string;
}

export interface DatasetManifestV2 {
  datasetId: string;
  family: string;
  surface: 'main' | 'bags' | 'tradfi' | 'unknown';
  timeRange: { from: string; to: string };
  schemaVersion: 'v2';
  recordCount: number;
  sha256: string;
  sourceMix: Record<string, number>;
  createdAt: string;
}

export interface TradeEvidenceV2 {
  tradeId: string;
  surface: 'main' | 'bags' | 'tradfi' | 'unknown';
  strategyId: string;
  decisionTs: string;
  route: string;
  expectedPrice: number | null;
  executedPrice: number | null;
  slippageBps: number | null;
  priorityFeeLamports: number | null;
  jitoUsed: boolean;
  mevRiskTag: 'low' | 'medium' | 'high' | 'unknown';
  datasetRefs: string[];
  outcome: 'confirmed' | 'failed' | 'unresolved' | 'no_route';
  metadata?: Record<string, unknown>;
}

export interface RunEvidenceV2 {
  runId: string;
  surface: 'main' | 'bags' | 'tradfi' | 'unknown';
  families: string[];
  datasetManifestIds: string[];
  params: Record<string, unknown>;
  metrics: Record<string, unknown>;
  artifacts: Record<string, string>;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'partial';
  failReasons: string[];
  createdAt: string;
  updatedAt: string;
}
