'use client';

import type { DashboardStats } from '@/lib/data';

function StatCard({ label, value, subValue, color }: {
  label: string;
  value: string;
  subValue?: string;
  color?: 'green' | 'red' | 'yellow' | 'blue' | 'default';
}) {
  const colorMap = {
    green: 'text-[#22c55e]',
    red: 'text-[#ef4444]',
    yellow: 'text-[#eab308]',
    blue: 'text-[#3b82f6]',
    default: 'text-[var(--text-primary)]',
  };

  return (
    <div className="card">
      <div className="text-xs uppercase tracking-wider text-[var(--text-muted)] mb-2">{label}</div>
      <div className={`text-2xl font-bold mono ${colorMap[color ?? 'default']}`}>{value}</div>
      {subValue && <div className="text-xs text-[var(--text-secondary)] mt-1">{subValue}</div>}
    </div>
  );
}

export function StatsGrid({ stats }: { stats: DashboardStats }) {
  const pnlColor = stats.totalPnlUsd >= 0 ? 'green' : 'red';
  const wrColor = stats.winRate >= 0.6 ? 'green' : stats.winRate >= 0.4 ? 'yellow' : 'red';
  const todayColor = stats.todayPnl >= 0 ? 'green' : 'red';

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
      <StatCard
        label="Total P&L"
        value={`${stats.totalPnlUsd >= 0 ? '+' : ''}$${stats.totalPnlUsd.toFixed(2)}`}
        color={pnlColor}
      />
      <StatCard
        label="Win Rate"
        value={`${(stats.winRate * 100).toFixed(1)}%`}
        subValue={`${stats.wins}W / ${stats.losses}L`}
        color={wrColor}
      />
      <StatCard
        label="Total Trades"
        value={stats.totalTrades.toString()}
        subValue={`${stats.todayTrades} today`}
        color="blue"
      />
      <StatCard
        label="Open Positions"
        value={stats.openPositions.toString()}
        subValue={`$${stats.totalValueUsd.toFixed(2)} value`}
      />
      <StatCard
        label="Today P&L"
        value={`${stats.todayPnl >= 0 ? '+' : ''}$${stats.todayPnl.toFixed(2)}`}
        color={todayColor}
      />
      <StatCard
        label="Best / Worst"
        value={`+$${stats.bestTradePnl.toFixed(2)}`}
        subValue={`Worst: $${stats.worstTradePnl.toFixed(2)}`}
        color="green"
      />
    </div>
  );
}
