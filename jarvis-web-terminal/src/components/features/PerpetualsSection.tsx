'use client';

/**
 * Perpetuals Section
 * 
 * Long/Short trading buttons marked as "Coming Soon - Jupiter Perps"
 */

import { useState } from 'react';
import { TrendingUp, TrendingDown, Zap, Lock, Rocket } from 'lucide-react';

interface PerpetualsSectionProps {
    tokenSymbol?: string;
}

export function PerpetualsSection({ tokenSymbol = 'SOL' }: PerpetualsSectionProps) {
    const [hovered, setHovered] = useState<'long' | 'short' | null>(null);

    return (
        <div className="sentiment-panel relative overflow-hidden">
            {/* Coming Soon Overlay */}
            <div className="absolute inset-0 bg-bg-primary/80 backdrop-blur-sm z-10 flex flex-col items-center justify-center">
                <div className="flex items-center gap-2 mb-2">
                    <Lock className="w-5 h-5 text-accent-primary" />
                    <span className="text-lg font-semibold text-text-primary">Coming Soon</span>
                </div>

                <div className="flex items-center gap-2 mb-4">
                    <img
                        src="https://jup.ag/svg/jupiter-logo.svg"
                        alt="Jupiter"
                        className="w-6 h-6"
                        onError={(e) => {
                            e.currentTarget.style.display = 'none';
                        }}
                    />
                    <span className="text-accent-primary font-medium">Jupiter Perps</span>
                </div>

                <p className="text-sm text-text-muted text-center max-w-xs">
                    Leveraged perpetual trading with up to 100x on SOL, ETH, BTC and more.
                </p>

                <div className="mt-4 flex items-center gap-2 text-xs text-text-muted">
                    <Rocket className="w-4 h-4" />
                    <span>Launching Q2 2026</span>
                </div>
            </div>

            {/* Underlying Content (blurred) */}
            <div className="sentiment-panel-header">
                <Zap className="w-5 h-5 text-accent-neon" />
                <h3>⚡ Perpetual Trading</h3>
            </div>

            <div className="space-y-4">
                {/* Token Selector (placeholder) */}
                <div className="flex items-center justify-between p-3 rounded-lg bg-bg-secondary border border-white/10">
                    <span className="text-text-primary font-medium">{tokenSymbol}</span>
                    <span className="text-xs text-text-muted">Select Token</span>
                </div>

                {/* Trade Buttons */}
                <div className="grid grid-cols-2 gap-3">
                    <button
                        onMouseEnter={() => setHovered('long')}
                        onMouseLeave={() => setHovered(null)}
                        className={`perps-button perps-button-long ${hovered === 'long' ? 'perps-button-long-hover' : ''}`}
                    >
                        <TrendingUp className="w-5 h-5" />
                        <span className="font-semibold">LONG</span>
                    </button>

                    <button
                        onMouseEnter={() => setHovered('short')}
                        onMouseLeave={() => setHovered(null)}
                        className={`perps-button perps-button-short ${hovered === 'short' ? 'perps-button-short-hover' : ''}`}
                    >
                        <TrendingDown className="w-5 h-5" />
                        <span className="font-semibold">SHORT</span>
                    </button>
                </div>

                {/* Leverage Slider (placeholder) */}
                <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                        <span className="text-text-muted">Leverage</span>
                        <span className="text-text-primary font-mono">10x</span>
                    </div>
                    <div className="h-2 rounded-full bg-bg-tertiary">
                        <div className="h-full w-1/4 rounded-full bg-gradient-to-r from-emerald-500 to-purple-500" />
                    </div>
                    <div className="flex justify-between text-xs text-text-muted">
                        <span>1x</span>
                        <span>25x</span>
                        <span>50x</span>
                        <span>100x</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
