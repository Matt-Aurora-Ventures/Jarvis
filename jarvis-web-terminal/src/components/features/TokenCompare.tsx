'use client';

/**
 * TokenCompare
 *
 * Side-by-side comparison of two Solana tokens using DexScreener data.
 * Starts collapsed; expands to show search inputs + metric comparison.
 */

import { useState, useCallback, useRef } from 'react';
import { GitCompareArrows, Search, ExternalLink, X, Loader2 } from 'lucide-react';
import { QuickBuyWidget } from '@/components/features/QuickBuyWidget';
import { CollapsiblePanel } from '@/components/ui/CollapsiblePanel';
import {
  searchDexScreener,
  filterSolanaPairs,
  formatCompactNumber,
  type DexScreenerPair,
} from '@/lib/dexscreener';

// ── Types ────────────────────────────────────────────────────────────

export interface CompareToken {
  address: string;
  symbol: string;
  name: string;
  priceUsd: number;
  change24h: number;
  volume24h: number;
  fdv: number;
  liquidity: number;
}

// ── Pure helpers (exported for testing) ──────────────────────────────

/**
 * Determine which side "wins" for a given metric.
 *
 * @param valueA - Token A's value
 * @param valueB - Token B's value
 * @param mode   - "higher" means bigger is better; "lower" means smaller is better
 * @returns "A" | "B" | "tie"
 */
export function determineWinner(
  valueA: number,
  valueB: number,
  mode: 'higher' | 'lower'
): 'A' | 'B' | 'tie' {
  if (valueA === valueB) return 'tie';
  if (mode === 'higher') {
    return valueA > valueB ? 'A' : 'B';
  }
  return valueA < valueB ? 'A' : 'B';
}

/**
 * Build a Jupiter swap URL for a given token mint address.
 * Default input token is SOL.
 */
export function buildJupiterSwapUrl(tokenAddress: string): string {
  return `https://jup.ag/swap/SOL-${tokenAddress}`;
}

/**
 * Format a price for the comparison panel.
 */
export function formatComparePrice(price: number): string {
  if (price === 0) return '$0.00';
  if (price < 0.0001) return `$${price.toExponential(2)}`;
  if (price < 1) return `$${price.toFixed(4)}`;
  if (price >= 1000) {
    return `$${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `$${price.toFixed(2)}`;
}

/**
 * Format a percentage change for display.
 */
export function formatComparePercent(value: number): string {
  if (value === 0) return '0.0%';
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(1)}%`;
}

// ── Internal helpers ─────────────────────────────────────────────────

function pairToCompareToken(pair: DexScreenerPair): CompareToken {
  return {
    address: pair.baseToken.address,
    symbol: pair.baseToken.symbol,
    name: pair.baseToken.name,
    priceUsd: parseFloat(pair.priceUsd) || 0,
    change24h: pair.priceChange.h24 ?? 0,
    volume24h: pair.volume.h24 ?? 0,
    fdv: pair.fdv ?? 0,
    liquidity: pair.liquidity.usd ?? 0,
  };
}

// ── Metric row definitions ───────────────────────────────────────────

interface MetricDef {
  label: string;
  key: keyof CompareToken;
  format: (v: number) => string;
  mode: 'higher' | 'lower';
}

const METRICS: MetricDef[] = [
  { label: 'Price', key: 'priceUsd', format: formatComparePrice, mode: 'higher' },
  { label: '24h', key: 'change24h', format: formatComparePercent, mode: 'higher' },
  { label: 'Volume', key: 'volume24h', format: formatCompactNumber, mode: 'higher' },
  { label: 'FDV', key: 'fdv', format: formatCompactNumber, mode: 'higher' },
  { label: 'Liquidity', key: 'liquidity', format: formatCompactNumber, mode: 'higher' },
];

// ── Search Input Sub-Component ───────────────────────────────────────

interface TokenSearchInputProps {
  label: string;
  selectedToken: CompareToken | null;
  onSelect: (token: CompareToken) => void;
  onClear: () => void;
}

function TokenSearchInput({
  label,
  selectedToken,
  onSelect,
  onClear,
}: TokenSearchInputProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<DexScreenerPair[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearch = useCallback((value: string) => {
    setQuery(value);

    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (value.trim().length < 2) {
      setResults([]);
      setShowDropdown(false);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setIsSearching(true);
      try {
        const pairs = await searchDexScreener(value);
        const filtered = filterSolanaPairs(pairs, 6);
        setResults(filtered);
        setShowDropdown(filtered.length > 0);
      } finally {
        setIsSearching(false);
      }
    }, 350);
  }, []);

  const handleSelect = (pair: DexScreenerPair) => {
    onSelect(pairToCompareToken(pair));
    setQuery('');
    setResults([]);
    setShowDropdown(false);
  };

  if (selectedToken) {
    return (
      <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-bg-secondary/60 border border-border-primary/30">
        <div className="min-w-0">
          <span className="text-sm font-semibold text-accent-neon">
            {selectedToken.symbol}
          </span>
          <span className="text-xs text-text-muted ml-2 truncate">
            {selectedToken.name}
          </span>
        </div>
        <button
          onClick={onClear}
          className="text-text-muted hover:text-accent-error transition-colors shrink-0"
          title={`Clear ${label}`}
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-bg-secondary/60 border border-border-primary/30 focus-within:border-accent-neon/50 transition-colors">
        {isSearching ? (
          <Loader2 className="w-3.5 h-3.5 text-text-muted animate-spin shrink-0" />
        ) : (
          <Search className="w-3.5 h-3.5 text-text-muted shrink-0" />
        )}
        <input
          type="text"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
          placeholder={`Search ${label}...`}
          className="bg-transparent text-sm text-text-primary placeholder-text-muted outline-none w-full font-mono"
        />
      </div>

      {/* Dropdown Results */}
      {showDropdown && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 rounded-lg bg-bg-primary border border-border-primary/40 shadow-xl max-h-48 overflow-y-auto">
          {results.map((pair) => (
            <button
              key={`${pair.baseToken.address}-${pair.pairAddress}`}
              onMouseDown={() => handleSelect(pair)}
              className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-bg-tertiary/60 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <span className="text-sm font-semibold text-text-primary">
                  {pair.baseToken.symbol}
                </span>
                <span className="text-xs text-text-muted ml-2 truncate">
                  {pair.baseToken.name}
                </span>
              </div>
              <span className="text-xs font-mono text-text-muted shrink-0">
                {pair.priceUsd ? `$${parseFloat(pair.priceUsd).toFixed(4)}` : '--'}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── MetricRow Sub-Component ──────────────────────────────────────────

interface MetricRowProps {
  label: string;
  valueA: number;
  valueB: number;
  format: (v: number) => string;
  mode: 'higher' | 'lower';
  hasA: boolean;
  hasB: boolean;
}

function MetricRow({ label, valueA, valueB, format, mode, hasA, hasB }: MetricRowProps) {
  const winner = hasA && hasB ? determineWinner(valueA, valueB, mode) : 'tie';

  const winnerBgA = winner === 'A' ? 'bg-accent-success/10' : '';
  const winnerBgB = winner === 'B' ? 'bg-accent-success/10' : '';

  // Color-code 24h change values
  const changeColorA =
    label === '24h'
      ? valueA > 0
        ? 'text-accent-success'
        : valueA < 0
          ? 'text-accent-error'
          : 'text-text-muted'
      : 'text-text-primary';
  const changeColorB =
    label === '24h'
      ? valueB > 0
        ? 'text-accent-success'
        : valueB < 0
          ? 'text-accent-error'
          : 'text-text-muted'
      : 'text-text-primary';

  return (
    <div className="grid grid-cols-[1fr_80px_1fr] items-center gap-2 py-1.5">
      <div
        className={`text-right font-mono text-sm px-2 py-0.5 rounded ${winnerBgA} ${changeColorA}`}
      >
        {hasA ? format(valueA) : '--'}
      </div>
      <div className="text-center text-xs font-mono uppercase text-text-muted">
        {label}
      </div>
      <div
        className={`text-left font-mono text-sm px-2 py-0.5 rounded ${winnerBgB} ${changeColorB}`}
      >
        {hasB ? format(valueB) : '--'}
      </div>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────

export function TokenCompare() {
  const [tokenA, setTokenA] = useState<CompareToken | null>(null);
  const [tokenB, setTokenB] = useState<CompareToken | null>(null);

  return (
    <CollapsiblePanel
      title="Compare Tokens"
      icon={<GitCompareArrows className="w-4 h-4" />}
      defaultExpanded={false}
    >
      {/* Search Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
        <TokenSearchInput
          label="Token A"
          selectedToken={tokenA}
          onSelect={setTokenA}
          onClear={() => setTokenA(null)}
        />
        <TokenSearchInput
          label="Token B"
          selectedToken={tokenB}
          onSelect={setTokenB}
          onClear={() => setTokenB(null)}
        />
      </div>

      {/* Symbol Headers */}
      {(tokenA || tokenB) && (
        <div className="grid grid-cols-[1fr_80px_1fr] items-center gap-2 mb-2">
          <div className="text-right text-sm font-semibold text-accent-neon">
            {tokenA?.symbol ?? '--'}
          </div>
          <div className="text-center text-xs text-text-muted">vs</div>
          <div className="text-left text-sm font-semibold text-accent-neon">
            {tokenB?.symbol ?? '--'}
          </div>
        </div>
      )}

      {/* Divider */}
      {(tokenA || tokenB) && (
        <div className="border-t border-border-primary/30 mb-2" />
      )}

      {/* Metric Rows */}
      {(tokenA || tokenB) && (
        <div className="space-y-0.5">
          {METRICS.map((m) => (
            <MetricRow
              key={m.key}
              label={m.label}
              valueA={(tokenA?.[m.key] as number) ?? 0}
              valueB={(tokenB?.[m.key] as number) ?? 0}
              format={m.format}
              mode={m.mode}
              hasA={!!tokenA}
              hasB={!!tokenB}
            />
          ))}
        </div>
      )}

      {/* Trade Buttons */}
      {(tokenA || tokenB) && (
        <>
          <div className="border-t border-border-primary/30 mt-3 mb-3" />
          <div className="grid grid-cols-[1fr_80px_1fr] items-center gap-2">
            <div className="flex justify-end">
              {tokenA && (
                <QuickBuyWidget
                  tokenMint={tokenA.address}
                  tokenSymbol={tokenA.symbol}
                  compact
                />
              )}
            </div>
            <div />
            <div className="flex justify-start">
              {tokenB && (
                <QuickBuyWidget
                  tokenMint={tokenB.address}
                  tokenSymbol={tokenB.symbol}
                  compact
                />
              )}
            </div>
          </div>
        </>
      )}

      {/* Empty state */}
      {!tokenA && !tokenB && (
        <p className="text-xs text-text-muted text-center py-4">
          Search for two tokens above to compare them side by side.
        </p>
      )}
    </CollapsiblePanel>
  );
}
