/**
 * Staking Dashboard Component
 *
 * Main staking interface for KR8TIV token staking:
 * - View current stake and rewards
 * - Stake/unstake tokens
 * - Claim rewards
 * - Auto-compound settings
 * - Early holder status
 */

import React, { useState, useEffect, useCallback } from 'react';

// =============================================================================
// Sub-components
// =============================================================================

const StakeCard = ({ title, value, subtitle, icon }) => (
  <div className="stake-card">
    <div className="stake-card-icon">{icon}</div>
    <div className="stake-card-content">
      <h3 className="stake-card-title">{title}</h3>
      <p className="stake-card-value">{value}</p>
      {subtitle && <span className="stake-card-subtitle">{subtitle}</span>}
    </div>
  </div>
);

const MultiplierBadge = ({ multiplier, daysStaked }) => {
  const getTierName = (m) => {
    if (m >= 2.5) return 'Diamond';
    if (m >= 2.0) return 'Gold';
    if (m >= 1.5) return 'Silver';
    return 'Bronze';
  };

  const getNextTier = (days) => {
    if (days >= 90) return null;
    if (days >= 30) return { name: 'Diamond', days: 90, multiplier: '2.5x' };
    if (days >= 7) return { name: 'Gold', days: 30, multiplier: '2.0x' };
    return { name: 'Silver', days: 7, multiplier: '1.5x' };
  };

  const next = getNextTier(daysStaked);

  return (
    <div className="multiplier-badge">
      <div className="multiplier-current">
        <span className="tier-name">{getTierName(multiplier)}</span>
        <span className="multiplier-value">{multiplier}x</span>
      </div>
      {next && (
        <div className="multiplier-next">
          Next: {next.name} ({next.multiplier}) in {next.days - daysStaked} days
        </div>
      )}
    </div>
  );
};

const ActionButton = ({ onClick, disabled, loading, children, variant = 'primary' }) => (
  <button
    className={`action-button action-button-${variant}`}
    onClick={onClick}
    disabled={disabled || loading}
  >
    {loading ? <span className="spinner" /> : children}
  </button>
);

const CooldownTimer = ({ endTime }) => {
  const [timeLeft, setTimeLeft] = useState('');

  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      const end = new Date(endTime);
      const diff = end - now;

      if (diff <= 0) {
        setTimeLeft('Ready');
        clearInterval(timer);
      } else {
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        setTimeLeft(`${hours}h ${minutes}m`);
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [endTime]);

  return <span className="cooldown-timer">{timeLeft}</span>;
};

// =============================================================================
// Main Component
// =============================================================================

const StakingDashboard = ({ wallet, onConnect }) => {
  // State
  const [loading, setLoading] = useState(true);
  const [stakeData, setStakeData] = useState(null);
  const [poolData, setPoolData] = useState(null);
  const [earlyHolder, setEarlyHolder] = useState(null);
  const [autoCompound, setAutoCompound] = useState(false);

  // UI State
  const [stakeAmount, setStakeAmount] = useState('');
  const [actionLoading, setActionLoading] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // API base URL
  const API_URL = process.env.REACT_APP_API_URL || '';

  // ==========================================================================
  // Data Fetching
  // ==========================================================================

  const fetchStakingData = useCallback(async () => {
    if (!wallet) return;

    try {
      setLoading(true);
      setError(null);

      // Fetch user stake info
      const stakeRes = await fetch(`${API_URL}/api/staking/stake/${wallet}`);
      const stakeJson = await stakeRes.json();

      // Fetch pool info
      const poolRes = await fetch(`${API_URL}/api/staking/pool`);
      const poolJson = await poolRes.json();

      // Fetch early holder status
      const earlyRes = await fetch(`${API_URL}/api/staking/early-rewards/holder/${wallet}`);
      const earlyJson = earlyRes.ok ? await earlyRes.json() : null;

      // Fetch auto-compound settings
      const compoundRes = await fetch(`${API_URL}/api/staking/compound/settings/${wallet}`);
      const compoundJson = await compoundRes.json();

      setStakeData(stakeJson);
      setPoolData(poolJson);
      setEarlyHolder(earlyJson);
      setAutoCompound(compoundJson?.enabled || false);

    } catch (err) {
      console.error('Failed to fetch staking data:', err);
      setError('Failed to load staking data');
    } finally {
      setLoading(false);
    }
  }, [wallet, API_URL]);

  useEffect(() => {
    fetchStakingData();
  }, [fetchStakingData]);

  // ==========================================================================
  // Actions
  // ==========================================================================

  const handleStake = async () => {
    if (!stakeAmount || parseFloat(stakeAmount) <= 0) {
      setError('Please enter a valid amount');
      return;
    }

    setActionLoading('stake');
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/staking/stake`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wallet,
          amount: parseFloat(stakeAmount) * 1e9, // Convert to smallest unit
        }),
      });

      const data = await res.json();

      if (data.success) {
        setSuccess(`Successfully staked ${stakeAmount} KR8TIV`);
        setStakeAmount('');
        fetchStakingData();
      } else {
        setError(data.error || 'Stake failed');
      }
    } catch (err) {
      setError('Stake failed: ' + err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRequestUnstake = async () => {
    setActionLoading('unstake');
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/staking/request-unstake`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wallet }),
      });

      const data = await res.json();

      if (data.success) {
        setSuccess('Unstake requested. Cooldown period started.');
        fetchStakingData();
      } else {
        setError(data.error || 'Request failed');
      }
    } catch (err) {
      setError('Request failed: ' + err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleUnstake = async () => {
    setActionLoading('complete-unstake');
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/staking/unstake`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wallet }),
      });

      const data = await res.json();

      if (data.success) {
        setSuccess(`Unstaked ${data.amount} tokens and claimed ${data.rewards} SOL rewards`);
        fetchStakingData();
      } else {
        setError(data.error || 'Unstake failed');
      }
    } catch (err) {
      setError('Unstake failed: ' + err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleClaimRewards = async () => {
    setActionLoading('claim');
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/staking/claim`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wallet }),
      });

      const data = await res.json();

      if (data.success) {
        setSuccess(`Claimed ${data.amount} SOL`);
        fetchStakingData();
      } else {
        setError(data.error || 'Claim failed');
      }
    } catch (err) {
      setError('Claim failed: ' + err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleToggleAutoCompound = async () => {
    setActionLoading('compound');
    setError(null);

    try {
      const endpoint = autoCompound ? 'disable' : 'enable';
      const res = await fetch(`${API_URL}/api/staking/compound/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wallet }),
      });

      const data = await res.json();

      if (data.success) {
        setAutoCompound(!autoCompound);
        setSuccess(`Auto-compound ${autoCompound ? 'disabled' : 'enabled'}`);
      } else {
        setError(data.error || 'Failed to update setting');
      }
    } catch (err) {
      setError('Failed: ' + err.message);
    } finally {
      setActionLoading(null);
    }
  };

  // ==========================================================================
  // Render
  // ==========================================================================

  if (!wallet) {
    return (
      <div className="staking-connect">
        <h2>Connect Wallet to Stake</h2>
        <p>Connect your Solana wallet to start earning rewards.</p>
        <ActionButton onClick={onConnect}>Connect Wallet</ActionButton>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="staking-loading">
        <div className="spinner-large" />
        <p>Loading staking data...</p>
      </div>
    );
  }

  const hasStake = stakeData?.amount > 0;
  const isUnstaking = stakeData?.unstake_time > 0;
  const cooldownComplete = isUnstaking && new Date(stakeData.cooldown_end) <= new Date();

  return (
    <div className="staking-dashboard">
      {/* Notifications */}
      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Header */}
      <div className="staking-header">
        <h1>KR8TIV Staking</h1>
        <p>Stake your KR8TIV tokens to earn SOL rewards</p>
      </div>

      {/* Stats Cards */}
      <div className="stake-cards">
        <StakeCard
          title="Your Stake"
          value={`${((stakeData?.amount || 0) / 1e9).toLocaleString()} KR8TIV`}
          subtitle={hasStake ? `Staked ${stakeData.days_staked} days` : 'No active stake'}
          icon="$"
        />
        <StakeCard
          title="Pending Rewards"
          value={`${((stakeData?.pending_rewards || 0) / 1e9).toFixed(6)} SOL`}
          subtitle={hasStake ? 'Claim anytime' : '-'}
          icon="~"
        />
        <StakeCard
          title="Total Pool"
          value={`${((poolData?.total_staked || 0) / 1e9).toLocaleString()} KR8TIV`}
          subtitle={`${poolData?.staker_count || 0} stakers`}
          icon="#"
        />
        <StakeCard
          title="Pool APY"
          value={`${((poolData?.apy || 0) * 100).toFixed(1)}%`}
          subtitle="Varies with multiplier"
          icon="%"
        />
      </div>

      {/* Multiplier */}
      {hasStake && (
        <MultiplierBadge
          multiplier={stakeData.multiplier}
          daysStaked={stakeData.days_staked}
        />
      )}

      {/* Early Holder Badge */}
      {earlyHolder && (
        <div className="early-holder-badge">
          <span className="tier">{earlyHolder.tier.toUpperCase()}</span>
          <span className="position">Early Holder #{earlyHolder.position}</span>
          <span className="bonus">{earlyHolder.multiplier}x Bonus</span>
          {!earlyHolder.bonus_claimed && (
            <ActionButton
              onClick={async () => {
                const res = await fetch(`${API_URL}/api/staking/early-rewards/claim/${wallet}`, {
                  method: 'POST',
                });
                const data = await res.json();
                if (data.success) {
                  setSuccess(`Claimed ${data.bonus_sol} SOL early holder bonus!`);
                  fetchStakingData();
                }
              }}
              variant="secondary"
            >
              Claim Bonus
            </ActionButton>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="staking-actions">
        {/* Stake */}
        <div className="action-group">
          <h3>Stake Tokens</h3>
          <div className="input-group">
            <input
              type="number"
              value={stakeAmount}
              onChange={(e) => setStakeAmount(e.target.value)}
              placeholder="Amount to stake"
              disabled={actionLoading}
            />
            <ActionButton
              onClick={handleStake}
              loading={actionLoading === 'stake'}
              disabled={!stakeAmount}
            >
              Stake
            </ActionButton>
          </div>
        </div>

        {/* Claim Rewards */}
        {hasStake && (
          <div className="action-group">
            <h3>Claim Rewards</h3>
            <ActionButton
              onClick={handleClaimRewards}
              loading={actionLoading === 'claim'}
              disabled={stakeData.pending_rewards <= 0}
            >
              Claim {(stakeData.pending_rewards / 1e9).toFixed(6)} SOL
            </ActionButton>
          </div>
        )}

        {/* Unstake */}
        {hasStake && (
          <div className="action-group">
            <h3>Unstake</h3>
            {!isUnstaking ? (
              <ActionButton
                onClick={handleRequestUnstake}
                loading={actionLoading === 'unstake'}
                variant="secondary"
              >
                Request Unstake (3-day cooldown)
              </ActionButton>
            ) : cooldownComplete ? (
              <ActionButton
                onClick={handleUnstake}
                loading={actionLoading === 'complete-unstake'}
              >
                Complete Unstake
              </ActionButton>
            ) : (
              <div className="cooldown-info">
                Cooldown: <CooldownTimer endTime={stakeData.cooldown_end} />
              </div>
            )}
          </div>
        )}

        {/* Auto-Compound */}
        <div className="action-group">
          <h3>Auto-Compound</h3>
          <p>Automatically reinvest rewards to maximize APY</p>
          <label className="toggle">
            <input
              type="checkbox"
              checked={autoCompound}
              onChange={handleToggleAutoCompound}
              disabled={actionLoading === 'compound'}
            />
            <span className="toggle-slider" />
            {autoCompound ? 'Enabled' : 'Disabled'}
          </label>
        </div>
      </div>

      {/* Pool Info */}
      <div className="pool-info">
        <h3>Reward Pool</h3>
        <div className="pool-stats">
          <div>
            <span>Total Rewards Distributed</span>
            <span>{((poolData?.total_rewards_distributed || 0) / 1e9).toFixed(2)} SOL</span>
          </div>
          <div>
            <span>Next Distribution</span>
            <span>{poolData?.next_distribution || 'Sunday 00:00 UTC'}</span>
          </div>
          <div>
            <span>Your Share</span>
            <span>{((stakeData?.pool_share || 0) * 100).toFixed(2)}%</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StakingDashboard;
