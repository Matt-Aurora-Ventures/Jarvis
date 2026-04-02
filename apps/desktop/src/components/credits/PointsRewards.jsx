/**
 * Points & Rewards Component
 *
 * Shows points balance and rewards:
 * - Points accumulation
 * - Tier progress
 * - Redemption options
 * - Referral program
 */

import React, { useState, useEffect } from 'react';

const API_BASE = '/api/credits';

// Tier definitions
const TIERS = [
  { id: 'free', name: 'Free', minPoints: 0, benefits: ['5 free trades/day', 'Basic signals'] },
  { id: 'starter', name: 'Starter', minPoints: 1000, benefits: ['10% bonus credits', 'Priority signals', 'Email support'] },
  { id: 'pro', name: 'Pro', minPoints: 5000, benefits: ['20% bonus credits', 'Advanced analytics', 'Priority support'] },
  { id: 'whale', name: 'Whale', minPoints: 25000, benefits: ['30% bonus credits', 'VIP access', 'Dedicated support', 'Early features'] },
];

// Reward options
const REWARDS = [
  { id: 'credits_100', name: '100 Credits', cost: 500, icon: '💳' },
  { id: 'credits_500', name: '500 Credits', cost: 2000, icon: '💳' },
  { id: 'priority_week', name: 'Priority Access (1 Week)', cost: 1000, icon: '⚡' },
  { id: 'exclusive_signals', name: 'Exclusive Signals (1 Month)', cost: 3000, icon: '📊' },
];

export default function PointsRewards({ userId, points, tier }) {
  const [loading, setLoading] = useState(false);
  const [referralCode, setReferralCode] = useState(null);
  const [referralStats, setReferralStats] = useState({ count: 0, earned: 0 });
  const [redeemLoading, setRedeemLoading] = useState(null);
  const [message, setMessage] = useState(null);

  // Fetch referral info
  useEffect(() => {
    const fetchReferralInfo = async () => {
      try {
        const response = await fetch(`${API_BASE}/referral/${userId}`);
        if (response.ok) {
          const data = await response.json();
          setReferralCode(data.code);
          setReferralStats(data.stats || { count: 0, earned: 0 });
        }
      } catch (err) {
        console.error('Failed to fetch referral info:', err);
      }
    };

    if (userId) {
      fetchReferralInfo();
    }
  }, [userId]);

  // Find current and next tier
  const currentTierIndex = TIERS.findIndex((t) => t.id === tier);
  const currentTierDef = TIERS[currentTierIndex] || TIERS[0];
  const nextTier = TIERS[currentTierIndex + 1] || null;

  // Calculate progress to next tier
  const progressToNext = nextTier
    ? ((points - currentTierDef.minPoints) / (nextTier.minPoints - currentTierDef.minPoints)) * 100
    : 100;

  const handleRedeem = async (reward) => {
    if (points < reward.cost) {
      setMessage({ type: 'error', text: 'Not enough points' });
      return;
    }

    setRedeemLoading(reward.id);
    try {
      const response = await fetch(`${API_BASE}/redeem`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          reward_id: reward.id,
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || 'Failed to redeem');
      }

      setMessage({ type: 'success', text: `Successfully redeemed ${reward.name}!` });
      // Note: Parent component should refresh balance
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setRedeemLoading(null);
    }
  };

  const copyReferralLink = () => {
    const link = `${window.location.origin}/signup?ref=${referralCode}`;
    navigator.clipboard.writeText(link);
    setMessage({ type: 'success', text: 'Referral link copied!' });
    setTimeout(() => setMessage(null), 3000);
  };

  return (
    <div className="space-y-8">
      {/* Points Overview */}
      <div className="bg-gradient-to-r from-yellow-900/50 to-orange-900/50 rounded-xl p-6 border border-yellow-700/50">
        <div className="flex items-center gap-4 mb-6">
          <div className="p-3 bg-yellow-600 rounded-xl">
            <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
          </div>
          <div>
            <div className="text-gray-400 text-sm">Your Points</div>
            <div className="text-4xl font-bold text-white">{points.toLocaleString()}</div>
          </div>
        </div>

        {/* Tier Progress */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-300">{currentTierDef.name}</span>
            {nextTier && <span className="text-gray-400">{nextTier.name}</span>}
          </div>
          <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-yellow-500 to-orange-500 transition-all duration-500"
              style={{ width: `${Math.min(100, progressToNext)}%` }}
            />
          </div>
          {nextTier && (
            <div className="text-sm text-gray-400 text-center">
              {(nextTier.minPoints - points).toLocaleString()} points to {nextTier.name}
            </div>
          )}
        </div>
      </div>

      {/* Tier Benefits */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">Tier Benefits</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {TIERS.map((t) => (
            <TierCard
              key={t.id}
              tier={t}
              isCurrent={t.id === tier}
              isAchieved={points >= t.minPoints}
            />
          ))}
        </div>
      </div>

      {/* Rewards Shop */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">Redeem Points</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {REWARDS.map((reward) => (
            <RewardCard
              key={reward.id}
              reward={reward}
              userPoints={points}
              onRedeem={() => handleRedeem(reward)}
              loading={redeemLoading === reward.id}
            />
          ))}
        </div>
      </div>

      {/* Referral Program */}
      <div className="bg-gray-700/50 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>👥</span> Referral Program
        </h3>
        <p className="text-gray-400 mb-4">
          Invite friends and earn 500 points for each successful signup!
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="text-gray-400 text-sm">Total Referrals</div>
            <div className="text-2xl font-bold text-white">{referralStats.count}</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="text-gray-400 text-sm">Points Earned</div>
            <div className="text-2xl font-bold text-yellow-400">{referralStats.earned.toLocaleString()}</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="text-gray-400 text-sm">Per Referral</div>
            <div className="text-2xl font-bold text-green-400">500 pts</div>
          </div>
        </div>

        {/* Referral Link */}
        <div className="flex gap-2">
          <input
            type="text"
            readOnly
            value={referralCode ? `${window.location.origin}/signup?ref=${referralCode}` : 'Loading...'}
            className="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-4 py-2 text-gray-300"
          />
          <button
            onClick={copyReferralLink}
            disabled={!referralCode}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            Copy
          </button>
        </div>
      </div>

      {/* How to Earn Points */}
      <div className="border border-gray-700 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">How to Earn Points</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <EarnMethod icon="💳" action="Purchase Credits" points="10 pts/$" />
          <EarnMethod icon="⚡" action="Execute Trade" points="5 pts/trade" />
          <EarnMethod icon="👥" action="Refer Friend" points="500 pts/ref" />
          <EarnMethod icon="📅" action="Daily Login" points="10 pts/day" />
        </div>
      </div>

      {/* Message Toast */}
      {message && (
        <div className={`fixed bottom-4 right-4 px-6 py-3 rounded-lg shadow-lg ${
          message.type === 'success' ? 'bg-green-900 text-green-100' : 'bg-red-900 text-red-100'
        }`}>
          {message.text}
          <button
            onClick={() => setMessage(null)}
            className="ml-4 opacity-75 hover:opacity-100"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}

// Tier card component
function TierCard({ tier, isCurrent, isAchieved }) {
  return (
    <div className={`rounded-lg p-4 border ${
      isCurrent
        ? 'bg-blue-900/30 border-blue-500'
        : isAchieved
        ? 'bg-gray-700/50 border-gray-600'
        : 'bg-gray-800/50 border-gray-700 opacity-60'
    }`}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-semibold text-white">{tier.name}</span>
        {isCurrent && (
          <span className="text-xs bg-blue-600 text-white px-2 py-0.5 rounded">Current</span>
        )}
      </div>
      <div className="text-xs text-gray-400 mb-2">
        {tier.minPoints.toLocaleString()} pts
      </div>
      <ul className="text-xs text-gray-300 space-y-1">
        {tier.benefits.slice(0, 2).map((benefit, i) => (
          <li key={i} className="flex items-center gap-1">
            <svg className="w-3 h-3 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            {benefit}
          </li>
        ))}
      </ul>
    </div>
  );
}

// Reward card component
function RewardCard({ reward, userPoints, onRedeem, loading }) {
  const canAfford = userPoints >= reward.cost;

  return (
    <div className={`bg-gray-700/50 rounded-lg p-4 border ${
      canAfford ? 'border-gray-600' : 'border-gray-700 opacity-60'
    }`}>
      <div className="text-3xl mb-2">{reward.icon}</div>
      <div className="font-medium text-white mb-1">{reward.name}</div>
      <div className="text-sm text-yellow-400 mb-3">{reward.cost.toLocaleString()} pts</div>
      <button
        onClick={onRedeem}
        disabled={!canAfford || loading}
        className={`w-full py-2 rounded text-sm font-medium transition-colors ${
          canAfford
            ? 'bg-yellow-600 hover:bg-yellow-500 text-white'
            : 'bg-gray-600 text-gray-400 cursor-not-allowed'
        }`}
      >
        {loading ? 'Redeeming...' : canAfford ? 'Redeem' : 'Not enough'}
      </button>
    </div>
  );
}

// Earn method component
function EarnMethod({ icon, action, points }) {
  return (
    <div className="text-center">
      <div className="text-2xl mb-2">{icon}</div>
      <div className="text-sm text-white mb-1">{action}</div>
      <div className="text-xs text-yellow-400">{points}</div>
    </div>
  );
}
