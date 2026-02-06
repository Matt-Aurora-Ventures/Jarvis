'use client';

/**
 * Trending Tokens Panel
 * 
 * Displays hot Solana tokens with sentiment grades, buy/sell ratios,
 * and price momentum in a premium card layout.
 */

import { TokenSentiment, GRADE_COLORS, REGIME_COLORS } from '@/types/sentiment-types';
import { TrendingUp, TrendingDown, Minus, Activity, DollarSign, BarChart3, Droplets } from 'lucide-react';

interface TrendingTokensPanelProps {
    tokens: TokenSentiment[];
    isLoading?: boolean;
}

export function TrendingTokensPanel({ tokens, isLoading }: TrendingTokensPanelProps) {
    if (isLoading) {
        return (
            <div className="sentiment-panel">
                <div className="sentiment-panel-header">
                    <Activity className="w-5 h-5 text-accent-primary" />
                    <h3>Trending Tokens</h3>
                </div>
                <div className="flex items-center justify-center h-64">
                    <div className="animate-pulse text-text-muted">Loading trending tokens...</div>
                </div>
            </div>
        );
    }

    return (
        <div className="sentiment-panel">
            <div className="sentiment-panel-header">
                <Activity className="w-5 h-5 text-accent-primary" />
                <h3>🔥 Hot Trending Solana</h3>
                <span className="ml-auto text-xs text-text-muted">{tokens.length} tokens</span>
            </div>

            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-2">
                {tokens.map((token, index) => (
                    <TokenRow key={token.contractAddress || index} token={token} rank={index + 1} />
                ))}

                {tokens.length === 0 && (
                    <div className="text-center text-text-muted py-8">
                        No trending tokens found
                    </div>
                )}
            </div>
        </div>
    );
}

function TokenRow({ token, rank }: { token: TokenSentiment; rank: number }) {
    const gradeColor = GRADE_COLORS[token.grade];
    const isPositive = token.change24h > 0;
    const isNegative = token.change24h < 0;

    const TrendIcon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;
    const trendColor = isPositive ? 'text-emerald-400' : isNegative ? 'text-red-400' : 'text-yellow-400';

    // Calculate buy/sell bar width
    const buySellTotal = token.buys24h + token.sells24h;
    const buyPercent = buySellTotal > 0 ? (token.buys24h / buySellTotal) * 100 : 50;

    return (
        <div className="token-row group">
            {/* Rank Badge */}
            <div className="token-rank">
                #{rank}
            </div>

            {/* Token Info */}
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <span className="font-semibold text-text-primary truncate">{token.symbol}</span>
                    <span className={`sentiment-grade ${gradeColor.bg} ${gradeColor.text} ${gradeColor.border}`}>
                        {token.grade}
                    </span>
                </div>
                <div className="text-xs text-text-muted truncate">{token.name}</div>
            </div>

            {/* Price & Change */}
            <div className="text-right">
                <div className="text-sm font-mono text-text-primary">
                    ${token.priceUsd < 0.01 ? token.priceUsd.toExponential(2) : token.priceUsd.toFixed(4)}
                </div>
                <div className={`flex items-center justify-end gap-1 text-xs ${trendColor}`}>
                    <TrendIcon className="w-3 h-3" />
                    {token.change24h > 0 ? '+' : ''}{token.change24h.toFixed(1)}%
                </div>
            </div>

            {/* Buy/Sell Ratio Bar */}
            <div className="w-20 hidden sm:block">
                <div className="text-xs text-text-muted text-center mb-1">
                    {token.buySellRatio.toFixed(2)}x
                </div>
                <div className="h-1.5 rounded-full bg-bg-tertiary overflow-hidden flex">
                    <div
                        className="h-full bg-emerald-500 transition-all duration-300"
                        style={{ width: `${buyPercent}%` }}
                    />
                    <div
                        className="h-full bg-red-500 transition-all duration-300"
                        style={{ width: `${100 - buyPercent}%` }}
                    />
                </div>
            </div>

            {/* Volume & MCap */}
            <div className="hidden lg:flex flex-col text-right text-xs">
                <div className="flex items-center gap-1 text-text-muted">
                    <BarChart3 className="w-3 h-3" />
                    ${formatCompact(token.volume24h)}
                </div>
                <div className="flex items-center gap-1 text-text-muted">
                    <DollarSign className="w-3 h-3" />
                    ${formatCompact(token.mcap)}
                </div>
            </div>

            {/* Sentiment Label */}
            <div className={`hidden xl:block text-xs px-2 py-1 rounded ${getSentimentBg(token.sentimentLabel)}`}>
                {token.sentimentLabel.replace('SLIGHTLY ', '')}
            </div>
        </div>
    );
}

function formatCompact(num: number): string {
    if (num >= 1e9) return (num / 1e9).toFixed(1) + 'B';
    if (num >= 1e6) return (num / 1e6).toFixed(1) + 'M';
    if (num >= 1e3) return (num / 1e3).toFixed(1) + 'K';
    return num.toFixed(0);
}

function getSentimentBg(label: string): string {
    switch (label) {
        case 'BULLISH': return 'bg-emerald-500/20 text-emerald-400';
        case 'SLIGHTLY BULLISH': return 'bg-green-500/15 text-green-400';
        case 'NEUTRAL': return 'bg-yellow-500/15 text-yellow-400';
        case 'SLIGHTLY BEARISH': return 'bg-orange-500/15 text-orange-400';
        case 'BEARISH': return 'bg-red-500/20 text-red-400';
        default: return 'bg-bg-tertiary text-text-muted';
    }
}
