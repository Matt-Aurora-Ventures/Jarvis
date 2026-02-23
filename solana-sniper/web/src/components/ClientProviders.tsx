'use client';

import { ReactNode } from 'react';
import { WalletContextProvider } from './WalletProvider';
import { TokenGate } from './TokenGate';

export function ClientProviders({ children }: { children: ReactNode }) {
  return (
    <WalletContextProvider>
      <TokenGate>
        {children}
      </TokenGate>
    </WalletContextProvider>
  );
}
