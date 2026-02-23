'use client';

import { useState, useEffect, useRef, useCallback, type KeyboardEvent } from 'react';
import { Search, Loader2, Clock, X } from 'lucide-react';
import { searchDexScreener, filterSolanaPairs, type DexScreenerPair } from '@/lib/dexscreener';
import { useTokenStore } from '@/stores/useTokenStore';

// ── Constants ────────────────────────────────────────────────────────

const DEBOUNCE_MS = 300;
const MAX_RESULTS = 10;

// ── Helpers ──────────────────────────────────────────────────────────

function formatPrice(priceUsd: string): string {
  const num = parseFloat(priceUsd);
  if (isNaN(num)) return '$0.00';
  if (num >= 1) return `$${num.toFixed(2)}`;
  if (num >= 0.01) return `$${num.toFixed(4)}`;
  return `$${num.toFixed(6)}`;
}

function formatVolume(vol: number): string {
  if (vol >= 1_000_000) return `$${(vol / 1_000_000).toFixed(1)}M`;
  if (vol >= 1_000) return `$${(vol / 1_000).toFixed(1)}K`;
  return `$${vol.toFixed(0)}`;
}

function formatPriceChange(change: number): { text: string; className: string } {
  const sign = change >= 0 ? '+' : '';
  const text = `${sign}${change.toFixed(1)}%`;
  const className = change >= 0
    ? 'text-accent-success'
    : 'text-accent-error';
  return { text, className };
}

// ── Component ────────────────────────────────────────────────────────

export function TokenSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<DexScreenerPair[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { setSelectedToken, addRecentSearch, recentSearches } = useTokenStore();

  // ── Debounced Search ─────────────────────────────────────────────

  const performSearch = useCallback(async (searchQuery: string) => {
    const trimmed = searchQuery.trim();
    if (trimmed.length === 0) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const allPairs = await searchDexScreener(trimmed);
      const solanaPairs = filterSolanaPairs(allPairs, MAX_RESULTS);
      setResults(solanaPairs);
    } catch {
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (query.trim().length === 0) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    debounceRef.current = setTimeout(() => {
      performSearch(query);
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query, performSearch]);

  // ── Click Outside ────────────────────────────────────────────────

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ── Selection ────────────────────────────────────────────────────

  const selectPair = useCallback(
    (pair: DexScreenerPair) => {
      setSelectedToken({
        address: pair.baseToken.address,
        name: pair.baseToken.name,
        symbol: pair.baseToken.symbol,
        poolAddress: pair.pairAddress,
      });
      addRecentSearch(pair.baseToken.symbol);
      setQuery('');
      setResults([]);
      setIsOpen(false);
      setActiveIndex(-1);
      inputRef.current?.blur();
    },
    [setSelectedToken, addRecentSearch]
  );

  const selectRecentSearch = useCallback(
    (search: string) => {
      setQuery(search);
      setIsOpen(true);
    },
    []
  );

  // ── Keyboard Navigation ──────────────────────────────────────────

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
        setActiveIndex(-1);
        inputRef.current?.blur();
        return;
      }

      const showingRecent = query.trim().length === 0 && recentSearches.length > 0;
      const itemCount = showingRecent ? recentSearches.length : results.length;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((prev) => (prev + 1) % itemCount);
        return;
      }

      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((prev) => (prev <= 0 ? itemCount - 1 : prev - 1));
        return;
      }

      if (e.key === 'Enter' && activeIndex >= 0) {
        e.preventDefault();
        if (showingRecent) {
          selectRecentSearch(recentSearches[activeIndex]);
        } else if (results[activeIndex]) {
          selectPair(results[activeIndex]);
        }
        return;
      }
    },
    [query, results, recentSearches, activeIndex, selectPair, selectRecentSearch]
  );

  // ── Derived State ────────────────────────────────────────────────

  const showRecent = isOpen && query.trim().length === 0 && recentSearches.length > 0;
  const showResults = isOpen && query.trim().length > 0;
  const showDropdown = showRecent || showResults;

  // ── Render ───────────────────────────────────────────────────────

  return (
    <div className="relative w-full max-w-full sm:max-w-lg">
      {/* Search Input */}
      <div className="relative">
        <Search
          className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted pointer-events-none"
          aria-hidden="true"
        />
        <input
          id="token-search-input"
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
            setActiveIndex(-1);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search tokens..."
          className="w-full pl-9 pr-9 py-2 bg-bg-secondary/60 backdrop-blur-sm border border-border-primary rounded-lg
                     text-sm font-mono text-text-primary placeholder:text-text-muted
                     focus:outline-none focus:border-accent-neon/50 focus:ring-1 focus:ring-accent-neon/20
                     transition-all duration-200"
          role="combobox"
          aria-expanded={showDropdown}
          aria-haspopup="listbox"
          aria-controls="token-search-listbox"
          aria-label="Search Solana tokens"
          aria-activedescendant={
            activeIndex >= 0 ? `token-search-option-${activeIndex}` : undefined
          }
          autoComplete="off"
        />
        {isLoading && (
          <Loader2
            className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-accent-neon animate-spin"
            aria-label="Loading results"
          />
        )}
        {!isLoading && query.length > 0 && (
          <button
            onClick={() => {
              setQuery('');
              setResults([]);
              setActiveIndex(-1);
              inputRef.current?.focus();
            }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
            aria-label="Clear search"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <div
          ref={dropdownRef}
          id="token-search-listbox"
          role="listbox"
          aria-label="Search results"
          className="absolute top-full mt-1 w-full card-glass border border-border-primary rounded-lg shadow-xl
                     shadow-black/30 overflow-hidden z-50 max-h-[400px] overflow-y-auto custom-scrollbar"
        >
          {/* Recent Searches */}
          {showRecent && (
            <div>
              <div className="px-3 py-2 text-[10px] font-mono uppercase tracking-wider text-text-muted border-b border-border-primary/50">
                Recent Searches
              </div>
              {recentSearches.map((search, i) => (
                <button
                  key={search}
                  id={`token-search-option-${i}`}
                  role="option"
                  aria-selected={i === activeIndex}
                  onClick={() => selectRecentSearch(search)}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors
                    ${i === activeIndex
                      ? 'bg-accent-neon/10 text-accent-neon'
                      : 'text-text-primary hover:bg-bg-secondary/80'
                    }`}
                >
                  <Clock className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
                  <span className="font-mono">{search}</span>
                </button>
              ))}
            </div>
          )}

          {/* Search Results */}
          {showResults && (
            <div>
              {isLoading && results.length === 0 && (
                <div className="flex items-center justify-center py-8 gap-2">
                  <Loader2 className="w-4 h-4 text-accent-neon animate-spin" />
                  <span className="text-xs font-mono text-text-muted">Searching DexScreener...</span>
                </div>
              )}

              {!isLoading && results.length === 0 && query.trim().length > 0 && (
                <div className="py-6 text-center">
                  <span className="text-xs font-mono text-text-muted">No Solana tokens found</span>
                </div>
              )}

              {results.map((pair, i) => {
                const price = formatPrice(pair.priceUsd);
                const volume = formatVolume(pair.volume.h24);
                const change = formatPriceChange(pair.priceChange.h24);

                return (
                  <button
                    key={`${pair.baseToken.address}-${pair.pairAddress}`}
                    id={`token-search-option-${i}`}
                    role="option"
                    aria-selected={i === activeIndex}
                    onClick={() => selectPair(pair)}
                    className={`w-full flex items-center justify-between px-3 py-2.5 text-left transition-colors
                      ${i === activeIndex
                        ? 'bg-accent-neon/10'
                        : 'hover:bg-bg-secondary/80'
                      }`}
                  >
                    {/* Left: Token Info */}
                    <div className="flex flex-col min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-sm text-text-primary truncate">
                          {pair.baseToken.symbol}
                        </span>
                        <span className="text-[10px] font-mono text-text-muted px-1.5 py-0.5 bg-bg-secondary/60 rounded">
                          {pair.dexId}
                        </span>
                      </div>
                      <span className="text-[11px] text-text-muted truncate max-w-[200px]">
                        {pair.baseToken.name}
                      </span>
                    </div>

                    {/* Right: Price & Stats */}
                    <div className="flex flex-col items-end flex-shrink-0 ml-3">
                      <span className="font-mono text-sm font-bold text-text-primary">
                        {price}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className={`font-mono text-[11px] font-medium ${change.className}`}>
                          {change.text}
                        </span>
                        <span className="font-mono text-[10px] text-text-muted">
                          Vol {volume}
                        </span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
