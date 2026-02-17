'use client';

import { useMemo } from 'react';
import { ExternalLink, Clock } from 'lucide-react';
import type { TradeRecord } from '@/stores/useTradeStore';

// ---------------------------------------------------------------------------
// Pure helpers (exported for testing)
// ---------------------------------------------------------------------------

export interface TradeGroup {
  label: string;
  dateKey: string;
  trades: TradeRecord[];
}

/**
 * Returns "TODAY", "YESTERDAY", or a formatted date string (e.g. "Feb 1, 2026")
 * for the given timestamp.
 */
export function getDayLabel(timestamp: number): string {
  const date = new Date(timestamp);
  const now = new Date();

  // Compare calendar dates in local timezone
  const dateDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (dateDay.getTime() === today.getTime()) return 'TODAY';
  if (dateDay.getTime() === yesterday.getTime()) return 'YESTERDAY';

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * Build a Solscan transaction URL.
 */
export function solscanTxUrl(txSignature: string): string {
  return `https://solscan.io/tx/${txSignature}`;
}

/**
 * Groups an array of TradeRecord into day-buckets, sorted most recent day first.
 * Trades within each group are sorted most recent first.
 */
export function groupTradesByDay(trades: TradeRecord[]): TradeGroup[] {
  if (trades.length === 0) return [];

  // Sort all trades most-recent-first
  const sorted = [...trades].sort((a, b) => b.timestamp - a.timestamp);

  const groupMap = new Map<string, TradeGroup>();

  for (const trade of sorted) {
    const d = new Date(trade.timestamp);
    const dateKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

    if (!groupMap.has(dateKey)) {
      groupMap.set(dateKey, {
        label: getDayLabel(trade.timestamp),
        dateKey,
        trades: [],
      });
    }
    groupMap.get(dateKey)!.trades.push(trade);
  }

  // Convert to array -- already in order because we iterate sorted trades
  // and Map preserves insertion order
  return Array.from(groupMap.values());
}

// ---------------------------------------------------------------------------
// Relative time helper
// ---------------------------------------------------------------------------

function timeAgo(timestamp: number): string {
  const seconds = Math.floor((Date.now() - timestamp) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Format a USD price with appropriate decimal places. */
function formatPrice(price: number): string {
  if (price === 0) return '$0.00';
  if (price < 0.0001) return `$${price.toExponential(2)}`;
  if (price < 0.01) return `$${price.toFixed(6)}`;
  if (price < 1) return `$${price.toFixed(4)}`;
  if (price < 1000) return `$${price.toFixed(2)}`;
  return `$${price.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
}

/** Format amount with smart precision. */
function formatAmount(amount: number, symbol: string): string {
  if (amount >= 1_000_000) return `${(amount / 1_000_000).toFixed(1)}M ${symbol}`;
  if (amount >= 1_000) return `${(amount / 1_000).toFixed(1)}K ${symbol}`;
  if (amount >= 1) return `${amount.toFixed(2)} ${symbol}`;
  return `${amount.toFixed(4)} ${symbol}`;
}

// ---------------------------------------------------------------------------
// TradeTimeline Component
// ---------------------------------------------------------------------------

interface TradeTimelineProps {
  trades: TradeRecord[];
}

export function TradeTimeline({ trades }: TradeTimelineProps) {
  const groups = useMemo(() => groupTradesByDay(trades), [trades]);

  if (groups.length === 0) {
    return (
      <div className="text-center py-8">
        <Clock className="w-10 h-10 text-text-muted mx-auto mb-2 opacity-30" />
        <p className="text-sm text-text-muted">
          No trades yet. Execute your first trade to see it here.
        </p>
      </div>
    );
  }

  return (
    <div className="card-glass bg-bg-secondary/30 rounded-lg p-4 max-h-[400px] overflow-y-auto custom-scrollbar">
      {groups.map((group) => (
        <div key={group.dateKey} className="mb-4 last:mb-0">
          {/* Day header */}
          <div className="text-xs text-text-muted font-mono uppercase tracking-wider mb-2">
            {group.label}
          </div>

          {/* Timeline spine */}
          <div className="border-l-2 border-accent-neon/20 ml-1.5 pl-4 space-y-3">
            {group.trades.map((trade) => {
              const isBuy = trade.side === 'buy';
              return (
                <div key={trade.id} className="relative">
                  {/* Timeline node dot */}
                  <div
                    className={`absolute -left-[1.3rem] top-1.5 w-3 h-3 rounded-full border-2 border-bg-primary ${
                      isBuy ? 'bg-accent-neon' : 'bg-accent-error'
                    }`}
                  />

                  {/* Trade card */}
                  <div className="flex items-start justify-between gap-3 p-2 rounded-md bg-bg-secondary/20 hover:bg-bg-secondary/40 transition-colors">
                    <div className="flex items-center gap-2 min-w-0">
                      {/* Side badge */}
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold font-mono uppercase shrink-0 ${
                          isBuy
                            ? 'bg-accent-success/15 text-accent-success'
                            : 'bg-accent-error/15 text-accent-error'
                        }`}
                      >
                        {trade.side}
                      </span>

                      {/* Token + details */}
                      <div className="min-w-0">
                        <span className="font-mono font-bold text-sm text-text-primary">
                          {trade.tokenSymbol}
                        </span>
                        <span className="text-text-secondary font-mono text-xs ml-2">
                          {formatPrice(trade.price)}
                        </span>
                        <span className="text-text-muted font-mono text-xs ml-2">
                          {formatAmount(trade.amount, trade.tokenSymbol)}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      {/* Relative time */}
                      <span className="text-[10px] text-text-muted font-mono whitespace-nowrap">
                        {timeAgo(trade.timestamp)}
                      </span>

                      {/* View TX link */}
                      <a
                        href={solscanTxUrl(trade.txSignature)}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`View transaction on Solscan`}
                        className="flex items-center gap-1 text-[10px] font-mono text-accent-neon hover:text-accent-neon/80 hover:underline transition-colors whitespace-nowrap"
                      >
                        View TX
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

export default TradeTimeline;
