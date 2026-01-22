/**
 * Real-Time Price Ticker (WebSocket Version)
 * Displays live price updates using WebSocket connections.
 *
 * Features:
 * - Real WebSocket connections to backend
 * - Smooth animations for price changes
 * - Color-coded price movements
 * - Auto-reconnect on disconnect
 * - Connection status indicators
 */
import React, { useState, useCallback } from 'react';
import { TrendingUp, TrendingDown, Activity, Wifi, WifiOff } from 'lucide-react';
import clsx from 'clsx';
import { usePriceWebSocket, PriceUpdate } from '../../hooks/usePriceWebSocket';
import { getTokenBySymbol } from '../../constants/tokens';

interface TokenPriceData {
  symbol: string;
  address: string;
  price: number;
  change24h: number;
  volume24h: number;
  lastUpdate: number;
  priceDirection: 'up' | 'down' | null;
}

interface RealTimePriceTickerProps {
  tokens?: string[]; // Token symbols
  compact?: boolean;
}

const TokenPriceItem: React.FC<{
  symbol: string;
  address: string;
  compact?: boolean;
}> = ({ symbol, address, compact }) => {
  const [priceData, setPriceData] = useState<TokenPriceData>({
    symbol,
    address,
    price: 0,
    change24h: 0,
    volume24h: 0,
    lastUpdate: Date.now(),
    priceDirection: null
  });

  const handlePriceUpdate = useCallback((update: PriceUpdate) => {
    setPriceData((prev) => {
      // Determine price direction
      let direction: 'up' | 'down' | null = null;
      if (update.price > prev.price) {
        direction = 'up';
      } else if (update.price < prev.price) {
        direction = 'down';
      }

      // Clear direction after animation
      if (direction) {
        setTimeout(() => {
          setPriceData((current) => ({ ...current, priceDirection: null }));
        }, 500);
      }

      return {
        symbol: prev.symbol,
        address: prev.address,
        price: update.price,
        change24h: update.price_change_24h,
        volume24h: update.volume_24h,
        lastUpdate: Date.now(),
        priceDirection: direction
      };
    });
  }, []);

  const { isConnected, error } = usePriceWebSocket({
    tokenAddress: address,
    onPriceUpdate: handlePriceUpdate,
    autoConnect: true
  });

  const formatPrice = (price: number) => {
    if (price === 0) return '$--.--';
    if (price >= 1000) return `$${price.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
    if (price >= 1) return `$${price.toFixed(2)}`;
    return `$${price.toFixed(4)}`;
  };

  const formatVolume = (volume: number) => {
    if (volume >= 1_000_000_000) {
      return `$${(volume / 1_000_000_000).toFixed(2)}B`;
    }
    return `$${(volume / 1_000_000).toFixed(0)}M`;
  };

  const isPositive = priceData.change24h >= 0;

  if (compact) {
    return (
      <div
        className={clsx(
          'flex items-center gap-2 px-4 py-2 bg-surface rounded-lg transition-all duration-300',
          priceData.priceDirection === 'up' && 'bg-success/20',
          priceData.priceDirection === 'down' && 'bg-error/20'
        )}
      >
        <span className="text-sm font-semibold">{symbol}</span>
        <span className="text-sm font-mono">{formatPrice(priceData.price)}</span>
        <span
          className={clsx(
            'text-xs flex items-center gap-0.5',
            isPositive ? 'text-success' : 'text-error'
          )}
        >
          {isPositive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
          {Math.abs(priceData.change24h).toFixed(2)}%
        </span>
        {/* Connection indicator */}
        {isConnected ? (
          <Wifi size={12} className="text-success" />
        ) : (
          <WifiOff size={12} className="text-error" />
        )}
      </div>
    );
  }

  return (
    <div
      className={clsx(
        'relative overflow-hidden rounded-xl p-4 transition-all duration-300',
        'bg-surface border border-border hover:border-accent/50',
        priceData.priceDirection === 'up' && 'border-success shadow-glow-success',
        priceData.priceDirection === 'down' && 'border-error shadow-glow-error'
      )}
    >
      {/* Background glow */}
      <div
        className={clsx(
          'absolute inset-0 opacity-0 transition-opacity duration-500',
          priceData.priceDirection === 'up' && 'bg-gradient-to-br from-success/10 to-transparent opacity-100',
          priceData.priceDirection === 'down' && 'bg-gradient-to-br from-error/10 to-transparent opacity-100'
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
            {priceData.change24h.toFixed(2)}%
          </div>
        </div>

        {/* Price */}
        <div className="mb-3">
          <div className="text-2xl font-mono font-bold">{formatPrice(priceData.price)}</div>
          <div className="text-xs text-muted mt-1">
            24h Vol: {priceData.volume24h > 0 ? formatVolume(priceData.volume24h) : 'N/A'}
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

        {/* Connection Status */}
        <div className="mt-2 text-xs flex items-center justify-between">
          {isConnected ? (
            <div className="flex items-center gap-1 text-success">
              <div className="w-1.5 h-1.5 bg-success rounded-full animate-pulse" />
              <span>Live</span>
            </div>
          ) : (
            <div className="flex items-center gap-1 text-error">
              <WifiOff size={12} />
              <span>{error || 'Disconnected'}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const RealTimePriceTicker: React.FC<RealTimePriceTickerProps> = ({
  tokens = ['SOL', 'USDC', 'USDT'],
  compact = false
}) => {
  // Map symbols to addresses
  const tokenData = tokens
    .map((symbol) => {
      const token = getTokenBySymbol(symbol);
      return token ? { symbol, address: token.address } : null;
    })
    .filter((t): t is { symbol: string; address: string } => t !== null);

  if (compact) {
    return (
      <div className="flex items-center gap-4 overflow-x-auto scrollbar-hide">
        {tokenData.map(({ symbol, address }) => (
          <TokenPriceItem key={address} symbol={symbol} address={address} compact />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {tokenData.map(({ symbol, address }) => (
        <TokenPriceItem key={address} symbol={symbol} address={address} />
      ))}
    </div>
  );
};
