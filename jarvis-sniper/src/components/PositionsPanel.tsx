'use client';

import { X, DollarSign, Clock, ExternalLink, Shield, Target, BarChart3, Trash2 } from 'lucide-react';
import { useSniperStore } from '@/stores/useSniperStore';

export function PositionsPanel() {
  const { positions, updatePosition, addExecution, setSelectedMint, selectedMint, resetSession } = useSniperStore();
  const openPositions = positions.filter(p => p.status === 'open');
  const closedPositions = positions.filter(p => p.status !== 'open').slice(0, 10);

  const totalOpen = openPositions.reduce((sum, p) => sum + p.solInvested, 0);
  const unrealizedPnl = openPositions.reduce((sum, p) => sum + p.pnlSol, 0);

  function handleClose(id: string) {
    const pos = positions.find(p => p.id === id);
    if (!pos) return;
    updatePosition(id, { status: 'closed' });
    addExecution({
      id: `close-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      type: 'manual_exit',
      symbol: pos.symbol,
      mint: pos.mint,
      amount: pos.solInvested,
      pnlPercent: pos.pnlPercent,
      timestamp: Date.now(),
    });
  }

  const hasData = positions.length > 0;

  return (
    <div className="card-glass p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-accent-neon" />
          <h2 className="font-display text-sm font-semibold">Positions</h2>
        </div>
        <div className="flex items-center gap-3 text-[10px] font-mono">
          <span className="text-text-muted">Open: <span className="text-text-primary font-bold">{totalOpen.toFixed(2)} SOL</span></span>
          <span className={unrealizedPnl >= 0 ? 'text-accent-neon' : 'text-accent-error'}>
            {unrealizedPnl >= 0 ? '+' : ''}{unrealizedPnl.toFixed(3)} SOL
          </span>
          {hasData && (
            <button
              onClick={resetSession}
              className="flex items-center gap-1 text-text-muted hover:text-accent-error transition-colors"
              title="Clear all positions & data"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* Open Positions */}
      {openPositions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 gap-2">
          <div className="w-8 h-8 rounded-full bg-bg-tertiary flex items-center justify-center">
            <DollarSign className="w-4 h-4 text-text-muted" />
          </div>
          <p className="text-[11px] text-text-muted">No open positions</p>
        </div>
      ) : (
        <div className="space-y-2 mb-4">
          {openPositions.map((pos) => (
            <PositionRow
              key={pos.id}
              pos={pos}
              isSelected={selectedMint === pos.mint}
              onClose={handleClose}
              onSelect={() => setSelectedMint(pos.mint)}
            />
          ))}
        </div>
      )}

      {/* Closed Positions (recent) */}
      {closedPositions.length > 0 && (
        <>
          <div className="flex items-center gap-2 mb-2 mt-4 pt-3 border-t border-border-primary">
            <span className="text-[10px] text-text-muted uppercase tracking-wider font-medium">Recent Closes</span>
          </div>
          <div className="space-y-1.5">
            {closedPositions.map((pos) => (
              <div key={pos.id} className="flex items-center justify-between p-2 rounded-lg bg-bg-secondary/40 text-[11px]">
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    pos.status === 'tp_hit' ? 'bg-accent-neon' : pos.status === 'sl_hit' ? 'bg-accent-error' : 'bg-text-muted'
                  }`} />
                  <span className="font-bold">{pos.symbol}</span>
                  <span className="text-[9px] text-text-muted font-mono uppercase">{pos.status.replace('_', ' ')}</span>
                </div>
                <span className={`font-mono font-bold ${pos.pnlPercent >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
                  {pos.pnlPercent >= 0 ? '+' : ''}{pos.pnlPercent.toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function PositionRow({ pos, isSelected, onClose, onSelect }: {
  pos: any;
  isSelected: boolean;
  onClose: (id: string) => void;
  onSelect: () => void;
}) {
  const ageMin = Math.floor((Date.now() - pos.entryTime) / 60000);
  const ageLabel = ageMin < 1 ? '<1m' : ageMin < 60 ? `${ageMin}m` : `${Math.floor(ageMin / 60)}h`;

  // Use per-position recommended SL/TP (set at snipe time)
  const sl = pos.recommendedSl ?? useSniperStore.getState().config.stopLossPct;
  const tp = pos.recommendedTp ?? useSniperStore.getState().config.takeProfitPct;

  return (
    <div
      onClick={onSelect}
      className={`relative p-3 rounded-lg border transition-all cursor-pointer ${
        isSelected
          ? 'bg-accent-neon/[0.06] border-accent-neon/40 ring-1 ring-accent-neon/20'
          : pos.pnlPercent >= 0
            ? 'bg-accent-neon/[0.03] border-accent-neon/20 hover:border-accent-neon/30'
            : 'bg-accent-error/[0.03] border-accent-error/20 hover:border-accent-error/30'
      }`}
    >
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold">{pos.symbol}</span>
          <span className="text-[9px] font-mono text-text-muted bg-bg-tertiary px-1.5 py-0.5 rounded">
            {pos.solInvested.toFixed(2)} SOL
          </span>
          {isSelected && (
            <BarChart3 className="w-3 h-3 text-accent-neon" />
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-mono font-bold ${pos.pnlPercent >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
            {pos.pnlPercent >= 0 ? '+' : ''}{pos.pnlPercent.toFixed(1)}%
          </span>
          <button
            onClick={(e) => { e.stopPropagation(); onClose(pos.id); }}
            className="w-6 h-6 rounded-full flex items-center justify-center bg-accent-error/10 text-accent-error hover:bg-accent-error/20 transition-all"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Per-position SL/TP + age */}
      <div className="flex items-center gap-2 text-[9px] font-mono text-text-muted">
        <Clock className="w-3 h-3" />
        <span>{ageLabel}</span>
        <span className="text-text-muted/50">|</span>
        <span className="flex items-center gap-0.5 text-accent-error">
          <Shield className="w-2.5 h-2.5" /> SL -{sl}%
        </span>
        <span className="text-text-muted/50">|</span>
        <span className="flex items-center gap-0.5 text-accent-neon">
          <Target className="w-2.5 h-2.5" /> TP +{tp}%
        </span>
        {pos.score != null && (
          <>
            <span className="text-text-muted/50">|</span>
            <span className="text-text-muted">Score {pos.score}</span>
          </>
        )}
        {pos.txHash && (
          <>
            <span className="text-text-muted/50">|</span>
            <a
              href={`https://solscan.io/tx/${pos.txHash}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-0.5 text-text-muted hover:text-accent-neon transition-colors"
              onClick={(e) => e.stopPropagation()}
            >
              <ExternalLink className="w-2.5 h-2.5" /> Tx
            </a>
          </>
        )}
      </div>
    </div>
  );
}
