'use client';

import { useState, useEffect, useCallback } from 'react';
import { Newspaper, TrendingUp, TrendingDown, Minus, RefreshCw, Loader2 } from 'lucide-react';
import { getDexterIntelClient, MarketNews } from '@/lib/dexter-intel';

// Fallback news when API not configured
const FALLBACK_NEWS: MarketNews[] = [
    {
        id: '1',
        title: 'Solana DEX Volume Hits New ATH',
        summary: 'Solana decentralized exchanges processed over $5B in 24h volume, driven by memecoin activity and Jupiter aggregation improvements.',
        source: 'DeFi Pulse',
        sentiment: 'bullish',
        relevance: 90,
        category: 'crypto',
        timestamp: Date.now(),
        symbols: ['SOL', 'JUP'],
    },
    {
        id: '2',
        title: 'Fed Holds Rates Steady, Markets React',
        summary: 'Federal Reserve maintains current rate policy. Risk assets showing resilience as inflation data trends lower than expected.',
        source: 'MarketWatch',
        sentiment: 'neutral',
        relevance: 85,
        category: 'macro',
        timestamp: Date.now(),
    },
    {
        id: '3',
        title: 'AI Agent Tokens Surge on New Framework Launch',
        summary: 'AI-related tokens on Solana see 20-40% gains as new agent frameworks drive developer interest and retail speculation.',
        source: 'CryptoSlate',
        sentiment: 'bullish',
        relevance: 80,
        category: 'crypto',
        symbols: ['AI16Z', 'VIRTUAL'],
        timestamp: Date.now(),
    },
    {
        id: '4',
        title: 'Bitcoin ETF Inflows Continue Record Pace',
        summary: 'Spot Bitcoin ETFs see $500M+ daily inflows for the third consecutive week, supporting bullish market structure.',
        source: 'Bloomberg',
        sentiment: 'bullish',
        relevance: 88,
        category: 'crypto',
        symbols: ['BTC'],
        timestamp: Date.now(),
    },
    {
        id: '5',
        title: 'SEC Regulatory Clarity Expected Q1 2026',
        summary: 'Anticipated framework for crypto asset classification could provide clearer guidelines for token projects and exchanges.',
        source: 'Reuters',
        sentiment: 'neutral',
        relevance: 75,
        category: 'regulatory',
        timestamp: Date.now(),
    },
];

function getSentimentIcon(sentiment: MarketNews['sentiment']) {
    switch (sentiment) {
        case 'bullish': return <TrendingUp className="w-3.5 h-3.5 text-accent-success" />;
        case 'bearish': return <TrendingDown className="w-3.5 h-3.5 text-accent-error" />;
        default: return <Minus className="w-3.5 h-3.5 text-text-muted" />;
    }
}

function getSentimentBg(sentiment: MarketNews['sentiment']): string {
    switch (sentiment) {
        case 'bullish': return 'border-l-accent-success';
        case 'bearish': return 'border-l-accent-error';
        default: return 'border-l-text-muted';
    }
}

function getCategoryBadge(category: MarketNews['category']): string {
    switch (category) {
        case 'crypto': return 'bg-accent-neon/10 text-accent-neon';
        case 'stocks': return 'bg-accent-success/10 text-accent-success';
        case 'macro': return 'bg-accent-warning/10 text-accent-warning';
        case 'regulatory': return 'bg-accent-error/10 text-accent-error';
        case 'technical': return 'bg-bg-tertiary text-text-muted';
    }
}

export function MarketNewsPanel() {
    const [news, setNews] = useState<MarketNews[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isLive, setIsLive] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);

    const fetchNews = useCallback(async (showRefresh = false) => {
        if (showRefresh) setIsRefreshing(true);

        try {
            const client = getDexterIntelClient();
            const result = await client.getMarketNews('Solana ecosystem');

            if (result.length > 0) {
                setNews(result);
                setIsLive(true);
            } else {
                // Fall back to curated news
                setNews(FALLBACK_NEWS);
                setIsLive(false);
            }
        } catch {
            setNews(FALLBACK_NEWS);
            setIsLive(false);
        } finally {
            setIsLoading(false);
            setIsRefreshing(false);
        }
    }, []);

    useEffect(() => {
        fetchNews();
        // Refresh every 5 minutes
        const interval = setInterval(() => fetchNews(), 5 * 60 * 1000);
        return () => clearInterval(interval);
    }, [fetchNews]);

    return (
        <div className="card-glass p-4 space-y-3">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Newspaper className="w-4 h-4 text-accent-neon" />
                    <span className="text-xs font-mono uppercase tracking-wider text-text-muted">MARKET INTEL</span>
                    {isLive ? (
                        <span className="text-[10px] font-mono text-accent-success flex items-center gap-1">
                            <span className="w-1.5 h-1.5 bg-accent-success rounded-full animate-pulse" />
                            LIVE
                        </span>
                    ) : (
                        <span className="text-[10px] font-mono text-text-muted">CURATED</span>
                    )}
                </div>
                <button
                    onClick={() => fetchNews(true)}
                    disabled={isRefreshing}
                    className="p-2 rounded-lg bg-bg-tertiary hover:bg-bg-secondary transition-all"
                >
                    <RefreshCw className={`w-4 h-4 text-text-muted ${isRefreshing ? 'animate-spin' : ''}`} />
                </button>
            </div>

            {/* Loading */}
            {isLoading && (
                <div className="flex items-center justify-center py-6">
                    <Loader2 className="w-5 h-5 text-accent-neon animate-spin" />
                </div>
            )}

            {/* News Items */}
            {!isLoading && (
                <div className="space-y-2">
                    {news.map(item => (
                        <div key={item.id} className={`p-3 rounded-lg bg-bg-tertiary/50 border-l-4 ${getSentimentBg(item.sentiment)} space-y-1.5`}>
                            <div className="flex items-start justify-between gap-2">
                                <div className="flex items-center gap-2 min-w-0">
                                    {getSentimentIcon(item.sentiment)}
                                    <h4 className="text-sm font-medium text-text-primary leading-tight">{item.title}</h4>
                                </div>
                                <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-mono ${getCategoryBadge(item.category)}`}>
                                    {item.category.toUpperCase()}
                                </span>
                            </div>
                            <p className="text-xs text-text-secondary leading-relaxed">{item.summary}</p>
                            <div className="flex items-center gap-2 text-[10px] text-text-muted">
                                <span>{item.source}</span>
                                {item.symbols && item.symbols.length > 0 && (
                                    <div className="flex gap-1">
                                        {item.symbols.map(s => (
                                            <span key={s} className="px-1 py-0.5 rounded bg-accent-neon/10 text-accent-neon font-mono">{s}</span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Footer */}
            <div className="text-center text-[10px] text-text-muted pt-1 border-t border-border-primary">
                {isLive ? 'Powered by Dexter AI Intelligence' : 'Curated market intelligence -- Connect API for live updates'}
            </div>
        </div>
    );
}
