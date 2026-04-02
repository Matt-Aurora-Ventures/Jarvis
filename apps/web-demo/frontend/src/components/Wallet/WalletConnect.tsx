/**
 * Wallet Connect Component - Beautiful Solana Wallet Connection
 * Matches jarvislife.io design system
 */
import React, { useEffect, useState } from 'react';
import { useWallet } from '@solana/wallet-adapter-react';
import { WalletMultiButton } from '@solana/wallet-adapter-react-ui';
import { Wallet, Check, AlertCircle } from 'lucide-react';
import { GlassCard } from '../UI/GlassCard';
import clsx from 'clsx';

interface WalletConnectProps {
  onConnect?: (publicKey: string) => void;
  onDisconnect?: () => void;
}

export const WalletConnect: React.FC<WalletConnectProps> = ({
  onConnect,
  onDisconnect,
}) => {
  const { publicKey, connected, connecting, wallet } = useWallet();
  const [balance, setBalance] = useState<number | null>(null);

  useEffect(() => {
    if (connected && publicKey) {
      // Notify parent component
      onConnect?.(publicKey.toString());

      // Fetch balance from API (server-side)
      fetchBalance(publicKey.toString());
    } else {
      onDisconnect?.();
      setBalance(null);
    }
  }, [connected, publicKey]);

  const fetchBalance = async (address: string) => {
    try {
      // Call backend API to get balance (Rule #1: Server calculates balance)
      const response = await fetch(`/api/wallet/balance?address=${address}`);
      const data = await response.json();
      setBalance(data.sol_balance);
    } catch (error) {
      console.error('Failed to fetch balance:', error);
    }
  };

  return (
    <GlassCard className="max-w-md mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-display font-semibold flex items-center gap-2">
          <Wallet className="text-accent" size={24} />
          <span>Connect Wallet</span>
        </h3>
        {connected && (
          <span className="badge badge-success flex items-center gap-1">
            <Check size={12} />
            Connected
          </span>
        )}
      </div>

      {/* Wallet Connection Button */}
      <div className="mb-4">
        <WalletMultiButton className="!bg-accent !text-bg-dark hover:!shadow-glow-strong !rounded-lg !font-semibold !px-6 !py-3 !transition-all w-full" />
      </div>

      {/* Connected Wallet Info */}
      {connected && publicKey && (
        <div className="space-y-3 pt-4 border-t border-white/10">
          {/* Wallet Name */}
          <div className="flex items-center justify-between">
            <span className="text-muted text-sm">Wallet</span>
            <span className="font-semibold">{wallet?.adapter.name || 'Unknown'}</span>
          </div>

          {/* Address */}
          <div className="flex items-center justify-between">
            <span className="text-muted text-sm">Address</span>
            <code className="text-xs bg-surface px-2 py-1 rounded">
              {publicKey.toString().slice(0, 8)}...{publicKey.toString().slice(-8)}
            </code>
          </div>

          {/* Balance */}
          {balance !== null && (
            <div className="flex items-center justify-between">
              <span className="text-muted text-sm">Balance</span>
              <span className="font-semibold text-accent">
                ◎ {balance.toFixed(4)} SOL
              </span>
            </div>
          )}
        </div>
      )}

      {/* Loading State */}
      {connecting && (
        <div className="flex items-center justify-center gap-2 p-4 text-muted">
          <div className="animate-spin">⏳</div>
          <span>Connecting...</span>
        </div>
      )}

      {/* Security Note */}
      <div className="mt-4 p-3 bg-surface rounded-lg flex items-start gap-2">
        <AlertCircle size={16} className="text-info mt-0.5 flex-shrink-0" />
        <p className="text-xs text-muted">
          <strong>Security:</strong> Your private keys never leave your wallet. All
          transactions are signed locally and verified server-side.
        </p>
      </div>
    </GlassCard>
  );
};
