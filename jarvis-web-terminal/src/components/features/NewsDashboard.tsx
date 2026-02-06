'use client';

import { useState, useEffect, useCallback } from 'react';
import { getDexterIntelClient, MarketNews, MarketRegime, SectorAnalysis, DexterIntelClient } from '@/lib/dexter-intel';
import {
    Newspaper,
    TrendingUp,
    TrendingDown,
    AlertTriangle,
    Globe,
    BarChart3,
    Activity,
    RefreshCw,
    ChevronRight,
    Zap,
    Clock,
    Filter,
    Sparkles,
    Building2,
    Coins,
    Scale,
    Code,
    ArrowUpRight
} from 'lucide-react';

type NewsCategory = 'all' | 'crypto' | 'stocks' | 'macro' | 'regulatory' | 'technical';

const CATEGORY_ICONS: Record<NewsCategory, React.ReactNode> = {
    all: <Globe className="w-3 h-3" />,
    crypto: <Coins className="w-3 h-3" />,
    stocks: <Building2 className="w-3 h-3" />,
    macro: <Activity className="w-3 h-3" />,
    regulatory: <Scale className="w-3 h-3" />,
    technical: <Code className="w-3 h-3" />,
};

const SENTIMENT_COLORS = {
    bullish: { bg: 'bg-accent-success/10', text: 'text-accent-success', border: 'border-accent-success/30' },
    neutral: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/30' },
    bearish: { bg: 'bg-accent-danger/10', text: 'text-accent-danger', border: 'border-accent-danger/30' },
};

export function NewsDashboard() {
    const [news, setNews] = useState<MarketNews[]>([]);
    const [regime, setRegime] = useState<MarketRegime | null>(null);
    const [sectors, setSectors] = useState<SectorAnalysis[]>([]);
    const [loading, setLoading] = useState(true);
    const [category, setCategory] = useState<NewsCategory>('all');
    const [refreshing, setRefreshing] = useState(false);

    // Fetch data
    const fetchData = useCallback(async () => {
        const client = getDexterIntelClient();

        try {
            const [newsData, regimeData] = await Promise.all([
                client.getMarketNews(category === 'all' ? undefined : category),
                client.getMarketRegime(),
            ]);

            setNews(newsData);
            setRegime(regimeData);

            // Fetch sector data
            const sectorNames = ['DeFi', 'NFT', 'Gaming', 'AI'];
            const sectorResults = await Promise.all(
                sectorNames.map(s => client.analyzeSector(s))
            );
            setSectors(sectorResults.filter(Boolean) as SectorAnalysis[]);

        } catch (error) {
            console.error('Failed to fetch intel:', error);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [category]);

    // Initial fetch
    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Manual refresh
    const handleRefresh = useCallback(() => {
        setRefreshing(true);
        // Clear cache for fresh data
        getDexterIntelClient().clearCache();
        fetchData();
    }, [fetchData]);

    // Filter news by category
    const filteredNews = category === 'all'
        ? news
        : news.filter(n => n.category === category);

    return (
        <div className="card-glass overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-theme-border/30">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-accent-neon/20 flex items-center justify-center">
                            <Newspaper className="w-5 h-5 text-accent-neon" />
                        </div>
                        <div>
                            <h3 className="font-display font-bold text-lg text-text-primary">
                                Market Intelligence
                            </h3>
                            <p className="text-xs text-text-muted flex items-center gap-1">
                                <Sparkles className="w-3 h-3" />
                                Powered by Dexter AI
                            </p>
                        </div>
                    </div>

                    <button
                        onClick={handleRefresh}
                        disabled={refreshing}
                        className="p-2 rounded-lg hover:bg-theme-dark/50 transition-colors"
                    >
                        <RefreshCw className={`w-4 h-4 text-text-muted ${refreshing ? 'animate-spin' : ''}`} />
                    </button>
                </div>

                {/* Market Regime Banner */}
                {regime && (
                    <div className={`
                        mt-4 p-3 rounded-xl border flex items-center justify-between
                        ${regime.regime === 'risk_on' ? 'bg-accent-success/10 border-accent-success/30' :
                            regime.regime === 'risk_off' ? 'bg-accent-danger/10 border-accent-danger/30' :
                                regime.regime === 'volatile' ? 'bg-yellow-500/10 border-yellow-500/30' :
                                    'bg-theme-dark/50 border-theme-border/30'}
                    `}>
                        <div className="flex items-center gap-3">
                            <div className={`
                                w-3 h-3 rounded-full animate-pulse
                                ${regime.regime === 'risk_on' ? 'bg-accent-success' :
                                    regime.regime === 'risk_off' ? 'bg-accent-danger' :
                                        regime.regime === 'volatile' ? 'bg-yellow-400' :
                                            'bg-text-muted'}
                            `} />
                            <div>
                                <p className="text-xs text-text-muted">MARKET REGIME</p>
                                <p className={`font-mono font-bold uppercase
                                    ${regime.regime === 'risk_on' ? 'text-accent-success' :
                                        regime.regime === 'risk_off' ? 'text-accent-danger' :
                                            regime.regime === 'volatile' ? 'text-yellow-400' :
                                                'text-text-primary'}
                                `}>
                                    {regime.regime.replace('_', ' ')}
                                </p>
                            </div>
                        </div>
                        <div className="text-right">
                            <p className="text-xs text-text-muted">CONFIDENCE</p>
                            <p className="font-mono font-bold text-text-primary">{regime.confidence}%</p>
                        </div>
                    </div>
                )}

                {/* Regime Indicators */}
                {regime && (
                    <div className="grid grid-cols-4 gap-2 mt-3">
                        <div className="p-2 rounded bg-theme-dark/30 text-center">
                            <p className="text-[10px] text-text-muted">BTC</p>
                            <p className={`text-xs font-mono font-bold ${regime.indicators.btcTrend === 'up' ? 'text-accent-success' :
                                regime.indicators.btcTrend === 'down' ? 'text-accent-danger' : 'text-text-muted'
                                }`}>
                                {regime.indicators.btcTrend.toUpperCase()}
                            </p>
                        </div>
                        <div className="p-2 rounded bg-theme-dark/30 text-center">
                            <p className="text-[10px] text-text-muted">SOL</p>
                            <p className={`text-xs font-mono font-bold ${regime.indicators.solTrend === 'up' ? 'text-accent-success' :
                                regime.indicators.solTrend === 'down' ? 'text-accent-danger' : 'text-text-muted'
                                }`}>
                                {regime.indicators.solTrend.toUpperCase()}
                            </p>
                        </div>
                        <div className="p-2 rounded bg-theme-dark/30 text-center">
                            <p className="text-[10px] text-text-muted">VOLUME</p>
                            <p className="text-xs font-mono font-bold text-text-primary">
                                {regime.indicators.volumeTrend.charAt(0).toUpperCase()}
                            </p>
                        </div>
                        <div className="p-2 rounded bg-theme-dark/30 text-center">
                            <p className="text-[10px] text-text-muted">SENTIMENT</p>
                            <p className={`text-xs font-mono font-bold ${regime.indicators.sentimentIndex >= 60 ? 'text-accent-success' :
                                regime.indicators.sentimentIndex >= 40 ? 'text-yellow-400' : 'text-accent-danger'
                                }`}>
                                {regime.indicators.sentimentIndex}
                            </p>
                        </div>
                    </div>
                )}

                {/* Recommendation */}
                {regime?.recommendation && (
                    <div className="mt-3 p-2 rounded bg-theme-dark/30 flex items-start gap-2">
                        <Zap className="w-4 h-4 text-accent-neon shrink-0 mt-0.5" />
                        <p className="text-xs text-text-secondary">{regime.recommendation}</p>
                    </div>
                )}
            </div>

            {/* Sectors Strip */}
            {sectors.length > 0 && (
                <div className="px-4 py-3 border-b border-theme-border/30 overflow-x-auto">
                    <div className="flex gap-2">
                        {sectors.map(sector => (
                            <div
                                key={sector.sector}
                                className={`
                                    shrink-0 px-3 py-2 rounded-lg border
                                    ${sector.trend === 'bullish' ? 'bg-accent-success/10 border-accent-success/30' :
                                        sector.trend === 'bearish' ? 'bg-accent-danger/10 border-accent-danger/30' :
                                            'bg-theme-dark/30 border-theme-border/30'}
                                `}
                            >
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-xs font-mono font-bold text-text-primary">{sector.sector}</span>
                                    {sector.trend === 'bullish' ? (
                                        <TrendingUp className="w-3 h-3 text-accent-success" />
                                    ) : sector.trend === 'bearish' ? (
                                        <TrendingDown className="w-3 h-3 text-accent-danger" />
                                    ) : null}
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className={`text-lg font-mono font-bold
                                        ${sector.score >= 65 ? 'text-accent-success' :
                                            sector.score >= 45 ? 'text-yellow-400' : 'text-accent-danger'}
                                    `}>
                                        {sector.score}
                                    </span>
                                    <div className="flex flex-wrap gap-1">
                                        {sector.topTokens.slice(0, 2).map(token => (
                                            <span key={token} className="text-[10px] px-1.5 py-0.5 rounded bg-theme-dark/50 text-text-muted">
                                                {token}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Category Filter */}
            <div className="px-4 py-3 border-b border-theme-border/30">
                <div className="flex gap-1 overflow-x-auto pb-1">
                    {(['all', 'crypto', 'stocks', 'macro', 'regulatory', 'technical'] as NewsCategory[]).map(cat => (
                        <button
                            key={cat}
                            onClick={() => setCategory(cat)}
                            className={`
                                px-3 py-1.5 rounded-lg flex items-center gap-1.5 text-xs font-mono whitespace-nowrap transition-all
                                ${category === cat
                                    ? 'bg-accent-neon/20 text-accent-neon'
                                    : 'bg-theme-dark/30 text-text-muted hover:bg-theme-dark/50'}
                            `}
                        >
                            {CATEGORY_ICONS[cat]}
                            {cat.charAt(0).toUpperCase() + cat.slice(1)}
                        </button>
                    ))}
                </div>
            </div>

            {/* News Feed */}
            <div className="max-h-[400px] overflow-y-auto">
                {loading ? (
                    <div className="text-center py-12">
                        <Activity className="w-8 h-8 text-accent-neon animate-pulse mx-auto mb-2" />
                        <p className="text-sm text-text-muted">Loading intelligence...</p>
                    </div>
                ) : filteredNews.length === 0 ? (
                    <div className="text-center py-12">
                        <Newspaper className="w-12 h-12 text-text-muted mx-auto mb-3 opacity-30" />
                        <p className="text-text-muted">No news available</p>
                    </div>
                ) : (
                    filteredNews.map(item => (
                        <NewsItem key={item.id} news={item} />
                    ))
                )}
            </div>
        </div>
    );
}

function NewsItem({ news }: { news: MarketNews }) {
    const colors = SENTIMENT_COLORS[news.sentiment];
    const timeAgo = Math.floor((Date.now() - news.timestamp) / (1000 * 60));

    return (
        <div className={`
            p-4 border-b border-theme-border/20 hover:bg-theme-dark/20 transition-colors cursor-pointer
        `}>
            <div className="flex items-start gap-3">
                {/* Sentiment Indicator */}
                <div className={`
                    w-8 h-8 rounded-lg shrink-0 flex items-center justify-center
                    ${colors.bg} ${colors.border} border
                `}>
                    {news.sentiment === 'bullish' ? (
                        <TrendingUp className={`w-4 h-4 ${colors.text}`} />
                    ) : news.sentiment === 'bearish' ? (
                        <TrendingDown className={`w-4 h-4 ${colors.text}`} />
                    ) : (
                        <Activity className={`w-4 h-4 ${colors.text}`} />
                    )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    <h4 className="font-display font-bold text-sm text-text-primary mb-1 line-clamp-2">
                        {news.title}
                    </h4>
                    <p className="text-xs text-text-muted line-clamp-2 mb-2">
                        {news.summary}
                    </p>

                    {/* Meta */}
                    <div className="flex items-center gap-3 text-[10px] text-text-muted">
                        <span className="flex items-center gap-1">
                            {CATEGORY_ICONS[news.category as NewsCategory]}
                            {news.category}
                        </span>
                        <span>{news.source}</span>
                        <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {timeAgo}m ago
                        </span>
                        <span className={`px-1.5 py-0.5 rounded ${colors.bg} ${colors.text}`}>
                            {news.sentiment}
                        </span>
                    </div>

                    {/* Symbols */}
                    {news.symbols && news.symbols.length > 0 && (
                        <div className="flex gap-1 mt-2">
                            {news.symbols.map(symbol => (
                                <span
                                    key={symbol}
                                    className="text-[10px] px-2 py-0.5 rounded-full bg-theme-dark/50 text-accent-neon font-mono"
                                >
                                    ${symbol}
                                </span>
                            ))}
                        </div>
                    )}
                </div>

                {/* Relevance */}
                <div className="text-right shrink-0">
                    <p className="text-[10px] text-text-muted">Relevance</p>
                    <p className={`font-mono font-bold text-sm
                        ${news.relevance >= 70 ? 'text-accent-success' :
                            news.relevance >= 50 ? 'text-yellow-400' : 'text-text-muted'}
                    `}>
                        {news.relevance}
                    </p>
                </div>
            </div>
        </div>
    );
}

export default NewsDashboard;
