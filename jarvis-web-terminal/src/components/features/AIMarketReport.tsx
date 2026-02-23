'use client';

import { useMemo } from 'react';
import {
    TrendingUp,
    TrendingDown,
    AlertTriangle,
    Activity,
    BarChart3,
    Clock,
    RefreshCw,
    Flame,
    Minus,
    ArrowUpRight,
    ArrowDownRight,
    Brain,
    Sparkles
} from 'lucide-react';
import { useSentimentData } from '@/hooks/useSentimentData';

// Market regime types matching /demo
type MarketRegimeType = 'BULL' | 'BEAR' | 'NEUTRAL' | 'VOLATILE';
type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'EXTREME';
type Momentum = 'STRONG UP' | 'UP' | 'NEUTRAL' | 'DOWN' | 'STRONG DOWN';
type Trend = 'BULLISH' | 'BEARISH' | 'NEUTRAL';

interface AIStrategy {
    recommendation: 'AGGRESSIVE' | 'MODERATE' | 'CAUTION ADVISED' | 'RISK OFF';
    advice: string;
}

// Helper functions for colors
function getRegimeColor(regime: MarketRegimeType): string {
    switch (regime) {
        case 'BULL': return 'text-accent-success bg-accent-success/20';
        case 'BEAR': return 'text-accent-error bg-accent-error/20';
        case 'NEUTRAL': return 'text-text-muted bg-bg-tertiary';
        case 'VOLATILE': return 'text-accent-neon bg-accent-neon/20';
    }
}

function getRegimeIcon(regime: MarketRegimeType) {
    switch (regime) {
        case 'BULL': return <TrendingUp className="w-4 h-4" />;
        case 'BEAR': return <TrendingDown className="w-4 h-4" />;
        case 'NEUTRAL': return <Minus className="w-4 h-4" />;
        case 'VOLATILE': return <Activity className="w-4 h-4" />;
    }
}

function getRiskColor(risk: RiskLevel): string {
    switch (risk) {
        case 'LOW': return 'text-accent-success bg-accent-success/20';
        case 'MEDIUM': return 'text-text-muted bg-bg-tertiary';
        case 'HIGH': return 'text-accent-error bg-accent-error/20';
        case 'EXTREME': return 'text-accent-error bg-accent-error/20';
    }
}

function getMomentumColor(momentum: Momentum): string {
    if (momentum.includes('UP')) return 'text-accent-success';
    if (momentum.includes('DOWN')) return 'text-accent-error';
    return 'text-text-muted';
}

function getMomentumIcon(momentum: Momentum) {
    if (momentum === 'STRONG UP') return <ArrowUpRight className="w-4 h-4 text-accent-success" />;
    if (momentum === 'UP') return <TrendingUp className="w-4 h-4 text-accent-success" />;
    if (momentum === 'STRONG DOWN') return <ArrowDownRight className="w-4 h-4 text-accent-error" />;
    if (momentum === 'DOWN') return <TrendingDown className="w-4 h-4 text-accent-error" />;
    return <Minus className="w-4 h-4 text-text-muted" />;
}

function getFearGreedColor(value: number): string {
    if (value >= 75) return 'text-accent-success';
    if (value >= 55) return 'text-accent-neon';
    if (value >= 45) return 'text-text-muted';
    if (value >= 25) return 'text-accent-error';
    return 'text-accent-error';
}

function getFearGreedLabel(value: number): string {
    if (value >= 75) return 'Extreme Greed';
    if (value >= 55) return 'Greed';
    if (value >= 45) return 'Neutral';
    if (value >= 25) return 'Fear';
    return 'Extreme Fear';
}

function getStrategyColor(rec: AIStrategy['recommendation']): string {
    switch (rec) {
        case 'AGGRESSIVE': return 'text-accent-success bg-accent-success/20 border-accent-success/30';
        case 'MODERATE': return 'text-accent-neon bg-accent-neon/20 border-accent-neon/30';
        case 'CAUTION ADVISED': return 'text-text-muted bg-bg-tertiary border-border-primary';
        case 'RISK OFF': return 'text-accent-error bg-accent-error/20 border-accent-error/30';
    }
}

function deriveMomentum(btcChange: number, solChange: number): Momentum {
    const avg = (btcChange + solChange) / 2;
    if (avg > 5) return 'STRONG UP';
    if (avg > 2) return 'UP';
    if (avg < -5) return 'STRONG DOWN';
    if (avg < -2) return 'DOWN';
    return 'NEUTRAL';
}

function deriveStrategy(regime: string, riskLevel: string, avgBuySellRatio: number): AIStrategy {
    if (regime === 'BEAR' || riskLevel === 'HIGH') {
        return {
            recommendation: avgBuySellRatio > 1.5 ? 'CAUTION ADVISED' : 'RISK OFF',
            advice: riskLevel === 'HIGH'
                ? 'Reduce sizes, tight stops. Wait for confirmation.'
                : 'Defensive positioning. Focus on blue chips only.'
        };
    }
    if (regime === 'BULL' && riskLevel === 'LOW') {
        return {
            recommendation: avgBuySellRatio > 2 ? 'AGGRESSIVE' : 'MODERATE',
            advice: avgBuySellRatio > 2
                ? 'Strong momentum. Size up on high-conviction plays.'
                : 'Trend is positive. Standard position sizing.'
        };
    }
    return {
        recommendation: 'MODERATE',
        advice: 'Mixed signals. Selective entries with defined risk.'
    };
}

export function AIMarketReport() {
    const {
        marketRegime,
        trendingTokens,
        stats,
        isLoading,
        lastUpdated,
        refresh,
        timeSinceUpdate,
    } = useSentimentData({ autoRefresh: true, refreshInterval: 5 * 60 * 1000 });

    // Derive display data from live sentiment
    const report = useMemo(() => {
        const regime = (marketRegime.regime || 'NEUTRAL') as MarketRegimeType;
        const riskLevel = (marketRegime.riskLevel === 'NORMAL' ? 'MEDIUM' : marketRegime.riskLevel || 'MEDIUM') as RiskLevel;
        const momentum = deriveMomentum(marketRegime.btcChange24h, marketRegime.solChange24h);

        const bullish = stats.bullishCount;
        const total = trendingTokens.length;
        const breadth = total > 0
            ? `${Math.round((bullish / total) * 100)}% up (${bullish}/${total})`
            : 'No data';

        // Fear & Greed approximation from buy/sell ratios and price changes
        const avgChange = trendingTokens.length > 0
            ? trendingTokens.reduce((sum, t) => sum + t.change24h, 0) / trendingTokens.length
            : 0;
        const fearGreed = Math.max(0, Math.min(100, 50 + avgChange * 2 + (stats.avgBuySellRatio - 1) * 15));

        const strategy = deriveStrategy(regime, riskLevel, stats.avgBuySellRatio);

        // Detect hot sectors from token names/symbols
        const sectorKeywords: Record<string, string[]> = {
            'AI': ['AI', 'GPT', 'AGENT', 'BOT', 'NEURAL'],
            'DeFi': ['SWAP', 'DEX', 'LEND', 'YIELD', 'FI'],
            'Memes': ['BONK', 'WIF', 'PEPE', 'DOGE', 'SHIB', 'FLOKI', 'MEME'],
            'Gaming': ['GAME', 'PLAY', 'NFT', 'META'],
            'L1/L2': ['SOL', 'ETH', 'AVAX', 'SUI'],
        };
        const detectedSectors = new Set<string>();
        for (const token of trendingTokens) {
            for (const [sector, keywords] of Object.entries(sectorKeywords)) {
                if (keywords.some(kw => token.symbol.toUpperCase().includes(kw) || token.name.toUpperCase().includes(kw))) {
                    detectedSectors.add(sector);
                }
            }
        }
        const hotSectors = detectedSectors.size > 0 ? Array.from(detectedSectors).slice(0, 4) : ['Mixed'];

        return {
            overview: { regime, risk: riskLevel, momentum, breadth, fearGreed: Math.round(fearGreed) },
            btc: {
                change24h: marketRegime.btcChange24h,
                trend: marketRegime.btcTrend as Trend,
            },
            sol: {
                change24h: marketRegime.solChange24h,
                trend: marketRegime.solTrend as Trend,
            },
            activity: {
                hotSectors,
                topGainer: stats.topGainer ? { symbol: stats.topGainer.symbol, change: stats.topGainer.change24h } : null,
                topLoser: stats.topLoser ? { symbol: stats.topLoser.symbol, change: stats.topLoser.change24h } : null,
            },
            strategy,
        };
    }, [marketRegime, trendingTokens, stats]);

    return (
        <div className="card-glass p-3 space-y-3">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Brain className="w-4 h-4 text-accent-neon" />
                    <span className="text-xs font-mono uppercase tracking-wider text-text-muted">AI MARKET REPORT</span>
                </div>
                <button
                    onClick={refresh}
                    disabled={isLoading}
                    className="p-2 rounded-lg bg-bg-tertiary hover:bg-bg-secondary transition-all"
                >
                    <RefreshCw className={`w-4 h-4 text-text-muted ${isLoading ? 'animate-spin' : ''}`} />
                </button>
            </div>

            {/* Loading State */}
            {isLoading && trendingTokens.length === 0 && (
                <div className="text-center py-8 font-mono text-text-muted animate-pulse">
                    SCANNING MARKETS...
                </div>
            )}

            {/* Market Overview */}
            <div className="p-3 rounded-lg bg-bg-tertiary/50 border border-border-primary space-y-2">
                <div className="flex items-center gap-2 mb-2">
                    <BarChart3 className="w-4 h-4 text-text-muted" />
                    <span className="text-xs font-mono text-text-muted uppercase">Market Overview</span>
                </div>

                <div className="grid grid-cols-2 gap-2">
                    {/* Regime */}
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-text-muted">Regime:</span>
                        <span className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-bold ${getRegimeColor(report.overview.regime)}`}>
                            {getRegimeIcon(report.overview.regime)}
                            {report.overview.regime}
                        </span>
                    </div>

                    {/* Risk */}
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-text-muted">Risk:</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${getRiskColor(report.overview.risk)}`}>
                            {report.overview.risk}
                        </span>
                    </div>

                    {/* Momentum */}
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-text-muted">Momentum:</span>
                        <span className={`flex items-center gap-1 text-xs font-mono ${getMomentumColor(report.overview.momentum)}`}>
                            {getMomentumIcon(report.overview.momentum)}
                            {report.overview.momentum}
                        </span>
                    </div>

                    {/* Breadth */}
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-text-muted">Breadth:</span>
                        <span className="text-xs font-mono text-text-secondary">{report.overview.breadth}</span>
                    </div>
                </div>

                {/* Fear & Greed */}
                <div className="flex items-center gap-2 pt-2 border-t border-border-primary">
                    <span className="text-xs text-text-muted">Fear/Greed:</span>
                    <span className={`text-lg font-mono font-bold ${getFearGreedColor(report.overview.fearGreed)}`}>
                        {report.overview.fearGreed}
                    </span>
                    <span className={`text-xs ${getFearGreedColor(report.overview.fearGreed)}`}>
                        ({getFearGreedLabel(report.overview.fearGreed)})
                    </span>
                </div>
            </div>

            {/* BTC & SOL */}
            <div className="grid grid-cols-2 gap-2">
                {/* Bitcoin */}
                <div className="p-3 rounded-lg bg-bg-tertiary/50 border border-border-primary">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-lg">&#8383;</span>
                        <span className="font-mono font-bold text-text-primary">Bitcoin (BTC)</span>
                    </div>
                    <div className="space-y-1 text-xs">
                        <div className="flex justify-between">
                            <span className="text-text-muted">24h:</span>
                            <span className={report.btc.change24h >= 0 ? 'text-accent-success' : 'text-accent-error'}>
                                {report.btc.change24h >= 0 ? '+' : ''}{report.btc.change24h.toFixed(1)}%
                            </span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-text-muted">Trend:</span>
                            <span className={report.btc.trend === 'BULLISH' ? 'text-accent-success' : report.btc.trend === 'BEARISH' ? 'text-accent-error' : 'text-text-muted'}>
                                {report.btc.trend}
                            </span>
                        </div>
                    </div>
                </div>

                {/* Solana */}
                <div className="p-3 rounded-lg bg-bg-tertiary/50 border border-border-primary">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-lg">&#9678;</span>
                        <span className="font-mono font-bold text-text-primary">Solana (SOL)</span>
                    </div>
                    <div className="space-y-1 text-xs">
                        <div className="flex justify-between">
                            <span className="text-text-muted">24h:</span>
                            <span className={report.sol.change24h >= 0 ? 'text-accent-success' : 'text-accent-error'}>
                                {report.sol.change24h >= 0 ? '+' : ''}{report.sol.change24h.toFixed(1)}%
                            </span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-text-muted">Trend:</span>
                            <span className={report.sol.trend === 'BULLISH' ? 'text-accent-success' : report.sol.trend === 'BEARISH' ? 'text-accent-error' : 'text-text-muted'}>
                                {report.sol.trend}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Market Activity */}
            <div className="p-3 rounded-lg bg-bg-tertiary/50 border border-border-primary">
                <div className="flex items-center gap-2 mb-2">
                    <Flame className="w-4 h-4 text-accent-error" />
                    <span className="text-xs font-mono text-text-muted uppercase">Market Activity</span>
                </div>

                <div className="space-y-2 text-xs">
                    <div className="flex items-center gap-2">
                        <span className="text-text-muted">Hot Sectors:</span>
                        <div className="flex gap-1 flex-wrap">
                            {report.activity.hotSectors.map(sector => (
                                <span key={sector} className="px-2 py-0.5 rounded bg-accent-neon/20 text-accent-neon font-mono">
                                    {sector}
                                </span>
                            ))}
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <span className="text-text-muted">Top Gainer:</span>
                        {report.activity.topGainer ? (
                            <span className="text-accent-success font-mono font-bold">
                                {report.activity.topGainer.symbol} +{report.activity.topGainer.change.toFixed(1)}%
                            </span>
                        ) : (
                            <span className="text-text-muted italic">Scanning...</span>
                        )}
                    </div>

                    <div className="flex items-center gap-2">
                        <span className="text-text-muted">Top Loser:</span>
                        {report.activity.topLoser ? (
                            <span className="text-accent-error font-mono font-bold">
                                {report.activity.topLoser.symbol} {report.activity.topLoser.change.toFixed(1)}%
                            </span>
                        ) : (
                            <span className="text-text-muted italic">Scanning...</span>
                        )}
                    </div>
                </div>
            </div>

            {/* AI Strategy */}
            <div className={`p-3 rounded-lg border ${getStrategyColor(report.strategy.recommendation)}`}>
                <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="w-4 h-4" />
                    <span className="text-xs font-mono uppercase">AI Strategy</span>
                </div>
                <div className="flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5" />
                    <span className="font-mono font-bold">{report.strategy.recommendation}</span>
                </div>
                <p className="text-xs mt-1 opacity-80">{report.strategy.advice}</p>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between text-[10px] text-text-muted pt-2 border-t border-border-primary">
                <span>Live data from DexScreener + CoinGecko</span>
                <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {timeSinceUpdate < 1 ? 'Just now' : `${timeSinceUpdate}m ago`}
                </span>
            </div>
        </div>
    );
}
