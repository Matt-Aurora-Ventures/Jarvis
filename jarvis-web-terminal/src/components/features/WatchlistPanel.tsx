'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useTokenStore } from '@/stores/useTokenStore';
import { usePriceFlash } from '@/hooks/usePriceFlash';
import { Eye, Plus, X, RefreshCw, ChevronDown, ChevronUp, Star } from 'lucide-react';
import { SkeletonTable } from '@/components/ui/Skeleton';

// ── Constants ────────────────────────────────────────────────────────

const REFRESH_INTERVAL_MS = 30_000; // 30 seconds

// ── Types ────────────────────────────────────────────────────────────

interface WatchlistPrice {
  price: number;
  change24h: number;
}

// ── Helpers ──────────────────────────────────────────────────────────

function formatPrice(price: number): string {
  if (price === 0) return '$0.00';
  if (price < 0.0001) return `$${price.toExponential(2)}`;
  if (price < 0.01) return `$${price.toFixed(6)}`;
  if (price < 1) return `$${price.toFixed(4)}`;
  if (price < 1000) return `$${price.toFixed(2)}`;
  return `$${price.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
}

function truncateAddress(address: string): string {
  if (address.length <= 8) return address;
  return `${address.slice(0, 4)}...${address.slice(-4)}`;
}

// ── Watchlist Row Sub-Component ───────────────────────────────────────

interface WatchlistRowProps {
  address: string;
  priceData: WatchlistPrice | undefined;
  isSelected: boolean;
  isLoading: boolean;
  onSelect: (address: string) => void;
  onRemove: (address: string) => void;
}

function WatchlistRow({ address, priceData, isSelected, isLoading, onSelect, onRemove }: WatchlistRowProps) {
  const priceFlash = usePriceFlash(priceData?.price ?? 0);

  return (
    <div
      role="listitem"
      onClick={() => onSelect(address)}
      className={`flex items-center justify-between gap-2 px-2 py-1.5 rounded-lg cursor-pointer
                  transition-all group ${
                    isSelected
                      ? 'bg-accent-neon/10 border border-accent-neon/20'
                      : 'bg-bg-tertiary/30 border border-transparent hover:bg-bg-tertiary/60 hover:border-border-hover'
                  }`}
    >
      {/* Left: Symbol/Address */}
      <div className="flex-1 min-w-0">
        <div className="text-xs font-mono font-semibold text-text-primary truncate">
          {truncateAddress(address)}
        </div>
      </div>

      {/* Right: Price + Remove */}
      <div className="flex items-center gap-2">
        {priceData ? (
          <span className={`text-xs font-mono text-text-secondary rounded px-0.5 ${priceFlash}`}>
            {formatPrice(priceData.price)}
          </span>
        ) : isLoading ? (
          <span className="text-[10px] font-mono text-text-muted animate-pulse">
            ...
          </span>
        ) : (
          <span className="text-[10px] font-mono text-text-muted">--</span>
        )}

        {/* Remove button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove(address);
          }}
          className="p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-accent-error/20 transition-all"
          title="Remove from watchlist"
          aria-label={`Remove ${truncateAddress(address)} from watchlist`}
        >
          <X className="w-3 h-3 text-accent-error" />
        </button>
      </div>
    </div>
  );
}

// ── Component ────────────────────────────────────────────────────────

export function WatchlistPanel() {
  const watchlist = useTokenStore((s) => s.watchlist);
  const selectedToken = useTokenStore((s) => s.selectedToken);
  const addToWatchlist = useTokenStore((s) => s.addToWatchlist);
  const removeFromWatchlist = useTokenStore((s) => s.removeFromWatchlist);
  const setSelectedToken = useTokenStore((s) => s.setSelectedToken);

  const [prices, setPrices] = useState<Map<string, WatchlistPrice>>(new Map());
  const [isLoading, setIsLoading] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Determine if current token can be added
  const currentAddress = selectedToken?.address ?? '';
  const canAddCurrent = currentAddress !== '' && !watchlist.includes(currentAddress);

  // Fetch prices for all watchlist tokens from Jupiter
  const fetchPrices = useCallback(async () => {
    if (watchlist.length === 0) {
      setPrices(new Map());
      return;
    }

    setIsLoading(true);
    try {
      const mints = watchlist.join(',');
      const res = await fetch(`https://api.jup.ag/price/v2?ids=${mints}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();

      const newPrices = new Map<string, WatchlistPrice>();
      const data = json.data as Record<string, { price: string }> | undefined;

      if (data) {
        for (const [mint, info] of Object.entries(data)) {
          const price = parseFloat(info.price);
          if (!isNaN(price)) {
            // Jupiter v2 does not return 24h change; default to 0
            newPrices.set(mint, { price, change24h: 0 });
          }
        }
      }

      setPrices(newPrices);
    } catch (e) {
      console.error('[WatchlistPanel] Failed to fetch prices:', e);
    } finally {
      setIsLoading(false);
    }
  }, [watchlist]);

  // Initial fetch + interval
  useEffect(() => {
    fetchPrices();

    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(fetchPrices, REFRESH_INTERVAL_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchPrices]);

  // Handle clicking a watchlist row to select that token
  const handleSelect = (address: string) => {
    setSelectedToken({
      address,
      name: truncateAddress(address),
      symbol: truncateAddress(address),
    });
  };

  // Handle adding current token
  const handleAddCurrent = () => {
    if (selectedToken) {
      addToWatchlist(selectedToken.address);
    }
  };

  return (
    <div className="card-glass p-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Eye className="w-4 h-4 text-accent-neon" />
          <span className="text-xs font-mono uppercase tracking-wider text-text-muted">
            WATCHLIST
          </span>
          {watchlist.length > 0 && (
            <span className="text-[10px] font-mono text-text-muted bg-bg-tertiary/50 px-1.5 py-0.5 rounded">
              {watchlist.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {/* Add Current Token */}
          {canAddCurrent && (
            <button
              onClick={handleAddCurrent}
              className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-mono font-bold uppercase
                         bg-accent-neon/10 text-accent-neon border border-accent-neon/20
                         hover:bg-accent-neon/20 hover:border-accent-neon/40 transition-all"
              title={`Add ${selectedToken?.symbol ?? 'current token'} to watchlist`}
            >
              <Plus className="w-3 h-3" />
              ADD
            </button>
          )}
          {/* Refresh */}
          <button
            onClick={fetchPrices}
            disabled={isLoading}
            className="p-1.5 rounded-lg hover:bg-bg-tertiary transition-all"
            title="Refresh prices"
            aria-label="Refresh watchlist prices"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 text-text-muted hover:text-accent-neon transition-colors ${
                isLoading ? 'animate-spin' : ''
              }`}
            />
          </button>
          {/* Expand/Collapse */}
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1.5 rounded-lg hover:bg-bg-tertiary transition-all"
            title={expanded ? 'Collapse' : 'Expand'}
            aria-expanded={expanded}
            aria-label={expanded ? 'Collapse watchlist' : 'Expand watchlist'}
          >
            {expanded ? (
              <ChevronUp className="w-3.5 h-3.5 text-text-muted" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 text-text-muted" />
            )}
          </button>
        </div>
      </div>

      {expanded && (
        <>
          {/* Empty State */}
          {watchlist.length === 0 && (
            <div className="flex flex-col items-center justify-center py-6 gap-2">
              <Star className="w-6 h-6 text-text-muted/40" />
              <p className="text-[11px] text-text-muted text-center leading-relaxed">
                Add tokens to your watchlist
              </p>
              {selectedToken && (
                <button
                  onClick={handleAddCurrent}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-mono font-semibold
                             bg-accent-neon/10 text-accent-neon border border-accent-neon/20
                             hover:bg-accent-neon/20 hover:border-accent-neon/40 transition-all"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add {selectedToken.symbol}
                </button>
              )}
            </div>
          )}

          {/* Watchlist Rows */}
          {watchlist.length > 0 && isLoading && prices.size === 0 && (
            <SkeletonTable rows={Math.min(watchlist.length, 3)} />
          )}
          {watchlist.length > 0 && (prices.size > 0 || !isLoading) && (
            <div className="flex flex-col gap-1 max-h-[280px] overflow-y-auto custom-scrollbar" role="list" aria-label="Watchlist tokens">
              {watchlist.map((address) => (
                <WatchlistRow
                  key={address}
                  address={address}
                  priceData={prices.get(address)}
                  isSelected={selectedToken?.address === address}
                  isLoading={isLoading}
                  onSelect={handleSelect}
                  onRemove={removeFromWatchlist}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
