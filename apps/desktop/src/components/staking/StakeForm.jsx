/**
 * Stake Form Component
 *
 * Allows users to stake $KR8TIV tokens:
 * - Token balance display
 * - Amount input with max button
 * - Stake confirmation
 * - Transaction status
 */

import React, { useState, useEffect } from 'react';
import { useWallet, useConnection } from '@solana/wallet-adapter-react';
import { PublicKey, Transaction } from '@solana/web3.js';
import { getAssociatedTokenAddress, TOKEN_PROGRAM_ID } from '@solana/spl-token';

const KR8TIV_MINT = new PublicKey(process.env.REACT_APP_KR8TIV_MINT || '11111111111111111111111111111111');
const STAKING_PROGRAM = new PublicKey(process.env.REACT_APP_STAKING_PROGRAM || '11111111111111111111111111111111');
const API_BASE = '/api/staking';

export default function StakeForm({ onSuccess, currentStake }) {
  const { publicKey, signTransaction } = useWallet();
  const { connection } = useConnection();

  const [amount, setAmount] = useState('');
  const [balance, setBalance] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [txStatus, setTxStatus] = useState(null);

  // Fetch token balance
  useEffect(() => {
    const fetchBalance = async () => {
      if (!publicKey) return;

      try {
        const tokenAccount = await getAssociatedTokenAddress(
          KR8TIV_MINT,
          publicKey
        );

        const accountInfo = await connection.getTokenAccountBalance(tokenAccount);
        setBalance(accountInfo.value.uiAmount || 0);
      } catch (err) {
        // Account might not exist yet
        setBalance(0);
      }
    };

    fetchBalance();
    const interval = setInterval(fetchBalance, 10000);
    return () => clearInterval(interval);
  }, [publicKey, connection]);

  const handleAmountChange = (e) => {
    const value = e.target.value;
    // Only allow numbers and decimals
    if (/^\d*\.?\d*$/.test(value)) {
      setAmount(value);
      setError(null);
    }
  };

  const handleMaxClick = () => {
    setAmount(balance.toString());
  };

  const handleStake = async () => {
    if (!publicKey || !signTransaction) {
      setError('Wallet not connected');
      return;
    }

    const stakeAmount = parseFloat(amount);
    if (isNaN(stakeAmount) || stakeAmount <= 0) {
      setError('Please enter a valid amount');
      return;
    }

    if (stakeAmount > balance) {
      setError('Insufficient balance');
      return;
    }

    setLoading(true);
    setError(null);
    setTxStatus('Preparing transaction...');

    try {
      // Get stake transaction from backend
      const response = await fetch(`${API_BASE}/stake`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wallet: publicKey.toBase58(),
          amount: Math.floor(stakeAmount * 1e9), // Convert to lamports
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || 'Failed to create stake transaction');
      }

      const { transaction: txBase64 } = await response.json();

      // Deserialize and sign
      setTxStatus('Please sign the transaction...');
      const txBuffer = Buffer.from(txBase64, 'base64');
      const transaction = Transaction.from(txBuffer);

      const signedTx = await signTransaction(transaction);

      // Send transaction
      setTxStatus('Sending transaction...');
      const signature = await connection.sendRawTransaction(signedTx.serialize());

      // Confirm
      setTxStatus('Confirming transaction...');
      await connection.confirmTransaction(signature, 'confirmed');

      setTxStatus('Stake successful!');
      setAmount('');

      // Notify parent
      if (onSuccess) {
        onSuccess(stakeAmount, signature);
      }

      // Clear status after delay
      setTimeout(() => setTxStatus(null), 3000);
    } catch (err) {
      console.error('Stake error:', err);
      setError(err.message || 'Failed to stake');
      setTxStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const stakeAmountNum = parseFloat(amount) || 0;
  const isValidAmount = stakeAmountNum > 0 && stakeAmountNum <= balance;

  return (
    <div className="space-y-6">
      {/* Balance Display */}
      <div className="bg-gray-700/50 rounded-lg p-4">
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Available Balance</span>
          <span className="text-white font-semibold">
            {balance.toLocaleString()} KR8TIV
          </span>
        </div>
        {currentStake > 0 && (
          <div className="flex justify-between items-center mt-2 pt-2 border-t border-gray-600">
            <span className="text-gray-400">Currently Staked</span>
            <span className="text-blue-400 font-semibold">
              {(currentStake / 1e9).toLocaleString()} KR8TIV
            </span>
          </div>
        )}
      </div>

      {/* Amount Input */}
      <div>
        <label className="block text-sm text-gray-400 mb-2">
          Amount to Stake
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

      {/* Stake Info */}
      {stakeAmountNum > 0 && (
        <div className="bg-blue-900/30 border border-blue-700 rounded-lg p-4 space-y-2">
          <h4 className="text-blue-400 font-semibold">Staking Benefits</h4>
          <ul className="text-sm text-gray-300 space-y-1">
            <li className="flex items-center gap-2">
              <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Start earning SOL rewards immediately
            </li>
            <li className="flex items-center gap-2">
              <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Multiplier increases over time (up to 2.5x)
            </li>
            <li className="flex items-center gap-2">
              <svg className="w-4 h-4 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              3-day cooldown period for unstaking
            </li>
          </ul>
        </div>
      )}

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

      {/* Stake Button */}
      <button
        onClick={handleStake}
        disabled={loading || !isValidAmount}
        className={`w-full py-4 rounded-lg font-semibold text-lg transition-colors ${
          isValidAmount && !loading
            ? 'bg-blue-600 hover:bg-blue-500 text-white'
            : 'bg-gray-600 text-gray-400 cursor-not-allowed'
        }`}
      >
        {loading ? 'Processing...' : `Stake ${stakeAmountNum > 0 ? stakeAmountNum.toLocaleString() : ''} KR8TIV`}
      </button>
    </div>
  );
}
