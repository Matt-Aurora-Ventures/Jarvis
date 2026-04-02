/**
 * Rewards Panel Component
 *
 * Shows pending SOL rewards and allows claiming:
 * - Pending rewards display
 * - Multiplier bonus indicator
 * - Claim button
 * - Rewards history
 */

import React, { useState, useEffect } from 'react';
import { useWallet, useConnection } from '@solana/wallet-adapter-react';
import { Transaction, LAMPORTS_PER_SOL } from '@solana/web3.js';

const API_BASE = '/api/staking';

export default function RewardsPanel({ onSuccess, pendingRewards, multiplier }) {
  const { publicKey, signTransaction } = useWallet();
  const { connection } = useConnection();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [txStatus, setTxStatus] = useState(null);
  const [claimHistory, setClaimHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Fetch claim history
  useEffect(() => {
    const fetchHistory = async () => {
      if (!publicKey) return;

      setLoadingHistory(true);
      try {
        const response = await fetch(`${API_BASE}/rewards/history/${publicKey.toBase58()}`);
        if (response.ok) {
          const data = await response.json();
          setClaimHistory(data.claims || []);
        }
      } catch (err) {
        console.error('Failed to fetch claim history:', err);
      } finally {
        setLoadingHistory(false);
      }
    };

    fetchHistory();
  }, [publicKey]);

  const handleClaim = async () => {
    if (!publicKey || !signTransaction) {
      setError('Wallet not connected');
      return;
    }

    if (pendingRewards <= 0) {
      setError('No rewards to claim');
      return;
    }

    setLoading(true);
    setError(null);
    setTxStatus('Preparing claim transaction...');

    try {
      const response = await fetch(`${API_BASE}/rewards/claim`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wallet: publicKey.toBase58(),
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || 'Failed to create claim transaction');
      }

      const { transaction: txBase64 } = await response.json();

      setTxStatus('Please sign the transaction...');
      const txBuffer = Buffer.from(txBase64, 'base64');
      const transaction = Transaction.from(txBuffer);

      const signedTx = await signTransaction(transaction);

      setTxStatus('Sending transaction...');
      const signature = await connection.sendRawTransaction(signedTx.serialize());

      setTxStatus('Confirming transaction...');
      await connection.confirmTransaction(signature, 'confirmed');

      setTxStatus('Rewards claimed successfully!');

      if (onSuccess) {
        onSuccess();
      }

      // Refresh history
      const historyResponse = await fetch(`${API_BASE}/rewards/history/${publicKey.toBase58()}`);
      if (historyResponse.ok) {
        const data = await historyResponse.json();
        setClaimHistory(data.claims || []);
      }

      setTimeout(() => setTxStatus(null), 3000);
    } catch (err) {
      console.error('Claim error:', err);
      setError(err.message || 'Failed to claim rewards');
      setTxStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const rewardsSOL = pendingRewards / LAMPORTS_PER_SOL;
  const hasRewards = pendingRewards > 0;

  return (
    <div className="space-y-6">
      {/* Rewards Overview */}
      <div className="bg-gradient-to-r from-green-900/50 to-blue-900/50 rounded-xl p-6 border border-green-700/50">
        <div className="text-center">
          <div className="text-gray-400 text-sm mb-2">Pending Rewards</div>
          <div className="text-4xl font-bold text-green-400 mb-2">
            {rewardsSOL.toFixed(6)} SOL
          </div>
          <div className="flex items-center justify-center gap-2 text-sm">
            <span className="text-gray-400">With</span>
            <span className="px-2 py-1 bg-blue-600 rounded text-white font-semibold">
              {multiplier}x multiplier
            </span>
          </div>
        </div>
      </div>

      {/* Multiplier Breakdown */}
      <div className="bg-gray-700/50 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-gray-300 mb-3">Multiplier Breakdown</h4>
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <span className="text-gray-400">Base rewards</span>
            <span className="text-white">{(rewardsSOL / multiplier).toFixed(6)} SOL</span>
          </div>
          <div className="flex justify-between items-center text-green-400">
            <span>Multiplier bonus ({multiplier}x)</span>
            <span>+{(rewardsSOL - rewardsSOL / multiplier).toFixed(6)} SOL</span>
          </div>
          <div className="border-t border-gray-600 pt-2 mt-2">
            <div className="flex justify-between items-center font-semibold">
              <span className="text-white">Total</span>
              <span className="text-green-400">{rewardsSOL.toFixed(6)} SOL</span>
            </div>
          </div>
        </div>
      </div>

      {/* Multiplier Progress */}
      <div className="bg-gray-700/50 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-gray-300 mb-3">Multiplier Progress</h4>
        <div className="space-y-3">
          <MultiplierTier tier="1.0x" label="Start" achieved={multiplier >= 1.0} current={multiplier < 1.5} />
          <MultiplierTier tier="1.5x" label="7 days" achieved={multiplier >= 1.5} current={multiplier >= 1.5 && multiplier < 2.0} />
          <MultiplierTier tier="2.0x" label="30 days" achieved={multiplier >= 2.0} current={multiplier >= 2.0 && multiplier < 2.5} />
          <MultiplierTier tier="2.5x" label="90 days" achieved={multiplier >= 2.5} current={multiplier >= 2.5} />
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 text-red-400">
          {error}
        </div>
      )}

      {/* Transaction Status */}
      {txStatus && (
        <div className="bg-blue-900/30 border border-blue-700 rounded-lg p-3 flex items-center gap-3">
          {loading && (
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-400"></div>
          )}
          <span className="text-blue-400">{txStatus}</span>
        </div>
      )}

      {/* Claim Button */}
      <button
        onClick={handleClaim}
        disabled={loading || !hasRewards}
        className={`w-full py-4 rounded-lg font-semibold text-lg transition-colors ${
          hasRewards && !loading
            ? 'bg-green-600 hover:bg-green-500 text-white'
            : 'bg-gray-600 text-gray-400 cursor-not-allowed'
        }`}
      >
        {loading ? 'Processing...' : hasRewards ? `Claim ${rewardsSOL.toFixed(6)} SOL` : 'No Rewards to Claim'}
      </button>

      {/* Claim History */}
      <div className="border-t border-gray-700 pt-6">
        <h4 className="text-sm font-semibold text-gray-300 mb-4">Recent Claims</h4>

        {loadingHistory ? (
          <div className="text-center py-4">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-400 mx-auto"></div>
          </div>
        ) : claimHistory.length === 0 ? (
          <div className="text-center py-4 text-gray-500">
            No claims yet
          </div>
        ) : (
          <div className="space-y-2">
            {claimHistory.slice(0, 5).map((claim, index) => (
              <div key={index} className="flex justify-between items-center bg-gray-800/50 rounded-lg p-3">
                <div>
                  <div className="text-white font-medium">
                    {(claim.amount / LAMPORTS_PER_SOL).toFixed(6)} SOL
                  </div>
                  <div className="text-xs text-gray-400">
                    {new Date(claim.timestamp).toLocaleDateString()}
                  </div>
                </div>
                <a
                  href={`https://solscan.io/tx/${claim.signature}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300 text-sm"
                >
                  View →
                </a>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Multiplier tier indicator component
function MultiplierTier({ tier, label, achieved, current }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
        achieved
          ? 'bg-green-600 text-white'
          : 'bg-gray-600 text-gray-400'
      } ${current ? 'ring-2 ring-green-400' : ''}`}>
        {achieved ? '✓' : tier}
      </div>
      <div className="flex-1">
        <div className={achieved ? 'text-white' : 'text-gray-500'}>{tier}</div>
        <div className="text-xs text-gray-500">{label}</div>
      </div>
      {current && (
        <span className="text-xs text-green-400 font-medium">Current</span>
      )}
    </div>
  );
}
