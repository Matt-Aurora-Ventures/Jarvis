'use client';

import { useState, useEffect, useCallback } from 'react';
import { useConnection, useWallet } from '@solana/wallet-adapter-react';
import { useBagsGraduations } from '@/hooks/useBagsGraduations';
import { GraduationFeed } from '@/components/features/GraduationFeed';
import { getBagsTradingClient } from '@/lib/bags-trading';
import { bagsClient, getScoreTier, TIER_COLORS, BagsGraduation } from '@/lib/bags-api';
import { getGrokSentimentClient } from '@/lib/grok-sentiment';
import { NeuralLattice } from '@/components/visuals/NeuralLattice';
import {
    Rocket,
    Zap,
    TrendingUp,
    Users,
    Droplets,
    Twitter,
    ExternalLink,
    Gift,
    DollarSign,
    ArrowRight,
    Shield,
    Loader2,
    RefreshCw,
    Star,
    Activity
} from 'lucide-react';

// SOL mint
const SOL_MINT = 'So11111111111111111111111111111111111111112';

// Demo rewards recipient (would come from bags.fm API)
const REWARDS_RECIPIENT = {
    twitter: '@bags_fm',
    handle: 'bags_fm',
    name: 'bags.fm',
    avatar: 'https://pbs.twimg.com/profile_images/bags_fm.jpg',
    totalRewards: 12847.50,
    weeklyRewards: 1250.00,
};

export default function LaunchesPage() {
    const { connection } = useConnection();
    const { publicKey, signTransaction, connected } = useWallet();
    const { graduations, loading, refresh, lastUpdated } = useBagsGraduations({ limit: 50, refreshInterval: 15000 });

    // Swap state
    const [selectedToken, setSelectedToken] = useState<BagsGraduation | null>(null);
    const [swapAmount, setSwapAmount] = useState('0.1');
    const [isSwapping, setIsSwapping] = useState(false);
    const [swapResult, setSwapResult] = useState<{ success: boolean; message: string } | null>(null);

    // Quick swap handler
    const handleQuickSwap = useCallback(async (graduation: BagsGraduation) => {
        if (!publicKey || !signTransaction || !connected) {
            setSwapResult({ success: false, message: 'Connect wallet first' });
            return;
        }

        const amount = parseFloat(swapAmount);
        if (isNaN(amount) || amount <= 0) {
            setSwapResult({ success: false, message: 'Invalid amount' });
            return;
        }

        setIsSwapping(true);
        setSelectedToken(graduation);
        setSwapResult(null);

        try {
            const client = getBagsTradingClient(connection);
            const result = await client.executeSwap(
                publicKey.toBase58(),
                SOL_MINT,
                graduation.mint,
                amount,
                500, // 5% slippage
                signTransaction,
                true // Jito MEV protection
            );

            setSwapResult({
                success: true,
                message: `Bought ${graduation.symbol}! Tx: ${(result.signature || result.txHash || 'unknown').slice(0, 8)}...`
            });
        } catch (error) {
            setSwapResult({
                success: false,
                message: `Failed: ${String(error).slice(0, 50)}`
            });
        } finally {
            setIsSwapping(false);
        }
    }, [publicKey, signTransaction, connected, swapAmount, connection]);

    // Stats
    const stats = {
        total: graduations.length,
        exceptional: graduations.filter(g => g.score >= 85).length,
        strong: graduations.filter(g => g.score >= 70 && g.score < 85).length,
        avgScore: graduations.length > 0
            ? Math.round(graduations.reduce((sum, g) => sum + g.score, 0) / graduations.length)
            : 0,
    };

    return (
        <div className="min-h-screen flex flex-col relative overflow-hidden">
            <NeuralLattice />

            <div className="relative z-10 pt-24 pb-12 px-4 max-w-7xl mx-auto w-full">
                {/* Header */}
                <section className="text-center mb-8">
                    <div className="flex items-center justify-center gap-2 mb-2">
                        <Rocket className="w-6 h-6 text-accent-neon" />
                        <span className="text-sm text-accent-neon font-mono">LIVE LAUNCHES</span>
                    </div>
                    <h1 className="font-display text-4xl md:text-5xl font-bold text-text-primary mb-4">
                        bags.fm Graduations
                    </h1>
                    <p className="text-text-secondary text-lg max-w-2xl mx-auto">
                        Real-time token launches with AI-powered scoring and instant swaps
                    </p>
                </section>

                {/* Stats Strip */}
                <section className="grid grid-cols-4 gap-4 mb-8">
                    <div className="card-glass p-4 text-center">
                        <p className="text-[10px] text-text-muted uppercase mb-1">Total Launches</p>
                        <p className="font-display font-bold text-2xl text-text-primary">{stats.total}</p>
                    </div>
                    <div className="card-glass p-4 text-center">
                        <p className="text-[10px] text-text-muted uppercase mb-1">Exceptional</p>
                        <p className="font-display font-bold text-2xl text-emerald-400">{stats.exceptional}</p>
                    </div>
                    <div className="card-glass p-4 text-center">
                        <p className="text-[10px] text-text-muted uppercase mb-1">Strong</p>
                        <p className="font-display font-bold text-2xl text-green-400">{stats.strong}</p>
                    </div>
                    <div className="card-glass p-4 text-center">
                        <p className="text-[10px] text-text-muted uppercase mb-1">Avg Score</p>
                        <p className="font-display font-bold text-2xl text-accent-neon">{stats.avgScore}</p>
                    </div>
                </section>

                {/* Main Content Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left: Rewards & Quick Swap */}
                    <div className="space-y-6">
                        {/* Rewards Recipient Card */}
                        <div className="card-glass p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <Gift className="w-5 h-5 text-purple-400" />
                                <h3 className="font-display font-bold text-lg text-text-primary">
                                    Trading Rewards
                                </h3>
                            </div>

                            <div className="flex items-center gap-4 p-4 rounded-xl bg-purple-500/10 border border-purple-500/30 mb-4">
                                <div className="w-12 h-12 rounded-full bg-theme-dark flex items-center justify-center overflow-hidden">
                                    <Twitter className="w-6 h-6 text-blue-400" />
                                </div>
                                <div className="flex-1">
                                    <a
                                        href={`https://x.com/${REWARDS_RECIPIENT.handle}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="font-display font-bold text-text-primary hover:text-accent-neon flex items-center gap-1"
                                    >
                                        {REWARDS_RECIPIENT.name}
                                        <ExternalLink className="w-3 h-3" />
                                    </a>
                                    <p className="text-xs text-text-muted">{REWARDS_RECIPIENT.twitter}</p>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div className="p-3 rounded-lg bg-theme-dark/50">
                                    <p className="text-[10px] text-text-muted">Total Earned</p>
                                    <p className="font-mono font-bold text-accent-success">
                                        ${REWARDS_RECIPIENT.totalRewards.toLocaleString()}
                                    </p>
                                </div>
                                <div className="p-3 rounded-lg bg-theme-dark/50">
                                    <p className="text-[10px] text-text-muted">This Week</p>
                                    <p className="font-mono font-bold text-accent-neon">
                                        ${REWARDS_RECIPIENT.weeklyRewards.toLocaleString()}
                                    </p>
                                </div>
                            </div>

                            <p className="text-xs text-text-muted mt-3 text-center">
                                Trade via bags.fm to earn partner rewards
                            </p>
                        </div>

                        {/* Quick Swap Card */}
                        <div className="card-glass p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <Zap className="w-5 h-5 text-accent-neon" />
                                <h3 className="font-display font-bold text-lg text-text-primary">
                                    Quick Swap
                                </h3>
                            </div>

                            {/* Amount Input */}
                            <div className="mb-4">
                                <label className="text-xs text-text-muted mb-1 block">Amount (SOL)</label>
                                <div className="relative">
                                    <input
                                        type="number"
                                        value={swapAmount}
                                        onChange={(e) => setSwapAmount(e.target.value)}
                                        step="0.1"
                                        min="0.01"
                                        className="w-full px-4 py-3 rounded-lg bg-theme-dark/50 border border-theme-border/30 text-text-primary focus:border-accent-neon/50 focus:outline-none font-mono"
                                        placeholder="0.1"
                                    />
                                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
                                        {[0.1, 0.5, 1].map(amt => (
                                            <button
                                                key={amt}
                                                onClick={() => setSwapAmount(String(amt))}
                                                className="px-2 py-1 rounded bg-theme-dark text-text-muted text-xs hover:bg-accent-neon/20 hover:text-accent-neon"
                                            >
                                                {amt}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            {/* Selected Token */}
                            {selectedToken && (
                                <div className="p-3 rounded-lg bg-accent-neon/10 border border-accent-neon/30 mb-4">
                                    <div className="flex items-center justify-between">
                                        <span className="font-mono font-bold text-accent-neon">
                                            {selectedToken.symbol}
                                        </span>
                                        <span className="text-xs text-text-muted">
                                            Score: {selectedToken.score}
                                        </span>
                                    </div>
                                </div>
                            )}

                            {/* Swap Status */}
                            {swapResult && (
                                <div className={`
                                    p-3 rounded-lg mb-4 text-sm
                                    ${swapResult.success
                                        ? 'bg-accent-success/10 border border-accent-success/30 text-accent-success'
                                        : 'bg-accent-danger/10 border border-accent-danger/30 text-accent-danger'}
                                `}>
                                    {swapResult.message}
                                </div>
                            )}

                            {/* Status */}
                            <div className="flex items-center justify-between text-xs text-text-muted">
                                <span className="flex items-center gap-1">
                                    <Shield className="w-3 h-3 text-accent-neon" />
                                    Jito MEV Protection
                                </span>
                                <span>5% Slippage</span>
                            </div>

                            {!connected && (
                                <p className="text-xs text-yellow-400 text-center mt-3">
                                    Connect wallet to swap
                                </p>
                            )}
                        </div>

                        {/* Top Launches Quick List */}
                        <div className="card-glass p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="font-display font-bold text-text-primary flex items-center gap-2">
                                    <Star className="w-4 h-4 text-yellow-400" />
                                    Top Launches
                                </h3>
                                <button
                                    onClick={refresh}
                                    className="p-1 hover:bg-theme-dark/50 rounded"
                                >
                                    <RefreshCw className="w-4 h-4 text-text-muted" />
                                </button>
                            </div>

                            <div className="space-y-2">
                                {graduations
                                    .filter(g => g.score >= 70)
                                    .slice(0, 5)
                                    .map(grad => {
                                        const tier = getScoreTier(grad.score);
                                        const colors = TIER_COLORS[tier];
                                        return (
                                            <div
                                                key={grad.mint}
                                                className={`
                                                    p-3 rounded-lg cursor-pointer transition-all
                                                    ${colors.bg} ${colors.border} border
                                                    hover:scale-[1.02]
                                                `}
                                                onClick={() => {
                                                    setSelectedToken(grad);
                                                    handleQuickSwap(grad);
                                                }}
                                            >
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-mono font-bold text-text-primary">
                                                            {grad.symbol}
                                                        </span>
                                                        <span className={`text-xs ${colors.text}`}>
                                                            {grad.score}
                                                        </span>
                                                    </div>
                                                    {isSwapping && selectedToken?.mint === grad.mint ? (
                                                        <Loader2 className="w-4 h-4 animate-spin text-accent-neon" />
                                                    ) : (
                                                        <button className="text-accent-neon hover:brightness-110">
                                                            <ArrowRight className="w-4 h-4" />
                                                        </button>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })}
                            </div>

                            {graduations.filter(g => g.score >= 70).length === 0 && (
                                <p className="text-xs text-text-muted text-center py-4">
                                    No high-score launches yet
                                </p>
                            )}
                        </div>
                    </div>

                    {/* Right: Full Graduation Feed */}
                    <div className="lg:col-span-2">
                        <GraduationFeed />
                    </div>
                </div>
            </div>
        </div>
    );
}
