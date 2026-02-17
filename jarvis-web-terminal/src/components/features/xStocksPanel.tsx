'use client';

/**
 * xStocks Panel -- Self-contained tokenized-equities browser
 *
 * Fetches live price data from DexScreener via the useXStocksData() hook,
 * merges it with the static token registry, and presents a filterable,
 * sortable table with category tabs, search, and trade links.
 *
 * No props required -- drop in anywhere.
 */

import { useState, useMemo, useCallback } from 'react';
import { useXStocksData, type DexPairData } from '@/lib/xstocks-api';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { QuickBuyWidget } from '@/components/features/QuickBuyWidget';
import {
  ALL_TOKENIZED_EQUITIES,
  XSTOCKS,
  PRESTOCKS,
  INDEXES,
  COMMODITIES_TOKENS,
  type TokenizedEquity,
  type EquityCategory,
} from '@/lib/xstocks-data';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type CategoryFilter = 'ALL' | EquityCategory;

type SortField = 'ticker' | 'price' | 'change24h' | 'volume' | 'fdv';
type SortDirection = 'asc' | 'desc';

interface SortConfig {
  field: SortField;
  direction: SortDirection;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCompact(n: number): string {
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

function formatPrice(raw: string | undefined): string {
  if (!raw) return '\u2014';
  const n = parseFloat(raw);
  if (Number.isNaN(n)) return '\u2014';
  if (n >= 1000) return `$${n.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
  if (n >= 1) return `$${n.toFixed(2)}`;
  if (n >= 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(6)}`;
}

function tokenListForCategory(cat: CategoryFilter): TokenizedEquity[] {
  switch (cat) {
    case 'XSTOCK':
      return XSTOCKS;
    case 'PRESTOCK':
      return PRESTOCKS;
    case 'INDEX':
      return INDEXES;
    case 'COMMODITY':
      return COMMODITIES_TOKENS;
    default:
      return ALL_TOKENIZED_EQUITIES;
  }
}

// ---------------------------------------------------------------------------
// Category tab config
// ---------------------------------------------------------------------------

const CATEGORY_TABS: { key: CategoryFilter; label: string }[] = [
  { key: 'ALL', label: 'ALL' },
  { key: 'XSTOCK', label: 'xStocks' },
  { key: 'PRESTOCK', label: 'PreStocks' },
  { key: 'INDEX', label: 'Indexes' },
  { key: 'COMMODITY', label: 'Commodities' },
];

// ---------------------------------------------------------------------------
// Sort header labels
// ---------------------------------------------------------------------------

const SORT_COLUMNS: { field: SortField; label: string; numeric: boolean }[] = [
  { field: 'ticker', label: 'Ticker', numeric: false },
  { field: 'price', label: 'Price', numeric: true },
  { field: 'change24h', label: '24h %', numeric: true },
  { field: 'volume', label: 'Volume', numeric: true },
  { field: 'fdv', label: 'FDV', numeric: true },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function XStocksPanel() {
  // ---- data hook ----
  const { data, isLoading, error, lastUpdated, refetch } = useXStocksData();

  // ---- local UI state ----
  const [category, setCategory] = useState<CategoryFilter>(() => 'ALL');
  const [search, setSearch] = useState<string>(() => '');
  const [sort, setSort] = useState<SortConfig>(() => ({
    field: 'ticker',
    direction: 'asc',
  }));

  // ---- derived helpers ----
  const getDex = useCallback(
    (mint: string): DexPairData | undefined => data.get(mint),
    [data],
  );

  // ---- sort click handler ----
  const handleSort = useCallback((field: SortField) => {
    setSort((prev) => ({
      field,
      direction: prev.field === field && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  }, []);

  // ---- filtered + sorted rows ----
  const rows = useMemo(() => {
    const base = tokenListForCategory(category);

    // filter by search
    const query = search.trim().toLowerCase();
    const filtered = query
      ? base.filter(
          (t) =>
            t.ticker.toLowerCase().includes(query) ||
            t.name.toLowerCase().includes(query) ||
            t.company.toLowerCase().includes(query) ||
            t.sector.toLowerCase().includes(query),
        )
      : base;

    // sort
    const sorted = [...filtered].sort((a, b) => {
      const dexA = getDex(a.mintAddress);
      const dexB = getDex(b.mintAddress);
      let cmp = 0;

      switch (sort.field) {
        case 'ticker':
          cmp = a.ticker.localeCompare(b.ticker);
          break;
        case 'price':
          cmp = (parseFloat(dexA?.priceUsd ?? '0') || 0) - (parseFloat(dexB?.priceUsd ?? '0') || 0);
          break;
        case 'change24h':
          cmp = (dexA?.priceChange24h ?? 0) - (dexB?.priceChange24h ?? 0);
          break;
        case 'volume':
          cmp = (dexA?.volume24h ?? 0) - (dexB?.volume24h ?? 0);
          break;
        case 'fdv':
          cmp = (dexA?.fdv ?? 0) - (dexB?.fdv ?? 0);
          break;
      }

      return sort.direction === 'asc' ? cmp : -cmp;
    });

    return sorted;
  }, [category, search, sort, getDex]);

  // ---- early returns ----
  if (isLoading && data.size === 0) {
    return (
      <div className="card-glass p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">
          Tokenized Equities
        </h2>
        <SkeletonTable rows={8} />
      </div>
    );
  }

  if (error && data.size === 0) {
    return (
      <div className="card-glass p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">
          Tokenized Equities
        </h2>
        <div className="flex flex-col items-center gap-3 py-12 text-text-muted">
          <span>Failed to load price data</span>
          <span className="text-xs text-accent-error">{error}</span>
          <button
            onClick={refetch}
            className="px-4 py-1.5 rounded-md text-sm bg-accent-neon/20 text-accent-neon hover:bg-accent-neon/30 transition-colors"
            aria-label="Retry loading price data"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // ---- render ----
  return (
    <div className="card-glass p-4 sm:p-6">
      {/* ---------- header ---------- */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">
            Tokenized Equities
          </h2>
          {lastUpdated && (
            <span className="text-xs text-text-muted">
              Updated {lastUpdated.toLocaleTimeString()}
              {isLoading && ' (refreshing...)'}
            </span>
          )}
        </div>
        <button
          onClick={refetch}
          className="text-xs text-text-muted hover:text-accent-neon transition-colors self-start sm:self-auto"
          aria-label="Refresh price data"
        >
          Refresh
        </button>
      </div>

      {/* ---------- category tabs ---------- */}
      <div
        className="flex flex-wrap gap-2 mb-4"
        role="tablist"
        aria-label="Equity category filter"
      >
        {CATEGORY_TABS.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={category === tab.key}
            aria-label={`Show ${tab.label}`}
            onClick={() => setCategory(tab.key)}
            className={`px-3 py-1 text-sm rounded-full transition-colors ${
              category === tab.key
                ? 'bg-accent-neon/20 text-accent-neon border border-accent-neon/40'
                : 'bg-bg-tertiary text-text-muted hover:text-text-primary border border-transparent'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ---------- search ---------- */}
      <div className="mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search ticker, name, company, sector..."
          aria-label="Search tokenized equities"
          className="w-full px-3 py-2 text-sm rounded-lg bg-bg-tertiary text-text-primary placeholder:text-text-muted border border-white/10 focus:border-accent-neon/50 focus:outline-none transition-colors"
        />
      </div>

      {/* ---------- table ---------- */}
      <div className="overflow-x-auto -mx-4 sm:-mx-6">
        <table className="w-full min-w-[640px] text-sm" role="grid">
          {/* -- header -- */}
          <thead>
            <tr className="text-left text-xs text-text-muted border-b border-white/10">
              {SORT_COLUMNS.map((col) => (
                <th key={col.field} className="px-4 sm:px-6 py-2 font-medium">
                  <button
                    onClick={() => handleSort(col.field)}
                    className="inline-flex items-center gap-1 hover:text-text-primary transition-colors"
                    aria-label={`Sort by ${col.label} ${
                      sort.field === col.field
                        ? sort.direction === 'asc'
                          ? 'descending'
                          : 'ascending'
                        : 'ascending'
                    }`}
                  >
                    {col.label}
                    {sort.field === col.field && (
                      <span aria-hidden="true">
                        {sort.direction === 'asc' ? '\u25B2' : '\u25BC'}
                      </span>
                    )}
                  </button>
                </th>
              ))}
              {/* trade column */}
              <th className="px-4 sm:px-6 py-2 font-medium text-right">Trade</th>
            </tr>
          </thead>

          {/* -- body -- */}
          <tbody>
            {rows.map((token) => {
              const dex = getDex(token.mintAddress);
              const change = dex?.priceChange24h ?? 0;
              const isPositive = change > 0;
              const isNeutral = change === 0;
              const changeArrow = isPositive ? '\u2191' : isNeutral ? '' : '\u2193';
              const changeColor = isPositive
                ? 'text-accent-neon'
                : isNeutral
                  ? 'text-text-muted'
                  : 'text-accent-error';

              return (
                <tr
                  key={token.mintAddress}
                  className="border-b border-white/5 hover:bg-white/[0.03] transition-colors"
                >
                  {/* Ticker + company */}
                  <td className="px-4 sm:px-6 py-3">
                    <div className="flex flex-col gap-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-bold font-mono text-text-primary">
                          {token.ticker}
                        </span>
                        <span className="px-1.5 py-0.5 text-[10px] rounded bg-bg-tertiary text-text-muted leading-tight">
                          {token.sector}
                        </span>
                      </div>
                      <span className="text-xs text-text-muted truncate max-w-[180px]">
                        {token.company}
                      </span>
                    </div>
                  </td>

                  {/* Price */}
                  <td className="px-4 sm:px-6 py-3 font-mono text-text-primary whitespace-nowrap">
                    {formatPrice(dex?.priceUsd)}
                  </td>

                  {/* 24h change */}
                  <td className={`px-4 sm:px-6 py-3 font-mono whitespace-nowrap ${changeColor}`}>
                    {dex ? (
                      <>
                        <span aria-hidden="true">{changeArrow}</span>
                        {' '}
                        {change >= 0 ? '+' : ''}
                        {change.toFixed(2)}%
                      </>
                    ) : (
                      '\u2014'
                    )}
                  </td>

                  {/* Volume */}
                  <td className="px-4 sm:px-6 py-3 font-mono text-text-muted whitespace-nowrap">
                    {dex && dex.volume24h > 0 ? formatCompact(dex.volume24h) : '\u2014'}
                  </td>

                  {/* FDV */}
                  <td className="px-4 sm:px-6 py-3 font-mono text-text-muted whitespace-nowrap">
                    {dex && dex.fdv > 0 ? formatCompact(dex.fdv) : '\u2014'}
                  </td>

                  {/* Trade */}
                  <td className="px-4 sm:px-6 py-3 text-right">
                    <QuickBuyWidget
                      tokenMint={token.mintAddress}
                      tokenSymbol={token.ticker}
                      compact
                    />
                  </td>
                </tr>
              );
            })}

            {rows.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 sm:px-6 py-8 text-center text-text-muted"
                >
                  No equities match your search.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* ---------- footer ---------- */}
      <div className="mt-3 flex items-center justify-between text-xs text-text-muted">
        <span>
          {rows.length} of {ALL_TOKENIZED_EQUITIES.length} equities
        </span>
        <a
          href="https://backed.fi"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-accent-neon transition-colors"
          aria-label="Visit backed.fi"
        >
          backed.fi
        </a>
      </div>
    </div>
  );
}

// Backward-compatible lowercase export
export { XStocksPanel as xStocksPanel };
