'use client';

import { RefreshCw, Loader2, Brain, Zap } from 'lucide-react';

interface GrokLiveBarProps {
  countdown: number;
  isRefreshing: boolean;
  lastRefreshed: Date | null;
  budgetStatus: { spent: number; remaining: number; requests: number } | null;
  tokenCount: number;
  onRefresh: () => void;
}

function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function formatLastRefreshed(date: Date | null): string {
  if (!date) return 'never';
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  return `${Math.floor(diffMin / 60)}h ago`;
}

export function GrokLiveBar({
  countdown,
  isRefreshing,
  lastRefreshed,
  budgetStatus,
  tokenCount,
  onRefresh,
}: GrokLiveBarProps) {
  const countdownColor =
    countdown < 30
      ? 'text-accent-error'
      : countdown < 120
        ? 'text-accent-warning'
        : 'text-text-primary';

  const spent = budgetStatus?.spent ?? 0;

  return (
    <div className="w-full h-10 flex items-center justify-between px-4 bg-bg-secondary/50 backdrop-blur-sm border border-border-primary rounded-lg">
      {/* Left: Live indicator */}
      <div className="flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-neon opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-neon" />
        </span>
        <Brain className="h-3.5 w-3.5 text-accent-neon" />
        <span className="font-mono text-xs text-accent-neon font-bold tracking-wide">
          GROK 4.1
        </span>
        <Zap className="h-3 w-3 text-accent-neon opacity-60" />
      </div>

      {/* Center: Countdown */}
      <div className="flex items-center gap-3">
        {isRefreshing ? (
          <div className="flex items-center gap-1.5">
            <Loader2 className="h-3.5 w-3.5 text-accent-neon animate-spin" />
            <span className="font-mono text-sm text-accent-neon">scanning...</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-text-muted font-mono">Next scan</span>
            <span className={`font-mono text-sm font-bold ${countdownColor}`}>
              {formatCountdown(countdown)}
            </span>
          </div>
        )}

        {lastRefreshed && (
          <span className="text-[10px] text-text-muted font-mono hidden sm:inline">
            updated {formatLastRefreshed(lastRefreshed)}
          </span>
        )}
      </div>

      {/* Right: Budget + token count + refresh */}
      <div className="flex items-center gap-2">
        <span className="font-mono text-[10px] text-text-muted px-1.5 py-0.5 rounded bg-bg-primary/50 border border-border-primary hidden sm:inline-block">
          {tokenCount} tokens
        </span>

        {budgetStatus && (
          <span className="font-mono text-[10px] text-text-muted px-1.5 py-0.5 rounded bg-bg-primary/50 border border-border-primary">
            ${spent.toFixed(2)}/$10
          </span>
        )}

        <button
          type="button"
          onClick={onRefresh}
          disabled={isRefreshing}
          className="hover:bg-accent-neon/20 rounded-lg p-1.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          title="Refresh now"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 text-text-muted hover:text-accent-neon transition-colors ${
              isRefreshing ? 'animate-spin' : ''
            }`}
          />
        </button>
      </div>
    </div>
  );
}
