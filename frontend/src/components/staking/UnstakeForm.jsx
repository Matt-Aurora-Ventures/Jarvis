/**
 * Unstake Form Component
 *
 * Handles unstaking with 3-day cooldown:
 * - Initiate unstake (starts cooldown)
 * - Show cooldown progress
 * - Complete unstake (after cooldown)
 */

import React, { useState, useEffect } from 'react';
import { useWallet, useConnection } from '@solana/wallet-adapter-react';
import { Transaction } from '@solana/web3.js';

const API_BASE = '/api/staking';

export default function UnstakeForm({ onSuccess, currentStake, cooldownEnd, cooldownAmount }) {
  const { publicKey, signTransaction } = useWallet();
  const { connection } = useConnection();

  const [amount, setAmount] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [txStatus, setTxStatus] = useState(null);
  const [timeRemaining, setTimeRemaining] = useState(null);

  // Calculate cooldown time remaining
  useEffect(() => {
    if (!cooldownEnd) {
      setTimeRemaining(null);
      return;
    }

    const updateTimeRemaining = () => {
      const now = new Date();
      const end = new Date(cooldownEnd);
      const diff = end - now;

      if (diff <= 0) {
        setTimeRemaining(0);
      } else {
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        setTimeRemaining({ days, hours, minutes, total: diff });
      }
    };

    updateTimeRemaining();
    const interval = setInterval(updateTimeRemaining, 60000);
    return () => clearInterval(interval);
  }, [cooldownEnd]);

  const handleAmountChange = (e) => {
    const value = e.target.value;
    if (/^\d*\.?\d*$/.test(value)) {
      setAmount(value);
      setError(null);
    }
  };

  const handleMaxClick = () => {
    setAmount((currentStake / 1e9).toString());
  };

  const handleInitiateUnstake = async () => {
    if (!publicKey || !signTransaction) {
      setError('Wallet not connected');
      return;
    }

    const unstakeAmount = parseFloat(amount);
    if (isNaN(unstakeAmount) || unstakeAmount <= 0) {
      setError('Please enter a valid amount');
      return;
    }

    const maxUnstake = currentStake / 1e9;
    if (unstakeAmount > maxUnstake) {
      setError('Amount exceeds staked balance');
      return;
    }

    setLoading(true);
    setError(null);
    setTxStatus('Preparing unstake transaction...');

    try {
      const response = await fetch(`${API_BASE}/unstake/initiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wallet: publicKey.toBase58(),
          amount: Math.floor(unstakeAmount * 1e9),
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || 'Failed to create unstake transaction');
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

      setTxStatus('Unstake initiated! 3-day cooldown started.');
      setAmount('');

      if (onSuccess) {
        onSuccess();
      }

      setTimeout(() => setTxStatus(null), 3000);
    } catch (err) {
      console.error('Unstake error:', err);
      setError(err.message || 'Failed to initiate unstake');
      setTxStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteUnstake = async () => {
    if (!publicKey || !signTransaction) {
      setError('Wallet not connected');
      return;
    }

    setLoading(true);
    setError(null);
    setTxStatus('Preparing withdrawal...');

    try {
      const response = await fetch(`${API_BASE}/unstake/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wallet: publicKey.toBase58(),
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || 'Failed to complete unstake');
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

      setTxStatus('Tokens withdrawn successfully!');

      if (onSuccess) {
        onSuccess();
      }

      setTimeout(() => setTxStatus(null), 3000);
    } catch (err) {
      console.error('Complete unstake error:', err);
      setError(err.message || 'Failed to complete unstake');
      setTxStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const stakedAmount = currentStake / 1e9;
  const unstakeAmountNum = parseFloat(amount) || 0;
  const isValidAmount = unstakeAmountNum > 0 && unstakeAmountNum <= stakedAmount;
  const hasCooldown = cooldownEnd && new Date(cooldownEnd) > new Date();
  const cooldownComplete = timeRemaining === 0;

  // If there's an active cooldown, show cooldown UI
  if (hasCooldown && !cooldownComplete) {
    return (
      <div className="space-y-6">
        {/* Cooldown Progress */}
        <div className="bg-yellow-900/30 border border-yellow-700 rounded-xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-yellow-600 rounded-full">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-yellow-400">Cooldown in Progress</h3>
              <p className="text-sm text-yellow-200">Your tokens are being unstaked</p>
            </div>
          </div>

          {/* Amount being unstaked */}
          <div className="bg-gray-800/50 rounded-lg p-4 mb-4">
            <div className="text-gray-400 text-sm">Amount being unstaked</div>
            <div className="text-2xl font-bold text-white">
              {(cooldownAmount / 1e9).toLocaleString()} KR8TIV
            </div>
          </div>

          {/* Time remaining */}
          <div className="text-center">
            <div className="text-gray-400 text-sm mb-2">Time remaining</div>
            <div className="flex justify-center gap-4">
              <div className="bg-gray-800 rounded-lg px-4 py-2">
                <div className="text-2xl font-bold text-white">{timeRemaining?.days || 0}</div>
                <div className="text-xs text-gray-400">days</div>
              </div>
              <div className="bg-gray-800 rounded-lg px-4 py-2">
                <div className="text-2xl font-bold text-white">{timeRemaining?.hours || 0}</div>
                <div className="text-xs text-gray-400">hours</div>
              </div>
              <div className="bg-gray-800 rounded-lg px-4 py-2">
                <div className="text-2xl font-bold text-white">{timeRemaining?.minutes || 0}</div>
                <div className="text-xs text-gray-400">mins</div>
              </div>
            </div>
          </div>

          {/* Progress bar */}
          <div className="mt-4">
            <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-yellow-500 transition-all duration-300"
                style={{
                  width: `${Math.max(0, 100 - (timeRemaining?.total || 0) / (3 * 24 * 60 * 60 * 1000) * 100)}%`
                }}
              />
            </div>
          </div>
        </div>

        <p className="text-center text-gray-400 text-sm">
          Your tokens will be available for withdrawal after the cooldown period ends.
        </p>
      </div>
    );
  }

  // If cooldown is complete, show withdraw button
  if (cooldownComplete && cooldownAmount > 0) {
    return (
      <div className="space-y-6">
        <div className="bg-green-900/30 border border-green-700 rounded-xl p-6 text-center">
          <div className="w-16 h-16 bg-green-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-green-400 mb-2">Cooldown Complete!</h3>
          <p className="text-gray-300 mb-4">
            Your {(cooldownAmount / 1e9).toLocaleString()} KR8TIV tokens are ready to withdraw
          </p>

          {error && (
            <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 text-red-400 mb-4">
              {error}
            </div>
          )}

          {txStatus && (
            <div className="bg-blue-900/30 border border-blue-700 rounded-lg p-3 flex items-center justify-center gap-3 mb-4">
              {loading && (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-400"></div>
              )}
              <span className="text-blue-400">{txStatus}</span>
            </div>
          )}

          <button
            onClick={handleCompleteUnstake}
            disabled={loading}
            className="w-full py-4 rounded-lg font-semibold text-lg bg-green-600 hover:bg-green-500 text-white transition-colors disabled:opacity-50"
          >
            {loading ? 'Processing...' : 'Withdraw Tokens'}
          </button>
        </div>
      </div>
    );
  }

  // Normal unstake form
  return (
    <div className="space-y-6">
      {/* Staked Balance */}
      <div className="bg-gray-700/50 rounded-lg p-4">
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Currently Staked</span>
          <span className="text-white font-semibold">
            {stakedAmount.toLocaleString()} KR8TIV
          </span>
        </div>
      </div>

      {stakedAmount === 0 ? (
        <div className="text-center py-8">
          <div className="text-gray-400 mb-2">No tokens staked</div>
          <p className="text-sm text-gray-500">
            Stake your KR8TIV tokens first to start earning rewards
          </p>
        </div>
      ) : (
        <>
          {/* Amount Input */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              Amount to Unstake
            </label>
            <div className="relative">
              <input
                type="text"
                value={amount}
                onChange={handleAmountChange}
                placeholder="0.00"
                disabled={loading}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white text-lg focus:outline-none focus:border-blue-500 disabled:opacity-50"
              />
              <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-2">
                <button
                  onClick={handleMaxClick}
                  disabled={loading}
                  className="px-3 py-1 text-sm bg-gray-600 hover:bg-gray-500 text-white rounded transition-colors disabled:opacity-50"
                >
                  MAX
                </button>
                <span className="text-gray-400">KR8TIV</span>
              </div>
            </div>
          </div>

          {/* Unstake Warning */}
          <div className="bg-yellow-900/30 border border-yellow-700 rounded-lg p-4 space-y-2">
            <h4 className="text-yellow-400 font-semibold flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              Important Information
            </h4>
            <ul className="text-sm text-gray-300 space-y-1">
              <li>• 3-day cooldown period before tokens can be withdrawn</li>
              <li>• You will stop earning rewards on unstaked amount immediately</li>
              <li>• Your multiplier will reset for unstaked tokens</li>
              <li>• Pending rewards can still be claimed</li>
            </ul>
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

          {/* Unstake Button */}
          <button
            onClick={handleInitiateUnstake}
            disabled={loading || !isValidAmount}
            className={`w-full py-4 rounded-lg font-semibold text-lg transition-colors ${
              isValidAmount && !loading
                ? 'bg-yellow-600 hover:bg-yellow-500 text-white'
                : 'bg-gray-600 text-gray-400 cursor-not-allowed'
            }`}
          >
            {loading ? 'Processing...' : `Unstake ${unstakeAmountNum > 0 ? unstakeAmountNum.toLocaleString() : ''} KR8TIV`}
          </button>
        </>
      )}
    </div>
  );
}
