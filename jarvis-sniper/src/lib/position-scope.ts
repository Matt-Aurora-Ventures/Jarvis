import type { Position, TradeSignerMode } from '@/stores/useSniperStore';

function normalizeWallet(value: string | null | undefined): string {
  return String(value || '').trim();
}

export function resolveActiveWallet(
  mode: TradeSignerMode,
  sessionWalletPubkey: string | null | undefined,
  phantomAddress: string | null | undefined,
): string | null {
  if (mode === 'session') {
    const session = normalizeWallet(sessionWalletPubkey);
    return session || null;
  }
  const phantom = normalizeWallet(phantomAddress);
  return phantom || null;
}

export function isPositionInActiveWallet(position: Position, activeWallet: string | null | undefined): boolean {
  const active = normalizeWallet(activeWallet);
  if (!active) return false;
  const owner = normalizeWallet(position.walletAddress);
  if (!owner) return false;
  return owner === active;
}

export function filterOpenPositionsForActiveWallet(
  positions: Position[],
  activeWallet: string | null | undefined,
  opts?: { includeManualOnly?: boolean },
): Position[] {
  const includeManualOnly = opts?.includeManualOnly ?? true;
  return positions.filter((p) => {
    if (p.status !== 'open') return false;
    if (!includeManualOnly && p.manualOnly) return false;
    return isPositionInActiveWallet(p, activeWallet);
  });
}

export function filterTradeManagedOpenPositionsForActiveWallet(
  positions: Position[],
  activeWallet: string | null | undefined,
  opts?: { excludeClosing?: boolean },
): Position[] {
  const excludeClosing = opts?.excludeClosing ?? true;
  return positions.filter((p) => {
    if (p.status !== 'open') return false;
    if (!isPositionInActiveWallet(p, activeWallet)) return false;
    if (p.manualOnly) return false;
    if (p.recoveredFrom === 'onchain-sync') return false;
    if (excludeClosing && p.isClosing) return false;
    return true;
  });
}

export function sumScopedUnrealizedPnl(
  positions: Position[],
  activeWallet: string | null | undefined,
): number {
  return filterOpenPositionsForActiveWallet(positions, activeWallet).reduce((acc, p) => acc + (p.pnlSol || 0), 0);
}
