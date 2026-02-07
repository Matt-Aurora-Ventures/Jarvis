'use client';

import { useState, useMemo } from 'react';
import { useWallet } from '@solana/wallet-adapter-react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import {
    TrendingUp,
    Zap,
    Shield,
    Rocket,
    Clock,
    ChevronDown,
    ChevronUp,
    Loader2,
    ExternalLink,
    Sparkles,
    Building2,
    Gem,
    Target,
    RefreshCw
} from 'lucide-react';
import { getBagsTradingClient, SOL_MINT, STAKER_COMMISSION_WALLET, WIN_COMMISSION_RATE } from '@/lib/bags-trading';
import { useToast } from '@/components/ui/Toast';
import { useSentimentData } from '@/hooks/useSentimentData';
import { TokenSentiment } from '@/types/sentiment-types';

// Asset categories
type AssetCategory = 'ai_picks' | 'trending' | 'blue_chips' | 'xstocks' | 'new_launches';

interface Asset {
    symbol: string;
    name: string;
    mint: string;
    price: number;
    change24h: number;
    sentiment: number; // 0-100
    volume24h: number;
    mcap?: number;
    category: AssetCategory;
    aiReason?: string;
    riskLevel: 'low' | 'medium' | 'high' | 'extreme';
    tags?: string[];
    buySellRatio?: number;
}

const CATEGORY_CONFIG: Record<AssetCategory, { label: string; icon: React.ReactNode; color: string; description: string }> = {
    ai_picks: {
        label: 'AI Picks',
        icon: <Sparkles className="w-4 h-4" />,
        color: 'text-accent-neon',
        description: 'High-conviction trades from sentiment analysis'
    },
    trending: {
        label: 'Trending',
        icon: <TrendingUp className="w-4 h-4" />,
        color: 'text-accent-neon',
        description: 'Hottest tokens by volume & momentum'
    },
    blue_chips: {
        label: 'Blue Chips',
        icon: <Shield className="w-4 h-4" />,
        color: 'text-accent-neon',
        description: 'Established, lower-risk tokens'
    },
    xstocks: {
        label: 'xStocks',
        icon: <Building2 className="w-4 h-4" />,
        color: 'text-accent-success',
        description: 'Tokenized stocks on Solana (coming soon)'
    },
    new_launches: {
        label: 'New Launches',
        icon: <Gem className="w-4 h-4" />,
        color: 'text-pink-400',
        description: 'Fresh bags.fm graduations'
    }
};

const QUICK_AMOUNTS = [0.1, 0.25, 0.5, 1, 2, 5];

function getSentimentColor(sentiment: number): string {
    if (sentiment >= 80) return 'text-accent-neon';
    if (sentiment >= 60) return 'text-accent-success';
    if (sentiment >= 40) return 'text-text-muted';
    if (sentiment >= 20) return 'text-accent-warning';
    return 'text-accent-error';
}

function getSentimentBg(sentiment: number): string {
    if (sentiment >= 80) return 'bg-accent-neon/20';
    if (sentiment >= 60) return 'bg-accent-success/20';
    if (sentiment >= 40) return 'bg-accent-warning/20';
    if (sentiment >= 20) return 'bg-accent-warning/20';
    return 'bg-accent-error/20';
}

function getRiskBadge(risk: Asset['riskLevel']): { color: string; label: string } {
    switch (risk) {
        case 'low': return { color: 'bg-accent-success/20 text-accent-success', label: 'LOW RISK' };
        case 'medium': return { color: 'bg-accent-warning/20 text-text-muted', label: 'MEDIUM' };
        case 'high': return { color: 'bg-accent-warning/20 text-accent-warning', label: 'HIGH RISK' };
        case 'extreme': return { color: 'bg-accent-error/20 text-accent-error', label: 'DEGEN' };
    }
}

function formatPrice(price: number): string {
    if (price >= 1) return `$${price.toFixed(2)}`;
    if (price >= 0.001) return `$${price.toFixed(4)}`;
    if (price >= 0.0001) return `$${price.toFixed(6)}`;
    return `$${price.toExponential(2)}`;
}

function formatVolume(volume: number): string {
    if (volume >= 1e9) return `$${(volume / 1e9).toFixed(1)}B`;
    if (volume >= 1e6) return `$${(volume / 1e6).toFixed(1)}M`;
    if (volume >= 1e3) return `$${(volume / 1e3).toFixed(1)}K`;
    return `$${volume.toFixed(0)}`;
}

function classifyRisk(mcap: number, liquidity: number): Asset['riskLevel'] {
    if (mcap >= 50_000_000 && liquidity >= 1_000_000) return 'low';
    if (mcap >= 5_000_000 && liquidity >= 100_000) return 'medium';
    if (mcap >= 500_000) return 'high';
    return 'extreme';
}

function categorizeToken(token: TokenSentiment, isConviction: boolean): AssetCategory {
    if (isConviction) return 'ai_picks';
    const risk = classifyRisk(token.mcap, token.liquidity);
    if (risk === 'low') return 'blue_chips';
    if (token.tokenRisk === 'SHITCOIN') return 'new_launches';
    return 'trending';
}

function tokenToAsset(token: TokenSentiment, category: AssetCategory, aiReason?: string): Asset {
    const sentimentScore = Math.round((token.sentimentScore + 1) * 50); // -1,1 -> 0-100
    return {
        symbol: token.symbol,
        name: token.name,
        mint: token.contractAddress,
        price: token.priceUsd,
        change24h: token.change24h,
        sentiment: sentimentScore,
        volume24h: token.volume24h,
        mcap: token.mcap,
        category,
        aiReason,
        riskLevel: classifyRisk(token.mcap, token.liquidity),
        tags: [token.tokenRisk, token.grade],
        buySellRatio: token.buySellRatio,
    };
}

interface QuickBuyRowProps {
    asset: Asset;
    onBuy: (asset: Asset, amount: number) => Promise<void>;
    isLoading: boolean;
    connected: boolean;
}

function QuickBuyRow({ asset, onBuy, isLoading, connected }: QuickBuyRowProps) {
    const [expanded, setExpanded] = useState(false);
    const [selectedAmount, setSelectedAmount] = useState(0.1);
    const [buying, setBuying] = useState(false);

    const handleBuy = async () => {
        setBuying(true);
        try {
            await onBuy(asset, selectedAmount);
        } finally {
            setBuying(false);
        }
    };

    const riskBadge = getRiskBadge(asset.riskLevel);

    return (
        <div className="border border-border-primary rounded-lg bg-bg-secondary/50 hover:bg-bg-secondary/80 transition-all">
            {/* Main Row */}
            <div
                className="flex items-center gap-3 p-3 cursor-pointer"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-text-primary">{asset.symbol}</span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${riskBadge.color}`}>
                            {riskBadge.label}
                        </span>
                    </div>
                    <p className="text-xs text-text-muted truncate">{asset.name}</p>
                </div>

                <div className="text-right">
                    <p className="font-mono font-medium text-text-primary">{formatPrice(asset.price)}</p>
                    <p className={`text-xs font-mono ${asset.change24h >= 0 ? 'text-accent-success' : 'text-accent-danger'}`}>
                        {asset.change24h >= 0 ? '+' : ''}{asset.change24h.toFixed(1)}%
                    </p>
                </div>

                <div className={`flex items-center gap-1.5 px-2 py-1 rounded ${getSentimentBg(asset.sentiment)}`}>
                    <Target className={`w-3 h-3 ${getSentimentColor(asset.sentiment)}`} />
                    <span className={`font-mono font-bold text-sm ${getSentimentColor(asset.sentiment)}`}>
                        {asset.sentiment}
                    </span>
                </div>

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
                    {buying ? <Loader2 className="w-3 h-3 animate-spin" /> : `BUY ${selectedAmount} SOL`}
                </button>

                <button className="p-1 text-text-muted hover:text-text-primary">
                    {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
            </div>

            {/* Expanded Details */}
            {expanded && (
                <div className="px-3 pb-3 border-t border-border-primary pt-3 space-y-3">
                    {asset.aiReason && (
                        <div className="flex items-start gap-2 p-2 rounded bg-accent-neon/10 border border-accent-neon/20">
                            <Sparkles className="w-4 h-4 text-accent-neon mt-0.5 flex-shrink-0" />
                            <p className="text-xs text-accent-neon/80">{asset.aiReason}</p>
                        </div>
                    )}

                    <div className="grid grid-cols-4 gap-2 text-xs">
                        <div className="p-2 rounded bg-bg-tertiary/50">
                            <p className="text-text-muted mb-0.5">24h Volume</p>
                            <p className="font-mono font-medium text-text-primary">{formatVolume(asset.volume24h)}</p>
                        </div>
                        {asset.mcap && (
                            <div className="p-2 rounded bg-bg-tertiary/50">
                                <p className="text-text-muted mb-0.5">Market Cap</p>
                                <p className="font-mono font-medium text-text-primary">{formatVolume(asset.mcap)}</p>
                            </div>
                        )}
                        <div className="p-2 rounded bg-bg-tertiary/50">
                            <p className="text-text-muted mb-0.5">B/S Ratio</p>
                            <p className={`font-mono font-bold ${(asset.buySellRatio || 0) >= 1.5 ? 'text-accent-success' : 'text-text-primary'}`}>
                                {(asset.buySellRatio || 0).toFixed(1)}x
                            </p>
                        </div>
                        <div className="p-2 rounded bg-bg-tertiary/50">
                            <p className="text-text-muted mb-0.5">Sentiment</p>
                            <span className={`font-mono font-bold ${getSentimentColor(asset.sentiment)}`}>
                                {asset.sentiment}/100
                            </span>
                        </div>
                    </div>

                    {asset.tags && asset.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                            {asset.tags.map(tag => (
                                <span key={tag} className="px-2 py-0.5 rounded-full bg-bg-tertiary text-[10px] font-mono text-text-muted">
                                    {tag}
                                </span>
                            ))}
                        </div>
                    )}

                    {asset.mint && (
                        <a
                            href={`https://solscan.io/token/${asset.mint}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-accent-neon hover:underline flex items-center gap-1"
                        >
                            View on Solscan <ExternalLink className="w-3 h-3" />
                        </a>
                    )}

                    <div className="flex items-center gap-2">
                        <span className="text-xs text-text-muted">Amount:</span>
                        <div className="flex flex-wrap gap-1">
                            {QUICK_AMOUNTS.map(amt => (
                                <button
                                    key={amt}
                                    onClick={() => setSelectedAmount(amt)}
                                    className={`
                                        px-2 py-1 rounded text-xs font-mono transition-all
                                        ${selectedAmount === amt
                                            ? 'bg-accent-neon text-black font-bold'
                                            : 'bg-bg-tertiary text-text-secondary hover:bg-bg-secondary'}
                                    `}
                                >
                                    {amt} SOL
                                </button>
                            ))}
                        </div>
                    </div>

                    <p className="text-[10px] text-text-muted text-center">
                        {WIN_COMMISSION_RATE * 100}% commission on wins goes to stakers
                    </p>
                </div>
            )}
        </div>
    );
}

export function QuickBuyTable() {
    const { publicKey, signTransaction, connected } = useWallet();
    const { success: toastSuccess, error: toastError, warning: toastWarning } = useToast();
    const {
        trendingTokens,
        convictionPicks,
        isLoading: dataLoading,
        refresh,
        timeSinceUpdate,
    } = useSentimentData({ autoRefresh: true, refreshInterval: 5 * 60 * 1000 });

    const [selectedCategory, setSelectedCategory] = useState<AssetCategory | 'all'>('all');
    const [isLoading, setIsLoading] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);

    // Convert API data to Asset format
    const assets = useMemo(() => {
        const convictionSymbols = new Set(
            convictionPicks.filter(p => p.assetType === 'TOKEN').map(p => p.symbol)
        );

        return trendingTokens.map(token => {
            const isConviction = convictionSymbols.has(token.symbol);
            const category = categorizeToken(token, isConviction);
            const convPick = isConviction
                ? convictionPicks.find(p => p.symbol === token.symbol)
                : undefined;

            return tokenToAsset(
                token,
                category,
                isConviction
                    ? convPick?.reasoning || `Strong buy/sell ratio of ${token.buySellRatio.toFixed(1)}x`
                    : undefined
            );
        });
    }, [trendingTokens, convictionPicks]);

    const filteredAssets = selectedCategory === 'all'
        ? assets
        : assets.filter(a => a.category === selectedCategory);

    const sortedAssets = [...filteredAssets].sort((a, b) => b.sentiment - a.sentiment);

    const handleRefresh = async () => {
        setIsRefreshing(true);
        refresh();
        await new Promise(r => setTimeout(r, 2000));
        setIsRefreshing(false);
    };

    const handleBuy = async (asset: Asset, amount: number) => {
        if (!publicKey || !signTransaction) {
            toastWarning('Please connect your wallet first');
            return;
        }

        setIsLoading(true);
        try {
            const rpcUrl = process.env.NEXT_PUBLIC_SOLANA_RPC_URL || 'https://api.mainnet-beta.solana.com';
            const connection = new Connection(rpcUrl);
            const tradingClient = getBagsTradingClient(connection);

            tradingClient.recordPositionEntry(asset.mint, asset.price, amount);

            const result = await tradingClient.executeSwap(
                publicKey.toString(),
                SOL_MINT,
                asset.mint,
                amount,
                100,
                signTransaction as (tx: VersionedTransaction) => Promise<VersionedTransaction>,
                true
            );

            if (result.success) {
                toastSuccess(`Bought ${asset.symbol}!`, result.txHash);
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

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="font-display text-lg font-bold text-text-primary flex items-center gap-2">
                        <Zap className="w-5 h-5 text-accent-neon" />
                        Quick Buy
                    </h2>
                    <p className="text-xs text-text-muted">
                        {dataLoading ? 'Loading live data...' : `${assets.length} tokens | Updated ${timeSinceUpdate}m ago`}
                    </p>
                </div>
                <button
                    onClick={handleRefresh}
                    disabled={isRefreshing || dataLoading}
                    className="p-2 rounded-lg bg-bg-tertiary hover:bg-bg-secondary transition-all"
                >
                    <RefreshCw className={`w-4 h-4 text-text-muted ${isRefreshing || dataLoading ? 'animate-spin' : ''}`} />
                </button>
            </div>

            {/* Category Tabs */}
            <div className="flex flex-wrap gap-1">
                <button
                    onClick={() => setSelectedCategory('all')}
                    className={`
                        px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                        ${selectedCategory === 'all'
                            ? 'bg-accent-neon text-black'
                            : 'bg-bg-tertiary text-text-secondary hover:bg-bg-secondary'}
                    `}
                >
                    All ({assets.length})
                </button>
                {Object.entries(CATEGORY_CONFIG).map(([key, config]) => {
                    const count = assets.filter(a => a.category === key).length;
                    return (
                        <button
                            key={key}
                            onClick={() => setSelectedCategory(key as AssetCategory)}
                            className={`
                                flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                                ${selectedCategory === key
                                    ? 'bg-accent-neon text-black'
                                    : `bg-bg-tertiary ${config.color} hover:bg-bg-secondary`}
                            `}
                        >
                            {config.icon}
                            {config.label}
                            {count > 0 && <span className="text-[10px] opacity-70">({count})</span>}
                        </button>
                    );
                })}
            </div>

            {selectedCategory !== 'all' && (
                <p className="text-xs text-text-muted italic">
                    {CATEGORY_CONFIG[selectedCategory].description}
                </p>
            )}

            {/* Loading State */}
            {dataLoading && assets.length === 0 && (
                <div className="text-center py-8">
                    <Loader2 className="w-8 h-8 mx-auto mb-2 text-accent-neon animate-spin" />
                    <p className="text-sm text-text-muted">Fetching live market data...</p>
                </div>
            )}

            {/* Asset List */}
            <div className="space-y-2">
                {sortedAssets.map(asset => (
                    <QuickBuyRow
                        key={asset.mint}
                        asset={asset}
                        onBuy={handleBuy}
                        isLoading={isLoading}
                        connected={connected}
                    />
                ))}
            </div>

            {!dataLoading && sortedAssets.length === 0 && (
                <div className="text-center py-8 text-text-muted">
                    <p>No assets in this category</p>
                </div>
            )}

            {!connected && (
                <div className="p-4 rounded-lg bg-accent-neon/10 border border-accent-neon/20 text-center">
                    <p className="text-sm text-accent-neon font-medium">
                        Connect your wallet to start trading
                    </p>
                </div>
            )}

            <div className="text-center text-[10px] text-text-muted py-2 border-t border-border-primary">
                <p>Trades executed via bags.app API with Jito MEV protection</p>
                <p>{WIN_COMMISSION_RATE * 100}% commission on winning trades only goes to stakers at {STAKER_COMMISSION_WALLET.slice(0, 8)}...</p>
            </div>
        </div>
    );
}
