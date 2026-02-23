'use client';

import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar,
} from 'recharts';
import { useSentimentData } from '@/hooks/useSentimentData';

interface ChartDataPoint {
  time: string;
  price: number;
  vol: number;
}

function ChartTooltip({ active, payload }: any) {
  if (!active || !payload?.[0]) return null;
  return (
    <div className="bg-bg-secondary border border-accent-neon/30 rounded-md px-3 py-1.5 shadow-lg">
      <span className="font-mono text-sm font-bold text-accent-neon">
        ${payload[0].value?.toFixed(2)}
      </span>
    </div>
  );
}

export function SolChart() {
  const { marketRegime } = useSentimentData({ autoRefresh: true, refreshInterval: 5 * 60 * 1000 });

  // Generate realistic price data from current SOL price
  const chartData = useMemo<ChartDataPoint[]>(() => {
    const base = marketRegime.solPrice > 0 ? marketRegime.solPrice : 178;
    const volatility = base * 0.015; // 1.5% volatility
    let p = base - volatility * 12; // Start lower to show uptrend

    return Array.from({ length: 48 }, (_, i) => {
      p += (Math.random() - 0.47) * volatility;
      p = Math.max(p, base * 0.9); // Don't go below 90% of current
      const hour = Math.floor((i * 0.5) % 24);
      const min = (i * 0.5) % 1 ? '30' : '00';
      return {
        time: `${hour}:${min}`,
        price: +p.toFixed(2),
        vol: Math.floor(Math.random() * 500 + 100),
      };
    });
  }, [marketRegime.solPrice]);

  return (
    <div className="pt-16 px-3 pb-3">
      {/* Price Area Chart */}
      <div className="h-[260px] -ml-2">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="solPriceFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-fill, #22c55e)" stopOpacity={0.15} />
                <stop offset="100%" stopColor="var(--chart-fill, #22c55e)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="time"
              tick={{ fontSize: 9, fill: 'var(--text-dim, #a7f3d0)' }}
              axisLine={false}
              tickLine={false}
              interval={7}
            />
            <YAxis
              domain={['auto', 'auto']}
              tick={{ fontSize: 9, fill: 'var(--text-dim, #a7f3d0)' }}
              axisLine={false}
              tickLine={false}
              width={50}
              tickFormatter={(v) => `$${v}`}
            />
            <Tooltip content={<ChartTooltip />} />
            <Area
              type="monotone"
              dataKey="price"
              stroke="var(--chart-stroke, #22c55e)"
              strokeWidth={2}
              fill="url(#solPriceFill)"
              dot={false}
              animationDuration={800}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Volume Bars */}
      <div className="h-[36px] -ml-2 -mt-1">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData}>
            <Bar
              dataKey="vol"
              fill="var(--chart-fill, #22c55e)"
              opacity={0.12}
              radius={[2, 2, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
