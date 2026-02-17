'use client';

import { TradePanel } from '@/components/features/TradePanel';
import { SnipePanel } from '@/components/features/SnipePanel';
import { MarketChart } from '@/components/features/MarketChart';
import { TradingGuard, ConfidenceBadge } from '@/components/features/TradingGuard';
import { AlgoConfig } from '@/components/features/AlgoConfig';
import { useSentimentData } from '@/hooks/useSentimentData';
import {
    TrendingUp,
    Settings2
} from 'lucide-react';
import { useState } from 'react';

export default function TradePage() {
    const [showAlgoConfig, setShowAlgoConfig] = useState(false);
    const { marketRegime } = useSentimentData({ autoRefresh: true, refreshInterval: 5 * 60 * 1000 });

    return (
        <>
            {/* Ambient Background */}
            <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
                <div className="ambient-orb absolute top-1/4 left-1/4 w-96 h-96 bg-accent-neon/[0.04] rounded-full blur-[128px]" />
                <div className="ambient-orb-2 absolute bottom-1/3 right-1/4 w-80 h-80 bg-accent-neon/[0.03] rounded-full blur-[128px]" />
                <div className="ambient-orb-3 absolute top-2/3 left-1/2 w-64 h-64 bg-accent-success/[0.02] rounded-full blur-[128px]" />
            </div>

            <div className="pt-[100px] pb-4 px-3 lg:px-6 max-w-[1920px] mx-auto w-full">
                {/* Header */}
                <section className="flex items-center justify-between mb-6">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <TrendingUp className="w-5 h-5 text-accent-neon" />
                            <span className="text-sm text-accent-neon font-mono">TRADE</span>
                        </div>
                        <h1 className="font-display text-3xl font-bold text-text-primary">
                            Execute Trades
                        </h1>
                    </div>

                    <div className="flex items-center gap-3">
                        {/* Trading Safety Status */}
                        <TradingGuard symbol="SOL" />

                        {/* Algo Config Toggle */}
                        <button
                            onClick={() => setShowAlgoConfig(!showAlgoConfig)}
                            className={`
                                p-2 rounded-lg transition-colors
                                ${showAlgoConfig
                                    ? 'bg-accent-neon/20 text-accent-neon'
                                    : 'bg-bg-secondary/50 text-text-muted hover:bg-bg-secondary'}
                            `}
                        >
                            <Settings2 className="w-5 h-5" />
                        </button>
                    </div>
                </section>

                {/* Algo Config Panel */}
                {showAlgoConfig && (
                    <section className="mb-6">
                        <AlgoConfig />
                    </section>
                )}

                {/* Main Trading Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                    {/* Left: Snipe Panel */}
                    <div className="lg:col-span-3">
                        <SnipePanel />
                    </div>

                    {/* Center: Chart */}
                    <div className="lg:col-span-6">
                        <div className="card-glass p-0 overflow-hidden h-full min-h-[500px] relative">
                            <div className="absolute top-4 left-4 z-10 flex gap-4 items-center">
                                <div className="flex flex-col">
                                    <span className="font-display font-bold text-2xl text-text-primary">SOL/USDC</span>
                                    <span className="font-mono text-xs text-text-muted">JUPITER AGGREGATOR</span>
                                </div>
                                <div className="h-10 w-[1px] bg-border-primary" />
                                <div className="flex flex-col">
                                    <span className="font-mono font-bold text-accent-neon">
                                        {marketRegime.solPrice > 0 ? `$${marketRegime.solPrice.toFixed(2)}` : '...'}
                                    </span>
                                    <span className={`font-mono text-xs ${marketRegime.solChange24h >= 0 ? 'text-accent-success' : 'text-accent-error'}`}>
                                        {marketRegime.solChange24h >= 0 ? '+' : ''}{marketRegime.solChange24h.toFixed(1)}%
                                    </span>
                                </div>
                                <ConfidenceBadge symbol="SOL" />
                            </div>
                            <MarketChart />
                        </div>
                    </div>

                    {/* Right: Trade Panel */}
                    <div className="lg:col-span-3">
                        <TradePanel />
                    </div>
                </div>
            </div>
        </>
    );
}
