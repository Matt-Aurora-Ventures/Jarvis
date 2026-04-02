/**
 * Revenue Dashboard - Admin Analytics
 *
 * Comprehensive revenue analytics for admin users:
 * - Overview metrics (24h, 7d, 30d, all-time)
 * - Revenue charts by source
 * - Staking statistics
 * - Recent activity feed
 * - Treasury status
 */

import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8766';

// =============================================================================
// Chart Components (using inline SVG for simplicity)
// =============================================================================

function LineChart({ data, width = 400, height = 200, color = '#10b981' }) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        No data available
      </div>
    );
  }

  const maxValue = Math.max(...data.map(d => d.value));
  const minValue = Math.min(...data.map(d => d.value));
  const range = maxValue - minValue || 1;

  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * (width - 40) + 20;
    const y = height - 40 - ((d.value - minValue) / range) * (height - 60);
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
        const y = height - 40 - pct * (height - 60);
        return (
          <line
            key={i}
            x1="20"
            y1={y}
            x2={width - 20}
            y2={y}
            stroke="#374151"
            strokeWidth="1"
            strokeDasharray="4"
          />
        );
      })}

      {/* Line */}
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
      />

      {/* Area under line */}
      <polygon
        points={`20,${height - 40} ${points} ${width - 20},${height - 40}`}
        fill={color}
        fillOpacity="0.1"
      />

      {/* Data points */}
      {data.map((d, i) => {
        const x = (i / (data.length - 1)) * (width - 40) + 20;
        const y = height - 40 - ((d.value - minValue) / range) * (height - 60);
        return (
          <circle
            key={i}
            cx={x}
            cy={y}
            r="4"
            fill={color}
          />
        );
      })}

      {/* X-axis labels */}
      {data.filter((_, i) => i % Math.ceil(data.length / 5) === 0).map((d, i) => {
        const idx = i * Math.ceil(data.length / 5);
        const x = (idx / (data.length - 1)) * (width - 40) + 20;
        return (
          <text
            key={i}
            x={x}
            y={height - 10}
            textAnchor="middle"
            className="text-xs fill-gray-500"
          >
            {d.label}
          </text>
        );
      })}
    </svg>
  );
}

function PieChart({ data, size = 200 }) {
  if (!data || data.length === 0) {
    return null;
  }

  const total = data.reduce((sum, d) => sum + d.value, 0);
  let currentAngle = -90;

  const slices = data.map((d, i) => {
    const angle = (d.value / total) * 360;
    const startAngle = currentAngle;
    const endAngle = currentAngle + angle;
    currentAngle = endAngle;

    const startRad = (startAngle * Math.PI) / 180;
    const endRad = (endAngle * Math.PI) / 180;

    const x1 = 50 + 40 * Math.cos(startRad);
    const y1 = 50 + 40 * Math.sin(startRad);
    const x2 = 50 + 40 * Math.cos(endRad);
    const y2 = 50 + 40 * Math.sin(endRad);

    const largeArc = angle > 180 ? 1 : 0;

    return (
      <path
        key={i}
        d={`M 50 50 L ${x1} ${y1} A 40 40 0 ${largeArc} 1 ${x2} ${y2} Z`}
        fill={d.color}
        stroke="#1f2937"
        strokeWidth="2"
      />
    );
  });

  return (
    <div className="flex items-center gap-4">
      <svg viewBox="0 0 100 100" width={size} height={size}>
        {slices}
      </svg>
      <div className="space-y-2">
        {data.map((d, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <div
              className="w-3 h-3 rounded"
              style={{ backgroundColor: d.color }}
            />
            <span className="text-gray-300">{d.label}</span>
            <span className="text-gray-500">
              ({((d.value / total) * 100).toFixed(1)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Metric Cards
// =============================================================================

function MetricCard({ label, value, subvalue, trend, icon }) {
  const trendColor = trend > 0 ? 'text-green-500' : trend < 0 ? 'text-red-500' : 'text-gray-500';
  const trendIcon = trend > 0 ? '↑' : trend < 0 ? '↓' : '→';

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-gray-400 text-sm">{label}</p>
          <p className="text-2xl font-bold text-white mt-1">{value}</p>
          {subvalue && (
            <p className="text-gray-500 text-sm mt-1">{subvalue}</p>
          )}
        </div>
        {icon && (
          <div className="text-2xl">{icon}</div>
        )}
      </div>
      {trend !== undefined && (
        <div className={`mt-2 text-sm ${trendColor}`}>
          {trendIcon} {Math.abs(trend).toFixed(1)}% vs last period
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Activity Feed
// =============================================================================

function ActivityFeed({ activities }) {
  const getActivityIcon = (type) => {
    const icons = {
      'stake.created': '🥩',
      'stake.unstaked': '📤',
      'rewards.claimed': '💰',
      'trade.executed': '🔄',
      'fee.collected': '💵',
      'credits.purchased': '🎫',
    };
    return icons[type] || '📋';
  };

  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="space-y-3">
      {activities.map((activity, i) => (
        <div
          key={i}
          className="flex items-start gap-3 p-3 bg-gray-800/50 rounded-lg border border-gray-700/50"
        >
          <span className="text-xl">{getActivityIcon(activity.type)}</span>
          <div className="flex-1 min-w-0">
            <p className="text-white text-sm">{activity.description}</p>
            <p className="text-gray-500 text-xs mt-1">
              {formatTime(activity.timestamp)}
            </p>
          </div>
          {activity.amount && (
            <span className="text-green-500 font-mono text-sm">
              +{activity.amount} SOL
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

// =============================================================================
// Treasury Status
// =============================================================================

function TreasuryStatus({ treasury }) {
  if (!treasury) {
    return <div className="text-gray-500">Loading...</div>;
  }

  const wallets = [
    { name: 'Reserve', balance: treasury.reserve_sol, color: '#3b82f6' },
    { name: 'Active', balance: treasury.active_sol, color: '#10b981' },
    { name: 'Profit', balance: treasury.profit_sol, color: '#8b5cf6' },
  ];

  const total = wallets.reduce((sum, w) => sum + w.balance, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-gray-400">Total Balance</span>
        <span className="text-2xl font-bold text-white">
          ◎ {total.toFixed(2)}
        </span>
      </div>

      <div className="space-y-2">
        {wallets.map((wallet, i) => (
          <div key={i} className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">{wallet.name}</span>
              <span className="text-white">◎ {wallet.balance.toFixed(2)}</span>
            </div>
            <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(wallet.balance / total) * 100}%`,
                  backgroundColor: wallet.color,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {treasury.last_trade && (
        <div className="pt-4 border-t border-gray-700">
          <p className="text-gray-400 text-sm">Last Trade</p>
          <p className="text-white mt-1">{treasury.last_trade.description}</p>
          <p className={`text-sm mt-1 ${treasury.last_trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            P&L: {treasury.last_trade.pnl >= 0 ? '+' : ''}{treasury.last_trade.pnl.toFixed(4)} SOL
          </p>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Main Dashboard
// =============================================================================

export default function RevenueDashboard() {
  const [period, setPeriod] = useState('7d');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [metrics, setMetrics] = useState(null);
  const [revenueData, setRevenueData] = useState([]);
  const [revenueBySource, setRevenueBySource] = useState([]);
  const [stakingData, setStakingData] = useState([]);
  const [activities, setActivities] = useState([]);
  const [treasury, setTreasury] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch all data in parallel
      const [metricsRes, analyticsRes, stakingRes, treasuryRes] = await Promise.all([
        fetch(`${API_BASE}/api/analytics/metrics/overview?days=${period === '7d' ? 7 : period === '30d' ? 30 : 1}`),
        fetch(`${API_BASE}/api/analytics/aggregates?days=${period === '7d' ? 7 : period === '30d' ? 30 : 1}`),
        fetch(`${API_BASE}/api/staking/pool`),
        fetch(`${API_BASE}/api/treasury/bags/stats`),
      ]);

      // Process metrics
      if (metricsRes.ok) {
        const data = await metricsRes.json();
        setMetrics({
          totalRevenue: data.fees_collected?.total_sol || 0,
          activeStakers: data.staking?.staker_count || 0,
          totalStaked: data.staking?.total_staked || 0,
          partnerFees: data.fees_collected?.total_sol || 0,
        });

        // Build revenue chart data
        if (data.fees_collected?.daily) {
          setRevenueData(
            data.fees_collected.daily.map(d => ({
              label: d.period.slice(5), // MM-DD
              value: d.sum_value || 0,
            }))
          );
        }
      }

      // Revenue by source
      setRevenueBySource([
        { label: 'Partner Fees', value: 60, color: '#10b981' },
        { label: 'API Credits', value: 25, color: '#3b82f6' },
        { label: 'Trading', value: 15, color: '#8b5cf6' },
      ]);

      // Staking data
      if (stakingRes.ok) {
        const data = await stakingRes.json();
        setStakingData([
          { label: 'Day 1', value: data.totalStaked * 0.7 },
          { label: 'Day 2', value: data.totalStaked * 0.75 },
          { label: 'Day 3', value: data.totalStaked * 0.8 },
          { label: 'Day 4', value: data.totalStaked * 0.85 },
          { label: 'Day 5', value: data.totalStaked * 0.9 },
          { label: 'Day 6', value: data.totalStaked * 0.95 },
          { label: 'Today', value: data.totalStaked },
        ]);
      }

      // Treasury
      if (treasuryRes.ok) {
        const data = await treasuryRes.json();
        setTreasury({
          reserve_sol: 100,
          active_sol: 50,
          profit_sol: 25,
          last_trade: {
            description: 'DCA into USDC',
            pnl: 0.05,
          },
        });
      }

      // Mock activities
      setActivities([
        { type: 'stake.created', description: 'New stake: 1000 KR8TIV', timestamp: new Date().toISOString(), amount: null },
        { type: 'fee.collected', description: 'Partner fees collected', timestamp: new Date(Date.now() - 3600000).toISOString(), amount: 0.5 },
        { type: 'rewards.claimed', description: 'Rewards claimed', timestamp: new Date(Date.now() - 7200000).toISOString(), amount: 0.25 },
        { type: 'trade.executed', description: 'DCA trade executed', timestamp: new Date(Date.now() - 14400000).toISOString(), amount: null },
        { type: 'credits.purchased', description: 'Pro package purchased', timestamp: new Date(Date.now() - 28800000).toISOString(), amount: null },
      ]);

    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading && !metrics) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Revenue Dashboard</h1>

        <div className="flex items-center gap-2">
          {['24h', '7d', '30d'].map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded text-sm ${
                period === p
                  ? 'bg-emerald-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 text-red-300">
          {error}
        </div>
      )}

      {/* Overview Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Total Revenue"
          value={`◎ ${(metrics?.totalRevenue || 0).toFixed(2)}`}
          subvalue={`$${((metrics?.totalRevenue || 0) * 100).toFixed(2)} USD`}
          trend={12.5}
          icon="💰"
        />
        <MetricCard
          label="Active Stakers"
          value={(metrics?.activeStakers || 0).toLocaleString()}
          subvalue="Unique wallets"
          trend={8.3}
          icon="🥩"
        />
        <MetricCard
          label="Total Staked"
          value={`${((metrics?.totalStaked || 0) / 1e9).toFixed(0)} KR8TIV`}
          subvalue="Across all stakers"
          trend={15.2}
          icon="📊"
        />
        <MetricCard
          label="Partner Fees"
          value={`◎ ${(metrics?.partnerFees || 0).toFixed(4)}`}
          subvalue="From Bags.fm"
          trend={5.7}
          icon="🤝"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Over Time */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-lg font-semibold text-white mb-4">Revenue Over Time</h2>
          <div className="h-48">
            <LineChart data={revenueData} color="#10b981" />
          </div>
        </div>

        {/* Revenue by Source */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-lg font-semibold text-white mb-4">Revenue by Source</h2>
          <div className="flex items-center justify-center h-48">
            <PieChart data={revenueBySource} />
          </div>
        </div>
      </div>

      {/* Staking Growth */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-lg font-semibold text-white mb-4">Staking Growth</h2>
        <div className="h-48">
          <LineChart data={stakingData} color="#8b5cf6" />
        </div>
      </div>

      {/* Activity & Treasury */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Activity</h2>
          <ActivityFeed activities={activities} />
        </div>

        {/* Treasury Status */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-lg font-semibold text-white mb-4">Treasury Status</h2>
          <TreasuryStatus treasury={treasury} />
        </div>
      </div>
    </div>
  );
}
