/**
 * Solana Wallet Connection Hook
 * Supports Phantom, Solflare, and other Solana wallets.
 *
 * Features:
 * - Auto-detect installed wallets
 * - Connection management
 * - Account balance fetching
 * - Transaction signing
 * - Disconnect handling
 */
import { useState, useEffect, useCallback } from 'react';
import { PublicKey, Connection, Transaction } from '@solana/web3.js';

interface WalletAdapter {
  publicKey: PublicKey | null;
  isConnected: boolean;
  signTransaction: (transaction: Transaction) => Promise<Transaction>;
  signAllTransactions: (transactions: Transaction[]) => Promise<Transaction[]>;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
}

export interface ConnectedWallet {
  publicKey: string;
  balance: number; // SOL
  adapter: WalletAdapter;
  walletName: string;
}

export interface UseWalletReturn {
  wallet: ConnectedWallet | null;
  connecting: boolean;
  error: string | null;
  availableWallets: string[];
  connectWallet: (walletName: string) => Promise<void>;
  disconnectWallet: () => Promise<void>;
  signTransaction: (transaction: Transaction) => Promise<Transaction>;
  refreshBalance: () => Promise<void>;
}

// Solana mainnet RPC (can be configured via env)
const SOLANA_RPC_URL =
  import.meta.env.VITE_SOLANA_RPC_URL || 'https://api.mainnet-beta.solana.com';

export const useWallet = (): UseWalletReturn => {
  const [wallet, setWallet] = useState<ConnectedWallet | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableWallets, setAvailableWallets] = useState<string[]>([]);
  const [connection] = useState(() => new Connection(SOLANA_RPC_URL, 'confirmed'));

  // Detect available wallets
  useEffect(() => {
    const detected: string[] = [];

    // Check for Phantom
    if ('phantom' in window && window.phantom?.solana?.isPhantom) {
      detected.push('Phantom');
    }

    // Check for Solflare
    if ('solflare' in window && window.solflare?.isSolflare) {
      detected.push('Solflare');
    }

    // Check for Backpack
    if ('backpack' in window) {
      detected.push('Backpack');
    }

    // Check for Glow
    if ('glow' in window) {
      detected.push('Glow');
    }

    setAvailableWallets(detected);
  }, []);

  // Get wallet adapter
  const getWalletAdapter = (walletName: string): WalletAdapter | null => {
    switch (walletName) {
      case 'Phantom':
        return window.phantom?.solana;
      case 'Solflare':
        return window.solflare;
      case 'Backpack':
        return window.backpack;
      case 'Glow':
        return window.glow;
      default:
        return null;
    }
  };

  // Fetch balance
  const fetchBalance = useCallback(
    async (publicKey: PublicKey): Promise<number> => {
      try {
        const lamports = await connection.getBalance(publicKey);
        return lamports / 1e9; // Convert lamports to SOL
      } catch (err) {
        console.error('Error fetching balance:', err);
        return 0;
      }
    },
    [connection]
  );

  // Connect wallet
  const connectWallet = useCallback(
    async (walletName: string) => {
      setConnecting(true);
      setError(null);

      try {
        const adapter = getWalletAdapter(walletName);

        if (!adapter) {
          throw new Error(
            `${walletName} wallet not found. Please install the ${walletName} browser extension.`
          );
        }

        // Connect to wallet
        await adapter.connect();

        if (!adapter.publicKey) {
          throw new Error('Failed to get wallet public key');
        }

        // Fetch balance
        const balance = await fetchBalance(adapter.publicKey);

        setWallet({
          publicKey: adapter.publicKey.toString(),
          balance,
          adapter,
          walletName
        });

        // Listen for account changes
        adapter.on?.('accountChanged', async (publicKey: PublicKey | null) => {
          if (publicKey) {
            const newBalance = await fetchBalance(publicKey);
            setWallet((prev) =>
              prev
                ? {
                    ...prev,
                    publicKey: publicKey.toString(),
                    balance: newBalance
                  }
                : null
            );
          } else {
            setWallet(null);
          }
        });

        // Listen for disconnect
        adapter.on?.('disconnect', () => {
          setWallet(null);
        });
      } catch (err: any) {
        console.error('Wallet connection error:', err);
        setError(err.message || 'Failed to connect wallet');
        setWallet(null);
      } finally {
        setConnecting(false);
      }
    },
    [fetchBalance]
  );

  // Disconnect wallet
  const disconnectWallet = useCallback(async () => {
    if (wallet?.adapter) {
      try {
        await wallet.adapter.disconnect();
      } catch (err) {
        console.error('Disconnect error:', err);
      }
    }
    setWallet(null);
    setError(null);
  }, [wallet]);

  // Sign transaction
  const signTransaction = useCallback(
    async (transaction: Transaction): Promise<Transaction> => {
      if (!wallet?.adapter) {
        throw new Error('No wallet connected');
      }

      return await wallet.adapter.signTransaction(transaction);
    },
    [wallet]
  );

  // Refresh balance
  const refreshBalance = useCallback(async () => {
    if (wallet?.adapter?.publicKey) {
      const balance = await fetchBalance(wallet.adapter.publicKey);
      setWallet((prev) => (prev ? { ...prev, balance } : null));
    }
  }, [wallet, fetchBalance]);

  // Auto-refresh balance every 30 seconds
  useEffect(() => {
    if (!wallet) return;

    const interval = setInterval(refreshBalance, 30000);
    return () => clearInterval(interval);
  }, [wallet, refreshBalance]);

  return {
    wallet,
    connecting,
    error,
    availableWallets,
    connectWallet,
    disconnectWallet,
    signTransaction,
    refreshBalance
  };
};

// Type declarations for wallet adapters
declare global {
  interface Window {
    phantom?: {
      solana?: WalletAdapter & {
        isPhantom: boolean;
        on?: (event: string, callback: (data: any) => void) => void;
      };
    };
    solflare?: WalletAdapter & {
      isSolflare: boolean;
      on?: (event: string, callback: (data: any) => void) => void;
    };
    backpack?: WalletAdapter;
    glow?: WalletAdapter;
  }
}
