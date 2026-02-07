'use client';

import { useWallet } from '@solana/wallet-adapter-react';
import { WalletMultiButton } from '@solana/wallet-adapter-react-ui';
import { useEffect, useState } from 'react';

export function WalletButton() {
    const { publicKey } = useWallet();
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    if (!mounted) return null;

    return (
        <div className="wallet-adapter-wrapper">
            <WalletMultiButton className="!bg-accent-neon !text-black !font-mono !font-bold !rounded-full !px-6 !py-2 !h-auto !text-sm hover:!bg-accent-neon/80 !transition-all" />
        </div>
    );
}
