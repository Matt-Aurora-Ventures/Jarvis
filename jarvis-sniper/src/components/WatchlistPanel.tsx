'use client';

import { Eye, X, TrendingUp, TrendingDown } from 'lucide-react';
import { useSniperStore } from '@/stores/useSniperStore';

export function WatchlistPanel() {
  const { watchlist, removeFromWatchlist, graduations, setSelectedMint } = useSniperStore();

  if (watchlist.length === 0) {
    return (
      <div className="card-glass p-4">
        <div className="flex items-center gap-2 mb-3">
          <Eye className="w-4 h-4 text-accent-warning" />
          <h2 className="font-display text-sm font-semibold">Watchlist</h2>
        </div>
        <p className="text-[10px] text-text-muted text-center py-4">
          Hover a token and click Watch to track it here
        </p>
      </div>
    );
  }

  return (
    <div className="card-glass p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Eye className="w-4 h-4 text-accent-warning" />
          <h2 className="font-display text-sm font-semibold">Watchlist</h2>
        </div>
        <span className="text-[10px] font-mono text-text-muted">{watchlist.length} tokens</span>
      </div>
      <div className="space-y-1.5">
        {watchlist.map((mint) => {
          const grad = graduations.find(g => g.mint === mint);
          const symbol = grad?.symbol || mint.slice(0, 6);
          const price = grad?.price_usd ?? 0;
          const change = grad?.price_change_1h ?? 0;
          return (
            <div
              key={mint}
              onClick={() => setSelectedMint(mint)}
              className="flex items-center justify-between px-2.5 py-2 rounded-lg bg-bg-secondary/60 border border-border-primary hover:border-border-hover cursor-pointer transition-colors"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-xs font-bold text-text-primary">{symbol}</span>
                {price > 0 && (
                  <span className="text-[10px] font-mono text-text-muted">
                    ${price < 0.01 ? price.toExponential(2) : price.toFixed(4)}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {change !== 0 && (
                  <span className={`flex items-center gap-0.5 text-[10px] font-mono font-semibold ${change >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
                    {change >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {change >= 0 ? '+' : ''}{change.toFixed(1)}%
                  </span>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); removeFromWatchlist(mint); }}
                  className="w-5 h-5 rounded flex items-center justify-center text-text-muted hover:text-accent-error hover:bg-accent-error/10 transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
