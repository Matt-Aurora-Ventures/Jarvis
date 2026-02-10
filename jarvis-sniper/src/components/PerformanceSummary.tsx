'use client';

import { TrendingUp, Target, Shield, Zap, BarChart3, Activity } from 'lucide-react';
import { useSniperStore, STRATEGY_PRESETS } from '@/stores/useSniperStore';

/** Backtest v5 WR data for each preset — updated from massive-backtest-results.json */
const BACKTEST_WR: Record<string, number> = {
  pump_fresh_tight: 81.0, insight_j: 73.0, genetic_best: 82.1, genetic_v2: 88.1,
  hybrid_b: 73.5, momentum: 20.9, let_it_ride: 82.4, micro_cap_surge: 78.8,
  elite: 81.8, loose: 29.9, hot: 20.9, xstock_momentum: 0, prestock_speculative: 0,
  index_revert: 0,
};

export function PerformanceSummary() {
  const { totalPnl, winCount, lossCount, totalTrades, positions, config, activePreset } = useSniperStore();
  const winRate = totalTrades > 0 ? (winCount / totalTrades) * 100 : 0;
  const openCount = positions.filter(p => p.status === 'open').length;
  const unrealizedPnl = positions.filter(p => p.status === 'open').reduce((s, p) => s + p.pnlSol, 0);
  const preset = STRATEGY_PRESETS.find(p => p.id === activePreset);
  const presetLabel = preset?.name || activePreset?.toUpperCase() || 'CUSTOM';
  const backtestWr = BACKTEST_WR[activePreset] ?? null;

  const stats = [
    {
      icon: <TrendingUp className="w-4 h-4" />,
      label: 'Total PnL',
      value: `${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(3)} SOL`,
      color: totalPnl >= 0 ? 'text-accent-neon' : 'text-accent-error',
      bgColor: totalPnl >= 0 ? 'bg-accent-neon/10 border-accent-neon/20' : 'bg-accent-error/10 border-accent-error/20',
    },
    {
      icon: <Target className="w-4 h-4" />,
      label: 'Win Rate',
      value: totalTrades > 0 ? `${winRate.toFixed(1)}%` : '--',
      color: winRate >= 60 ? 'text-accent-neon' : winRate >= 40 ? 'text-accent-warning' : 'text-accent-error',
      bgColor: 'bg-bg-secondary border-border-primary',
    },
    {
      icon: <BarChart3 className="w-4 h-4" />,
      label: 'Trades',
      value: `${winCount}W / ${lossCount}L`,
      color: 'text-text-primary',
      bgColor: 'bg-bg-secondary border-border-primary',
    },
    {
      icon: <Activity className="w-4 h-4" />,
      label: 'Open',
      value: `${openCount} (${unrealizedPnl >= 0 ? '+' : ''}${unrealizedPnl.toFixed(3)})`,
      color: 'text-text-secondary',
      bgColor: 'bg-bg-secondary border-border-primary',
    },
    {
      icon: <Shield className="w-4 h-4" />,
      label: 'Strategy',
      value: `${presetLabel} ${config.stopLossPct}/${config.takeProfitPct}+${config.trailingStopPct}t`,
      sub: backtestWr !== null && backtestWr > 0 ? `BT: ${backtestWr.toFixed(0)}% WR` : undefined,
      color: config.strategyMode === 'aggressive' ? 'text-accent-warning' : 'text-accent-neon',
      bgColor: config.strategyMode === 'aggressive' ? 'bg-accent-warning/5 border-accent-warning/15' : 'bg-accent-neon/5 border-accent-neon/15',
    },
    {
      icon: <Zap className="w-4 h-4" />,
      label: 'Mode',
      value: config.autoSnipe ? 'AUTO' : 'MANUAL',
      color: config.autoSnipe ? 'text-accent-neon' : 'text-text-muted',
      bgColor: config.autoSnipe ? 'bg-accent-neon/10 border-accent-neon/20' : 'bg-bg-secondary border-border-primary',
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className={`flex flex-col gap-1.5 p-3 rounded-lg border transition-all hover:shadow-md ${stat.bgColor}`}
        >
          <div className="flex items-center gap-1.5 text-text-muted">
            {stat.icon}
            <span className="text-[9px] uppercase tracking-wider font-medium">{stat.label}</span>
          </div>
          <span className={`text-sm font-mono font-bold ${stat.color} truncate`}>{stat.value}</span>
          {stat.sub && <span className="text-[9px] font-mono text-text-muted/70">{stat.sub}</span>}
        </div>
      ))}
    </div>
  );
}
