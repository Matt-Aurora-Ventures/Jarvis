'use client';

import { useState } from 'react';
import { useWallet } from '@solana/wallet-adapter-react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import {
    Flame,
    Target,
    Zap,
    ChevronRight,
    Loader2,
    CheckCircle2,
    RefreshCw,
    Brain,
} from 'lucide-react';
import { getBagsTradingClient, SOL_MINT } from '@/lib/bags-trading';
import { useToast } from '@/components/ui/Toast';
import { useSentimentData } from '@/hooks/useSentimentData';
import {
    ConvictionPick,
    TokenSentiment,
    GRADE_COLORS,
} from '@/types/sentiment-types';

const QUICK_AMOUNTS = [0.1, 0.5, 1, 5];

function getConvictionColor(score: number): string {
    if (score >= 80) return 'text-accent-neon';
    if (score >= 60) return 'text-green-400';
    if (score >= 40) return 'text-yellow-400';
    return 'text-red-400';
}

function getConvictionBg(score: number): string {
    if (score >= 80) return 'bg-accent-neon/20 border-accent-neon/30';
    if (score >= 60) return 'bg-green-500/20 border-green-500/30';
    if (score >= 40) return 'bg-yellow-500/20 border-yellow-500/30';
    return 'bg-red-500/20 border-red-500/30';
}

function formatPrice(price: number): string {
    if (price >= 100) return `$${price.toFixed(0)}`;
    if (price >= 1) return `$${price.toFixed(2)}`;
    if (price >= 0.01) return `$${price.toFixed(4)}`;
    if (price >= 0.0001) return `$${price.toFixed(6)}`;
    return `$${price.toExponential(2)}`;
}

interface PickCardProps {
    pick: ConvictionPick;
    onBuy: (contractAddress: string, amount: number) => Promise<void>;
    connected: boolean;
    isLoading: boolean;
}

function PickCard({ pick, onBuy, connected, isLoading }: PickCardProps) {
    const [selectedAmount, setSelectedAmount] = useState(0.5);
    const [buying, setBuying] = useState(false);
    const gradeColors = GRADE_COLORS[pick.grade] || GRADE_COLORS['C'];

    const handleBuy = async () => {
        if (!pick.contractAddress) return;
        setBuying(true);
        try {
            await onBuy(pick.contractAddress, selectedAmount);
        } finally {
            setBuying(false);
        }
    };

    const canTrade = pick.assetType === 'TOKEN' && !!pick.contractAddress;

    return (
        <div className={`p-3 rounded-lg border ${getConvictionBg(pick.convictionScore)} space-y-2`}>
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${gradeColors.bg} ${gradeColors.text} ${gradeColors.border} border`}>
                        {pick.grade}
                    </span>
                    <span className="font-mono font-bold text-text-primary">{pick.symbol}</span>
                    <span className="text-xs text-text-muted">|</span>
                    <span className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-bold ${getConvictionColor(pick.convictionScore)} ${getConvictionBg(pick.convictionScore)}`}>
                        <Target className="w-3 h-3" />
                        {pick.convictionScore}
                    </span>
                    <span className="text-[10px] text-text-muted px-1.5 py-0.5 rounded bg-bg-tertiary">
                        {pick.assetType}
                    </span>
                </div>
                <span className="font-mono text-xs text-text-secondary">
                    {formatPrice(pick.entryPrice)}
                </span>
            </div>

            {/* Reasoning */}
            <p className="text-xs text-text-secondary italic">{pick.reasoning}</p>

            {/* Targets */}
            <div className="grid grid-cols-3 gap-1 text-[10px]">
                <div className="p-1.5 rounded bg-bg-tertiary/50 text-center">
                    <p className="text-text-muted">Safe TP</p>
                    <p className="font-mono text-green-400">{formatPrice(pick.targets.safe.takeProfit)}</p>
                </div>
                <div className="p-1.5 rounded bg-bg-tertiary/50 text-center">
                    <p className="text-text-muted">Med TP</p>
                    <p className="font-mono text-yellow-400">{formatPrice(pick.targets.medium.takeProfit)}</p>
                </div>
                <div className="p-1.5 rounded bg-bg-tertiary/50 text-center">
                    <p className="text-text-muted">Degen TP</p>
                    <p className="font-mono text-orange-400">{formatPrice(pick.targets.degen.takeProfit)}</p>
                </div>
            </div>

            {/* Quick Buy */}
            {canTrade && (
                <div className="flex items-center gap-2 pt-2 border-t border-border-primary">
                    <div className="flex gap-1">
                        {QUICK_AMOUNTS.map(amt => (
                            <button
                                key={amt}
                                onClick={() => setSelectedAmount(amt)}
                                className={`px-2 py-1 rounded text-[10px] font-mono transition-all ${
                                    selectedAmount === amt
                                        ? 'bg-accent-neon text-theme-dark font-bold'
                                        : 'bg-bg-tertiary text-text-secondary hover:bg-bg-secondary'
                                }`}
                            >
                                {amt}
                            </button>
                        ))}
                    </div>
                    <button
                        onClick={handleBuy}
                        disabled={!connected || buying || isLoading}
                        className={`
                            flex-1 px-3 py-1.5 rounded-lg font-mono text-xs font-bold transition-all flex items-center justify-center gap-1
                            ${connected
                                ? 'bg-accent-neon text-theme-dark hover:bg-accent-neon/80'
                                : 'bg-bg-tertiary text-text-muted cursor-not-allowed'}
                        `}
                    >
                        {buying ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                            <>
                                <Zap className="w-3 h-3" />
                                BUY {selectedAmount} SOL
                            </>
                        )}
                    </button>
                </div>
            )}
        </div>
    );
}

export function AIConvictionPicks() {
    const { publicKey, signTransaction, connected } = useWallet();
    const { success: toastSuccess, error: toastError, warning: toastWarning } = useToast();
    const {
        convictionPicks,
        trendingTokens,
        stats,
        isLoading: dataLoading,
        refresh,
        timeSinceUpdate,
    } = useSentimentData({ autoRefresh: true, refreshInterval: 5 * 60 * 1000 });

    const [isLoading, setIsLoading] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);

    const handleRefresh = async () => {
        setIsRefreshing(true);
        refresh();
        // Wait a moment for data to start loading
        await new Promise(r => setTimeout(r, 2000));
        setIsRefreshing(false);
    };

    const handleBuy = async (contractAddress: string, amount: number) => {
        if (!publicKey || !signTransaction) {
            toastWarning('Please connect your wallet');
            return;
        }

        setIsLoading(true);
        try {
            const rpcUrl = process.env.NEXT_PUBLIC_SOLANA_RPC_URL || 'https://api.mainnet-beta.solana.com';
            const connection = new Connection(rpcUrl);
            const tradingClient = getBagsTradingClient(connection);

            const result = await tradingClient.executeSwap(
                publicKey.toString(),
                SOL_MINT,
                contractAddress,
                amount,
                100,
                signTransaction as (tx: VersionedTransaction) => Promise<VersionedTransaction>,
                true
            );

            if (result.success) {
                toastSuccess('Trade executed!', result.txHash);
            } else {
                toastError(`Trade failed: ${result.error}`);
            }
        } catch (error) {
            console.error('Buy failed:', error);
            toastError(`Buy failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        } finally {
            setIsLoading(false);
        }
    };

    // Derive performance from picks
    const tokenPicks = convictionPicks.filter(p => p.assetType === 'TOKEN');
    const avgConviction = convictionPicks.length > 0
        ? Math.round(convictionPicks.reduce((sum, p) => sum + p.convictionScore, 0) / convictionPicks.length)
        : 0;

    // Top trending for the sidebar
    const topTrending = trendingTokens
        .sort((a, b) => b.change24h - a.change24h)
        .slice(0, 4);

    return (
        <div className="card-glass p-4 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-accent-neon/20">
                        <Brain className="w-5 h-5 text-accent-neon" />
                    </div>
                    <div>
                        <h2 className="font-display font-bold text-lg text-text-primary">AI CONVICTION PICKS</h2>
                        <p className="text-[10px] font-mono text-text-muted">
                            {dataLoading ? 'Loading...' : `${convictionPicks.length} picks | Updated ${timeSinceUpdate}m ago`}
                        </p>
                    </div>
                </div>
                <button
                    onClick={handleRefresh}
                    disabled={isRefreshing || dataLoading}
                    className="p-2 rounded-lg bg-bg-tertiary hover:bg-bg-secondary transition-all"
                >
                    <RefreshCw className={`w-4 h-4 text-text-muted ${isRefreshing || dataLoading ? 'animate-spin' : ''}`} />
                </button>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-2">
                <div className="p-2 rounded-lg bg-bg-tertiary/50 border border-border-primary text-center">
                    <p className="text-[10px] text-text-muted mb-1">Bullish</p>
                    <p className="font-mono font-bold text-green-400">{stats.bullishCount}</p>
                </div>
                <div className="p-2 rounded-lg bg-bg-tertiary/50 border border-border-primary text-center">
                    <p className="text-[10px] text-text-muted mb-1">Avg Conviction</p>
                    <p className="font-mono font-bold text-accent-neon">{avgConviction}</p>
                </div>
                <div className="p-2 rounded-lg bg-bg-tertiary/50 border border-border-primary text-center">
                    <p className="text-[10px] text-text-muted mb-1">Avg B/S Ratio</p>
                    <p className="font-mono font-bold text-text-primary">{stats.avgBuySellRatio.toFixed(1)}x</p>
                </div>
            </div>

            {/* Selection Criteria */}
            <div className="p-3 rounded-lg bg-bg-tertiary/50 border border-border-primary">
                <div className="flex items-center gap-2 mb-2">
                    <Target className="w-4 h-4 text-accent-neon" />
                    <span className="text-xs font-mono text-text-muted uppercase">Selection Criteria</span>
                </div>
                <div className="space-y-1 text-xs">
                    <div className="flex items-center gap-2">
                        <ChevronRight className="w-3 h-3 text-text-muted" />
                        <span className="text-text-secondary">Buy/sell ratio filtering + momentum scoring</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <ChevronRight className="w-3 h-3 text-text-muted" />
                        <span className="text-text-secondary">DexScreener real-time pair data</span>
                        <CheckCircle2 className="w-3 h-3 text-green-400" />
                    </div>
                    <div className="flex items-center gap-2">
                        <ChevronRight className="w-3 h-3 text-text-muted" />
                        <span className="text-text-secondary">Risk-tiered TP/SL targets (safe/med/degen)</span>
                        <CheckCircle2 className="w-3 h-3 text-green-400" />
                    </div>
                </div>
            </div>

            {/* Loading State */}
            {dataLoading && convictionPicks.length === 0 && (
                <div className="text-center py-8">
                    <Loader2 className="w-8 h-8 mx-auto mb-2 text-accent-neon animate-spin" />
                    <p className="text-sm text-text-muted">Analyzing markets...</p>
                </div>
            )}

            {/* High Conviction Section */}
            {convictionPicks.length > 0 && (
                <div>
                    <div className="flex items-center gap-2 mb-3">
                        <Flame className="w-4 h-4 text-orange-400" />
                        <span className="font-mono font-bold text-text-primary">HIGH CONVICTION ({convictionPicks.length})</span>
                    </div>
                    <div className="space-y-2">
                        {convictionPicks.map(pick => (
                            <PickCard
                                key={`${pick.symbol}-${pick.rank}`}
                                pick={pick}
                                onBuy={handleBuy}
                                connected={connected}
                                isLoading={isLoading}
                            />
                        ))}
                    </div>
                </div>
            )}

            {/* Trending Now */}
            {topTrending.length > 0 && (
                <div>
                    <div className="flex items-center gap-2 mb-3">
                        <Flame className="w-4 h-4 text-accent-neon animate-pulse" />
                        <span className="font-mono font-bold text-text-primary">TRENDING NOW</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        {topTrending.map(token => (
                            <div key={token.symbol} className="p-2 rounded-lg bg-bg-tertiary/50 border border-border-primary flex items-center justify-between">
                                <div>
                                    <span className="font-mono font-bold text-text-primary text-sm">{token.symbol}</span>
                                    <p className="text-[10px] text-text-muted font-mono">{token.buySellRatio.toFixed(1)}x B/S</p>
                                </div>
                                <span className={`font-mono font-bold text-sm ${token.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {token.change24h >= 0 ? '+' : ''}{token.change24h.toFixed(1)}%
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Connect Wallet CTA */}
            {!connected && (
                <div className="p-3 rounded-lg bg-accent-neon/10 border border-accent-neon/20 text-center">
                    <p className="text-sm text-accent-neon font-medium">
                        Connect wallet to trade AI picks instantly
                    </p>
                </div>
            )}
        </div>
    );
}
