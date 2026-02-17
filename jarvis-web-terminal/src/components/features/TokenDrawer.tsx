'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useTokenStore } from '@/stores/useTokenStore';
import {
  X,
  Copy,
  Check,
  ExternalLink,
  TrendingUp,
  TrendingDown,
  Minus,
  BarChart3,
  DollarSign,
  Droplets,
  Brain,
  Loader2,
} from 'lucide-react';
import { QuickBuyWidget } from '@/components/features/QuickBuyWidget';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DexPairData {
  baseToken: { symbol: string; name: string };
  priceUsd: string;
  priceChange: { h24: number };
  volume: { h24: number };
  fdv: number;
  liquidity: { usd: number };
}

interface DexScreenerResponse {
  pairs: DexPairData[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCompact(num: number): string {
  if (num >= 1e12) return '$' + (num / 1e12).toFixed(2) + 'T';
  if (num >= 1e9) return '$' + (num / 1e9).toFixed(2) + 'B';
  if (num >= 1e6) return '$' + (num / 1e6).toFixed(2) + 'M';
  if (num >= 1e3) return '$' + (num / 1e3).toFixed(2) + 'K';
  return '$' + num.toFixed(2);
}

function formatPrice(priceStr: string): string {
  const price = parseFloat(priceStr);
  if (isNaN(price)) return '$0.00';
  if (price < 0.0001) return '$' + price.toExponential(2);
  if (price < 1) return '$' + price.toFixed(6);
  if (price < 1000) return '$' + price.toFixed(2);
  return '$' + price.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function truncateAddress(addr: string): string {
  if (addr.length <= 12) return addr;
  return addr.slice(0, 6) + '...' + addr.slice(-4);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TokenDrawer() {
  const selectedToken = useTokenStore((s) => s.selectedToken);
  const [isOpen, setIsOpen] = useState(false);
  const [dexData, setDexData] = useState<DexPairData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  // Open drawer when token is selected
  useEffect(() => {
    if (selectedToken) {
      setIsOpen(true);
      setDexData(null);
    }
  }, [selectedToken]);

  // Fetch DexScreener data
  useEffect(() => {
    if (!selectedToken?.address) return;

    let cancelled = false;
    setIsLoading(true);

    fetch(`https://api.dexscreener.com/tokens/v1/solana/${selectedToken.address}`)
      .then((res) => {
        if (!res.ok) throw new Error(`DexScreener ${res.status}`);
        return res.json() as Promise<DexScreenerResponse>;
      })
      .then((data) => {
        if (!cancelled && data.pairs?.length > 0) {
          setDexData(data.pairs[0]);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error('DexScreener fetch error:', err);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedToken?.address]);

  // Close handler
  const close = useCallback(() => {
    setIsOpen(false);
  }, []);

  // Escape key handler
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && isOpen) {
        close();
      }
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [isOpen, close]);

  // Copy address
  const copyAddress = useCallback(async () => {
    if (!selectedToken?.address) return;
    try {
      await navigator.clipboard.writeText(selectedToken.address);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      console.error('Failed to copy address');
    }
  }, [selectedToken]);

  // Don't render anything if not open
  if (!isOpen || !selectedToken) return null;

  const priceChange = dexData?.priceChange?.h24 ?? 0;
  const isPositive = priceChange > 0;
  const isNegative = priceChange < 0;
  const TrendIcon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;
  const trendColor = isPositive
    ? 'text-emerald-400'
    : isNegative
      ? 'text-red-400'
      : 'text-text-muted';

  return (
    <>
      {/* Overlay */}
      <div
        data-testid="token-drawer-overlay"
        className="fixed inset-0 bg-black/40 z-40 transition-opacity duration-300"
        onClick={close}
      />

      {/* Drawer Panel */}
      <div
        ref={drawerRef}
        data-testid="token-drawer"
        className="fixed top-0 right-0 h-full w-80 sm:w-96 z-50
          bg-bg-primary/95 backdrop-blur-xl border-l border-border-primary
          shadow-2xl shadow-black/30
          transform transition-transform duration-300 ease-out
          translate-x-0 overflow-y-auto"
      >
        {/* Header */}
        <div className="sticky top-0 bg-bg-primary/95 backdrop-blur-xl border-b border-border-primary p-4 z-10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 min-w-0">
              {selectedToken.logoURI && (
                <img
                  src={selectedToken.logoURI}
                  alt={selectedToken.symbol}
                  className="w-8 h-8 rounded-full flex-shrink-0"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              )}
              <div className="min-w-0">
                <h2 className="text-lg font-bold text-text-primary truncate">
                  {selectedToken.symbol}
                </h2>
                <p className="text-xs text-text-muted truncate">{selectedToken.name}</p>
              </div>
            </div>
            <button
              data-testid="token-drawer-close"
              onClick={close}
              className="p-1.5 rounded-lg hover:bg-bg-secondary text-text-muted hover:text-text-primary transition-colors flex-shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Copyable Address */}
          <button
            data-testid="copy-address"
            onClick={copyAddress}
            className="mt-2 flex items-center gap-1.5 text-xs text-text-muted hover:text-accent-neon transition-colors font-mono"
          >
            {truncateAddress(selectedToken.address)}
            {copied ? (
              <Check className="w-3 h-3 text-emerald-400" />
            ) : (
              <Copy className="w-3 h-3" />
            )}
          </button>
        </div>

        {/* Body */}
        <div className="p-4 space-y-4">
          {/* Price & Market Data */}
          <section className="space-y-3">
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
              Market Data
            </h3>

            {isLoading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="w-5 h-5 text-accent-neon animate-spin" />
              </div>
            ) : dexData ? (
              <div className="space-y-2">
                {/* Price Row */}
                <div className="flex items-center justify-between">
                  <span className="text-text-muted text-sm">Price</span>
                  <div className="flex items-center gap-2">
                    <span className="text-text-primary font-mono font-semibold">
                      {formatPrice(dexData.priceUsd)}
                    </span>
                    <span className={`flex items-center gap-0.5 text-xs font-medium ${trendColor}`}>
                      <TrendIcon className="w-3 h-3" />
                      {isPositive ? '+' : ''}
                      {priceChange.toFixed(1)}%
                    </span>
                  </div>
                </div>

                {/* Volume */}
                <div className="flex items-center justify-between">
                  <span className="text-text-muted text-sm flex items-center gap-1.5">
                    <BarChart3 className="w-3.5 h-3.5" />
                    Volume 24h
                  </span>
                  <span className="text-text-primary font-mono text-sm">
                    {formatCompact(dexData.volume.h24)}
                  </span>
                </div>

                {/* FDV */}
                <div className="flex items-center justify-between">
                  <span className="text-text-muted text-sm flex items-center gap-1.5">
                    <DollarSign className="w-3.5 h-3.5" />
                    FDV
                  </span>
                  <span className="text-text-primary font-mono text-sm">
                    {formatCompact(dexData.fdv)}
                  </span>
                </div>

                {/* Liquidity */}
                <div className="flex items-center justify-between">
                  <span className="text-text-muted text-sm flex items-center gap-1.5">
                    <Droplets className="w-3.5 h-3.5" />
                    Liquidity
                  </span>
                  <span className="text-text-primary font-mono text-sm">
                    {formatCompact(dexData.liquidity.usd)}
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-text-muted text-sm text-center py-4">
                No market data available
              </p>
            )}
          </section>

          <div className="border-t border-border-primary" />

          {/* Quick Links */}
          <section className="space-y-3">
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
              Quick Links
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <ExternalLinkButton
                href={`https://dexscreener.com/solana/${selectedToken.address}`}
                label="DexScreener"
              />
              <ExternalLinkButton
                href={`https://birdeye.so/token/${selectedToken.address}?chain=solana`}
                label="Birdeye"
              />
              <ExternalLinkButton
                href={`https://solscan.io/token/${selectedToken.address}`}
                label="Solscan"
              />
              <ExternalLinkButton
                href={`https://jup.ag/swap/SOL-${selectedToken.address}`}
                label="Jupiter"
              />
            </div>
          </section>

          <div className="border-t border-border-primary" />

          {/* CTA: Quick Buy via Bags API */}
          <QuickBuyWidget
            tokenMint={selectedToken.address}
            tokenSymbol={selectedToken.symbol}
            suggestedTP={20}
            suggestedSL={10}
          />

          {/* Secondary: Advanced Jupiter link */}
          <a
            data-testid="jupiter-swap-link"
            href={`https://jup.ag/swap/SOL-${selectedToken.address}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-1.5 mt-2 text-xs text-text-muted
              hover:text-accent-neon transition-colors"
          >
            Advanced: Trade on Jupiter
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ExternalLinkButton({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg
        bg-bg-secondary/60 border border-border-primary
        text-text-muted text-xs font-medium
        hover:bg-bg-secondary hover:text-text-primary hover:border-accent-neon/30
        transition-all duration-200"
    >
      {label}
      <ExternalLink className="w-3 h-3" />
    </a>
  );
}
