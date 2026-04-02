/**
 * Credit Dashboard Component
 *
 * Main dashboard for API credit system:
 * - Current credit balance
 * - Purchase options
 * - Usage history
 * - Tier benefits
 */

import React, { useState, useEffect } from 'react';
import CreditPackages from './CreditPackages';
import UsageHistory from './UsageHistory';
import PointsRewards from './PointsRewards';

const API_BASE = '/api/credits';

export default function CreditDashboard({ userId }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [balance, setBalance] = useState({
    credits: 0,
    points: 0,
    tier: 'free',
  });
  const [activeTab, setActiveTab] = useState('buy');

  // Fetch user balance
  const fetchBalance = async () => {
    try {
      const response = await fetch(`${API_BASE}/balance/${userId}`);
      if (response.ok) {
        const data = await response.json();
        setBalance(data);
      }
    } catch (err) {
      console.error('Failed to fetch balance:', err);
      setError('Failed to load balance');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (userId) {
      fetchBalance();
    }
  }, [userId]);

  const handlePurchaseComplete = () => {
    fetchBalance();
    setActiveTab('history');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-white">API Credits</h1>
          <p className="text-gray-400 mt-1">
            Purchase credits to access premium trading features
          </p>
        </div>
        <TierBadge tier={balance.tier} />
      </div>

      {/* Balance Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Credit Balance */}
        <div className="bg-gradient-to-br from-blue-900/50 to-purple-900/50 rounded-xl p-6 border border-blue-700/50">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-blue-600 rounded-lg">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span className="text-gray-400">Credits</span>
          </div>
          <div className="text-4xl font-bold text-white">
            {balance.credits.toLocaleString()}
          </div>
          <div className="text-sm text-gray-400 mt-1">
            ~{Math.floor(balance.credits / 5)} trades remaining
          </div>
        </div>

        {/* Points Balance */}
        <div className="bg-gradient-to-br from-yellow-900/50 to-orange-900/50 rounded-xl p-6 border border-yellow-700/50">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-yellow-600 rounded-lg">
              <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
            </div>
            <span className="text-gray-400">Points</span>
          </div>
          <div className="text-4xl font-bold text-white">
            {balance.points.toLocaleString()}
          </div>
          <div className="text-sm text-gray-400 mt-1">
            Earn points with every trade
          </div>
        </div>

        {/* Current Tier */}
        <div className="bg-gradient-to-br from-green-900/50 to-teal-900/50 rounded-xl p-6 border border-green-700/50">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-green-600 rounded-lg">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
              </svg>
            </div>
            <span className="text-gray-400">Tier</span>
          </div>
          <div className="text-2xl font-bold text-white capitalize">
            {balance.tier}
          </div>
          <div className="text-sm text-gray-400 mt-1">
            {getTierBenefits(balance.tier)}
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="bg-gray-800 rounded-xl overflow-hidden">
        <div className="flex border-b border-gray-700">
          <TabButton
            active={activeTab === 'buy'}
            onClick={() => setActiveTab('buy')}
            icon={
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            }
          >
            Buy Credits
          </TabButton>
          <TabButton
            active={activeTab === 'history'}
            onClick={() => setActiveTab('history')}
            icon={
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            }
          >
            Usage History
          </TabButton>
          <TabButton
            active={activeTab === 'rewards'}
            onClick={() => setActiveTab('rewards')}
            icon={
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
            }
          >
            Points & Rewards
          </TabButton>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === 'buy' && (
            <CreditPackages
              userId={userId}
              currentTier={balance.tier}
              onPurchaseComplete={handlePurchaseComplete}
            />
          )}
          {activeTab === 'history' && (
            <UsageHistory userId={userId} />
          )}
          {activeTab === 'rewards' && (
            <PointsRewards
              userId={userId}
              points={balance.points}
              tier={balance.tier}
            />
          )}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="fixed bottom-4 right-4 bg-red-900 text-red-100 px-6 py-3 rounded-lg shadow-lg">
          {error}
          <button onClick={() => setError(null)} className="ml-4 text-red-300 hover:text-white">
            ×
          </button>
        </div>
      )}
    </div>
  );
}

// Tab button component
function TabButton({ children, active, onClick, icon }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 py-4 flex items-center justify-center gap-2 font-medium transition-colors ${
        active
          ? 'text-blue-400 border-b-2 border-blue-400 bg-gray-700/50'
          : 'text-gray-400 hover:text-white'
      }`}
    >
      {icon}
      {children}
    </button>
  );
}

// Tier badge component
function TierBadge({ tier }) {
  const tierColors = {
    free: 'bg-gray-600 text-gray-200',
    starter: 'bg-blue-600 text-blue-100',
    pro: 'bg-purple-600 text-purple-100',
    whale: 'bg-yellow-600 text-yellow-100',
  };

  return (
    <span className={`px-4 py-2 rounded-full text-sm font-bold uppercase ${tierColors[tier] || tierColors.free}`}>
      {tier} Tier
    </span>
  );
}

// Get tier benefits text
function getTierBenefits(tier) {
  const benefits = {
    free: '5 free trades/day',
    starter: '10% bonus credits',
    pro: '20% bonus + priority',
    whale: '30% bonus + VIP access',
  };
  return benefits[tier] || benefits.free;
}
