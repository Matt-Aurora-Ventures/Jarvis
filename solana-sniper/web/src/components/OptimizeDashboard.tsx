'use client';

import type { BacktestRun, BestConfig } from '@/lib/data';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, AreaChart, Area } from 'recharts';

export function OptimizeDashboard({
  log,
  bestConfig,
}: {
  log: BacktestRun[];
  bestConfig: BestConfig | null;
}) {
  // Transform log into chart data
  const progressData = log.map((run, i) => ({
    run: i + 1,
    winRate: +(run.bestWinRate * 100).toFixed(1),
    pnl: +run.bestPnl.toFixed(2),
    iterations: run.iterations,
    timestamp: run.timestamp,
  }));

  const latestWinRate = progressData.length > 0 ? progressData[progressData.length - 1].winRate : 0;
  const targetWinRate = 80;
  const progressPct = Math.min(100, (latestWinRate / targetWinRate) * 100);

  return (
    <div className="space-y-6">
      {/* Progress Toward 80% Target */}
      <div className="card glow border-[var(--border-accent)]">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-[var(--accent)] uppercase tracking-wider">
            Target: 80% Win Rate
          </h2>
          <span className="text-xs text-[var(--text-muted)]">
            {log.length} optimization runs completed
          </span>
        </div>

        <div className="flex items-end gap-6 mb-4">
          <div>
            <div className="text-[10px] text-[var(--text-muted)] uppercase mb-1">Current Best</div>
            <div className={`text-4xl font-bold mono ${latestWinRate >= 80 ? 'text-[var(--accent)]' : latestWinRate >= 60 ? 'text-[var(--yellow)]' : 'text-[var(--red)]'}`}>
              {latestWinRate.toFixed(1)}%
            </div>
          </div>
          <div>
            <div className="text-[10px] text-[var(--text-muted)] uppercase mb-1">Target</div>
            <div className="text-4xl font-bold mono text-[var(--text-secondary)]">80.0%</div>
          </div>
          <div>
            <div className="text-[10px] text-[var(--text-muted)] uppercase mb-1">Gap</div>
            <div className={`text-4xl font-bold mono ${latestWinRate >= 80 ? 'text-[var(--accent)]' : 'text-[var(--red)]'}`}>
              {latestWinRate >= 80 ? '+' : ''}{(latestWinRate - 80).toFixed(1)}%
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="relative h-3 bg-[var(--bg-primary)] rounded-full overflow-hidden">
          <div
            className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
            style={{
              width: `${progressPct}%`,
              background: latestWinRate >= 80
                ? 'linear-gradient(90deg, #22c55e, #4ade80)'
                : latestWinRate >= 60
                ? 'linear-gradient(90deg, #eab308, #facc15)'
                : 'linear-gradient(90deg, #ef4444, #f87171)',
            }}
          />
          {/* 80% marker */}
          <div
            className="absolute inset-y-0 w-0.5 bg-[var(--text-secondary)]"
            style={{ left: '100%' }}
          />
        </div>
        <div className="flex justify-between mt-1 text-[10px] text-[var(--text-muted)]">
          <span>0%</span>
          <span>80% target</span>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Win Rate Progress */}
        <div className="card">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">
            Win Rate Evolution
          </h2>
          {progressData.length === 0 ? (
            <div className="flex items-center justify-center h-[250px] text-[var(--text-muted)] text-sm">
              Run self-improvement to see progress
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={progressData} margin={{ top: 5, right: 5, left: -10, bottom: 5 }}>
                <defs>
                  <linearGradient id="wrGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22c55e" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
                <XAxis
                  dataKey="run"
                  tick={{ fill: '#555555', fontSize: 10 }}
                  axisLine={{ stroke: '#222222' }}
                  tickLine={false}
                  label={{ value: 'Run #', position: 'bottom', fill: '#555555', fontSize: 10 }}
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
                  formatter={(value: number) => [`${value}%`, 'Best Win Rate']}
                />
                {/* Target line at 80% */}
                <Area
                  type="monotone"
                  dataKey="winRate"
                  stroke="#22c55e"
                  strokeWidth={2}
                  fill="url(#wrGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* P&L Progress */}
        <div className="card">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">
            P&L Evolution
          </h2>
          {progressData.length === 0 ? (
            <div className="flex items-center justify-center h-[250px] text-[var(--text-muted)] text-sm">
              Run self-improvement to see progress
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={progressData} margin={{ top: 5, right: 5, left: -10, bottom: 5 }}>
                <defs>
                  <linearGradient id="pnlGrad2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
                <XAxis
                  dataKey="run"
                  tick={{ fill: '#555555', fontSize: 10 }}
                  axisLine={{ stroke: '#222222' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: '#555555', fontSize: 10 }}
                  axisLine={{ stroke: '#222222' }}
                  tickLine={false}
                  tickFormatter={(v: number) => `$${v}`}
                />
                <Tooltip
                  contentStyle={{ background: '#161616', border: '1px solid #222222', borderRadius: 8, fontSize: 12, fontFamily: 'monospace' }}
                  formatter={(value: number) => [`$${value.toFixed(2)}`, 'Best P&L']}
                />
                <Area
                  type="monotone"
                  dataKey="pnl"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  fill="url(#pnlGrad2)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Current Best Config */}
      {bestConfig && (
        <div className="card">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">
            Optimized Parameters
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {Object.entries(bestConfig.config).map(([key, value]) => (
              <div key={key} className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                <div className="text-[10px] text-[var(--text-muted)] uppercase mb-1">{formatKey(key)}</div>
                <div className="text-lg font-bold mono text-[var(--text-primary)]">{formatValue(value)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Run History */}
      {log.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">
            Run History
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-[var(--text-muted)] border-b border-[var(--border)]">
                  <th className="text-left py-2 pr-3">#</th>
                  <th className="text-left py-2 pr-3">Timestamp</th>
                  <th className="text-right py-2 pr-3">Iterations</th>
                  <th className="text-right py-2 pr-3">Best Win Rate</th>
                  <th className="text-right py-2">Best P&L</th>
                </tr>
              </thead>
              <tbody>
                {log.slice().reverse().map((run, i) => {
                  const wrColor = run.bestWinRate >= 0.6 ? 'text-[#22c55e]' : run.bestWinRate >= 0.4 ? 'text-[#eab308]' : 'text-[#ef4444]';
                  const pnlColor = run.bestPnl >= 0 ? 'text-[#22c55e]' : 'text-[#ef4444]';

                  return (
                    <tr key={i} className="border-b border-[var(--border)] hover:bg-[var(--bg-card-hover)]">
                      <td className="py-2 pr-3 text-[var(--text-muted)]">{log.length - i}</td>
                      <td className="py-2 pr-3 text-xs text-[var(--text-secondary)]">
                        {new Date(run.timestamp).toLocaleString()}
                      </td>
                      <td className="py-2 pr-3 text-right mono">{run.iterations}</td>
                      <td className={`py-2 pr-3 text-right mono font-semibold ${wrColor}`}>
                        {(run.bestWinRate * 100).toFixed(1)}%
                      </td>
                      <td className={`py-2 text-right mono font-semibold ${pnlColor}`}>
                        ${run.bestPnl.toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
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
