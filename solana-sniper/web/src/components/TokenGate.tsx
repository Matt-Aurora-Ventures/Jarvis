'use client';

import { useEffect, useState, ReactNode } from 'react';
import { useConnection, useWallet } from '@solana/wallet-adapter-react';
import { WalletMultiButton } from '@solana/wallet-adapter-react-ui';
import { PublicKey } from '@solana/web3.js';

// The token mint that gates access — set via env or hardcode
const GATE_TOKEN_MINT = process.env.NEXT_PUBLIC_GATE_TOKEN_MINT || '';
const REQUIRED_BALANCE = Number(process.env.NEXT_PUBLIC_GATE_TOKEN_AMOUNT || '1000000');
const TOKEN_SYMBOL = process.env.NEXT_PUBLIC_GATE_TOKEN_SYMBOL || 'TOKEN';

interface TokenGateProps {
  children: ReactNode;
}

export function TokenGate({ children }: TokenGateProps) {
  const { connection } = useConnection();
  const { publicKey, connected } = useWallet();
  const [hasAccess, setHasAccess] = useState(!GATE_TOKEN_MINT); // no gate = auto-access
  const [balance, setBalance] = useState<number>(0);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // If no gate token configured, allow all access
    if (!GATE_TOKEN_MINT) {
      setHasAccess(true);
      return;
    }
    if (!publicKey || !connected) {
      setHasAccess(false);
      setBalance(0);
      return;
    }

    async function checkBalance() {
      setChecking(true);
      setError(null);
      try {
        const mintPubkey = new PublicKey(GATE_TOKEN_MINT);

        // Find associated token account
        const tokenAccounts = await connection.getParsedTokenAccountsByOwner(
          publicKey!,
          { mint: mintPubkey },
        );

        let totalBalance = 0;
        for (const account of tokenAccounts.value) {
          const info = account.account.data.parsed?.info;
          if (info?.tokenAmount?.uiAmount) {
            totalBalance += info.tokenAmount.uiAmount;
          }
        }

        setBalance(totalBalance);
        setHasAccess(totalBalance >= REQUIRED_BALANCE);
      } catch (err) {
        setError('Failed to check token balance');
        setHasAccess(false);
      } finally {
        setChecking(false);
      }
    }

    checkBalance();

    // Re-check every 30 seconds
    const interval = setInterval(checkBalance, 30_000);
    return () => clearInterval(interval);
  }, [publicKey, connected, connection]);

  // Not connected — show connect prompt
  if (!connected) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="card max-w-md w-full text-center space-y-6">
          <div className="space-y-2">
            <div className="w-16 h-16 mx-auto rounded-full bg-[var(--accent)]/10 flex items-center justify-center">
              <span className="text-3xl text-[var(--accent)]">&#x1F512;</span>
            </div>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">
              <span className="text-[var(--accent)]">SOLANA</span> SNIPER
            </h1>
            <p className="text-sm text-[var(--text-muted)]">
              Connect your wallet to access the trading terminal
            </p>
          </div>

          <div className="p-4 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
            <p className="text-xs text-[var(--text-muted)] mb-1">Required Balance</p>
            <p className="text-lg font-bold text-[var(--accent)] mono">
              {REQUIRED_BALANCE.toLocaleString()} {TOKEN_SYMBOL}
            </p>
          </div>

          <div className="flex justify-center">
            <WalletMultiButton />
          </div>

          <p className="text-[10px] text-[var(--text-muted)]">
            Phantom, Solflare, and other Solana wallets supported
          </p>
        </div>
      </div>
    );
  }

  // Connected but checking
  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="card max-w-md w-full text-center space-y-4">
          <div className="animate-pulse">
            <div className="w-12 h-12 mx-auto rounded-full bg-[var(--accent)]/20" />
          </div>
          <p className="text-sm text-[var(--text-muted)]">Verifying token balance...</p>
        </div>
      </div>
    );
  }

  // Connected but insufficient balance
  if (!hasAccess) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="card max-w-md w-full text-center space-y-6">
          <div className="space-y-2">
            <div className="w-16 h-16 mx-auto rounded-full bg-[#ef4444]/10 flex items-center justify-center">
              <span className="text-3xl">&#x26D4;</span>
            </div>
            <h1 className="text-lg font-bold text-[var(--text-primary)]">Access Denied</h1>
            <p className="text-sm text-[var(--text-muted)]">
              Insufficient {TOKEN_SYMBOL} balance
            </p>
          </div>

          <div className="space-y-3">
            <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
              <div className="flex justify-between text-xs">
                <span className="text-[var(--text-muted)]">Your Balance</span>
                <span className="text-[#ef4444] font-bold mono">{balance.toLocaleString()}</span>
              </div>
            </div>
            <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
              <div className="flex justify-between text-xs">
                <span className="text-[var(--text-muted)]">Required</span>
                <span className="text-[var(--accent)] font-bold mono">{REQUIRED_BALANCE.toLocaleString()}</span>
              </div>
            </div>
            <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[#ef4444]/30">
              <div className="flex justify-between text-xs">
                <span className="text-[var(--text-muted)]">Shortfall</span>
                <span className="text-[#ef4444] font-bold mono">
                  {(REQUIRED_BALANCE - balance).toLocaleString()} {TOKEN_SYMBOL}
                </span>
              </div>
            </div>
          </div>

          {error && (
            <p className="text-xs text-[#ef4444]">{error}</p>
          )}

          <div className="flex justify-center gap-3">
            <WalletMultiButton />
          </div>

          <p className="text-[10px] text-[var(--text-muted)]">
            Wallet: {publicKey?.toBase58().slice(0, 4)}...{publicKey?.toBase58().slice(-4)}
          </p>
        </div>
      </div>
    );
  }

  // Access granted
  return <>{children}</>;
}
