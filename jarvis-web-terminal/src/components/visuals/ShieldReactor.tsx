'use client';

import { useWallet } from '@solana/wallet-adapter-react';

export function ShieldReactor() {
    const { connected } = useWallet();

    return (
        <div className={`transition-all duration-1000 ${connected ? 'opacity-100' : 'opacity-30 grayscale'}`}>
            <svg width="40" height="40" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="50" cy="50" r="45" stroke="var(--accent-neon)" strokeWidth="2" className="animate-[spin_10s_linear_infinite]" />
                <circle cx="50" cy="50" r="35" stroke="var(--accent-neon)" strokeWidth="1" strokeDasharray="4 4" className="animate-[spin_15s_linear_infinite_reverse]" />
                <circle cx="50" cy="50" r="20" fill={connected ? "var(--accent-neon)" : "transparent"} className={`transition-colors duration-500 ${connected ? 'animate-pulse' : ''}`} />
            </svg>
        </div>
    );
}
