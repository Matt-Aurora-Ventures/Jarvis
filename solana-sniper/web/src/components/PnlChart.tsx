'use client';

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

interface PnlDataPoint {
  date: string;
  pnl: number;
  cumulative: number;
}

export function PnlChart({ data }: { data: PnlDataPoint[] }) {
  const hasData = data.length > 0;
  const latestCumulative = hasData ? data[data.length - 1].cumulative : 0;
  const isPositive = latestCumulative >= 0;

  return (
    <div className="card h-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
          Cumulative P&L
        </h2>
        {hasData && (
          <span className={`text-lg font-bold mono ${isPositive ? 'text-[#22c55e]' : 'text-[#ef4444]'}`}>
            {isPositive ? '+' : ''}${latestCumulative.toFixed(2)}
          </span>
        )}
      </div>

      {!hasData ? (
        <div className="flex items-center justify-center h-[250px] text-[var(--text-muted)] text-sm">
          Waiting for trade data...
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={250}>
          <AreaChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
            <defs>
              <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={isPositive ? '#22c55e' : '#ef4444'} stopOpacity={0.3} />
                <stop offset="100%" stopColor={isPositive ? '#22c55e' : '#ef4444'} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
            <XAxis
              dataKey="date"
              tick={{ fill: '#555555', fontSize: 10 }}
              axisLine={{ stroke: '#222222' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#555555', fontSize: 10 }}
              axisLine={{ stroke: '#222222' }}
              tickLine={false}
              tickFormatter={(v: number) => `$${v.toFixed(0)}`}
            />
            <Tooltip
              contentStyle={{
                background: '#161616',
                border: '1px solid #222222',
                borderRadius: 8,
                fontSize: 12,
                fontFamily: 'monospace',
              }}
              labelStyle={{ color: '#888888' }}
              formatter={(value: number) => [`$${value.toFixed(2)}`, 'Cumulative P&L']}
            />
            <Area
              type="monotone"
              dataKey="cumulative"
              stroke={isPositive ? '#22c55e' : '#ef4444'}
              strokeWidth={2}
              fill="url(#pnlGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
