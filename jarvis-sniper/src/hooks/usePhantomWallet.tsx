'use client';

import { createContext, useContext, useCallback, useEffect, useState, type ReactNode } from 'react';
import { PublicKey, VersionedTransaction, Transaction } from '@solana/web3.js';
import { withTimeout } from '@/lib/async-timeout';
import { WalletConnectModal } from '@/components/wallet/WalletConnectModal';

type WalletKind = 'phantom' | 'solflare' | 'unknown';

interface SolanaProvider {
  isPhantom?: boolean;
  isSolflare?: boolean;
  publicKey: PublicKey | null;
  isConnected: boolean;
  connect(opts?: { onlyIfTrusted?: boolean }): Promise<{ publicKey: PublicKey }>;
  disconnect(): Promise<void>;
  signTransaction<T extends Transaction | VersionedTransaction>(tx: T): Promise<T>;
  signAllTransactions<T extends Transaction | VersionedTransaction>(txs: T[]): Promise<T[]>;
  // Optional: Phantom supports message signing; used for deterministic session wallet recovery.
  signMessage?(
    message: Uint8Array,
    display?: 'utf8' | 'hex',
  ): Promise<{ signature: Uint8Array }> | Promise<Uint8Array> | Promise<{ signature: number[] }>;
  on(event: string, cb: (...args: any[]) => void): void;
  off(event: string, cb: (...args: any[]) => void): void;
}

interface PhantomWalletState {
  connected: boolean;
  connecting: boolean;
  publicKey: PublicKey | null;
  address: string | null;
  walletInstalled: boolean;
  walletKind: WalletKind;
  connect: () => Promise<string | null>;
  disconnect: () => Promise<void>;
  signTransaction: <T extends Transaction | VersionedTransaction>(tx: T) => Promise<T>;
  signAllTransactions: <T extends Transaction | VersionedTransaction>(txs: T[]) => Promise<T[]>;
  signMessage: (message: Uint8Array) => Promise<Uint8Array>;
}

const PhantomWalletContext = createContext<PhantomWalletState>({
  connected: false,
  connecting: false,
  publicKey: null,
  address: null,
  walletInstalled: false,
  walletKind: 'unknown',
  connect: async () => null,
  disconnect: async () => {},
  signTransaction: async () => { throw new Error('Wallet not connected'); },
  signAllTransactions: async () => { throw new Error('Wallet not connected'); },
  signMessage: async () => { throw new Error('Wallet not connected'); },
});

function getProvider(): SolanaProvider | null {
  if (typeof window === 'undefined') return null;
  const w = window as any;

  // Preferred: new Phantom injection location
  const p1 = w?.phantom?.solana;
  if (p1?.isPhantom) return p1 as SolanaProvider;

  // Solflare typically injects under window.solflare
  const sf = w?.solflare;
  if (sf?.isSolflare) return sf as SolanaProvider;

  // Fallback: legacy injection location
  const p2 = w?.solana;
  if (p2?.isPhantom || p2?.isSolflare) return p2 as SolanaProvider;

  return null;
}

export function PhantomWalletProvider({ children }: { children: ReactNode }) {
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [publicKey, setPublicKey] = useState<PublicKey | null>(null);
  const [walletInstalled, setWalletInstalled] = useState(false);
  const [walletKind, setWalletKind] = useState<WalletKind>('unknown');
  const [connectModalOpen, setConnectModalOpen] = useState(false);

  // Detect Phantom on mount
  useEffect(() => {
    let disposed = false;
    let cleanup: (() => void) | null = null;

    const initProvider = (provider: SolanaProvider) => {
      setWalletInstalled(true);
      if (provider?.isPhantom) setWalletKind('phantom');
      else if (provider?.isSolflare) setWalletKind('solflare');
      else setWalletKind('unknown');

      // Eager connect — silently reconnect if user previously approved
      let skipEager = false;
      try {
        skipEager = typeof sessionStorage !== 'undefined'
          && sessionStorage.getItem('jarvis-sniper:skip-eager-connect') === '1';
        if (skipEager) sessionStorage.removeItem('jarvis-sniper:skip-eager-connect');
      } catch {
        // ignore
      }

      if (!skipEager) {
        provider
          .connect({ onlyIfTrusted: true })
          .then(({ publicKey }) => {
            if (disposed) return;
            setPublicKey(publicKey);
            setConnected(true);
          })
          .catch(() => {
            // User hasn't approved before or rejected — silent fail
          });
      }

      // Listen for connect/disconnect/accountChanged
      const handleConnect = (pk: PublicKey) => {
        if (disposed) return;
        setPublicKey(pk);
        setConnected(true);
        setConnecting(false);
      };

      const handleDisconnect = () => {
        if (disposed) return;
        setPublicKey(null);
        setConnected(false);
        setConnecting(false);
      };

      const handleAccountChanged = (pk: PublicKey | null) => {
        if (disposed) return;
        if (pk) {
          setPublicKey(pk);
          setConnected(true);
          return;
        }

        // Phantom tells us to reconnect
        provider
          .connect()
          .then(({ publicKey }) => {
            if (disposed) return;
            setPublicKey(publicKey);
            setConnected(true);
          })
          .catch(() => {
            if (disposed) return;
            setPublicKey(null);
            setConnected(false);
          });
      };

      provider.on('connect', handleConnect);
      provider.on('disconnect', handleDisconnect);
      provider.on('accountChanged', handleAccountChanged);

      cleanup = () => {
        provider.off('connect', handleConnect);
        provider.off('disconnect', handleDisconnect);
        provider.off('accountChanged', handleAccountChanged);
      };
    };

    // Try immediately
    const initial = getProvider();
    if (initial) initProvider(initial);
    else setWalletInstalled(false);

    // Some environments inject the wallet provider late; poll briefly to avoid false negatives.
    let tries = 0;
    const timer = setInterval(() => {
      if (disposed) return;
      if (cleanup) return; // already initialized
      tries += 1;
      const p = getProvider();
      if (p) {
        initProvider(p);
        clearInterval(timer);
      } else if (tries >= 20) {
        clearInterval(timer);
      }
    }, 250);

    return () => {
      disposed = true;
      clearInterval(timer);
      cleanup?.();
    };
  }, []);

  const connect = useCallback(async () => {
    setConnectModalOpen(false);
    try {
      setConnecting(true);

      let provider = getProvider();
      if (!provider) {
        // Give extensions a beat in case injection is late on first load.
        await new Promise((r) => setTimeout(r, 250));
        provider = getProvider();
      }

      if (!provider) {
        setWalletInstalled(false);
        setWalletKind('unknown');
        setConnectModalOpen(true);
        console.warn('No Solana wallet provider detected (extension not installed / not injected).');
        return null;
      }

      const { publicKey } = await provider.connect();
      setPublicKey(publicKey);
      setConnected(true);
      setWalletInstalled(true);
      if (provider?.isPhantom) setWalletKind('phantom');
      else if (provider?.isSolflare) setWalletKind('solflare');
      else setWalletKind('unknown');
      setConnectModalOpen(false);
      return publicKey?.toBase58?.() ?? null;
    } catch (err) {
      console.warn('Wallet connect rejected:', err);
      return null;
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
    if (!provider) throw new Error('Wallet provider not found');
    if (!provider.isConnected || !provider.publicKey) throw new Error('Wallet not connected');
    // Timeout after 180s to prevent infinite hang if popup blocked or user ignores.
    // (60s was too aggressive for manual close flows; users often approve after a minute.)
    return await withTimeout(provider.signTransaction(tx), 180_000, 'Phantom wallet approval timeout (180s)') as T;
  }, []);

  const signAllTransactions = useCallback(async <T extends Transaction | VersionedTransaction>(txs: T[]): Promise<T[]> => {
    const provider = getProvider();
    if (!provider) throw new Error('Wallet provider not found');
    if (!provider.isConnected || !provider.publicKey) throw new Error('Wallet not connected');
    return provider.signAllTransactions(txs);
  }, []);

  const signMessage = useCallback(async (message: Uint8Array): Promise<Uint8Array> => {
    const provider = getProvider();
    if (!provider) throw new Error('Wallet provider not found');
    if (!provider.isConnected || !provider.publicKey) throw new Error('Wallet not connected');
    const fn: unknown = (provider as any).signMessage;
    if (typeof fn !== 'function') throw new Error('Phantom signMessage not available');

    // Timeout after 180s to avoid indefinite hang if popup blocked/ignored.
    const signed = Promise.resolve((fn as any).call(provider, message, 'utf8'));
    const res = await withTimeout(signed, 180_000, 'Phantom message approval timeout (180s)') as any;

    // Phantom may return { signature: Uint8Array } or Uint8Array directly.
    if (res instanceof Uint8Array) return res;
    const sig = res?.signature;
    if (sig instanceof Uint8Array) return sig;
    if (Array.isArray(sig)) return Uint8Array.from(sig.map((n: any) => Number(n)));
    throw new Error('Unknown signMessage response');
  }, []);

  const address = publicKey?.toBase58() ?? null;

  return (
    <PhantomWalletContext.Provider value={{ connected, connecting, publicKey, address, walletInstalled, walletKind, connect, disconnect, signTransaction, signAllTransactions, signMessage }}>
      {children}
      <WalletConnectModal
        open={connectModalOpen}
        onClose={() => setConnectModalOpen(false)}
        preferredKind={walletKind === 'solflare' ? 'solflare' : 'phantom'}
      />
    </PhantomWalletContext.Provider>
  );
}

export function usePhantomWallet() {
  return useContext(PhantomWalletContext);
}
