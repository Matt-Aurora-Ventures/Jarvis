'use client';

/**
 * AITradeSignals -- The killer differentiator component
 *
 * Shows AI-driven trade signals backed by real backtested win rates.
 * Each of 4 strategies displays:
 *  - Win rate (progress bar)
 *  - Average return
 *  - Current signal (BUY / SELL / HOLD)
 *  - TP/SL targets based on the strategy's backtest
 *  - "APPLY TO TRADE" button that prefills TradePanel with optimal TP/SL
 *
 * Consensus indicator at the bottom aggregates all strategy signals.
 */

import { useState } from 'react';
import { Activity, Zap, TrendingUp, TrendingDown, Minus, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { useBacktest, type StrategyResult } from '@/hooks/useBacktest';
import { useSettingsStore } from '@/stores/useSettingsStore';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AITradeSignalsProps {
  /** Pool address for GeckoTerminal OHLCV lookups */
  poolAddress: string | null;
  /** Current token price (for computing TP/SL targets) */
  currentPrice?: number;
  /** Label (e.g. token symbol) shown in the header */
  tokenSymbol?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function signalColor(signal: 'BUY' | 'SELL' | 'HOLD'): string {
  switch (signal) {
    case 'BUY':
      return 'text-accent-success';
    case 'SELL':
      return 'text-accent-error';
    case 'HOLD':
      return 'text-accent-warning';
  }
}

function signalBg(signal: 'BUY' | 'SELL' | 'HOLD'): string {
  switch (signal) {
    case 'BUY':
      return 'bg-accent-success/10 border-accent-success/30';
    case 'SELL':
      return 'bg-accent-error/10 border-accent-error/30';
    case 'HOLD':
      return 'bg-accent-warning/10 border-accent-warning/30';
  }
}

function signalIcon(signal: 'BUY' | 'SELL' | 'HOLD') {
  switch (signal) {
    case 'BUY':
      return <TrendingUp className="w-4 h-4" />;
    case 'SELL':
      return <TrendingDown className="w-4 h-4" />;
    case 'HOLD':
      return <Minus className="w-4 h-4" />;
  }
}

function winRateColor(rate: number): string {
  if (rate >= 65) return 'bg-accent-success';
  if (rate >= 50) return 'bg-accent-neon';
  if (rate >= 35) return 'bg-accent-warning';
  return 'bg-accent-error';
}

function formatPrice(price: number): string {
  if (price >= 1000) return `$${price.toFixed(2)}`;
  if (price >= 1) return `$${price.toFixed(4)}`;
  if (price >= 0.01) return `$${price.toFixed(6)}`;
  return `$${price.toFixed(8)}`;
}

// ---------------------------------------------------------------------------
// Strategy Card Sub-Component
// ---------------------------------------------------------------------------

function StrategyCard({
  result,
  currentPrice,
  onApply,
  isBest,
}: {
  result: StrategyResult;
  currentPrice: number;
  onApply: (tp: number, sl: number) => void;
  isBest: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const { backtest, currentSignal } = result;
  const { winRate, avgReturn, totalTrades, maxDrawdown, profitFactor, sharpeRatio } = backtest;

  // Compute suggested TP/SL from backtest performance
  const suggestedTP = Math.max(10, Math.round(Math.abs(avgReturn) * 1.2));
  const suggestedSL = Math.max(5, Math.round(Math.abs(maxDrawdown) * 0.6));
  const tpTarget = currentPrice * (1 + suggestedTP / 100);
  const slTarget = currentPrice * (1 - suggestedSL / 100);

  return (
    <div
      className={`
        rounded-lg border transition-all duration-200
        ${isBest ? 'border-accent-neon/40 shadow-[0_0_15px_rgba(34,197,94,0.1)]' : 'border-border-primary/30'}
        bg-bg-secondary/30 hover:bg-bg-secondary/50
      `}
    >
      {/* Card Header */}
      <div className="p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${
              currentSignal.signal === 'BUY' ? 'bg-accent-success animate-pulse' :
              currentSignal.signal === 'SELL' ? 'bg-accent-error animate-pulse' :
              'bg-accent-warning'
            }`} />
            <span className="text-sm font-bold font-display text-text-primary">
              {backtest.strategyName}
            </span>
            {isBest && (
              <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-accent-neon/20 text-accent-neon border border-accent-neon/30">
                BEST
              </span>
            )}
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-text-muted hover:text-text-primary transition-colors p-1"
          >
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </div>

        {/* Win Rate + Avg Return */}
        <div className="flex items-center gap-3 mb-2">
          <div className="flex-1">
            <div className="flex justify-between text-[10px] font-mono text-text-muted mb-1">
              <span>WIN RATE</span>
              <span className="font-bold text-text-primary">{winRate.toFixed(0)}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${winRateColor(winRate)}`}
                style={{ width: `${Math.min(100, winRate)}%` }}
              />
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] font-mono text-text-muted">AVG</div>
            <div className={`text-sm font-mono font-bold ${avgReturn >= 0 ? 'text-accent-success' : 'text-accent-error'}`}>
              {avgReturn >= 0 ? '+' : ''}{avgReturn.toFixed(1)}%
            </div>
          </div>
        </div>

        {/* Current Signal */}
        <div className={`flex items-center justify-between p-2 rounded-md border ${signalBg(currentSignal.signal)}`}>
          <div className="flex items-center gap-1.5">
            <span className={signalColor(currentSignal.signal)}>
              {signalIcon(currentSignal.signal)}
            </span>
            <span className={`text-xs font-mono font-bold ${signalColor(currentSignal.signal)}`}>
              {currentSignal.signal}
            </span>
            {currentSignal.signal !== 'HOLD' && currentSignal.price > 0 && (
              <span className="text-[10px] font-mono text-text-muted">
                @ {formatPrice(currentSignal.price)}
              </span>
            )}
          </div>
          <span className="text-[10px] font-mono text-text-muted">
            {totalTrades} trades
          </span>
        </div>

        {/* TP/SL Targets (for actionable signals) */}
        {currentSignal.signal === 'BUY' && currentPrice > 0 && (
          <div className="mt-2 space-y-1">
            <div className="flex justify-between text-[10px] font-mono">
              <span className="text-accent-success">TP: {formatPrice(tpTarget)} (+{suggestedTP}%)</span>
              <span className="text-accent-error">SL: {formatPrice(slTarget)} (-{suggestedSL}%)</span>
            </div>
            <button
              onClick={() => onApply(suggestedTP, suggestedSL)}
              className="
                w-full py-1.5 text-[10px] font-mono font-bold uppercase
                bg-accent-neon/10 text-accent-neon border border-accent-neon/30
                rounded-md hover:bg-accent-neon/20 transition-all
              "
            >
              Apply to Trade
            </button>
          </div>
        )}

        {currentSignal.signal === 'SELL' && currentPrice > 0 && (
          <div className="mt-2">
            <div className="text-[10px] font-mono text-accent-error text-center py-1">
              Strategy suggests EXIT / SELL
            </div>
          </div>
        )}
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="px-3 pb-3 border-t border-border-primary/20 pt-2 space-y-2">
          <div className="text-[10px] font-mono text-text-muted mb-1">
            {currentSignal.reason}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="text-[10px] font-mono">
              <span className="text-text-muted">Max DD:</span>{' '}
              <span className="text-accent-error">{maxDrawdown.toFixed(1)}%</span>
            </div>
            <div className="text-[10px] font-mono">
              <span className="text-text-muted">Sharpe:</span>{' '}
              <span className="text-text-primary">{sharpeRatio.toFixed(2)}</span>
            </div>
            <div className="text-[10px] font-mono">
              <span className="text-text-muted">Profit F:</span>{' '}
              <span className="text-text-primary">
                {profitFactor === Infinity ? 'inf' : profitFactor.toFixed(2)}
              </span>
            </div>
            <div className="text-[10px] font-mono">
              <span className="text-text-muted">Trades:</span>{' '}
              <span className="text-text-primary">{totalTrades}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function AITradeSignals({ poolAddress, currentPrice = 0, tokenSymbol }: AITradeSignalsProps) {
  const { results, isRunning, error, runAll, bestStrategy, consensus } = useBacktest(poolAddress);
  const { setAISignal } = useSettingsStore();

  const handleApplyToTrade = (tp: number, sl: number) => {
    // Pass full AI context to the settings store so TradePanel can display it
    const bestWR = bestStrategy?.backtest.winRate ?? 0;
    const buyCount = consensus?.buyCount ?? 0;
    const total = consensus?.total ?? 4;
    setAISignal({
      consensus: consensus?.consensus ?? 'HOLD',
      bestWinRate: Math.round(bestWR),
      signalStrength: `${buyCount}/${total}`,
      suggestedTP: tp,
      suggestedSL: sl,
    });
  };

  return (
    <div className="card-glass p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-primary/30 pb-3">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-accent-neon" />
          <h3 className="font-display font-bold text-sm text-text-primary">
            AI TRADE SIGNALS
          </h3>
          {tokenSymbol && (
            <span className="text-[10px] font-mono text-text-muted px-1.5 py-0.5 rounded bg-bg-secondary/50 border border-border-primary/30">
              {tokenSymbol}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-text-muted">
            Backtested 30d
          </span>
          <button
            onClick={() => runAll()}
            disabled={isRunning}
            className="p-1 rounded hover:bg-bg-secondary/50 transition-colors disabled:opacity-50"
            title="Refresh backtests"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-text-muted ${isRunning ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Loading State */}
      {isRunning && results.length === 0 && (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {/* Error State */}
      {error && !isRunning && (
        <div className="text-center py-4">
          <span className="text-xs font-mono text-accent-error">{error}</span>
          <button
            onClick={() => runAll()}
            className="block mx-auto mt-2 text-[10px] font-mono text-accent-neon hover:underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* No Pool Selected */}
      {!poolAddress && (
        <div className="text-center py-6">
          <Activity className="w-6 h-6 text-text-muted mx-auto mb-2" />
          <span className="text-xs font-mono text-text-muted">
            Select a token to see AI signals
          </span>
        </div>
      )}

      {/* Strategy Cards */}
      {results.length > 0 && (
        <div className="space-y-2">
          {results.map((result) => (
            <StrategyCard
              key={result.backtest.strategyName}
              result={result}
              currentPrice={currentPrice}
              onApply={handleApplyToTrade}
              isBest={bestStrategy?.backtest.strategyName === result.backtest.strategyName}
            />
          ))}
        </div>
      )}

      {/* Consensus Footer */}
      {consensus && results.length > 0 && (
        <div className="border-t border-border-primary/30 pt-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-text-muted uppercase">
                Best Strategy:
              </span>
              <span className="text-xs font-mono font-bold text-accent-neon">
                {bestStrategy?.backtest.strategyName}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-text-muted uppercase">
                Consensus:
              </span>
              <div className={`
                flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold
                ${signalBg(consensus.consensus)} border ${signalColor(consensus.consensus)}
              `}>
                {signalIcon(consensus.consensus)}
                <span>{consensus.buyCount}/{consensus.total} BUY</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
