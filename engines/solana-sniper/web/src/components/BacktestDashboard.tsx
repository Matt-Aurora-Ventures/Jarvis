'use client';

import type { StrategyRow, BacktestRun, BestConfig } from '@/lib/data';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis } from 'recharts';

export function BacktestDashboard({
  strategies,
  history,
  bestConfig,
}: {
  strategies: StrategyRow[];
  history: BacktestRun[];
  bestConfig: BestConfig | null;
}) {
  return (
    <div className="space-y-6">
      {/* Best Config Banner */}
      {bestConfig && (
        <div className="card glow border-[var(--border-accent)]">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-2.5 h-2.5 rounded-full bg-[var(--accent)] pulse-green" />
            <h2 className="text-sm font-semibold text-[var(--accent)] uppercase tracking-wider">
              Current Best Configuration
            </h2>
            <span className="text-xs text-[var(--text-muted)] ml-auto">
              Saved {bestConfig.savedAt ? new Date(bestConfig.savedAt).toLocaleString() : 'N/A'}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-6 mb-4">
            <div>
              <div className="text-xs text-[var(--text-muted)] uppercase mb-1">Win Rate</div>
              <div className="text-3xl font-bold mono text-[var(--accent)]">
                {(bestConfig.winRate * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-xs text-[var(--text-muted)] uppercase mb-1">P&L</div>
              <div className={`text-3xl font-bold mono ${bestConfig.pnl >= 0 ? 'text-[var(--accent)]' : 'text-[var(--red)]'}`}>
                {bestConfig.pnl >= 0 ? '+' : ''}${bestConfig.pnl.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-[var(--text-muted)] uppercase mb-1">Sharpe Ratio</div>
              <div className="text-3xl font-bold mono text-[var(--text-primary)]">
                {bestConfig.sharpe.toFixed(2)}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(bestConfig.config).map(([key, value]) => (
              <div key={key} className="p-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                <div className="text-[10px] text-[var(--text-muted)] uppercase">{formatKey(key)}</div>
                <div className="text-sm font-semibold mono text-[var(--text-primary)]">{formatValue(value)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Strategy Performance Table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">
            Strategy Comparison
          </h2>
          {strategies.length === 0 ? (
            <div className="text-center text-[var(--text-muted)] py-12 text-sm">
              Run backtests to generate strategy comparisons
            </div>
          ) : (
            <div className="space-y-2">
              {strategies.map((s, i) => {
                const wrColor = s.win_rate >= 0.6 ? '#22c55e' : s.win_rate >= 0.4 ? '#eab308' : '#ef4444';
                const pnlColor = s.total_pnl_usd >= 0 ? '#22c55e' : '#ef4444';

                return (
                  <div key={s.strategy} className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] hover:border-[var(--border-accent)] transition-colors">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        {i === 0 && <span className="text-xs px-1.5 py-0.5 rounded bg-[#22c55e22] text-[#22c55e]">BEST</span>}
                        <span className="text-xs font-semibold text-[var(--text-primary)]">{s.strategy}</span>
                      </div>
                      <span className="mono font-bold text-sm" style={{ color: wrColor }}>
                        {(s.win_rate * 100).toFixed(1)}%
                      </span>
                    </div>

                    <div className="grid grid-cols-4 gap-2 text-[10px]">
                      <div className="text-[var(--text-muted)]">
                        Trades: <span className="mono text-[var(--text-primary)]">{s.trades_count}</span>
                      </div>
                      <div className="text-[var(--text-muted)]">
                        P&L: <span className="mono" style={{ color: pnlColor }}>${s.total_pnl_usd.toFixed(2)}</span>
                      </div>
                      <div className="text-[var(--text-muted)]">
                        Sharpe: <span className="mono text-[var(--text-primary)]">{s.sharpe_ratio.toFixed(2)}</span>
                      </div>
                      <div className="text-[var(--text-muted)]">
                        DD: <span className="mono text-[var(--red)]">-{s.max_drawdown_pct.toFixed(1)}%</span>
                      </div>
                    </div>

                    <div className="mt-2 h-1.5 bg-[var(--bg-primary)] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{ width: `${s.win_rate * 100}%`, background: wrColor }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Win Rate Bar Chart */}
        <div className="card">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">
            Win Rate Distribution
          </h2>
          {strategies.length === 0 ? (
            <div className="flex items-center justify-center h-[300px] text-[var(--text-muted)] text-sm">
              No data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={strategies.map(s => ({
                name: s.strategy.length > 12 ? s.strategy.slice(0, 12) + '...' : s.strategy,
                winRate: +(s.win_rate * 100).toFixed(1),
                pnl: +s.total_pnl_usd.toFixed(2),
              }))} margin={{ top: 5, right: 5, left: -10, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
                <XAxis
                  dataKey="name"
                  tick={{ fill: '#555555', fontSize: 9 }}
                  axisLine={{ stroke: '#222222' }}
                  tickLine={false}
                  angle={-35}
                  textAnchor="end"
                />
                <YAxis
                  tick={{ fill: '#555555', fontSize: 10 }}
                  axisLine={{ stroke: '#222222' }}
                  tickLine={false}
                  tickFormatter={(v: number) => `${v}%`}
                  domain={[0, 100]}
                />
                <Tooltip
                  contentStyle={{ background: '#161616', border: '1px solid #222222', borderRadius: 8, fontSize: 12, fontFamily: 'monospace' }}
                  labelStyle={{ color: '#888888' }}
                  formatter={(value: number) => [`${value}%`, 'Win Rate']}
                />
                <Bar dataKey="winRate" radius={[4, 4, 0, 0]}>
                  {strategies.map((s, idx) => (
                    <Cell key={idx} fill={s.win_rate >= 0.6 ? '#22c55e' : s.win_rate >= 0.4 ? '#eab308' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Optimization History */}
      {history.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">
            Optimization Runs ({history.length})
          </h2>
          <div className="space-y-3">
            {history.slice().reverse().map((run, i) => (
              <div key={i} className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-[var(--text-muted)]">
                    {new Date(run.timestamp).toLocaleString()}
                  </span>
                  <span className="text-xs text-[var(--text-secondary)]">
                    {run.iterations} iterations
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-[10px] text-[var(--text-muted)] uppercase">Best Win Rate</span>
                    <div className="text-lg font-bold mono text-[var(--accent)]">
                      {(run.bestWinRate * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <span className="text-[10px] text-[var(--text-muted)] uppercase">Best P&L</span>
                    <div className={`text-lg font-bold mono ${run.bestPnl >= 0 ? 'text-[var(--accent)]' : 'text-[var(--red)]'}`}>
                      ${run.bestPnl.toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function formatKey(key: string): string {
  return key.replace(/([A-Z])/g, ' $1').replace(/^./, s => s.toUpperCase()).trim();
}

function formatValue(value: unknown): string {
  if (typeof value === 'number') return value % 1 === 0 ? value.toString() : value.toFixed(2);
  return String(value);
}
