export type AutonomyDecisionType = 'hold' | 'adjust' | 'rollback' | 'disable_strategy';

export type OverrideMutableField =
  | 'stopLossPct'
  | 'takeProfitPct'
  | 'trailingStopPct'
  | 'minScore'
  | 'minLiquidityUsd'
  | 'slippageBps'
  | 'maxTokenAgeHours'
  | 'minMomentum1h'
  | 'minVolLiqRatio';

export type StrategyOverrideConfigPatch = Partial<Record<OverrideMutableField, number>>;

export interface StrategyOverridePatch {
  strategyId: string;
  patch: StrategyOverrideConfigPatch;
  reason: string;
  confidence: number;
  evidence: string[];
  sourceCycleId: string;
  decidedAt: string;
}

export interface StrategyOverrideSnapshot {
  version: number;
  updatedAt: string;
  cycleId: string;
  patches: StrategyOverridePatch[];
  signature: string;
}

export interface AutonomyDecisionTarget {
  strategyId: string;
  patch?: StrategyOverrideConfigPatch;
  reason: string;
  confidence: number;
  evidence: string[];
}

export interface AutonomyDecision {
  decision: AutonomyDecisionType;
  reason: string;
  confidence: number;
  targets: AutonomyDecisionTarget[];
  evidence: string[];
  constraintsCheck: {
    pass: boolean;
    reasons: string[];
  };
  alternativesConsidered: Array<{
    option: string;
    rejectedBecause: string;
  }>;
}

export interface AutonomyDecisionMatrix {
  cycleId: string;
  generatedAt: string;
  wrGatePolicy: {
    primaryPct: number;
    fallbackPct: number;
    minTrades: number;
    method: 'wilson95_lower' | 'point';
    scope: 'memecoin_bags' | 'all' | 'memecoin';
  };
  strategyRows: Array<{
    strategyId: string;
    assetType: string;
    baselineWinRateText: string;
    baselineTrades: number;
    baseConfig: Record<string, number>;
  }>;
  metrics: {
    liquidityRegime: {
      sampleSize: number;
      avgLiquidityUsd: number;
      medianLiquidityUsd: number;
      avgMomentum1h: number;
      avgVolLiqRatio: number;
    };
    thompsonBeliefs: {
      availability: 'available' | 'unavailable_server_scope';
      reason?: string;
      rows: Array<{
        strategyId: string;
        alpha: number;
        beta: number;
        wins: number;
        losses: number;
      }>;
    };
    reliability: {
      confirmed: number;
      unresolved: number;
      failed: number;
    };
    realized: {
      totalPnlSol: number;
      winCount: number;
      lossCount: number;
      tradeCount: number;
      drawdownPct: number;
    };
  };
  tokenBudget: {
    maxInputTokens: number;
    maxOutputTokens: number;
    estimatedInputTokens: number;
  };
}

export interface AutonomyAuditArtifact {
  cycleId: string;
  status: 'pending' | 'completed' | 'noop' | 'error';
  reasonCode?: string;
  createdAt: string;
  updatedAt: string;
  batchId?: string;
  batchName?: string;
  requestIds?: string[];
  matrixHash: string;
  responseHash?: string;
  decisionHash?: string;
  appliedOverrideVersion?: number;
}

export interface AutonomyState {
  updatedAt: string;
  latestCycleId?: string;
  latestCompletedCycleId?: string;
  pendingBatch?: {
    cycleId: string;
    batchId: string;
    batchName?: string;
    requestIds?: [string, string] | string[];
    model: string;
    submittedAt: string;
    matrix: AutonomyDecisionMatrix;
    matrixHash: string;
  };
  cycles: Record<string, AutonomyAuditArtifact>;
  budgetUsageByDay: Record<
    string,
    {
      estimatedCostUsd: number;
      inputTokens: number;
      outputTokens: number;
      cycles: number;
    }
  >;
}

// ============================================================================
// Trade Telemetry (Client -> Server) for Autonomy / Backtests
// ============================================================================

export type TelemetryTradeSignerMode = 'session' | 'phantom';

export interface TradeTelemetryIngest {
  schemaVersion: 1;
  positionId: string;
  mint: string;
  status: 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired' | 'closed';
  symbol?: string;
  walletAddress?: string;
  strategyId?: string | null;
  entrySource?: 'auto' | 'manual';
  entryTime?: number;
  exitTime?: number;
  solInvested?: number;
  exitSolReceived?: number | null;
  pnlSol?: number;
  pnlPercent?: number;
  buyTxHash?: string | null;
  sellTxHash?: string | null;
  includedInStats?: boolean;
  manualOnly?: boolean;
  recoveredFrom?: string | null;
  tradeSignerMode?: TelemetryTradeSignerMode;
  sessionWalletPubkey?: string | null;
  activePreset?: string | null;
}

export interface TradeTelemetryRecord extends TradeTelemetryIngest {
  receivedAt: string;
  source: 'client';
}
