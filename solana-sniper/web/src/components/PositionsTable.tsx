'use client';

import type { PositionRow } from '@/lib/data';

export function PositionsTable({ positions }: { positions: PositionRow[] }) {
  return (
    <div className="card h-full">
      <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">
        Open Positions
        <span className="ml-2 text-[var(--accent)]">{positions.length}</span>
      </h2>

      {positions.length === 0 ? (
        <div className="text-center text-[var(--text-muted)] py-8 text-sm">
          No open positions
        </div>
      ) : (
        <div className="space-y-3">
          {positions.map((pos) => {
            const pnlColor = pos.unrealized_pnl >= 0 ? 'text-[#22c55e]' : 'text-[#ef4444]';
            const pnlSign = pos.unrealized_pnl >= 0 ? '+' : '';
            const safetyColor = pos.safety_score >= 0.7 ? 'bg-[#22c55e]' : pos.safety_score >= 0.5 ? 'bg-[#eab308]' : 'bg-[#ef4444]';

            return (
              <div key={pos.id} className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${safetyColor}`} />
                    <span className="font-semibold text-sm">{pos.symbol}</span>
                  </div>
                  <span className={`font-bold mono text-sm ${pnlColor}`}>
                    {pnlSign}{pos.unrealized_pnl_pct.toFixed(1)}%
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-x-4 text-xs text-[var(--text-secondary)]">
                  <div>Entry: <span className="mono text-[var(--text-primary)]">${pos.entry_price.toFixed(6)}</span></div>
                  <div>Now: <span className={`mono ${pnlColor}`}>${pos.current_price.toFixed(6)}</span></div>
                  <div>Size: <span className="mono">${pos.amount_usd.toFixed(2)}</span></div>
                  <div>P&L: <span className={`mono ${pnlColor}`}>{pnlSign}${pos.unrealized_pnl.toFixed(2)}</span></div>
                </div>

                {/* TP/SL bar */}
                <div className="mt-2 flex items-center gap-2 text-[10px] text-[var(--text-muted)]">
                  <span className="text-[#ef4444]">SL -{pos.stop_loss_pct}%</span>
                  <div className="flex-1 h-1 bg-[var(--bg-primary)] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${pos.unrealized_pnl_pct >= 0 ? 'bg-[#22c55e]' : 'bg-[#ef4444]'}`}
                      style={{ width: `${Math.min(100, Math.max(0, 50 + pos.unrealized_pnl_pct))}%` }}
                    />
                  </div>
                  <span className="text-[#22c55e]">TP +{pos.take_profit_pct}%</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
