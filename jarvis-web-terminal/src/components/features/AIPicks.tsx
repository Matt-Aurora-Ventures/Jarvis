'use client';

import { useState, useMemo } from 'react';
import { useSentimentData } from '@/hooks/useSentimentData';
import { ConvictionPick } from '@/types/sentiment-types';
import {
    Sparkles,
    AlertTriangle,
    RefreshCw,
    Target,
    Shield,
    Zap,
    Clock,
    ExternalLink,
    ChevronRight,
    Star,
    Brain,
    BarChart3,
    Flame
} from 'lucide-react';

interface AIPick {
    id: string;
    symbol: string;
    name: string;
    tokenAddress: string;
    recommendation: 'strong_buy' | 'buy' | 'hold' | 'sell' | 'strong_sell';
    sentimentScore: number;
    confidenceLevel: number;
    reasoning: string[];
    riskLevel: 'low' | 'medium' | 'high';
    suggestedEntry: number;
    suggestedTP: number;
    suggestedSL: number;
    timeHorizon: '1h' | '4h' | '1d' | '1w';
    generatedAt: number;
    sources: string[];
}

interface PickPerformance {
    pickId: string;
    actualOutcome: 'hit_tp' | 'hit_sl' | 'pending' | 'expired';
    actualReturn?: number;
    closedAt?: number;
}

const RECOMMENDATION_COLORS = {
    strong_buy: { bg: 'bg-accent-success/20', text: 'text-accent-success', border: 'border-accent-success/50' },
    buy: { bg: 'bg-accent-success/20', text: 'text-accent-success', border: 'border-accent-success/50' },
    hold: { bg: 'bg-accent-warning/20', text: 'text-text-muted', border: 'border-accent-warning/50' },
    sell: { bg: 'bg-accent-warning/20', text: 'text-accent-warning', border: 'border-accent-warning/50' },
    strong_sell: { bg: 'bg-accent-danger/20', text: 'text-accent-danger', border: 'border-accent-danger/50' },
};

const RISK_COLORS = {
    low: 'text-accent-success',
    medium: 'text-text-muted',
    high: 'text-accent-danger',
};

function convictionToAIPick(pick: ConvictionPick, index: number): AIPick {
    const score = pick.convictionScore;
    let recommendation: AIPick['recommendation'] = 'hold';
    if (score >= 80) recommendation = 'strong_buy';
    else if (score >= 60) recommendation = 'buy';
    else if (score >= 40) recommendation = 'hold';
    else if (score >= 20) recommendation = 'sell';
    else recommendation = 'strong_sell';

    let riskLevel: AIPick['riskLevel'] = 'medium';
    if (pick.grade === 'A+' || pick.grade === 'A') riskLevel = 'low';
    else if (pick.grade === 'D' || pick.grade === 'F') riskLevel = 'high';

    return {
        id: `pick-${index}`,
        symbol: pick.symbol,
        name: pick.symbol,
        tokenAddress: pick.contractAddress || '',
        recommendation,
        sentimentScore: score,
        confidenceLevel: Math.min(100, score + 5),
        reasoning: [pick.reasoning],
        riskLevel,
        suggestedEntry: pick.entryPrice,
        suggestedTP: pick.targets.medium.takeProfit,
        suggestedSL: pick.targets.medium.stopLoss,
        timeHorizon: '4h',
        generatedAt: Date.now(),
        sources: ['DexScreener', 'Buy/Sell Analysis'],
    };
}

export function AIPicks() {
    const {
        convictionPicks,
        isLoading: dataLoading,
        refresh,
    } = useSentimentData({ autoRefresh: true, refreshInterval: 5 * 60 * 1000 });

    const [selectedPick, setSelectedPick] = useState<AIPick | null>(null);
    const [refreshing, setRefreshing] = useState(false);

    const picks = useMemo(
        () => convictionPicks.map((cp, i) => convictionToAIPick(cp, i)),
        [convictionPicks]
    );

    const loading = dataLoading && picks.length === 0;

    const handleRefresh = async () => {
        setRefreshing(true);
        refresh();
        await new Promise(r => setTimeout(r, 2000));
        setRefreshing(false);
    };

    // Load performance history from localStorage
    const [performance] = useState<PickPerformance[]>(() => {
        if (typeof window === 'undefined') return [];
        try {
            const saved = localStorage.getItem('jarvis_pick_performance');
            return saved ? JSON.parse(saved) : [];
        } catch { return []; }
    });

    // Calculate pick accuracy
    const accuracy = performance.length > 0
        ? (performance.filter(p => p.actualOutcome === 'hit_tp').length / performance.length) * 100
        : 0;

    return (
        <div className="card-glass overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-border-primary/30">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-neon/30 to-purple-500/30 flex items-center justify-center">
                            <Sparkles className="w-5 h-5 text-accent-neon" />
                        </div>
                        <div>
                            <h3 className="font-display font-bold text-lg text-text-primary">
                                AI Trading Picks
                            </h3>
                            <p className="text-xs text-text-muted flex items-center gap-1">
                                <Brain className="w-3 h-3" />
                                Grok + Dexter Analysis
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        {/* Accuracy Badge */}
                        {performance.length >= 5 && (
                            <div className={`
                                px-2 py-1 rounded-lg text-xs font-mono flex items-center gap-1
                                ${accuracy >= 60 ? 'bg-accent-success/20 text-accent-success' :
                                    accuracy >= 40 ? 'bg-accent-warning/20 text-text-muted' :
                                        'bg-accent-danger/20 text-accent-danger'}
                            `}>
                                <Target className="w-3 h-3" />
                                {accuracy.toFixed(0)}% accuracy
                            </div>
                        )}

                        <button
                            onClick={handleRefresh}
                            disabled={refreshing}
                            className="p-2 rounded-lg hover:bg-bg-secondary/50 transition-colors"
                        >
                            <RefreshCw className={`w-4 h-4 text-text-muted ${refreshing ? 'animate-spin' : ''}`} />
                        </button>
                    </div>
                </div>
            </div>

            {/* Picks List */}
            <div className="divide-y divide-border-primary/20">
                {loading ? (
                    <div className="p-8 text-center">
                        <Brain className="w-8 h-8 text-accent-neon animate-pulse mx-auto mb-2" />
                        <p className="text-sm text-text-muted">Analyzing markets...</p>
                    </div>
                ) : picks.length === 0 ? (
                    <div className="p-8 text-center">
                        <AlertTriangle className="w-12 h-12 text-text-muted mx-auto mb-3 opacity-50" />
                        <p className="text-text-muted">No picks available</p>
                    </div>
                ) : (
                    picks.map((pick) => (
                        <PickCard
                            key={pick.id}
                            pick={pick}
                            onSelect={() => setSelectedPick(pick)}
                            isSelected={selectedPick?.id === pick.id}
                        />
                    ))
                )}
            </div>

            {/* Selected Pick Detail */}
            {selectedPick && (
                <div className="p-4 border-t border-border-primary/30 bg-bg-secondary/30">
                    <PickDetail pick={selectedPick} onClose={() => setSelectedPick(null)} />
                </div>
            )}

            {/* Disclaimer */}
            <div className="p-3 border-t border-border-primary/30 bg-bg-secondary/20">
                <p className="text-[10px] text-text-muted text-center">
                    AI picks are for informational purposes only. Always DYOR. Past performance ≠ future results.
                </p>
            </div>
        </div>
    );
}

function PickCard({ pick, onSelect, isSelected }: { pick: AIPick; onSelect: () => void; isSelected: boolean }) {
    const colors = RECOMMENDATION_COLORS[pick.recommendation];

    return (
        <button
            onClick={onSelect}
            className={`
                w-full p-4 text-left hover:bg-bg-secondary/30 transition-all
                ${isSelected ? 'bg-bg-secondary/40 border-l-2 border-accent-neon' : ''}
            `}
        >
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    {/* Recommendation Badge */}
                    <div className={`
                        px-2 py-1 rounded text-xs font-mono font-bold uppercase
                        ${colors.bg} ${colors.text} ${colors.border} border
                    `}>
                        {pick.recommendation === 'strong_buy' ? 'STRONG BUY' :
                            pick.recommendation === 'strong_sell' ? 'STRONG SELL' :
                                pick.recommendation.toUpperCase()}
                    </div>

                    <div>
                        <div className="flex items-center gap-2">
                            <span className="font-display font-bold text-text-primary">{pick.symbol}</span>
                            <span className="text-xs text-text-muted">{pick.name}</span>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                            <span className={`text-xs ${pick.sentimentScore >= 60 ? 'text-accent-success' : pick.sentimentScore >= 40 ? 'text-text-muted' : 'text-accent-danger'}`}>
                                Sentiment: {pick.sentimentScore}
                            </span>
                            <span className="text-xs text-text-muted">•</span>
                            <span className={`text-xs ${RISK_COLORS[pick.riskLevel]}`}>
                                {pick.riskLevel.toUpperCase()} RISK
                            </span>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {/* Confidence */}
                    <div className="text-right">
                        <p className="text-xs text-text-muted">Confidence</p>
                        <p className={`font-mono font-bold ${
                            pick.confidenceLevel >= 75 ? 'text-accent-success' :
                                pick.confidenceLevel >= 50 ? 'text-text-muted' : 'text-text-muted'
                        }`}>
                            {pick.confidenceLevel}%
                        </p>
                    </div>

                    <ChevronRight className="w-4 h-4 text-text-muted" />
                </div>
            </div>

            {/* Quick Stats */}
            <div className="flex items-center gap-4 mt-3 text-xs text-text-muted">
                <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {pick.timeHorizon}
                </span>
                <span className="flex items-center gap-1">
                    <Target className="w-3 h-3 text-accent-success" />
                    TP: +{(((pick.suggestedTP - pick.suggestedEntry) / pick.suggestedEntry) * 100).toFixed(0)}%
                </span>
                <span className="flex items-center gap-1">
                    <Shield className="w-3 h-3 text-accent-danger" />
                    SL: -{(((pick.suggestedEntry - pick.suggestedSL) / pick.suggestedEntry) * 100).toFixed(0)}%
                </span>
            </div>
        </button>
    );
}

function PickDetail({ pick, onClose }: { pick: AIPick; onSelect?: () => void; onClose: () => void }) {
    const formatPrice = (price: number) => {
        if (price < 0.0001) return price.toExponential(4);
        if (price < 1) return price.toFixed(6);
        return price.toFixed(2);
    };

    const tpPercent = ((pick.suggestedTP - pick.suggestedEntry) / pick.suggestedEntry) * 100;
    const slPercent = ((pick.suggestedEntry - pick.suggestedSL) / pick.suggestedEntry) * 100;

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h4 className="font-display font-bold text-lg text-text-primary flex items-center gap-2">
                    <Flame className="w-5 h-5 text-accent-neon" />
                    {pick.symbol} Analysis
                </h4>
                <button
                    onClick={onClose}
                    className="text-xs text-text-muted hover:text-text-primary"
                >
                    Close
                </button>
            </div>

            {/* Reasoning */}
            <div className="space-y-2">
                <p className="text-xs text-text-muted font-mono">WHY THIS PICK</p>
                <ul className="space-y-1">
                    {pick.reasoning.map((reason, i) => (
                        <li key={i} className="text-sm text-text-secondary flex items-start gap-2">
                            <Star className="w-3 h-3 text-accent-neon shrink-0 mt-1" />
                            {reason}
                        </li>
                    ))}
                </ul>
            </div>

            {/* Trade Levels */}
            <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-lg bg-bg-secondary/30 text-center">
                    <p className="text-[10px] text-text-muted mb-1">ENTRY</p>
                    <p className="font-mono font-bold text-text-primary">${formatPrice(pick.suggestedEntry)}</p>
                </div>
                <div className="p-3 rounded-lg bg-accent-success/10 border border-accent-success/30 text-center">
                    <p className="text-[10px] text-accent-success mb-1">TAKE PROFIT</p>
                    <p className="font-mono font-bold text-accent-success">${formatPrice(pick.suggestedTP)}</p>
                    <p className="text-[10px] text-accent-success">+{tpPercent.toFixed(0)}%</p>
                </div>
                <div className="p-3 rounded-lg bg-accent-danger/10 border border-accent-danger/30 text-center">
                    <p className="text-[10px] text-accent-danger mb-1">STOP LOSS</p>
                    <p className="font-mono font-bold text-accent-danger">${formatPrice(pick.suggestedSL)}</p>
                    <p className="text-[10px] text-accent-danger">-{slPercent.toFixed(0)}%</p>
                </div>
            </div>

            {/* Sources */}
            <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-text-muted">Sources:</span>
                {pick.sources.map((source, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-bg-secondary/50 text-text-secondary">
                        {source}
                    </span>
                ))}
            </div>

            {/* Action Buttons */}
            <div className="flex gap-2">
                <a
                    href={`/trade?token=${pick.tokenAddress}`}
                    className="flex-1 px-4 py-2 bg-accent-neon text-black font-bold rounded-lg text-center hover:bg-accent-neon/80 transition-colors flex items-center justify-center gap-2"
                >
                    <Zap className="w-4 h-4" />
                    Trade Now
                </a>
                <a
                    href={`https://birdeye.so/token/${pick.tokenAddress}?chain=solana`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-4 py-2 bg-bg-secondary/50 border border-border-primary/50 rounded-lg hover:bg-bg-secondary transition-colors flex items-center gap-2"
                >
                    <BarChart3 className="w-4 h-4" />
                    Chart
                    <ExternalLink className="w-3 h-3" />
                </a>
            </div>
        </div>
    );
}

export default AIPicks;
