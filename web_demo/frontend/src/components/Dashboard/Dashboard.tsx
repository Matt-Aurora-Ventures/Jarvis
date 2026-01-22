/**
 * Main Dashboard Component - Beautiful jarvislife.io Design
 * Central hub for all trading activities
 */
import React, { useEffect, useState } from 'react';
import { useWallet } from '@solana/wallet-adapter-react';
import {
  Activity,
  TrendingUp,
  Wallet,
  AlertCircle,
  Sparkles,
  Zap,
  BarChart3,
} from 'lucide-react';
import { GlassCard, GlassCardHeader, GlassCardTitle, GlassCardBody } from '../UI/GlassCard';
import { MarketRegime } from '../Sentiment/MarketRegime';
import { QuickActions } from '../Trading/QuickActions';
import { PositionsList } from '../Positions/PositionsList';
import { PortfolioOverview } from '../Portfolio/PortfolioOverview';
import clsx from 'clsx';

interface DashboardData {
  balance: {
    sol: number;
    usd: number;
  };
  positions: {
    count: number;
    totalPnL: number;
    winRate: number;
  };
  marketRegime: {
    regime: string;
    riskLevel: string;
    btcChange: number;
    solChange: number;
  };
}

export const Dashboard: React.FC = () => {
  const { publicKey, connected } = useWallet();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (connected && publicKey) {
      fetchDashboardData();
    }
  }, [connected, publicKey]);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch dashboard data from API
      const response = await fetch('/api/dashboard', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch dashboard data');
      }

      const dashboardData = await response.json();
      setData(dashboardData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  if (!connected) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <GlassCard className="max-w-md w-full text-center">
          <div className="mb-6">
            <Wallet className="w-16 h-16 text-accent mx-auto mb-4 animate-pulse" />
            <h2 className="text-2xl font-display font-semibold mb-2">
              Connect Your Wallet
            </h2>
            <p className="text-muted">
              Connect your Solana wallet to start trading with AI-powered insights
            </p>
          </div>

          <div className="flex items-center gap-2 p-3 bg-surface rounded-lg text-sm">
            <AlertCircle size={16} className="text-info flex-shrink-0" />
            <p className="text-muted text-left">
              Your private keys never leave your wallet. All transactions are signed
              locally and verified server-side.
            </p>
          </div>
        </GlassCard>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin text-accent text-4xl mb-4">⏳</div>
          <p className="text-muted">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <GlassCard className="max-w-md w-full">
          <div className="text-center">
            <AlertCircle className="w-12 h-12 text-error mx-auto mb-4" />
            <h3 className="text-xl font-semibold mb-2">Error Loading Dashboard</h3>
            <p className="text-muted mb-4">{error}</p>
            <button
              onClick={fetchDashboardData}
              className="btn btn-primary"
            >
              Retry
            </button>
          </div>
        </GlassCard>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6">
      {/* Header */}
      <div className="mb-8 fade-in">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-4xl font-display font-bold glow-text mb-2">
              JARVIS Trading
            </h1>
            <p className="text-muted">
              AI-Powered Solana Trading Dashboard
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button className="btn btn-ghost">
              <Activity size={18} />
              <span>Activity</span>
            </button>
            <button className="btn btn-secondary">
              <BarChart3 size={18} />
              <span>Analytics</span>
            </button>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Balance Card */}
          <GlassCard className="hover:shadow-glow transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted mb-1">Total Balance</p>
                <p className="text-2xl font-bold text-accent">
                  ◎ {data?.balance.sol.toFixed(4)}
                </p>
                <p className="text-sm text-muted">
                  ${data?.balance.usd.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </p>
              </div>
              <Wallet className="w-12 h-12 text-accent opacity-30" />
            </div>
          </GlassCard>

          {/* Positions Card */}
          <GlassCard className="hover:shadow-glow transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted mb-1">Open Positions</p>
                <p className="text-2xl font-bold">{data?.positions.count}</p>
                <p className="text-sm">
                  <span className="text-muted">Win Rate: </span>
                  <span className={clsx(
                    'font-semibold',
                    (data?.positions.winRate || 0) >= 60 ? 'text-success' : 'text-warning'
                  )}>
                    {data?.positions.winRate.toFixed(0)}%
                  </span>
                </p>
              </div>
              <Activity className="w-12 h-12 text-accent opacity-30" />
            </div>
          </GlassCard>

          {/* P&L Card */}
          <GlassCard className={clsx(
            'hover:shadow-glow transition-all',
            (data?.positions.totalPnL || 0) >= 0 ? 'border-success/30' : 'border-error/30'
          )}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted mb-1">Total P&L</p>
                <p className={clsx(
                  'text-2xl font-bold',
                  (data?.positions.totalPnL || 0) >= 0 ? 'text-success' : 'text-error'
                )}>
                  {(data?.positions.totalPnL || 0) >= 0 ? '+' : ''}
                  ${Math.abs(data?.positions.totalPnL || 0).toFixed(2)}
                </p>
                <p className="text-sm text-muted">
                  {(data?.positions.totalPnL || 0) >= 0 ? 'Profit' : 'Loss'}
                </p>
              </div>
              <TrendingUp className={clsx(
                'w-12 h-12 opacity-30',
                (data?.positions.totalPnL || 0) >= 0 ? 'text-success' : 'text-error'
              )} />
            </div>
          </GlassCard>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - 2/3 width */}
        <div className="lg:col-span-2 space-y-6">
          {/* Market Regime */}
          <div className="fade-in" style={{ animationDelay: '0.1s' }}>
            <MarketRegime
              regime={data?.marketRegime.regime || 'NEUTRAL'}
              riskLevel={data?.marketRegime.riskLevel || 'NORMAL'}
              btcChange={data?.marketRegime.btcChange || 0}
              solChange={data?.marketRegime.solChange || 0}
            />
          </div>

          {/* Quick Actions */}
          <div className="fade-in" style={{ animationDelay: '0.2s' }}>
            <GlassCard>
              <GlassCardHeader>
                <GlassCardTitle icon={<Zap size={20} />}>
                  Quick Actions
                </GlassCardTitle>
              </GlassCardHeader>
              <GlassCardBody>
                <QuickActions />
              </GlassCardBody>
            </GlassCard>
          </div>

          {/* Positions List */}
          <div className="fade-in" style={{ animationDelay: '0.3s' }}>
            <PositionsList />
          </div>
        </div>

        {/* Right Column - 1/3 width */}
        <div className="space-y-6">
          {/* Portfolio Overview */}
          <div className="fade-in" style={{ animationDelay: '0.4s' }}>
            <PortfolioOverview />
          </div>

          {/* AI Insights */}
          <div className="fade-in" style={{ animationDelay: '0.5s' }}>
            <GlassCard glow>
              <GlassCardHeader>
                <GlassCardTitle icon={<Sparkles size={20} />}>
                  AI Insights
                </GlassCardTitle>
              </GlassCardHeader>
              <GlassCardBody>
                <div className="space-y-3">
                  <div className="p-3 bg-surface rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="badge badge-success">High Confidence</span>
                      <span className="text-sm text-muted">2h ago</span>
                    </div>
                    <p className="text-sm">
                      Market regime shifted to BULLISH. Consider increasing position
                      sizes for high-conviction tokens.
                    </p>
                  </div>

                  <div className="p-3 bg-surface rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="badge badge-warning">Medium Confidence</span>
                      <span className="text-sm text-muted">5h ago</span>
                    </div>
                    <p className="text-sm">
                      Detected momentum keywords in 3 trending tokens. Review AI Picks
                      for opportunities.
                    </p>
                  </div>

                  <div className="p-3 bg-surface rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="badge badge-info">Risk Alert</span>
                      <span className="text-sm text-muted">1d ago</span>
                    </div>
                    <p className="text-sm">
                      Position concentration above 20% in single token. Consider
                      diversification.
                    </p>
                  </div>
                </div>

                <button className="btn btn-ghost w-full mt-4">
                  View All Insights
                </button>
              </GlassCardBody>
            </GlassCard>
          </div>
        </div>
      </div>
    </div>
  );
};
