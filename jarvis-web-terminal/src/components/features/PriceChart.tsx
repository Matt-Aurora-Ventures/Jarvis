'use client';

import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar,
} from 'recharts';
import { useChartData } from '@/hooks/useChartData';
import type { Market, Timeframe } from '@/lib/chart-data';

const MARKETS: Market[] = ['SOL', 'ETH', 'BTC'];
const TIMEFRAMES: Timeframe[] = ['1h', '4h', '1d'];

function ChartTooltip({ active, payload }: any) {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-bg-secondary border border-accent-neon/30 rounded-md px-3 py-2 shadow-lg font-mono text-xs space-y-0.5">
      <div className="text-accent-neon font-bold text-sm">${d.close?.toFixed(2)}</div>
      <div className="text-text-muted">
        O {d.open?.toFixed(2)} H {d.high?.toFixed(2)} L {d.low?.toFixed(2)}
      </div>
      <div className="text-text-muted">Vol {(d.volume / 1e6).toFixed(1)}M</div>
    </div>
  );
}

export function PriceChart() {
  const { candles, price, loading, market, timeframe, setMarket, setTimeframe } = useChartData('SOL');

  // Compute 24h change from candles
  const first = candles[0]?.open ?? 0;
  const last = candles[candles.length - 1]?.close ?? 0;
  const change = first > 0 ? ((last - first) / first) * 100 : 0;

  return (
    <div className="card-glass p-0 overflow-hidden min-h-[420px] relative">
      {/* Header */}
      <div className="absolute top-3 left-3 z-10 flex gap-3 items-center">
        <div className="flex flex-col">
          <span className="font-display font-bold text-xl text-text-primary">{market}/USDC</span>
          <span className="font-mono text-[10px] text-text-muted">GECKOTERMINAL</span>
        </div>
        <div className="h-8 w-[1px] bg-border-primary" />
        <div className="flex flex-col">
          <span className="font-mono font-bold text-accent-neon text-sm">
            {price > 0 ? `$${price.toFixed(2)}` : '...'}
          </span>
          <span className={`font-mono text-[10px] ${change >= 0 ? 'text-accent-success' : 'text-accent-error'}`}>
            {change >= 0 ? '+' : ''}{change.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Controls — top right */}
      <div className="absolute top-3 right-3 z-10 flex gap-2">
        {/* Market Selector */}
        <div className="flex bg-bg-secondary/80 rounded-md p-0.5 border border-border-primary">
          {MARKETS.map((m) => (
            <button
              key={m}
              onClick={() => setMarket(m)}
              className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded transition-colors ${
                market === m
                  ? 'bg-accent-neon/20 text-accent-neon'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {m}
            </button>
          ))}
        </div>

        {/* Timeframe Selector */}
        <div className="flex bg-bg-secondary/80 rounded-md p-0.5 border border-border-primary">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded transition-colors ${
                timeframe === tf
                  ? 'bg-accent-neon/20 text-accent-neon'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {tf.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Chart Body */}
      <div className="pt-16 px-3 pb-3">
        {loading && candles.length === 0 ? (
          <div className="flex items-center justify-center h-[260px] text-text-muted font-mono text-xs animate-pulse">
            LOADING {market} OHLCV...
          </div>
        ) : (
          <>
            {/* Price Area */}
            <div className="h-[260px] -ml-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={candles}>
                  <defs>
                    <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#22c55e" stopOpacity={0.15} />
                      <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 9, fill: '#a7f3d0' }}
                    axisLine={false}
                    tickLine={false}
                    interval={Math.floor(candles.length / 6)}
                    tickFormatter={(ts: number) => {
                      const d = new Date(ts * 1000);
                      return timeframe === '1d'
                        ? `${d.getMonth() + 1}/${d.getDate()}`
                        : `${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
                    }}
                  />
                  <YAxis
                    domain={['auto', 'auto']}
                    tick={{ fontSize: 9, fill: '#a7f3d0' }}
                    axisLine={false}
                    tickLine={false}
                    width={55}
                    tickFormatter={(v: number) => `$${v.toLocaleString()}`}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="close"
                    stroke="#22c55e"
                    strokeWidth={2}
                    fill="url(#priceFill)"
                    dot={false}
                    animationDuration={800}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Volume Bars */}
            <div className="h-[36px] -ml-2 -mt-1">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={candles}>
                  <Bar
                    dataKey="volume"
                    fill="#22c55e"
                    opacity={0.12}
                    radius={[2, 2, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
