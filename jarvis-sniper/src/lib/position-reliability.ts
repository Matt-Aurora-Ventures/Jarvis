export const MIN_RELIABLE_SOL_INVESTED = 0.005;
export const MAX_ABS_REALISTIC_PNL_PCT = 5000;

export type PositionReliabilityLike = {
  id?: string;
  manualOnly?: boolean;
  recoveredFrom?: 'onchain-sync';
  solInvested?: number;
  pnlPercent?: number;
  realPnlPercent?: number;
  status?: string;
};

export function isLegacyRecoveredPositionId(id?: string): boolean {
  return typeof id === 'string' && id.startsWith('recovered-');
}

export function isOperatorManagedPositionMeta(position: Pick<PositionReliabilityLike, 'id' | 'manualOnly' | 'recoveredFrom'>): boolean {
  return !position.manualOnly && position.recoveredFrom !== 'onchain-sync' && !isLegacyRecoveredPositionId(position.id);
}

export function sanitizePnlPercent(raw: number | undefined | null): number {
  if (!Number.isFinite(raw)) return 0;
  const value = Number(raw);
  if (Math.abs(value) > MAX_ABS_REALISTIC_PNL_PCT) return 0;
  return value;
}

export function resolvePositionPnlPercent(position: PositionReliabilityLike): number {
  const raw = typeof position.realPnlPercent === 'number' ? position.realPnlPercent : position.pnlPercent;
  return sanitizePnlPercent(raw);
}

export function isReliableTradeForStats(position: PositionReliabilityLike): boolean {
  if (!isOperatorManagedPositionMeta(position)) return false;
  const invested = Number(position.solInvested || 0);
  if (!Number.isFinite(invested) || invested < MIN_RELIABLE_SOL_INVESTED) return false;
  const raw = typeof position.realPnlPercent === 'number' ? position.realPnlPercent : position.pnlPercent;
  if (!Number.isFinite(raw)) return false;
  return Math.abs(Number(raw)) <= MAX_ABS_REALISTIC_PNL_PCT;
}

