export interface AutonomyRuntimeStatus {
  autonomyEnabled: boolean;
  applyOverridesEnabled: boolean;
  xaiConfigured: boolean;
  latestCycleId: string | null;
  latestReasonCode: string | null;
  overrideVersion: number;
  overrideUpdatedAt: string | null;
}
