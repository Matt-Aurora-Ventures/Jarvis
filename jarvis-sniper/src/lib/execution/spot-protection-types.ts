export type SpotProtectionStatus = 'pending' | 'active' | 'failed' | 'cancelled';
export type SpotProtectionProvider = 'upstream' | 'local' | 'none';

export interface SpotProtectionRecord {
  positionId: string;
  walletAddress: string;
  mint: string;
  symbol: string;
  entryPriceUsd: number;
  quantity: number;
  tpPercent: number;
  slPercent: number;
  status: SpotProtectionStatus;
  tpOrderKey?: string;
  slOrderKey?: string;
  failureReason?: string;
  provider: SpotProtectionProvider;
  strategyId?: string;
  surface?: string;
  createdAt: number;
  updatedAt: number;
  cancelledAt?: number;
}

export interface SpotProtectionPreflightResult {
  ok: boolean;
  provider: SpotProtectionProvider;
  checkedAt: number;
  reason?: string;
}

export interface SpotProtectionActivationInput {
  positionId: string;
  walletAddress: string;
  mint: string;
  symbol: string;
  entryPriceUsd: number;
  quantity: number;
  tpPercent: number;
  slPercent: number;
  strategyId?: string;
  surface?: string;
  idempotencyKey?: string;
}

export interface SpotProtectionActivationResult {
  ok: boolean;
  provider: SpotProtectionProvider;
  status: SpotProtectionStatus;
  tpOrderKey?: string;
  slOrderKey?: string;
  record?: SpotProtectionRecord;
  reason?: string;
}

export interface SpotProtectionCancelResult {
  ok: boolean;
  provider: SpotProtectionProvider;
  positionId: string;
  status: SpotProtectionStatus;
  record?: SpotProtectionRecord;
  reason?: string;
}

export interface SpotProtectionReconcileResult {
  ok: boolean;
  provider: SpotProtectionProvider;
  records: SpotProtectionRecord[];
  reason?: string;
}
