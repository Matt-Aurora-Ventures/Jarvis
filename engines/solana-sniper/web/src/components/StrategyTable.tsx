'use client';

import type { StrategyRow } from '@/lib/data';

export function StrategyTable({ strategies }: { strategies: StrategyRow[] }) {
  return (
    <div className="card h-full">
      <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">
        Strategy Performance
      </h2>

      {strategies.length === 0 ? (
        <div className="text-center text-[var(--text-muted)] py-8 text-sm">
          Run backtest to see strategy comparisons
        </div>
      ) : (
        <div className="space-y-3">
          {strategies.map((strat, idx) => {
            const wrColor = strat.win_rate >= 0.6 ? 'text-[#22c55e]' : strat.win_rate >= 0.4 ? 'text-[#eab308]' : 'text-[#ef4444]';
            const pnlColor = strat.total_pnl_usd >= 0 ? 'text-[#22c55e]' : 'text-[#ef4444]';

            return (
              <div key={strat.strategy} className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-[var(--text-primary)]">
                    {idx === 0 && <span className="text-[#22c55e] mr-1">*</span>}
                    {strat.strategy}
                  </span>
                  <span className={`font-bold mono text-sm ${wrColor}`}>
                    {(strat.win_rate * 100).toFixed(0)}%
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-[10px] text-[var(--text-secondary)]">
                  <div>
                    Trades: <span className="mono text-[var(--text-primary)]">{strat.trades_count}</span>
                  </div>
                  <div>
                    P&L: <span className={`mono ${pnlColor}`}>${strat.total_pnl_usd.toFixed(2)}</span>
                  </div>
                  <div>
                    Sharpe: <span className="mono text-[var(--text-primary)]">{strat.sharpe_ratio.toFixed(2)}</span>
                  </div>
                </div>

                {/* Win rate bar */}
                <div className="mt-2 h-1 bg-[var(--bg-primary)] rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-[#22c55e]"
                    style={{ width: `${strat.win_rate * 100}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
