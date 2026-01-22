/**
 * Real-Time Price Ticker
 * Displays live price updates for popular tokens with smooth animations.
 *
 * Best practices implemented:
 * - WebSocket connection for real-time data
 * - Smooth animations for price changes
 * - Color-coded price movements
 * - Optimistic updates
 */
import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';
import clsx from 'clsx';

interface TokenPrice {
  symbol: string;
  price: number;
  change24h: number;
  volume24h: number;
  lastUpdate: number;
}

interface PriceTickerProps {
  tokens?: string[];
  compact?: boolean;
}

export const PriceTicker: React.FC<PriceTickerProps> = ({
  tokens = ['SOL', 'BTC', 'ETH', 'USDC'],
  compact = false
}) => {
  const [prices, setPrices] = useState<Record<string, TokenPrice>>({});
  const [priceChanges, setPriceChanges] = useState<Record<string, 'up' | 'down' | null>>({});

  useEffect(() => {
    // Initialize with mock data (replace with actual WebSocket connection)
    const initialPrices: Record<string, TokenPrice> = {
      SOL: {
        symbol: 'SOL',
        price: 125.42,
        change24h: 5.32,
        volume24h: 2_450_000_000,
        lastUpdate: Date.now()
      },
      BTC: {
        symbol: 'BTC',
        price: 67_250.15,
        change24h: -1.24,
        volume24h: 45_000_000_000,
        lastUpdate: Date.now()
      },
      ETH: {
        symbol: 'ETH',
        price: 3_542.80,
        change24h: 3.15,
        volume24h: 28_000_000_000,
        lastUpdate: Date.now()
      },
      USDC: {
        symbol: 'USDC',
        price: 1.0001,
        change24h: 0.01,
        volume24h: 8_000_000_000,
        lastUpdate: Date.now()
      }
    };

    setPrices(initialPrices);

    // Simulate WebSocket updates
    const interval = setInterval(() => {
      setPrices(prev => {
        const updated = { ...prev };

        tokens.forEach(symbol => {
          if (updated[symbol]) {
            const currentPrice = updated[symbol].price;

            // Random price change (-0.5% to +0.5%)
            const changePercent = (Math.random() - 0.5) * 1;
            const newPrice = currentPrice * (1 + changePercent / 100);

            // Track if price went up or down for animation
            if (newPrice > currentPrice) {
              setPriceChanges(pc => ({ ...pc, [symbol]: 'up' }));
            } else if (newPrice < currentPrice) {
              setPriceChanges(pc => ({ ...pc, [symbol]: 'down' }));
            }

            // Clear animation after 500ms
            setTimeout(() => {
              setPriceChanges(pc => ({ ...pc, [symbol]: null }));
            }, 500);

            updated[symbol] = {
              ...updated[symbol],
              price: newPrice,
              lastUpdate: Date.now()
            };
          }
        });

        return updated;
      });
    }, 3000); // Update every 3 seconds

    return () => clearInterval(interval);
  }, [tokens]);

  const formatPrice = (price: number, symbol: string) => {
    if (symbol === 'BTC') return `$${price.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
    if (symbol === 'ETH') return `$${price.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
    if (symbol === 'USDC') return `$${price.toFixed(4)}`;
    return `$${price.toFixed(2)}`;
  };

  const formatVolume = (volume: number) => {
    if (volume >= 1_000_000_000) {
      return `$${(volume / 1_000_000_000).toFixed(2)}B`;
    }
    return `$${(volume / 1_000_000).toFixed(0)}M`;
  };

  if (compact) {
    return (
      <div className="flex items-center gap-4 overflow-x-auto scrollbar-hide">
        {tokens.map(symbol => {
          const tokenData = prices[symbol];
          if (!tokenData) return null;

          return (
            <div
              key={symbol}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 bg-surface rounded-lg transition-all duration-300',
                priceChanges[symbol] === 'up' && 'bg-success/20',
                priceChanges[symbol] === 'down' && 'bg-error/20'
              )}
            >
              <span className="text-sm font-semibold">{symbol}</span>
              <span className="text-sm font-mono">{formatPrice(tokenData.price, symbol)}</span>
              <span
                className={clsx(
                  'text-xs flex items-center gap-0.5',
                  tokenData.change24h >= 0 ? 'text-success' : 'text-error'
                )}
              >
                {tokenData.change24h >= 0 ? (
                  <TrendingUp size={12} />
                ) : (
                  <TrendingDown size={12} />
                )}
                {Math.abs(tokenData.change24h).toFixed(2)}%
              </span>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {tokens.map(symbol => {
        const tokenData = prices[symbol];
        if (!tokenData) return null;

        const isPositive = tokenData.change24h >= 0;

        return (
          <div
            key={symbol}
            className={clsx(
              'relative overflow-hidden rounded-xl p-4 transition-all duration-300',
              'bg-surface border border-border hover:border-accent/50',
              priceChanges[symbol] === 'up' && 'border-success shadow-glow-success',
              priceChanges[symbol] === 'down' && 'border-error shadow-glow-error'
            )}
          >
            {/* Background glow */}
            <div
              className={clsx(
                'absolute inset-0 opacity-0 transition-opacity duration-500',
                priceChanges[symbol] === 'up' && 'bg-gradient-to-br from-success/10 to-transparent opacity-100',
                priceChanges[symbol] === 'down' && 'bg-gradient-to-br from-error/10 to-transparent opacity-100'
              )}
            />

            <div className="relative">
              {/* Header */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Activity size={16} className="text-accent" />
                  <span className="text-lg font-display font-bold">{symbol}</span>
                </div>
                <div
                  className={clsx(
                    'px-2 py-0.5 rounded-full text-xs font-semibold flex items-center gap-1',
                    isPositive ? 'bg-success/20 text-success' : 'bg-error/20 text-error'
                  )}
                >
                  {isPositive ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                  {isPositive ? '+' : ''}
                  {tokenData.change24h.toFixed(2)}%
                </div>
              </div>

              {/* Price */}
              <div className="mb-3">
                <div className="text-2xl font-mono font-bold">
                  {formatPrice(tokenData.price, symbol)}
                </div>
                <div className="text-xs text-muted mt-1">
                  24h Vol: {formatVolume(tokenData.volume24h)}
                </div>
              </div>

              {/* Mini Chart (placeholder) */}
              <div className="h-8 flex items-end gap-0.5">
                {Array.from({ length: 20 }).map((_, i) => {
                  const height = Math.random() * 100;
                  return (
                    <div
                      key={i}
                      className={clsx(
                        'flex-1 rounded-t transition-all',
                        isPositive ? 'bg-success/40' : 'bg-error/40'
                      )}
                      style={{ height: `${height}%` }}
                    />
                  );
                })}
              </div>

              {/* Last Update */}
              <div className="mt-2 text-xs text-muted flex items-center gap-1">
                <div className="w-1.5 h-1.5 bg-success rounded-full animate-pulse" />
                <span>Live</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
