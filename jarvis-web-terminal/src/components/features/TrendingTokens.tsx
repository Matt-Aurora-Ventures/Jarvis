'use client';

/**
 * TrendingTokens
 *
 * Compact component showing the hottest tokens on Solana using
 * DexScreener's token-boosts API. Auto-refreshes every 60 seconds.
 * Clicking a token updates the global useTokenStore to navigate
 * the chart + trade panel.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { Flame, TrendingUp, TrendingDown, Minus, ExternalLink, RefreshCw } from 'lucide-react';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { useTokenStore } from '@/stores/useTokenStore';
import { QuickBuyWidget } from '@/components/features/QuickBuyWidget';
import {
  fetchTrendingTokens,
  enrichTrendingTokens,
  formatCompactNumber,
  type EnrichedTrendingToken,
} from '@/lib/dexscreener';

// ── Constants ────────────────────────────────────────────────────────

const REFRESH_INTERVAL_MS = 60_000; // 60 seconds
const MAX_DISPLAY = 8;

// ── Helpers ──────────────────────────────────────────────────────────

function formatPrice(price: string): string {
  const num = parseFloat(price);
  if (isNaN(num) || num === 0) return '$0.00';
  if (num < 0.0001) return `$${num.toExponential(2)}`;
  if (num < 0.01) return `$${num.toFixed(6)}`;
  if (num < 1) return `$${num.toFixed(4)}`;
  if (num < 1000) return `$${num.toFixed(2)}`;
  return `$${num.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
}

// ── Component ────────────────────────────────────────────────────────

export function TrendingTokens() {
  const [tokens, setTokens] = useState<EnrichedTrendingToken[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const setSelectedToken = useTokenStore((s) => s.setSelectedToken);

  const loadTrending = useCallback(async (showRefresh = false) => {
    if (showRefresh) setIsRefreshing(true);
    try {
      // Step 1: Get trending/boosted token addresses
      const boosted = await fetchTrendingTokens();
      if (boosted.length === 0) {
        setTokens([]);
        setError(null);
        setIsLoading(false);
        setIsRefreshing(false);
        return;
      }

      // Step 2: Enrich with price data (take top N addresses)
      const addresses = boosted.slice(0, MAX_DISPLAY).map((t) => t.tokenAddress);
      const enriched = await enrichTrendingTokens(addresses);

      setTokens(enriched);
      setError(null);
    } catch {
      setError('Failed to load trending tokens');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  // Initial load + interval
  useEffect(() => {
    loadTrending();
    intervalRef.current = setInterval(() => loadTrending(), REFRESH_INTERVAL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [loadTrending]);

  const handleTokenClick = (token: EnrichedTrendingToken) => {
    setSelectedToken({
      address: token.address,
      name: token.name,
      symbol: token.symbol,
      poolAddress: token.poolAddress,
    });
  };

  // ── Loading state ──────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="card-glass p-4">
        <div className="flex items-center gap-2 mb-3">
          <Flame className="w-4 h-4 text-accent-neon" />
          <h3 className="text-sm font-semibold text-text-primary">TRENDING ON SOLANA</h3>
        </div>
        <SkeletonTable rows={5} />
      </div>
    );
  }

  // ── Error state ────────────────────────────────────────────────────

  if (error && tokens.length === 0) {
    return (
      <div className="card-glass p-4">
        <div className="flex items-center gap-2 mb-2">
          <Flame className="w-4 h-4 text-accent-neon" />
          <h3 className="text-sm font-semibold text-text-primary">TRENDING ON SOLANA</h3>
        </div>
        <p className="text-xs text-text-muted">{error}</p>
      </div>
    );
  }

  // ── Empty state ────────────────────────────────────────────────────

  if (tokens.length === 0) {
    return (
      <div className="card-glass p-4">
        <div className="flex items-center gap-2 mb-2">
          <Flame className="w-4 h-4 text-accent-neon" />
          <h3 className="text-sm font-semibold text-text-primary">TRENDING ON SOLANA</h3>
        </div>
        <p className="text-xs text-text-muted">No trending tokens found</p>
      </div>
    );
  }

  // ── Main render ────────────────────────────────────────────────────

  return (
    <div className="card-glass p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Flame className="w-4 h-4 text-accent-neon" />
          <h3 className="text-sm font-semibold text-text-primary">TRENDING ON SOLANA</h3>
        </div>
        <button
          onClick={() => loadTrending(true)}
          disabled={isRefreshing}
          className="text-text-muted hover:text-text-primary transition-colors disabled:opacity-50"
          title="Refresh trending"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Token List */}
      <div className="space-y-1">
        {tokens.slice(0, MAX_DISPLAY).map((token, index) => {
          const change = token.priceChange24h;
          const isPositive = change > 0;
          const isNegative = change < 0;
          const TrendIcon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;
          const changeColor = isPositive
            ? 'text-accent-success'
            : isNegative
              ? 'text-accent-error'
              : 'text-text-muted';

          return (
            <button
              key={token.address}
              onClick={() => handleTokenClick(token)}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg
                         hover:bg-bg-tertiary/60 transition-all group cursor-pointer text-left"
            >
              {/* Rank */}
              <span className="text-xs font-mono text-text-muted w-5 shrink-0">
                {index + 1}.
              </span>

              {/* Symbol + Name + Address */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-semibold text-text-primary group-hover:text-accent-neon transition-colors">
                    {token.symbol}
                  </span>
                  <span className="text-[10px] font-mono text-text-muted hidden sm:inline">
                    {token.address.slice(0, 4)}...{token.address.slice(-4)}
                  </span>
                </div>
                <span className="text-xs text-text-muted hidden sm:inline truncate">
                  {token.name}
                </span>
              </div>

              {/* Price */}
              <span className="text-sm font-mono text-text-primary shrink-0">
                {formatPrice(token.priceUsd)}
              </span>

              {/* 24h Change */}
              <div className={`flex items-center gap-1 shrink-0 ${changeColor}`}>
                <TrendIcon className="w-3 h-3" />
                <span className="text-xs font-mono">
                  {isPositive ? '+' : ''}{change?.toFixed(1) ?? '0.0'}%
                </span>
              </div>

              {/* Volume */}
              <span className="text-xs font-mono text-text-muted shrink-0 hidden md:inline w-16 text-right">
                {formatCompactNumber(token.volume24h)}
              </span>

              {/* Quick Buy */}
              <div className="shrink-0" onClick={(e) => e.stopPropagation()}>
                <QuickBuyWidget
                  tokenMint={token.address}
                  tokenSymbol={token.symbol}
                  compact
                  defaultAmount={0.25}
                />
              </div>
            </button>
          );
        })}
      </div>

      {/* View All link */}
      <div className="mt-3 pt-2 border-t border-border-primary">
        <a
          href="/launches"
          className="flex items-center justify-center gap-1 text-xs text-text-muted hover:text-accent-neon transition-colors"
        >
          View All Launches
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
}
