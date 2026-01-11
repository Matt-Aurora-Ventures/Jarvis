import React, { useMemo } from 'react';
import { TrendingUp, TrendingDown, Activity, DollarSign, Target, Percent } from 'lucide-react';

interface TradeRecord {
  id: string;
  strategy: string;
  token: string;
  side: 'buy' | 'sell';
  entryPrice: number;
  exitPrice?: number;
  amount: number;
  pnl: number;
  pnlPercent: number;
  timestamp: string;
  status: 'open' | 'closed' | 'stopped';
}

interface StrategyPerformance {
  name: string;
  totalTrades: number;
  winRate: number;
  totalPnl: number;
  avgPnl: number;
  maxDrawdown: number;
  sharpeRatio: number;
}

interface TradingPerformanceProps {
  trades: TradeRecord[];
  strategies: StrategyPerformance[];
  timeframe: '24h' | '7d' | '30d' | 'all';
  onTimeframeChange?: (tf: '24h' | '7d' | '30d' | 'all') => void;
}

export const TradingPerformance: React.FC<TradingPerformanceProps> = ({
  trades,
  strategies,
  timeframe,
  onTimeframeChange,
}) => {
  const stats = useMemo(() => {
    const closedTrades = trades.filter(t => t.status === 'closed');
    const wins = closedTrades.filter(t => t.pnl > 0);
    const totalPnl = closedTrades.reduce((sum, t) => sum + t.pnl, 0);

    return {
      totalTrades: closedTrades.length,
      winRate: closedTrades.length > 0 ? (wins.length / closedTrades.length) * 100 : 0,
      totalPnl,
      avgPnl: closedTrades.length > 0 ? totalPnl / closedTrades.length : 0,
      openPositions: trades.filter(t => t.status === 'open').length,
    };
  }, [trades]);

  const formatUsd = (value: number) => {
    const absValue = Math.abs(value);
    const formatted = new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(absValue);
    return value < 0 ? `-${formatted}` : formatted;
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const timeframes: Array<'24h' | '7d' | '30d' | 'all'> = ['24h', '7d', '30d', 'all'];

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-white">Trading Performance</h2>
        {onTimeframeChange && (
          <div className="flex gap-1 bg-gray-700 rounded-lg p-1">
            {timeframes.map((tf) => (
              <button
                key={tf}
                onClick={() => onTimeframeChange(tf)}
                className={`px-3 py-1 rounded text-sm transition-colors ${
                  timeframe === tf
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {tf.toUpperCase()}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <div className="bg-gray-700/50 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
            <Activity className="w-4 h-4" />
            Total Trades
          </div>
          <p className="text-2xl font-bold text-white">{stats.totalTrades}</p>
        </div>

        <div className="bg-gray-700/50 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
            <Target className="w-4 h-4" />
            Win Rate
          </div>
          <p className={`text-2xl font-bold ${
            stats.winRate >= 50 ? 'text-green-400' : 'text-red-400'
          }`}>
            {stats.winRate.toFixed(1)}%
          </p>
        </div>

        <div className="bg-gray-700/50 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
            <DollarSign className="w-4 h-4" />
            Total P&L
          </div>
          <p className={`text-2xl font-bold ${
            stats.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {formatUsd(stats.totalPnl)}
          </p>
        </div>

        <div className="bg-gray-700/50 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
            <Percent className="w-4 h-4" />
            Avg P&L
          </div>
          <p className={`text-2xl font-bold ${
            stats.avgPnl >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {formatUsd(stats.avgPnl)}
          </p>
        </div>

        <div className="bg-gray-700/50 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
            <Activity className="w-4 h-4" />
            Open Positions
          </div>
          <p className="text-2xl font-bold text-blue-400">{stats.openPositions}</p>
        </div>
      </div>

      {/* Strategy Breakdown */}
      <div className="mb-6">
        <h3 className="text-lg font-medium text-white mb-3">Strategy Performance</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-gray-400 text-sm border-b border-gray-700">
                <th className="text-left py-2 px-3">Strategy</th>
                <th className="text-right py-2 px-3">Trades</th>
                <th className="text-right py-2 px-3">Win Rate</th>
                <th className="text-right py-2 px-3">Total P&L</th>
                <th className="text-right py-2 px-3">Avg P&L</th>
                <th className="text-right py-2 px-3">Max DD</th>
                <th className="text-right py-2 px-3">Sharpe</th>
              </tr>
            </thead>
            <tbody>
              {strategies.map((strategy) => (
                <tr key={strategy.name} className="border-b border-gray-700/50">
                  <td className="py-3 px-3 text-white font-medium">{strategy.name}</td>
                  <td className="py-3 px-3 text-right text-gray-300">{strategy.totalTrades}</td>
                  <td className={`py-3 px-3 text-right ${
                    strategy.winRate >= 50 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {strategy.winRate.toFixed(1)}%
                  </td>
                  <td className={`py-3 px-3 text-right ${
                    strategy.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {formatUsd(strategy.totalPnl)}
                  </td>
                  <td className={`py-3 px-3 text-right ${
                    strategy.avgPnl >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {formatUsd(strategy.avgPnl)}
                  </td>
                  <td className="py-3 px-3 text-right text-red-400">
                    -{strategy.maxDrawdown.toFixed(1)}%
                  </td>
                  <td className={`py-3 px-3 text-right ${
                    strategy.sharpeRatio >= 1 ? 'text-green-400' : 'text-yellow-400'
                  }`}>
                    {strategy.sharpeRatio.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent Trades */}
      <div>
        <h3 className="text-lg font-medium text-white mb-3">Recent Trades</h3>
        <div className="space-y-2">
          {trades.slice(0, 5).map((trade) => (
            <div
              key={trade.id}
              className="flex items-center justify-between bg-gray-700/30 rounded-lg p-3"
            >
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded ${
                  trade.side === 'buy' ? 'bg-green-500/20' : 'bg-red-500/20'
                }`}>
                  {trade.side === 'buy' ? (
                    <TrendingUp className="w-4 h-4 text-green-400" />
                  ) : (
                    <TrendingDown className="w-4 h-4 text-red-400" />
                  )}
                </div>
                <div>
                  <p className="text-white font-medium">
                    {trade.token} <span className="text-gray-400 text-sm">({trade.strategy})</span>
                  </p>
                  <p className="text-gray-400 text-sm">
                    {new Date(trade.timestamp).toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className={`font-medium ${
                  trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {formatUsd(trade.pnl)}
                </p>
                <p className={`text-sm ${
                  trade.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {formatPercent(trade.pnlPercent)}
                </p>
              </div>
            </div>
          ))}

          {trades.length === 0 && (
            <div className="text-center py-8 text-gray-400">
              No trades recorded
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TradingPerformance;
