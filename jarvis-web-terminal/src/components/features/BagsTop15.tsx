'use client';

import { useState } from 'react';
import { useWallet } from '@solana/wallet-adapter-react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import {
    Rocket,
    Users,
    Clock,
    Zap,
    Shield,
    ExternalLink,
    Loader2,
    Flame,
    Target,
    RefreshCw,
    ChevronDown,
    ChevronUp,
    Sparkles,
    BarChart3,
    Activity,
    AlertTriangle,
    Droplets,
    Share2
} from 'lucide-react';
import { getBagsTradingClient, SOL_MINT } from '@/lib/bags-trading';
import { useToast } from '@/components/ui/Toast';
import { useBagsGraduations } from '@/hooks/useBagsGraduations';
import { BagsGraduation, getScoreTier, TIER_COLORS } from '@/lib/bags-api';

// Time ago helper
function timeAgo(timestamp: number): string {
    const seconds = Math.floor(Date.now() / 1000 - timestamp);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

function formatMarketCap(mcap: number): string {
    if (mcap >= 1_000_000) return `$${(mcap / 1_000_000).toFixed(1)}M`;
    if (mcap >= 1_000) return `$${(mcap / 1_000).toFixed(1)}K`;
    return `$${mcap.toFixed(0)}`;
}

function formatPrice(price: number): string {
    if (price >= 1) return `$${price.toFixed(2)}`;
    if (price >= 0.01) return `$${price.toFixed(4)}`;
    if (price >= 0.0001) return `$${price.toFixed(6)}`;
    return `$${price.toExponential(2)}`;
}

const QUICK_AMOUNTS = [0.1, 0.25, 0.5, 1];

interface GraduationCardProps {
    graduation: BagsGraduation;
    onBuy: (mint: string, amount: number) => Promise<void>;
    connected: boolean;
    isLoading: boolean;
    expanded: boolean;
    onToggle: () => void;
}

function GraduationCard({ graduation, onBuy, connected, isLoading, expanded, onToggle }: GraduationCardProps) {
    const [selectedAmount, setSelectedAmount] = useState(0.25);
    const [buying, setBuying] = useState(false);
    const tier = getScoreTier(graduation.score);
    const colors = TIER_COLORS[tier];

    const handleBuy = async () => {
        setBuying(true);
        try {
            await onBuy(graduation.mint, selectedAmount);
        } finally {
            setBuying(false);
        }
    };

    return (
        <div className={`rounded-lg border ${colors.bg} ${colors.border} overflow-hidden`}>
            {/* Main Row */}
            <div
                className="p-3 flex items-center gap-3 cursor-pointer hover:bg-bg-secondary/30 transition-all"
                onClick={onToggle}
            >
                {/* Score Badge */}
                <div className={`w-12 h-12 rounded-lg ${colors.bg} border ${colors.border} flex flex-col items-center justify-center`}>
                    <span className={`font-mono font-bold text-lg ${colors.text}`}>{graduation.score}</span>
                    <span className="text-[8px] text-text-muted uppercase">{tier}</span>
                </div>

                {/* Token Info */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-text-primary">{graduation.symbol}</span>
                        <span className="text-[10px] text-text-muted">{timeAgo(graduation.graduation_time)}</span>
                    </div>
                    <p className="text-xs text-text-muted truncate">{graduation.name}</p>
                </div>

                {/* Market Cap */}
                <div className="text-right">
                    <p className="font-mono font-bold text-text-primary text-sm">
                        {formatMarketCap(graduation.market_cap)}
                    </p>
                    <p className="text-[10px] text-text-muted font-mono">{formatPrice(graduation.price_usd)}</p>
                </div>

                {/* Quick Buy */}
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        if (connected && !buying) handleBuy();
                    }}
                    disabled={!connected || buying || isLoading}
                    className={`
                        px-3 py-1.5 rounded-lg font-mono text-xs font-bold transition-all
                        ${connected
                            ? 'bg-accent-neon text-black hover:bg-accent-neon/80'
                            : 'bg-bg-tertiary text-text-muted cursor-not-allowed'}
                    `}
                >
                    {buying ? <Loader2 className="w-3 h-3 animate-spin" /> : `${selectedAmount} SOL`}
                </button>

                {/* Expand */}
                <button className="p-1 text-text-muted">
                    {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
            </div>

            {/* Expanded Details */}
            {expanded && (
                <div className="px-3 pb-3 border-t border-border-primary/50 space-y-3">
                    {/* Sub-Scores */}
                    <div className="grid grid-cols-4 gap-2 pt-3">
                        <ScoreBar label="Bonding" value={graduation.bonding_curve_score} icon={<BarChart3 className="w-3 h-3" />} />
                        <ScoreBar label="Holders" value={graduation.holder_distribution_score} icon={<Users className="w-3 h-3" />} />
                        <ScoreBar label="Liquidity" value={graduation.liquidity_score} icon={<Droplets className="w-3 h-3" />} />
                        <ScoreBar label="Social" value={graduation.social_score} icon={<Share2 className="w-3 h-3" />} />
                    </div>

                    {/* Market Details */}
                    <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-4">
                            <div>
                                <span className="text-text-muted">MCap: </span>
                                <span className="text-text-primary font-mono">{formatMarketCap(graduation.market_cap)}</span>
                            </div>
                            <div>
                                <span className="text-text-muted">Price: </span>
                                <span className="text-text-primary font-mono">{formatPrice(graduation.price_usd)}</span>
                            </div>
                            <div>
                                <span className="text-text-muted">Graduated: </span>
                                <span className="text-text-primary font-mono">{timeAgo(graduation.graduation_time)}</span>
                            </div>
                        </div>
                        {graduation.mint && !graduation.mint.startsWith('Demo') && (
                            <a
                                href={`https://solscan.io/token/${graduation.mint}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-accent-neon hover:underline flex items-center gap-1"
                                onClick={(e) => e.stopPropagation()}
                            >
                                Solscan <ExternalLink className="w-3 h-3" />
                            </a>
                        )}
                    </div>

                    {/* Amount Selector */}
                    <div className="flex items-center gap-2 pt-2 border-t border-border-primary/50">
                        <span className="text-xs text-text-muted">Buy Amount:</span>
                        <div className="flex gap-1">
                            {QUICK_AMOUNTS.map(amt => (
                                <button
                                    key={amt}
                                    onClick={() => setSelectedAmount(amt)}
                                    className={`px-2 py-1 rounded text-xs font-mono transition-all ${
                                        selectedAmount === amt
                                            ? 'bg-accent-neon text-black font-bold'
                                            : 'bg-bg-tertiary text-text-secondary hover:bg-bg-secondary'
                                    }`}
                                >
                                    {amt} SOL
                                </button>
                            ))}
                        </div>
                        <button
                            onClick={handleBuy}
                            disabled={!connected || buying || isLoading}
                            className={`flex-1 px-3 py-1.5 rounded-lg font-mono text-xs font-bold transition-all flex items-center justify-center gap-1 ${
                                connected
                                    ? 'bg-accent-neon text-black hover:bg-accent-neon/80'
                                    : 'bg-bg-tertiary text-text-muted cursor-not-allowed'
                            }`}
                        >
                            {buying ? <Loader2 className="w-3 h-3 animate-spin" /> : <><Zap className="w-3 h-3" /> SNIPE</>}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

function ScoreBar({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
    const barColor = value >= 70 ? 'bg-accent-success' : value >= 40 ? 'bg-accent-warning' : 'bg-accent-error';
    const textColor = value >= 70 ? 'text-accent-success' : value >= 40 ? 'text-text-muted' : 'text-accent-error';

    return (
        <div className="p-2 rounded bg-bg-tertiary/50 text-center space-y-1">
            <div className="flex items-center justify-center gap-1 text-text-muted">
                {icon}
                <p className="text-[10px]">{label}</p>
            </div>
            <p className={`font-mono text-xs font-bold ${textColor}`}>{value}</p>
            <div className="h-1 rounded-full bg-bg-secondary overflow-hidden">
                <div className={`h-full rounded-full ${barColor} transition-all`} style={{ width: `${value}%` }} />
            </div>
        </div>
    );
}

export function BagsTop15() {
    const { publicKey, signTransaction, connected } = useWallet();
    const { success: toastSuccess, error: toastError, warning: toastWarning } = useToast();
    const { graduations, loading, error, refresh, lastUpdated } = useBagsGraduations({
        limit: 15,
        refreshInterval: 30000,
    });
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [filter, setFilter] = useState<'all' | 'exceptional' | 'strong'>('all');

    const isDemo = error?.includes('demo');

    // Sort by score descending and filter
    const sortedGraduations = [...graduations]
        .filter(g => {
            if (filter === 'exceptional') return g.score >= 85;
            if (filter === 'strong') return g.score >= 70;
            return true;
        })
        .sort((a, b) => b.score - a.score)
        .slice(0, 15);

    const handleRefresh = async () => {
        setIsRefreshing(true);
        await refresh();
        setIsRefreshing(false);
    };

    const handleBuy = async (mint: string, amount: number) => {
        if (!publicKey || !signTransaction) {
            toastWarning('Please connect your wallet');
            return;
        }

        if (mint.startsWith('Demo')) {
            toastWarning('Demo token - connect to live API to trade');
            return;
        }

        setIsLoading(true);
        try {
            const rpcUrl = process.env.NEXT_PUBLIC_SOLANA_RPC_URL || 'https://api.mainnet-beta.solana.com';
            const connection = new Connection(rpcUrl);
            const tradingClient = getBagsTradingClient(connection);

            const graduation = graduations.find(g => g.mint === mint);
            const result = await tradingClient.executeSwap(
                publicKey.toString(),
                SOL_MINT,
                mint,
                amount,
                150, // Higher slippage for new tokens
                signTransaction as (tx: VersionedTransaction) => Promise<VersionedTransaction>,
                true // Jito for MEV protection
            );

            if (result.success) {
                toastSuccess(`Sniped ${graduation?.symbol || 'token'}!`, result.txHash);
            } else {
                toastError(`Snipe failed: ${result.error}`);
            }
        } catch (error) {
            console.error('Snipe failed:', error);
            toastError(`Snipe failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="card-glass p-4 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-pink-500/20">
                        <Rocket className="w-5 h-5 text-pink-400" />
                    </div>
                    <div>
                        <h2 className="font-display font-bold text-lg text-text-primary">BAGS TOP 15</h2>
                        <p className="text-[10px] font-mono text-text-muted">bags.fm graduations with AI scoring</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {isDemo ? (
                        <>
                            <AlertTriangle className="w-4 h-4 text-text-muted" />
                            <span className="text-[10px] font-mono text-text-muted">DEMO</span>
                        </>
                    ) : (
                        <>
                            <Activity className="w-4 h-4 text-accent-success animate-pulse" />
                            <span className="text-[10px] font-mono text-accent-success">LIVE</span>
                        </>
                    )}
                    <button
                        onClick={handleRefresh}
                        disabled={isRefreshing || loading}
                        className="p-2 rounded-lg bg-bg-tertiary hover:bg-bg-secondary transition-all"
                    >
                        <RefreshCw className={`w-4 h-4 text-text-muted ${isRefreshing || loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            {/* Last Updated */}
            {lastUpdated && (
                <div className="flex items-center gap-1 text-[10px] text-text-muted">
                    <Clock className="w-3 h-3" />
                    <span>Updated {timeAgo(lastUpdated.getTime() / 1000)}</span>
                    <span className="ml-auto">{sortedGraduations.length} tokens</span>
                </div>
            )}

            {/* Filter Tabs */}
            <div className="flex gap-1">
                {[
                    { key: 'all', label: 'All' },
                    { key: 'exceptional', label: '85+ Score' },
                    { key: 'strong', label: '70+ Score' }
                ].map(({ key, label }) => (
                    <button
                        key={key}
                        onClick={() => setFilter(key as typeof filter)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                            filter === key
                                ? 'bg-accent-neon text-black'
                                : 'bg-bg-tertiary text-text-secondary hover:bg-bg-secondary'
                        }`}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {/* Score Legend */}
            <div className="flex items-center gap-3 text-[10px]">
                <span className="text-text-muted">Score tiers:</span>
                <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400">85+ Exceptional</span>
                <span className="px-2 py-0.5 rounded bg-accent-success/10 text-accent-success">70-84 Strong</span>
                <span className="px-2 py-0.5 rounded bg-accent-warning/10 text-text-muted">50-69 Average</span>
                <span className="px-2 py-0.5 rounded bg-accent-warning/10 text-accent-warning">&lt;50 Weak</span>
            </div>

            {/* Loading State */}
            {loading && graduations.length === 0 && (
                <div className="text-center py-8">
                    <Loader2 className="w-8 h-8 mx-auto mb-2 text-accent-neon animate-spin" />
                    <p className="text-sm text-text-muted">Loading graduations...</p>
                </div>
            )}

            {/* Graduations List */}
            <div className="space-y-2">
                {sortedGraduations.map(grad => (
                    <GraduationCard
                        key={grad.mint}
                        graduation={grad}
                        onBuy={handleBuy}
                        connected={connected}
                        isLoading={isLoading}
                        expanded={expandedId === grad.mint}
                        onToggle={() => setExpandedId(expandedId === grad.mint ? null : grad.mint)}
                    />
                ))}
            </div>

            {/* Empty State */}
            {!loading && sortedGraduations.length === 0 && (
                <div className="text-center py-8 text-text-muted">
                    <Rocket className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>No graduations matching filter</p>
                </div>
            )}

            {/* Connect Wallet CTA */}
            {!connected && (
                <div className="p-3 rounded-lg bg-pink-500/10 border border-pink-500/20 text-center">
                    <p className="text-sm text-pink-400 font-medium">
                        Connect wallet to snipe new launches instantly
                    </p>
                </div>
            )}

            {/* Footer */}
            <div className="text-center text-[10px] text-text-muted pt-2 border-t border-border-primary">
                <p>Live bags.fm graduation feed with AI-powered scoring</p>
                <p>0.5% commission on winning trades goes to stakers</p>
            </div>
        </div>
    );
}
