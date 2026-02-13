'use client';

import { type ReactNode } from 'react';
import { Buffer } from 'buffer';
import { PhantomWalletProvider } from '@/hooks/usePhantomWallet';

// Polyfill Buffer for @solana/web3.js on the client
if (typeof window !== 'undefined') {
  (window as any).Buffer = Buffer;
}

export function WalletProvider({ children }: { children: ReactNode }) {
  return (
    <PhantomWalletProvider>
      {children}
    </PhantomWalletProvider>
  );
}
