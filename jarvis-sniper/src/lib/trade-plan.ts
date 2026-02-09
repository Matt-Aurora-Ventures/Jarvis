import type { BagsGraduation } from '@/lib/bags-api';

const BLUE_CHIP_LONG_CONVICTION_SYMBOLS = new Set<string>([
  // Solana + majors
  'SOL',
  'USDC',
  'USDT',
  'BTC',
  'ETH',
  'WETH',
  'WBTC',
]);

export function isBlueChipLongConvictionSymbol(symbol: string | null | undefined): boolean {
  if (!symbol) return false;
  return BLUE_CHIP_LONG_CONVICTION_SYMBOLS.has(symbol.trim().toUpperCase());
}

export function isBlueChipLongConviction(grad: Partial<BagsGraduation> | null | undefined): boolean {
  if (!grad) return false;
  if (isBlueChipLongConvictionSymbol(grad.symbol)) return true;

  // Heuristic: extremely deep liquidity usually means "not a fresh launch" trade.
  // Keep threshold high so we don't accidentally classify memecoins as "blue chip".
  const liq = grad.liquidity ?? 0;
  if (Number.isFinite(liq) && liq >= 5_000_000) return true;

  return false;
}

function trimTrailingZeros(value: string): string {
  if (!value.includes('.')) return value;
  return value.replace(/0+$/, '').replace(/\.$/, '');
}

/**
 * Price formatting optimized for tiny memecoin prices while staying readable for $1+ assets.
 * Returns "—" for missing/invalid values.
 */
export function formatUsdPrice(value: number | null | undefined): string {
  if (value == null) return '—';
  if (!Number.isFinite(value) || value <= 0) return '—';

  const abs = Math.abs(value);
  let decimals = 4;
  if (abs >= 1000) decimals = 2;
  else if (abs >= 1) decimals = 4;
  else {
    // Ensure we keep a couple significant digits for sub-$1 values.
    const log10 = Math.floor(Math.log10(abs)); // negative for < 1
    decimals = Math.min(12, Math.max(4, -log10 + 2));
  }

  return `$${trimTrailingZeros(value.toFixed(decimals))}`;
}

export function computeTargetsFromEntryUsd(
  entryUsd: number | null | undefined,
  slPct: number,
  tpPct: number,
): { entryUsd: number | null; slUsd: number | null; tpUsd: number | null } {
  if (entryUsd == null || !Number.isFinite(entryUsd) || entryUsd <= 0) {
    return { entryUsd: null, slUsd: null, tpUsd: null };
  }
  const slUsd = entryUsd * (1 - slPct / 100);
  const tpUsd = entryUsd * (1 + tpPct / 100);
  return { entryUsd, slUsd, tpUsd };
}
