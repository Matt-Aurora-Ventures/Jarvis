'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useTradeStore, type Position } from '@/stores/useTradeStore';
import { useToast } from '@/components/ui/Toast';
import { TradeTimeline } from '@/components/features/TradeTimeline';
import {
  Briefcase,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  Target,
  ShieldAlert,
  X as XIcon,
} from 'lucide-react';
import { computeRiskScore } from '@/lib/risk-score';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PriceMap {
  [mint: string]: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format a timestamp into a human-readable relative time string. */
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

// ---------------------------------------------------------------------------
// Price Hook
// ---------------------------------------------------------------------------

/**
 * Fetches live prices from Jupiter Price API v2 for the given mints.
 * Polls every `intervalMs` milliseconds (default 10 000).
 */
function useLivePrices(mints: string[], intervalMs = 10_000): PriceMap {
  const [prices, setPrices] = useState<PriceMap>({});

  const fetchPrices = useCallback(async () => {
    if (mints.length === 0) return;
    try {
      const ids = mints.join(',');
      const res = await fetch(
        `https://api.jup.ag/price/v2?ids=${ids}`,
      );
      if (!res.ok) return;
      const json = await res.json();
      const data: Record<string, { price: string }> = json.data ?? {};
      const next: PriceMap = {};
      for (const [mint, info] of Object.entries(data)) {
        const p = parseFloat(info.price);
        if (!isNaN(p)) next[mint] = p;
      }
      setPrices((prev) => ({ ...prev, ...next }));
    } catch {
      // Silently swallow fetch errors; stale prices remain.
    }
  }, [mints]);

  useEffect(() => {
    fetchPrices();
    const id = setInterval(fetchPrices, intervalMs);
    return () => clearInterval(id);
  }, [fetchPrices, intervalMs]);

  return prices;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

type Tab = 'positions' | 'history';

interface PositionRowProps {
  position: Position;
  currentPrice: number | undefined;
  onClose: () => void;
}

function PositionRow({ position, currentPrice, onClose }: PositionRowProps) {
  const entry = position.entryPrice;
  const current = currentPrice ?? 0;
  const hasCurrent = currentPrice !== undefined && currentPrice > 0;

  const pnlPercent = hasCurrent ? ((current - entry) / entry) * 100 : 0;
  const pnlDollar = hasCurrent ? (current - entry) * position.amount : 0;
  const isPositive = pnlPercent >= 0;

  // Compute risk assessment
  const risk = computeRiskScore({
    pnlPercent,
    holdDurationMs: Date.now() - position.timestamp,
    hasStopLoss: position.stopLossPercent !== null,
    hasTakeProfit: position.takeProfitPercent !== null,
    positionSizeSol: position.solAmount,
  });

  const riskBadgeStyles: Record<string, string> = {
    LOW: 'bg-accent-neon/10 text-accent-neon',
    MEDIUM: 'bg-accent-warning/10 text-accent-warning',
    HIGH: 'bg-accent-error/10 text-accent-error',
    EXTREME: 'bg-accent-error/20 text-accent-error animate-pulse',
  };

  const riskLabel: Record<string, string> = {
    LOW: 'LOW RISK',
    MEDIUM: 'MED RISK',
    HIGH: 'HIGH RISK',
    EXTREME: 'EXTREME',
  };

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-bg-secondary/30 hover:bg-bg-secondary/50 transition-colors">
      {/* Token avatar + symbol */}
      <div className="flex items-center gap-2 min-w-0 flex-1">
        <div className="w-8 h-8 rounded-full bg-bg-tertiary/80 flex items-center justify-center shrink-0 border border-border-primary/30">
          <span className="font-mono font-bold text-xs text-text-primary">
            {position.tokenSymbol.slice(0, 2).toUpperCase()}
          </span>
        </div>
        <div className="min-w-0">
          <p className="font-mono font-bold text-sm text-text-primary truncate">
            {position.tokenSymbol}
          </p>
          <p className="text-[10px] text-text-muted flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {timeAgo(position.timestamp)}
          </p>
        </div>
      </div>

      {/* Prices */}
      <div className="text-right shrink-0">
        <p className="text-[10px] text-text-muted font-mono">ENTRY</p>
        <p className="font-mono text-xs text-text-secondary">{formatPrice(entry)}</p>
      </div>

      <div className="text-right shrink-0">
        <p className="text-[10px] text-text-muted font-mono">CURRENT</p>
        <p className="font-mono text-xs text-text-primary">
          {hasCurrent ? formatPrice(current) : '--'}
        </p>
      </div>

      {/* P&L */}
      <div className="text-right w-20 shrink-0">
        {hasCurrent ? (
          <>
            <p
              className={`font-mono text-xs font-bold flex items-center justify-end gap-0.5 ${
                isPositive ? 'text-accent-success' : 'text-accent-error'
              }`}
            >
              {isPositive ? (
                <ArrowUpRight className="w-3 h-3" />
              ) : (
                <ArrowDownRight className="w-3 h-3" />
              )}
              {isPositive ? '+' : ''}
              {pnlPercent.toFixed(2)}%
            </p>
            <p
              className={`text-[10px] font-mono ${
                isPositive ? 'text-accent-success/70' : 'text-accent-error/70'
              }`}
            >
              {pnlDollar >= 0 ? '+' : ''}
              ${Math.abs(pnlDollar).toFixed(2)}
            </p>
          </>
        ) : (
          <p className="text-[10px] text-text-muted font-mono">Loading...</p>
        )}
      </div>

      {/* SL / TP badges */}
      <div className="flex flex-col items-end gap-0.5 shrink-0 w-14">
        {position.takeProfitPercent !== null && (
          <span className="flex items-center gap-0.5 text-[9px] font-mono text-accent-success">
            <Target className="w-2.5 h-2.5" />
            TP {position.takeProfitPercent}%
          </span>
        )}
        {position.stopLossPercent !== null && (
          <span className="flex items-center gap-0.5 text-[9px] font-mono text-accent-error">
            <ShieldAlert className="w-2.5 h-2.5" />
            SL {position.stopLossPercent}%
          </span>
        )}
        {position.takeProfitPercent === null && position.stopLossPercent === null && (
          <span className="text-[9px] text-text-muted font-mono">--</span>
        )}
      </div>

      {/* Risk badge */}
      <div className="shrink-0">
        <span
          className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-mono font-bold uppercase ${riskBadgeStyles[risk.level]}`}
          title={risk.factors.length > 0 ? risk.factors.join(' | ') : 'No risk factors detected'}
        >
          {riskLabel[risk.level]}
        </span>
      </div>

      {/* Close button */}
      <button
        onClick={onClose}
        aria-label={`Close ${position.tokenSymbol} position`}
        className="p-1.5 rounded-md bg-accent-error/10 text-accent-error hover:bg-accent-error/20 transition-colors shrink-0"
      >
        <XIcon className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function PositionsPanel() {
  const { positions, tradeHistory, getOpenPositions } = useTradeStore();
  const { info } = useToast();
  const [activeTab, setActiveTab] = useState<Tab>('positions');

  // Derive open positions
  const openPositions = getOpenPositions();

  // Collect unique mints for price fetching
  const openMints = useMemo(
    () => [...new Set(openPositions.map((p) => p.tokenMint))],
    [openPositions],
  );

  // Live prices, refreshed every 10s
  const livePrices = useLivePrices(openMints);

  const handleClose = useCallback(() => {
    info('Connect wallet to close positions');
  }, [info]);

  return (
    <div className="card-glass overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <Briefcase className="w-4 h-4 text-accent-neon" />
          <span className="text-xs font-mono uppercase tracking-wider text-text-muted">
            POSITIONS
          </span>
        </div>

        {/* Tab buttons */}
        <div
          className="flex items-center gap-1 p-0.5 rounded-lg bg-bg-secondary/50 border border-border-primary/30"
          role="tablist"
        >
          <button
            role="tab"
            aria-selected={activeTab === 'positions'}
            onClick={() => setActiveTab('positions')}
            className={`px-3 py-1 text-[11px] font-mono font-bold rounded-md transition-all ${
              activeTab === 'positions'
                ? 'bg-accent-neon text-black shadow-sm'
                : 'text-text-muted hover:text-text-primary'
            }`}
          >
            Open Positions
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'history'}
            onClick={() => setActiveTab('history')}
            className={`px-3 py-1 text-[11px] font-mono font-bold rounded-md transition-all ${
              activeTab === 'history'
                ? 'bg-accent-neon text-black shadow-sm'
                : 'text-text-muted hover:text-text-primary'
            }`}
          >
            Trade History
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 pb-4">
        {/* ----- OPEN POSITIONS TAB ----- */}
        {activeTab === 'positions' && (
          <div className="space-y-2 mt-2">
            {openPositions.length === 0 ? (
              <div className="text-center py-8">
                <Briefcase className="w-10 h-10 text-text-muted mx-auto mb-2 opacity-30" />
                <p className="text-sm text-text-muted">No open positions.</p>
                <p className="text-xs text-text-muted mt-1">
                  Use the Trade Panel to open one.
                </p>
              </div>
            ) : (
              openPositions.map((pos) => (
                <PositionRow
                  key={pos.id}
                  position={pos}
                  currentPrice={livePrices[pos.tokenMint]}
                  onClose={handleClose}
                />
              ))
            )}
          </div>
        )}

        {/* ----- TRADE HISTORY TAB ----- */}
        {activeTab === 'history' && (
          <div className="mt-2">
            <TradeTimeline trades={tradeHistory} />
          </div>
        )}
      </div>
    </div>
  );
}

export default PositionsPanel;
