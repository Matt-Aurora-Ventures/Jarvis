'use client';

import type { TradeRow } from '@/lib/data';

function timeAgo(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function TradesTable({ trades }: { trades: TradeRow[] }) {
  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">
        Recent Trades
      </h2>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-[var(--text-muted)] border-b border-[var(--border)]">
              <th className="text-left py-2 pr-3">Token</th>
              <th className="text-left py-2 pr-3">Side</th>
              <th className="text-right py-2 pr-3">Size</th>
              <th className="text-right py-2 pr-3">P&L</th>
              <th className="text-right py-2 pr-3">Safety</th>
              <th className="text-left py-2 pr-3">Exit</th>
              <th className="text-right py-2">Time</th>
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center text-[var(--text-muted)] py-8">
                  No trades yet — sniper is listening...
                </td>
              </tr>
            ) : (
              trades.map((trade) => {
                const pnlColor = (trade.pnl_usd ?? 0) >= 0 ? 'text-[#22c55e]' : 'text-[#ef4444]';
                const sideColor = trade.side === 'BUY' ? 'text-[#22c55e]' : 'text-[#ef4444]';
                const safetyPct = (trade.safety_score * 100).toFixed(0);
                const safetyColor = trade.safety_score >= 0.7 ? 'text-[#22c55e]' : trade.safety_score >= 0.5 ? 'text-[#eab308]' : 'text-[#ef4444]';

                const exitBadge = trade.exit_reason ? {
                  TAKE_PROFIT: { text: 'TP', color: 'bg-[#22c55e22] text-[#22c55e]' },
                  STOP_LOSS: { text: 'SL', color: 'bg-[#ef444422] text-[#ef4444]' },
                  MANUAL: { text: 'MAN', color: 'bg-[#3b82f622] text-[#3b82f6]' },
                  TIME_EXIT: { text: 'TIME', color: 'bg-[#eab30822] text-[#eab308]' },
                  RUG: { text: 'RUG', color: 'bg-[#ef444422] text-[#ef4444]' },
                }[trade.exit_reason] ?? { text: trade.exit_reason, color: 'bg-[var(--bg-secondary)] text-[var(--text-muted)]' } : null;

                return (
                  <tr key={trade.id} className="border-b border-[var(--border)] hover:bg-[var(--bg-card-hover)]">
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">{trade.symbol}</span>
                        {trade.mode === 'paper' && (
                          <span className="text-[10px] px-1 rounded bg-[#3b82f622] text-[#3b82f6]">PAPER</span>
                        )}
                      </div>
                    </td>
                    <td className={`py-2 pr-3 font-semibold ${sideColor}`}>{trade.side}</td>
                    <td className="py-2 pr-3 text-right mono">${trade.amount_usd.toFixed(2)}</td>
                    <td className={`py-2 pr-3 text-right mono font-semibold ${pnlColor}`}>
                      {trade.pnl_usd !== null
                        ? `${trade.pnl_usd >= 0 ? '+' : ''}$${trade.pnl_usd.toFixed(2)}`
                        : '—'}
                      {trade.pnl_pct !== null && (
                        <div className="text-[10px]">{trade.pnl_pct >= 0 ? '+' : ''}{trade.pnl_pct.toFixed(1)}%</div>
                      )}
                    </td>
                    <td className={`py-2 pr-3 text-right mono ${safetyColor}`}>{safetyPct}%</td>
                    <td className="py-2 pr-3">
                      {exitBadge ? (
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${exitBadge.color}`}>{exitBadge.text}</span>
                      ) : (
                        <span className="text-[10px] text-[var(--text-muted)]">OPEN</span>
                      )}
                    </td>
                    <td className="py-2 text-right text-[var(--text-muted)] text-xs">{timeAgo(trade.entry_at)}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
