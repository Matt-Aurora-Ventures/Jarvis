/**
 * Positions List Component - Beautiful Position Cards
 * Shows open positions with health indicators and P&L
 */
import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, X, Edit, ExternalLink, Clock } from 'lucide-react';
import { GlassCard, GlassCardHeader, GlassCardTitle, GlassCardBody } from '../UI/GlassCard';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';

interface Position {
  id: string;
  tokenSymbol: string;
  tokenAddress: string;
  entryPrice: number;
  currentPrice: number;
  amount: number;
  pnlUsd: number;
  pnlPct: number;
  openedAt: Date;
}

export const PositionsList: React.FC = () => {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPositions();
  }, []);

  const fetchPositions = async () => {
    try {
      setLoading(true);

      const response = await fetch('/api/positions', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setPositions(data.positions || []);
      }
    } catch (error) {
      console.error('Failed to fetch positions:', error);
    } finally {
      setLoading(false);
    }
  };

  const getHealthIndicator = (pnlPct: number): string => {
    if (pnlPct >= 20) return '💪'; // Excellent
    if (pnlPct >= 5) return '🟢'; // Good
    if (pnlPct >= -5) return '🟡'; // Fair
    if (pnlPct >= -15) return '🟠'; // Weak
    return '🔴'; // Critical
  };

  const getHealthBar = (pnlPct: number): React.ReactNode => {
    const normalized = Math.min(100, Math.max(0, (pnlPct + 50) / 1.5));
    const filled = Math.round((normalized / 100) * 5);
    const empty = 5 - filled;

    let barColor = '🟩';
    if (pnlPct < 0) barColor = pnlPct >= -15 ? '🟧' : '🟥';
    else if (pnlPct < 20) barColor = '🟨';

    return (
      <div className="flex gap-0.5">
        {Array(filled).fill(barColor).map((color, i) => (
          <span key={`filled-${i}`}>{color}</span>
        ))}
        {Array(empty).fill('⬜').map((color, i) => (
          <span key={`empty-${i}`}>{color}</span>
        ))}
      </div>
    );
  };

  if (loading) {
    return (
      <GlassCard>
        <GlassCardHeader>
          <GlassCardTitle icon={<TrendingUp size={20} />}>
            Open Positions
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardBody>
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="animate-spin text-2xl mb-2">⏳</div>
              <p className="text-muted text-sm">Loading positions...</p>
            </div>
          </div>
        </GlassCardBody>
      </GlassCard>
    );
  }

  if (positions.length === 0) {
    return (
      <GlassCard>
        <GlassCardHeader>
          <GlassCardTitle icon={<TrendingUp size={20} />}>
            Open Positions
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardBody>
          <div className="text-center py-12">
            <div className="text-4xl mb-4">📊</div>
            <p className="text-lg font-semibold mb-2">No Open Positions</p>
            <p className="text-muted text-sm mb-6">
              Start trading to see your positions here
            </p>
            <button className="btn btn-primary">
              <TrendingUp size={18} />
              <span>Start Trading</span>
            </button>
          </div>
        </GlassCardBody>
      </GlassCard>
    );
  }

  return (
    <GlassCard>
      <GlassCardHeader>
        <div className="flex items-center justify-between">
          <GlassCardTitle icon={<TrendingUp size={20} />}>
            Open Positions ({positions.length})
          </GlassCardTitle>
          <button className="btn btn-ghost btn-sm">
            View All
          </button>
        </div>
      </GlassCardHeader>
      <GlassCardBody>
        <div className="space-y-3">
          {positions.slice(0, 5).map((position) => (
            <div
              key={position.id}
              className="p-4 bg-surface rounded-lg hover:bg-surface-hover transition-all border border-border hover:border-border-hover"
            >
              {/* Header Row */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-semibold text-lg">
                      {position.tokenSymbol}
                    </h4>
                    <span className="text-xs text-muted">
                      {getHealthIndicator(position.pnlPct)}
                    </span>
                  </div>
                  <p className="text-xs text-muted font-mono">
                    {position.tokenAddress.slice(0, 8)}...{position.tokenAddress.slice(-6)}
                  </p>
                </div>

                <div className="text-right">
                  <p className={clsx(
                    'text-lg font-bold mb-1',
                    position.pnlPct >= 0 ? 'text-success' : 'text-error'
                  )}>
                    {position.pnlPct >= 0 ? '+' : ''}{position.pnlPct.toFixed(2)}%
                  </p>
                  <p className={clsx(
                    'text-sm',
                    position.pnlPct >= 0 ? 'text-success' : 'text-error'
                  )}>
                    {position.pnlPct >= 0 ? '+' : ''}${Math.abs(position.pnlUsd).toFixed(2)}
                  </p>
                </div>
              </div>

              {/* Health Bar */}
              <div className="mb-3">
                {getHealthBar(position.pnlPct)}
              </div>

              {/* Details Grid */}
              <div className="grid grid-cols-3 gap-3 mb-3 text-sm">
                <div>
                  <p className="text-muted text-xs mb-1">Entry Price</p>
                  <p className="font-semibold">
                    ${position.entryPrice < 0.01
                      ? position.entryPrice.toFixed(8)
                      : position.entryPrice.toFixed(4)}
                  </p>
                </div>
                <div>
                  <p className="text-muted text-xs mb-1">Current Price</p>
                  <p className="font-semibold">
                    ${position.currentPrice < 0.01
                      ? position.currentPrice.toFixed(8)
                      : position.currentPrice.toFixed(4)}
                  </p>
                </div>
                <div>
                  <p className="text-muted text-xs mb-1">Amount</p>
                  <p className="font-semibold">
                    {position.amount.toFixed(2)}
                  </p>
                </div>
              </div>

              {/* Time & Actions Row */}
              <div className="flex items-center justify-between pt-3 border-t border-border">
                <div className="flex items-center gap-1 text-xs text-muted">
                  <Clock size={12} />
                  <span>
                    {formatDistanceToNow(position.openedAt, { addSuffix: true })}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button className="btn btn-ghost btn-sm">
                    <Edit size={14} />
                  </button>
                  <button className="btn btn-ghost btn-sm">
                    <ExternalLink size={14} />
                  </button>
                  <button className="btn btn-danger btn-sm">
                    <X size={14} />
                    <span>Close</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {positions.length > 5 && (
          <button className="btn btn-secondary w-full mt-4">
            View All {positions.length} Positions
          </button>
        )}
      </GlassCardBody>
    </GlassCard>
  );
};
