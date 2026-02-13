'use client';

import { TrendingUp, Target, Shield, Zap, BarChart3, Activity } from 'lucide-react';
import { useSniperStore, STRATEGY_PRESETS } from '@/stores/useSniperStore';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';
import { filterOpenPositionsForActiveWallet, isPositionInActiveWallet, resolveActiveWallet } from '@/lib/position-scope';
import { isOperatorManagedPositionMeta, isReliableTradeForStats, resolvePositionPnlPercent } from '@/lib/position-reliability';

export function PerformanceSummary() {
  const { address } = usePhantomWallet();
  const { positions, config, activePreset, backtestMeta, tradeSignerMode, sessionWalletPubkey } = useSniperStore();
  const activeWallet = resolveActiveWallet(tradeSignerMode, sessionWalletPubkey, address);
  const scopedOpen = filterOpenPositionsForActiveWallet(positions, activeWallet).filter(
    (p) => isOperatorManagedPositionMeta(p),
  );
  const scopedClosed = positions.filter(
    (p) =>
      p.status !== 'open' &&
      isPositionInActiveWallet(p, activeWallet) &&
      isReliableTradeForStats(p),
  );
  const scopedWins = scopedClosed.filter((p) => {
    if (p.status === 'tp_hit') return true;
    if (p.status === 'sl_hit') return false;
    return resolvePositionPnlPercent(p) >= 0;
  }).length;
  const scopedLosses = Math.max(0, scopedClosed.length - scopedWins);
  const scopedTrades = scopedClosed.length;
  const winRate = scopedTrades > 0 ? (scopedWins / scopedTrades) * 100 : 0;
  const scopedRealizedPnl = scopedClosed.reduce((acc, p) => {
    if (typeof p.realPnlSol === 'number') return acc + p.realPnlSol;
    return acc + (typeof p.pnlSol === 'number' ? p.pnlSol : 0);
  }, 0);
  const openCount = scopedOpen.length;
  const unrealizedPnl = scopedOpen.reduce((s, p) => s + p.pnlSol, 0);
  const preset = STRATEGY_PRESETS.find(p => p.id === activePreset);
  const presetLabel = preset?.name || activePreset?.toUpperCase() || 'CUSTOM';
  const meta = (backtestMeta as any)?.[activePreset] as
    | { winRate: string; trades: number; backtested: boolean; dataSource: string; underperformer: boolean; stage?: string; promotionEligible?: boolean }
    | undefined;
  const stageTag =
    meta?.stage === 'promotion' ? 'S3' :
    meta?.stage === 'stability' ? 'S2' :
    meta?.stage === 'sanity' ? 'S1' :
    '';

  const stats = [
    {
      icon: <TrendingUp className="w-4 h-4" />,
      label: 'Total PnL',
      value: `${scopedRealizedPnl >= 0 ? '+' : ''}${scopedRealizedPnl.toFixed(3)} SOL`,
      color: scopedRealizedPnl >= 0 ? 'text-accent-neon' : 'text-accent-error',
      bgColor: scopedRealizedPnl >= 0 ? 'bg-accent-neon/10 border-accent-neon/20' : 'bg-accent-error/10 border-accent-error/20',
    },
    {
      icon: <Target className="w-4 h-4" />,
      label: 'Win Rate',
      value: scopedTrades > 0 ? `${winRate.toFixed(1)}%` : '--',
      color: winRate >= 60 ? 'text-accent-neon' : winRate >= 40 ? 'text-accent-warning' : 'text-accent-error',
      bgColor: 'bg-bg-secondary border-border-primary',
    },
    {
      icon: <BarChart3 className="w-4 h-4" />,
      label: 'Trades',
      value: `${scopedWins}W / ${scopedLosses}L`,
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
      sub: meta?.backtested
        ? `BT: ${meta.winRate} (${meta.trades}T${stageTag ? ` ${stageTag}` : ''}, ${meta.dataSource})${meta.promotionEligible ? '  PROMO' : ''}${meta.underperformer ? '  UNDERPERF' : ''}`
        : 'BT: Unverified (run Strategy Validation)',
      color: meta?.underperformer
        ? 'text-accent-error'
        : config.strategyMode === 'aggressive'
          ? 'text-accent-warning'
          : 'text-accent-neon',
      bgColor: meta?.underperformer
        ? 'bg-accent-error/5 border-accent-error/15'
        : config.strategyMode === 'aggressive'
          ? 'bg-accent-warning/5 border-accent-warning/15'
          : 'bg-accent-neon/5 border-accent-neon/15',
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
          <span
            className={`font-mono font-bold ${stat.color} ${
              stat.label === 'Strategy'
                ? 'text-xs leading-tight break-words whitespace-normal'
                : 'text-sm truncate'
            }`}
          >
            {stat.value}
          </span>
          {stat.sub && (
            <span
              className={`font-mono text-text-muted/70 ${
                stat.label === 'Strategy'
                  ? 'text-[8px] leading-tight break-words whitespace-normal'
                  : 'text-[9px]'
              }`}
            >
              {stat.sub}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
