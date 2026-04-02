/**
 * Pool Stats Component
 *
 * Displays global staking pool statistics:
 * - Total value locked
 * - Number of stakers
 * - Current APY
 * - Reward pool balance
 */

import React from 'react';

export default function PoolStats({ stats }) {
  const {
    totalStaked = 0,
    stakerCount = 0,
    rewardRate = 0,
    apy = 0,
    rewardsPoolBalance = 0,
  } = stats || {};

  // Format large numbers
  const formatNumber = (num) => {
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K';
    return num.toLocaleString();
  };

  return (
    <div className="bg-gray-800 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-purple-600 rounded-lg">
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <div>
          <h3 className="text-lg font-semibold text-white">Pool Statistics</h3>
          <p className="text-sm text-gray-400">Global staking metrics</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Total Staked */}
        <StatCard
          label="Total Staked"
          value={`${formatNumber(totalStaked / 1e9)}`}
          suffix="KR8TIV"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          color="blue"
        />

        {/* Staker Count */}
        <StatCard
          label="Active Stakers"
          value={formatNumber(stakerCount)}
          suffix="users"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          }
          color="purple"
        />

        {/* Current APY */}
        <StatCard
          label="Current APY"
          value={`${(apy * 100).toFixed(1)}`}
          suffix="%"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          }
          color="green"
        />

        {/* Rewards Pool */}
        <StatCard
          label="Rewards Pool"
          value={(rewardsPoolBalance / 1e9).toFixed(2)}
          suffix="SOL"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          }
          color="yellow"
        />
      </div>

      {/* APY Tiers */}
      <div className="mt-6 pt-6 border-t border-gray-700">
        <h4 className="text-sm font-semibold text-gray-400 mb-4">APY by Multiplier Tier</h4>
        <div className="grid grid-cols-4 gap-2">
          <APYTier multiplier="1.0x" apy={apy * 100} />
          <APYTier multiplier="1.5x" apy={apy * 100 * 1.5} />
          <APYTier multiplier="2.0x" apy={apy * 100 * 2.0} />
          <APYTier multiplier="2.5x" apy={apy * 100 * 2.5} highlight />
        </div>
      </div>

      {/* Additional Info */}
      <div className="mt-6 pt-6 border-t border-gray-700 grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="text-gray-400">Reward Distribution</div>
          <div className="text-white">Weekly (Sundays)</div>
        </div>
        <div>
          <div className="text-gray-400">Cooldown Period</div>
          <div className="text-white">3 Days</div>
        </div>
        <div>
          <div className="text-gray-400">Min Stake</div>
          <div className="text-white">100 KR8TIV</div>
        </div>
        <div>
          <div className="text-gray-400">Max Multiplier</div>
          <div className="text-white">2.5x (90 days)</div>
        </div>
      </div>
    </div>
  );
}

// Individual stat card component
function StatCard({ label, value, suffix, icon, color }) {
  const colorClasses = {
    blue: 'text-blue-400',
    purple: 'text-purple-400',
    green: 'text-green-400',
    yellow: 'text-yellow-400',
  };

  return (
    <div className="bg-gray-700/50 rounded-lg p-4">
      <div className={`${colorClasses[color]} mb-2`}>
        {icon}
      </div>
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className="flex items-baseline gap-1">
        <span className="text-xl font-bold text-white">{value}</span>
        <span className="text-xs text-gray-400">{suffix}</span>
      </div>
    </div>
  );
}

// APY tier indicator
function APYTier({ multiplier, apy, highlight }) {
  return (
    <div className={`text-center p-2 rounded-lg ${
      highlight
        ? 'bg-green-900/50 border border-green-700'
        : 'bg-gray-700/50'
    }`}>
      <div className="text-xs text-gray-400 mb-1">{multiplier}</div>
      <div className={`font-bold ${highlight ? 'text-green-400' : 'text-white'}`}>
        {apy.toFixed(1)}%
      </div>
    </div>
  );
}
