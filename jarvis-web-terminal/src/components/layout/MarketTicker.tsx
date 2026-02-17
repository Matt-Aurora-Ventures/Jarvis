'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTokenStore } from '@/stores/useTokenStore';
import { usePriceFlash } from '@/hooks/usePriceFlash';

// ─── Types ──────────────────────────────────────────────────────────
export interface TickerItem {
  symbol: string;
  price: number;
  change24h: number;
  mint: string;
}

// ─── Tracked Tokens ─────────────────────────────────────────────────
// Top Solana tokens by volume / relevance
export const TRACKED_MINTS: Record<string, string> = {
  'So11111111111111111111111111111111111111112': 'SOL',
  'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v': 'USDC',
  'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN': 'JUP',
  'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263': 'BONK',
  'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': 'USDT',
  'mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So': 'mSOL',
  'rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof': 'RNDR',
  'HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3': 'PYTH',
};

// ─── Helpers ────────────────────────────────────────────────────────

/**
 * Format a price for display.
 * - >= $1      : $X,XXX.XX  (2 decimals, thousands separators)
 * - 0.01-0.99  : $0.XX      (2-4 decimals)
 * - < 0.01     : show enough significant digits so the number is meaningful
 * - 0          : $0.00
 */
export function formatPrice(price: number): string {
  if (price === 0) return '$0.00';

  if (price >= 1) {
    return '$' + price.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  if (price >= 0.01) {
    return '$' + price.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    });
  }

  // Very small prices: find leading zeros and show 4 significant digits
  const str = price.toFixed(20);
  const match = str.match(/^0\.(0*)/);
  const leadingZeros = match ? match[1].length : 0;
  const decimals = leadingZeros + 4;
  return '$' + price.toFixed(decimals);
}

/**
 * Format a 24h change percentage for display.
 * Positive: "+3.2%"   Negative: "-0.5%"   Zero: "0.0%"
 */
export function formatChange(change: number): string {
  const sign = change > 0 ? '+' : '';
  return `${sign}${change.toFixed(1)}%`;
}

// ─── Data Fetcher ───────────────────────────────────────────────────

/**
 * Fetch current prices from Jupiter Price API v2.
 * Returns TickerItem[] with price and 24h change.
 * Falls back to empty array on any error.
 */
export async function fetchTickerData(): Promise<TickerItem[]> {
  try {
    const mints = Object.keys(TRACKED_MINTS);
    const url = `https://api.jup.ag/price/v2?ids=${mints.join(',')}&showExtraInfo=true`;
    const res = await fetch(url);
    if (!res.ok) return [];

    const json = await res.json();
    if (!json.data) return [];

    const items: TickerItem[] = [];
    for (const mint of mints) {
      const entry = json.data[mint];
      if (!entry || !entry.price) continue;

      const price = parseFloat(entry.price);
      // Attempt to derive 24h change from extraInfo if available
      let change24h = 0;
      try {
        const buyPrice = parseFloat(
          entry.extraInfo?.lastSwappedPrice?.lastJupiterBuyPrice ?? entry.price
        );
        const sellPrice = parseFloat(
          entry.extraInfo?.lastSwappedPrice?.lastJupiterSellPrice ?? entry.price
        );
        // Use sell price as "prior" for a rough delta, or 0 if same
        if (sellPrice > 0 && sellPrice !== price) {
          change24h = ((price - sellPrice) / sellPrice) * 100;
        }
      } catch {
        change24h = 0;
      }

      items.push({
        symbol: TRACKED_MINTS[mint],
        price,
        change24h: parseFloat(change24h.toFixed(2)),
        mint,
      });
    }

    return items;
  } catch {
    return [];
  }
}

// ─── Ticker Token Chip ──────────────────────────────────────────────

function TickerToken({ item }: { item: TickerItem }) {
  const setSelectedToken = useTokenStore((s) => s.setSelectedToken);
  const isPositive = item.change24h >= 0;
  const priceFlash = usePriceFlash(item.price);

  const handleClick = () => {
    setSelectedToken({
      address: item.mint,
      name: item.symbol,
      symbol: item.symbol,
    });
  };

  return (
    <button
      onClick={handleClick}
      className="flex items-center gap-1 sm:gap-1.5 px-1.5 sm:px-2 py-0.5 whitespace-nowrap cursor-pointer hover:bg-bg-tertiary/60 rounded transition-colors shrink-0"
      title={`Select ${item.symbol}`}
    >
      <span className="text-[10px] sm:text-[11px] font-semibold text-text-primary font-mono">
        {item.symbol}
      </span>
      <span className={`text-[10px] sm:text-[11px] font-mono text-text-secondary rounded px-0.5 ${priceFlash}`}>
        {formatPrice(item.price)}
      </span>
      <span
        className={`text-[9px] sm:text-[10px] font-mono font-medium ${
          isPositive ? 'text-accent-success' : 'text-accent-error'
        }`}
      >
        {isPositive ? '\u25B2' : '\u25BC'}
        {formatChange(item.change24h)}
      </span>
    </button>
  );
}

// ─── MarketTicker Component ─────────────────────────────────────────

const REFRESH_INTERVAL = 30_000; // 30 seconds

export function MarketTicker() {
  const [items, setItems] = useState<TickerItem[]>([]);
  const [isPaused, setIsPaused] = useState(false);

  const refresh = useCallback(async () => {
    const data = await fetchTickerData();
    if (data.length > 0) {
      setItems(data);
    }
  }, []);

  // Fetch on mount and every REFRESH_INTERVAL
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, REFRESH_INTERVAL);
    return () => clearInterval(id);
  }, [refresh]);

  // Don't render until we have data
  if (items.length === 0) {
    return (
      <div className="w-full h-6 sm:h-7 bg-bg-secondary/50 border-b border-border-primary flex items-center justify-center">
        <span className="text-[9px] sm:text-[10px] text-text-muted font-mono animate-pulse">
          Loading market data...
        </span>
      </div>
    );
  }

  return (
    <div
      className="w-full overflow-hidden bg-bg-secondary/50 border-b border-border-primary h-6 sm:h-7 flex items-center"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      aria-label="Live market prices"
      role="region"
    >
      <div
        className={`flex gap-2 sm:gap-4 ticker-scroll ${isPaused ? 'ticker-paused' : ''}`}
        role="marquee"
        aria-live="off"
      >
        {/* Duplicate items for infinite scroll illusion */}
        {[...items, ...items].map((item, i) => (
          <TickerToken key={`${item.symbol}-${i}`} item={item} />
        ))}
      </div>
    </div>
  );
}
