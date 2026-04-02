/**
 * Portfolio Overview Component - Beautiful Portfolio Analytics
 * Shows wallet holdings, P&L chart, and performance metrics
 */
import React, { useState, useEffect } from 'react';
import { Wallet, TrendingUp, PieChart, Trophy } from 'lucide-react';
import { GlassCard, GlassCardHeader, GlassCardTitle, GlassCardBody } from '../UI/GlassCard';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
} from 'chart.js';
import clsx from 'clsx';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler
);

interface PortfolioData {
  totalValue: number;
  pnl24h: number;
  pnl24hPct: number;
  winRate: number;
  totalTrades: number;
  chart: {
    labels: string[];
    values: number[];
  };
}

export const PortfolioOverview: React.FC = () => {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPortfolioData();
  }, []);

  const fetchPortfolioData = async () => {
    try {
      setLoading(true);

      const response = await fetch('/api/portfolio/overview', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (response.ok) {
        const portfolioData = await response.json();
        setData(portfolioData);
      }
    } catch (error) {
      console.error('Failed to fetch portfolio data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <GlassCard>
        <GlassCardBody>
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin text-2xl">⏳</div>
          </div>
        </GlassCardBody>
      </GlassCard>
    );
  }

  // Chart data
  const chartData = {
    labels: data?.chart.labels || [],
    datasets: [
      {
        label: 'Portfolio Value',
        data: data?.chart.values || [],
        fill: true,
        backgroundColor: (data?.pnl24hPct || 0) >= 0
          ? 'rgba(57, 255, 20, 0.1)'
          : 'rgba(255, 57, 57, 0.1)',
        borderColor: (data?.pnl24hPct || 0) >= 0
          ? '#39FF14'
          : '#FF3939',
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.4,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: 'rgba(11, 12, 13, 0.9)',
        titleColor: '#FFFFFF',
        bodyColor: '#A0A0A0',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderWidth: 1,
        padding: 12,
        displayColors: false,
        callbacks: {
          label: (context: any) => `$${context.parsed.y.toFixed(2)}`,
        },
      },
    },
    scales: {
      x: {
        display: false,
      },
      y: {
        display: false,
      },
    },
    interaction: {
      intersect: false,
      mode: 'index' as const,
    },
  };

  return (
    <div className="space-y-4">
      {/* Portfolio Value Card */}
      <GlassCard>
        <GlassCardHeader>
          <GlassCardTitle icon={<Wallet size={20} />}>
            Portfolio
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardBody>
          <div className="mb-4">
            <p className="text-sm text-muted mb-1">Total Value</p>
            <p className="text-3xl font-bold">
              ${data?.totalValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </p>
          </div>

          {/* 24h Change */}
          <div className="flex items-center gap-2 mb-4">
            {(data?.pnl24hPct || 0) >= 0 ? (
              <TrendingUp className="text-success" size={20} />
            ) : (
              <TrendingUp className="text-error rotate-180" size={20} />
            )}
            <span className={clsx(
              'font-semibold',
              (data?.pnl24hPct || 0) >= 0 ? 'text-success' : 'text-error'
            )}>
              {(data?.pnl24hPct || 0) >= 0 ? '+' : ''}
              {data?.pnl24hPct.toFixed(2)}% (${Math.abs(data?.pnl24h || 0).toFixed(2)})
            </span>
            <span className="text-muted text-sm">24h</span>
          </div>

          {/* Mini Chart */}
          <div className="h-24 mb-2">
            <Line data={chartData} options={chartOptions} />
          </div>

          <button className="btn btn-ghost w-full">
            <PieChart size={16} />
            <span>Detailed Analytics</span>
          </button>
        </GlassCardBody>
      </GlassCard>

      {/* Performance Metrics Card */}
      <GlassCard>
        <GlassCardHeader>
          <GlassCardTitle icon={<Trophy size={20} />}>
            Performance
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardBody>
          <div className="space-y-4">
            {/* Win Rate */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-muted">Win Rate</span>
                <span className={clsx(
                  'font-semibold',
                  (data?.winRate || 0) >= 60 ? 'text-success' : 'text-warning'
                )}>
                  {data?.winRate.toFixed(0)}%
                </span>
              </div>
              <div className="w-full bg-surface rounded-full h-2">
                <div
                  className={clsx(
                    'h-2 rounded-full transition-all',
                    (data?.winRate || 0) >= 60 ? 'bg-success' : 'bg-warning'
                  )}
                  style={{ width: `${data?.winRate || 0}%` }}
                />
              </div>
            </div>

            {/* Total Trades */}
            <div className="flex items-center justify-between p-3 bg-surface rounded-lg">
              <span className="text-sm text-muted">Total Trades</span>
              <span className="font-semibold text-lg">
                {data?.totalTrades}
              </span>
            </div>

            {/* Average P&L */}
            <div className="flex items-center justify-between p-3 bg-surface rounded-lg">
              <span className="text-sm text-muted">Avg. P&L/Trade</span>
              <span className={clsx(
                'font-semibold',
                ((data?.pnl24h || 0) / (data?.totalTrades || 1)) >= 0
                  ? 'text-success'
                  : 'text-error'
              )}>
                ${((data?.pnl24h || 0) / (data?.totalTrades || 1)).toFixed(2)}
              </span>
            </div>
          </div>

          <button className="btn btn-secondary w-full mt-4">
            <TrendingUp size={16} />
            <span>Full Report</span>
          </button>
        </GlassCardBody>
      </GlassCard>
    </div>
  );
};
