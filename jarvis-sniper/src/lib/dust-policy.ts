export const DUST_VALUE_USD = 0.5;
export const DUST_REMAINDER_RATIO = 0.02;
export const RECENTLY_CLOSED_SUPPRESSION_WINDOW_MS = 60 * 60 * 1000; // 60 minutes

export interface RecentlyClosedMintMemo {
  mint: string;
  closedAt: number;
  amountLamportsAtClose?: string;
  uiAmountAtClose?: number;
}

export interface DustAwareHolding {
  mint: string;
  uiAmount: number;
  valueUsd: number;
  amountLamports: string;
  decimals: number;
  symbol?: string;
  name?: string;
}

export interface DustAwarePosition {
  mint: string;
  amount: number;
  walletAddress?: string;
  status?: 'open' | 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired' | 'closed';
  manualOnly?: boolean;
}

export interface DustPartitionResult<T extends DustAwareHolding> {
  visibleHoldings: T[];
  dustHoldings: T[];
  dustCount: number;
  dustValueUsd: number;
}

function toNumber(v: unknown, fallback = 0): number {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function lamportsToBigInt(raw: string): bigint {
  try {
    const s = String(raw || '').trim();
    if (!/^\d+$/.test(s)) return BigInt(0);
    return BigInt(s);
  } catch {
    return BigInt(0);
  }
}

function tinyUnknownValueHolding(holding: DustAwareHolding): boolean {
  const dec = Math.max(0, Math.floor(toNumber(holding.decimals, 0)));
  const ui = Math.max(0, toNumber(holding.uiAmount, 0));
  const lamports = lamportsToBigInt(holding.amountLamports);

  // Ultra-small token remnants (typically post-sell crumbs from pool rounding).
  const baseThreshold = Math.pow(10, -Math.min(dec, 6));
  if (ui > 0 && ui <= baseThreshold * 10) return true;
  if (lamports > BigInt(0) && lamports <= BigInt(10)) return true;
  return false;
}

export function isHoldingDustRecentlyClosed(
  holding: DustAwareHolding,
  memo: RecentlyClosedMintMemo,
  nowMs = Date.now(),
): boolean {
  const closedAt = toNumber(memo?.closedAt, 0);
  if (!closedAt || !Number.isFinite(closedAt)) return false;
  if (nowMs - closedAt > RECENTLY_CLOSED_SUPPRESSION_WINDOW_MS) return false;

  // If we have value, it wins.
  const valueUsd = toNumber(holding.valueUsd, 0);
  if (valueUsd > 0 && valueUsd < DUST_VALUE_USD) return true;

  // Prefer lamports ratio when available (decimal-safe).
  const closeLamports = lamportsToBigInt(String(memo.amountLamportsAtClose || ''));
  const currentLamports = lamportsToBigInt(String(holding.amountLamports || ''));
  if (closeLamports > BigInt(0) && currentLamports >= BigInt(0)) {
    const pct = BigInt(Math.max(1, Math.round(DUST_REMAINDER_RATIO * 100))); // 2% -> 2
    if (currentLamports * BigInt(100) <= closeLamports * pct) return true;
  }

  // Fallback: UI ratio when lamports missing.
  const closeUi = Math.max(toNumber(memo.uiAmountAtClose, 0), Number.EPSILON);
  const ui = Math.max(toNumber(holding.uiAmount, 0), 0);
  if (closeUi > Number.EPSILON && (ui / closeUi) <= DUST_REMAINDER_RATIO) return true;

  // If value is missing, we still suppress ultra-small crumbs.
  if (valueUsd <= 0) return tinyUnknownValueHolding(holding);
  return false;
}

export function isHoldingDustUntracked(holding: DustAwareHolding): boolean {
  const valueUsd = toNumber(holding.valueUsd, 0);
  if (valueUsd > 0) return valueUsd < DUST_VALUE_USD;

  // If value is missing/unreliable, still suppress ultra-small remnants (common post-sell residue).
  // Avoid hiding meaningful unknown-value holdings by only applying the tiny-amount heuristic.
  return tinyUnknownValueHolding(holding);
}

export function isHoldingDustForPosition(holding: DustAwareHolding, position: DustAwarePosition): boolean {
  const positionAmount = Math.max(toNumber(position.amount, 0), Number.EPSILON);
  const uiAmount = Math.max(toNumber(holding.uiAmount, 0), 0);
  const remainderRatio = uiAmount / positionAmount;

  if (remainderRatio > DUST_REMAINDER_RATIO) return false;

  const valueUsd = toNumber(holding.valueUsd, 0);
  if (valueUsd > 0 && valueUsd < DUST_VALUE_USD) return true;

  // Value missing/unreliable from source:
  // if this is already a tiny remainder of a known open position, treat as dust by default.
  // This suppresses post-sell residue cards even when price APIs temporarily miss value.
  if (valueUsd <= 0) return true;

  // Final fallback.
  return tinyUnknownValueHolding(holding);
}

export function partitionDustHoldings<T extends DustAwareHolding>(
  holdings: T[],
  openPositionsByMint: Map<string, DustAwarePosition>,
): DustPartitionResult<T> {
  const visibleHoldings: T[] = [];
  const dustHoldings: T[] = [];

  for (const holding of holdings) {
    const mint = String(holding?.mint || '').trim();
    if (!mint) continue;

    const local = openPositionsByMint.get(mint);
    const isDust = local
      ? isHoldingDustForPosition(holding, local)
      : isHoldingDustUntracked(holding);

    if (isDust) {
      dustHoldings.push(holding);
    } else {
      visibleHoldings.push(holding);
    }
  }

  const dustValueUsd = Number(
    dustHoldings
      .reduce((sum, h) => sum + Math.max(0, toNumber(h.valueUsd, 0)), 0)
      .toFixed(4),
  );

  return {
    visibleHoldings,
    dustHoldings,
    dustCount: dustHoldings.length,
    dustValueUsd,
  };
}
