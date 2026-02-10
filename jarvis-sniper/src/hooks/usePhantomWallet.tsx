'use client';

import { createContext, useContext, useCallback, useEffect, useState, type ReactNode } from 'react';
import { PublicKey, VersionedTransaction, Transaction } from '@solana/web3.js';

interface PhantomProvider {
  isPhantom: boolean;
  publicKey: PublicKey | null;
  isConnected: boolean;
  connect(opts?: { onlyIfTrusted?: boolean }): Promise<{ publicKey: PublicKey }>;
  disconnect(): Promise<void>;
  signTransaction<T extends Transaction | VersionedTransaction>(tx: T): Promise<T>;
  signAllTransactions<T extends Transaction | VersionedTransaction>(txs: T[]): Promise<T[]>;
  on(event: string, cb: (...args: any[]) => void): void;
  off(event: string, cb: (...args: any[]) => void): void;
}

interface PhantomWalletState {
  connected: boolean;
  connecting: boolean;
  publicKey: PublicKey | null;
  address: string | null;
  phantomInstalled: boolean;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  signTransaction: <T extends Transaction | VersionedTransaction>(tx: T) => Promise<T>;
  signAllTransactions: <T extends Transaction | VersionedTransaction>(txs: T[]) => Promise<T[]>;
}

const PhantomWalletContext = createContext<PhantomWalletState>({
  connected: false,
  connecting: false,
  publicKey: null,
  address: null,
  phantomInstalled: false,
  connect: async () => {},
  disconnect: async () => {},
  signTransaction: async () => { throw new Error('Wallet not connected'); },
  signAllTransactions: async () => { throw new Error('Wallet not connected'); },
});

function getProvider(): PhantomProvider | null {
  if (typeof window === 'undefined') return null;
  const phantom = (window as any).phantom;
  if (phantom?.solana?.isPhantom) {
    return phantom.solana as PhantomProvider;
  }
  return null;
}

export function PhantomWalletProvider({ children }: { children: ReactNode }) {
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [publicKey, setPublicKey] = useState<PublicKey | null>(null);
  const [phantomInstalled, setPhantomInstalled] = useState(false);

  // Detect Phantom on mount
  useEffect(() => {
    const provider = getProvider();
    setPhantomInstalled(!!provider);
    if (!provider) return;

    // Eager connect — silently reconnect if user previously approved
    provider.connect({ onlyIfTrusted: true })
      .then(({ publicKey }) => {
        setPublicKey(publicKey);
        setConnected(true);
      })
      .catch(() => {
        // User hasn't approved before or rejected — silent fail
      });

    // Listen for connect/disconnect/accountChanged
    const handleConnect = (pk: PublicKey) => {
      setPublicKey(pk);
      setConnected(true);
      setConnecting(false);
    };

    const handleDisconnect = () => {
      setPublicKey(null);
      setConnected(false);
    };

    const handleAccountChanged = (pk: PublicKey | null) => {
      if (pk) {
        setPublicKey(pk);
        setConnected(true);
      } else {
        // Phantom tells us to reconnect
        provider.connect().then(({ publicKey }) => {
          setPublicKey(publicKey);
          setConnected(true);
        }).catch(() => {
          setPublicKey(null);
          setConnected(false);
        });
      }
    };

    provider.on('connect', handleConnect);
    provider.on('disconnect', handleDisconnect);
    provider.on('accountChanged', handleAccountChanged);

    return () => {
      provider.off('connect', handleConnect);
      provider.off('disconnect', handleDisconnect);
      provider.off('accountChanged', handleAccountChanged);
    };
  }, []);

  const connect = useCallback(async () => {
    const provider = getProvider();
    if (!provider) {
      window.open('https://phantom.app/', '_blank');
      return;
    }
    setConnecting(true);
    try {
      const { publicKey } = await provider.connect();
      setPublicKey(publicKey);
      setConnected(true);
    } catch (err) {
      console.warn('Phantom connect rejected:', err);
    } finally {
      setConnecting(false);
    }
  }, []);

  const disconnect = useCallback(async () => {
    const provider = getProvider();
    if (provider) {
      await provider.disconnect();
    }
    setPublicKey(null);
    setConnected(false);
  }, []);

  const signTransaction = useCallback(async <T extends Transaction | VersionedTransaction>(tx: T): Promise<T> => {
    const provider = getProvider();
    if (!provider || !connected) throw new Error('Wallet not connected');
    // Timeout after 60s to prevent infinite hang if popup blocked or user ignores
    const signed = provider.signTransaction(tx);
    const timeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('Phantom wallet approval timeout (60s)')), 60_000)
    );
    return Promise.race([signed, timeout]) as Promise<T>;
  }, [connected]);

  const signAllTransactions = useCallback(async <T extends Transaction | VersionedTransaction>(txs: T[]): Promise<T[]> => {
    const provider = getProvider();
    if (!provider || !connected) throw new Error('Wallet not connected');
    return provider.signAllTransactions(txs);
  }, [connected]);

  const address = publicKey?.toBase58() ?? null;

  return (
    <PhantomWalletContext.Provider value={{ connected, connecting, publicKey, address, phantomInstalled, connect, disconnect, signTransaction, signAllTransactions }}>
      {children}
    </PhantomWalletContext.Provider>
  );
}

export function usePhantomWallet() {
  return useContext(PhantomWalletContext);
}
