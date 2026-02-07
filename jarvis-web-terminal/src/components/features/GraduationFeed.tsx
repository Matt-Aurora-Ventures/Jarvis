'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useBagsGraduations } from '@/hooks/useBagsGraduations';
import { useAlgoParams } from '@/components/features/AlgoConfig';
import { useToast } from '@/components/ui/Toast';
import { BagsGraduation, getScoreTier, TIER_COLORS, ScoreTier } from '@/lib/bags-api';
import { getGrokSentimentClient, TokenSentiment } from '@/lib/grok-sentiment';
import { TrendingUp, TrendingDown, Zap, Clock, Users, Droplets, Activity, Target, Settings2, ChevronDown, ChevronUp, Rocket } from 'lucide-react';

// Historical performance data by tier (would be populated from backend)
interface TierPerformance {
    tier: ScoreTier;
    avgReturn24h: number;
    avgReturn1h: number;
    winRate: number;
    sampleSize: number;
}

const DEMO_TIER_PERFORMANCE: TierPerformance[] = [
    { tier: 'exceptional', avgReturn24h: 142, avgReturn1h: 28, winRate: 72, sampleSize: 47 },
    { tier: 'strong', avgReturn24h: 68, avgReturn1h: 15, winRate: 58, sampleSize: 156 },
    { tier: 'average', avgReturn24h: 12, avgReturn1h: 4, winRate: 42, sampleSize: 289 },
    { tier: 'weak', avgReturn24h: -18, avgReturn1h: -3, winRate: 28, sampleSize: 198 },
    { tier: 'poor', avgReturn24h: -45, avgReturn1h: -12, winRate: 15, sampleSize: 87 },
];

interface SnipeConfig {
    enabled: boolean;
    minScore: number;
    maxPositionSol: number;
    autoBuy: boolean;
    autoTP: number;
    autoSL: number;
    minLiquidity: number;
}

// Store snipe config in localStorage
const SNIPE_CONFIG_KEY = 'jarvis_snipe_config';

function loadSnipeConfig(): SnipeConfig {
    if (typeof window === 'undefined') {
        return {
            enabled: false,
            minScore: 70,
            maxPositionSol: 0.5,
            autoBuy: false,
            autoTP: 50,
            autoSL: 20,
            minLiquidity: 10000,
        };
    }
    const stored = localStorage.getItem(SNIPE_CONFIG_KEY);
    if (stored) {
        try {
            return JSON.parse(stored);
        } catch {
            // fall through
        }
    }
    return {
        enabled: false,
        minScore: 70,
        maxPositionSol: 0.5,
        autoBuy: false,
        autoTP: 50,
        autoSL: 20,
        minLiquidity: 10000,
    };
}

function saveSnipeConfig(config: SnipeConfig) {
    if (typeof window !== 'undefined') {
        localStorage.setItem(SNIPE_CONFIG_KEY, JSON.stringify(config));
    }
}

interface GraduationCardProps {
    graduation: BagsGraduation;
    sentiment?: TokenSentiment;
    onSnipe: (grad: BagsGraduation) => void;
    algoParams: ReturnType<typeof useAlgoParams>;
}

function GraduationCard({ graduation, sentiment, onSnipe, algoParams }: GraduationCardProps) {
    const tier = getScoreTier(graduation.score);
    const colors = TIER_COLORS[tier];
    const timeSinceGrad = Math.floor((Date.now() / 1000 - graduation.graduation_time) / 60);

    const meetsAlgoThreshold = useMemo(() => {
        const { params } = algoParams;
        return (
            graduation.score >= params.graduationScoreCutoff &&
            graduation.market_cap >= params.minLiquidityUsd
        );
    }, [graduation, algoParams]);

    const historicalPerf = DEMO_TIER_PERFORMANCE.find(p => p.tier === tier);

    return (
        <div className={`
            relative p-4 rounded-xl border transition-all duration-300
            ${colors.bg} ${colors.border}
            hover:scale-[1.02] hover:shadow-lg
            ${meetsAlgoThreshold ? 'ring-2 ring-accent-neon/50' : ''}
        `}>
            {/* Algo Match Indicator */}
            {meetsAlgoThreshold && (
                <div className="absolute -top-2 -right-2 w-6 h-6 bg-accent-neon rounded-full flex items-center justify-center animate-pulse">
                    <Target className="w-3 h-3 text-black" />
                </div>
            )}

            {/* Header */}
            <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                    {graduation.logo_uri ? (
                        <img
                            src={graduation.logo_uri}
                            alt={graduation.symbol}
                            className="w-10 h-10 rounded-full bg-bg-secondary"
                        />
                    ) : (
                        <div className="w-10 h-10 rounded-full bg-bg-secondary flex items-center justify-center">
                            <span className="text-lg font-bold">{graduation.symbol[0]}</span>
                        </div>
                    )}
                    <div>
                        <h4 className="font-display font-bold text-lg text-text-primary">
                            {graduation.symbol}
                        </h4>
                        <p className="text-xs text-text-muted truncate max-w-[120px]">
                            {graduation.name}
                        </p>
                    </div>
                </div>

                {/* Score Badge */}
                <div className={`
                    px-3 py-1 rounded-full font-mono font-bold text-sm
                    ${colors.bg} ${colors.text} ${colors.border} border
                `}>
                    {graduation.score}
                </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 gap-2 mb-3">
                <div className="flex items-center gap-2 text-xs">
                    <Clock className="w-3 h-3 text-text-muted" />
                    <span className="text-text-muted">
                        {timeSinceGrad < 60 ? `${timeSinceGrad}m ago` : `${Math.floor(timeSinceGrad / 60)}h ago`}
                    </span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                    <Droplets className="w-3 h-3 text-accent-neon" />
                    <span className="text-text-muted">
                        ${(graduation.market_cap / 1000).toFixed(0)}k
                    </span>
                </div>
            </div>

            {/* Score Breakdown */}
            <div className="space-y-1 mb-3">
                <ScoreBar label="Bonding" value={graduation.bonding_curve_score} />
                <ScoreBar label="Holders" value={graduation.holder_distribution_score} />
                <ScoreBar label="Liquidity" value={graduation.liquidity_score} />
                <ScoreBar label="Social" value={graduation.social_score} />
            </div>

            {/* Sentiment (if available) */}
            {sentiment && (
                <div className="flex items-center justify-between py-2 border-t border-border-primary/30">
                    <span className="text-xs text-text-muted">AI Sentiment</span>
                    <div className="flex items-center gap-2">
                        <span className={`
                            text-sm font-mono font-bold
                            ${sentiment.score >= 65 ? 'text-accent-success' :
                                sentiment.score >= 45 ? 'text-text-muted' : 'text-accent-danger'}
                        `}>
                            {sentiment.score}
                        </span>
                        {sentiment.score >= 65 ? (
                            <TrendingUp className="w-3 h-3 text-accent-success" />
                        ) : sentiment.score < 45 ? (
                            <TrendingDown className="w-3 h-3 text-accent-danger" />
                        ) : null}
                    </div>
                </div>
            )}

            {/* Historical Performance */}
            {historicalPerf && (
                <div className="py-2 border-t border-border-primary/30 text-xs">
                    <div className="flex items-center justify-between text-text-muted mb-1">
                        <span>Historical ({tier})</span>
                        <span>{historicalPerf.sampleSize} tokens</span>
                    </div>
                    <div className="flex items-center justify-between">
                        <span className="text-text-muted">Avg 24h:</span>
                        <span className={historicalPerf.avgReturn24h >= 0 ? 'text-accent-success' : 'text-accent-danger'}>
                            {historicalPerf.avgReturn24h >= 0 ? '+' : ''}{historicalPerf.avgReturn24h}%
                        </span>
                    </div>
                    <div className="flex items-center justify-between">
                        <span className="text-text-muted">Win Rate:</span>
                        <span className={historicalPerf.winRate >= 50 ? 'text-accent-success' : 'text-accent-danger'}>
                            {historicalPerf.winRate}%
                        </span>
                    </div>
                </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 mt-3">
                <button
                    onClick={() => onSnipe(graduation)}
                    className={`
                        flex-1 py-2 rounded-lg font-mono text-sm font-bold
                        transition-all duration-200
                        ${meetsAlgoThreshold
                            ? 'bg-accent-neon text-black hover:brightness-110'
                            : 'bg-bg-secondary/50 text-text-muted hover:bg-bg-secondary'}
                    `}
                >
                    <Zap className="w-4 h-4 inline mr-1" />
                    SNIPE
                </button>
                <button
                    className="px-3 py-2 rounded-lg bg-bg-secondary/50 text-text-muted hover:bg-bg-secondary transition-colors"
                    title="View details"
                >
                    <Activity className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
    const color = value >= 70 ? 'bg-accent-success' :
        value >= 50 ? 'bg-accent-warning' :
            value >= 30 ? 'bg-accent-warning' : 'bg-accent-danger';

    return (
        <div className="flex items-center gap-2">
            <span className="text-[10px] text-text-muted w-14">{label}</span>
            <div className="flex-1 h-1.5 bg-bg-secondary/50 rounded-full overflow-hidden">
                <div
                    className={`h-full ${color} transition-all duration-500`}
                    style={{ width: `${value}%` }}
                />
            </div>
            <span className="text-[10px] font-mono text-text-muted w-6">{value}</span>
        </div>
    );
}

interface SnipeConfigPanelProps {
    config: SnipeConfig;
    onChange: (config: SnipeConfig) => void;
    onClose: () => void;
}

function SnipeConfigPanel({ config, onChange, onClose }: SnipeConfigPanelProps) {
    const [local, setLocal] = useState(config);

    const handleSave = () => {
        onChange(local);
        onClose();
    };

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-bg-secondary border border-border-primary rounded-2xl p-6 max-w-md w-full">
                <div className="flex items-center justify-between mb-6">
                    <h3 className="font-display font-bold text-xl text-text-primary flex items-center gap-2">
                        <Rocket className="w-5 h-5 text-accent-neon" />
                        Snipe Configuration
                    </h3>
                    <button
                        onClick={onClose}
                        className="text-text-muted hover:text-text-primary"
                    >
                        ✕
                    </button>
                </div>

                <div className="space-y-4">
                    {/* Enable Toggle */}
                    <div className="flex items-center justify-between">
                        <span className="text-sm text-text-secondary">Enable Sniper</span>
                        <button
                            onClick={() => setLocal(l => ({ ...l, enabled: !l.enabled }))}
                            className={`
                                w-12 h-6 rounded-full transition-colors relative
                                ${local.enabled ? 'bg-accent-neon' : 'bg-bg-secondary/50 border border-border-primary'}
                            `}
                        >
                            <span className={`
                                absolute top-0.5 w-5 h-5 rounded-full transition-all
                                ${local.enabled ? 'left-6 bg-black' : 'left-0.5 bg-text-muted'}
                            `} />
                        </button>
                    </div>

                    {/* Min Score */}
                    <div>
                        <div className="flex justify-between text-sm mb-1">
                            <span className="text-text-muted">Min Score</span>
                            <span className="font-mono text-accent-neon">{local.minScore}</span>
                        </div>
                        <input
                            type="range"
                            min="30"
                            max="95"
                            value={local.minScore}
                            onChange={(e) => setLocal(l => ({ ...l, minScore: parseInt(e.target.value) }))}
                            className="w-full accent-accent-neon"
                        />
                    </div>

                    {/* Max Position */}
                    <div>
                        <div className="flex justify-between text-sm mb-1">
                            <span className="text-text-muted">Max Position (SOL)</span>
                            <span className="font-mono text-accent-neon">{local.maxPositionSol}</span>
                        </div>
                        <input
                            type="range"
                            min="0.1"
                            max="5"
                            step="0.1"
                            value={local.maxPositionSol}
                            onChange={(e) => setLocal(l => ({ ...l, maxPositionSol: parseFloat(e.target.value) }))}
                            className="w-full accent-accent-neon"
                        />
                    </div>

                    {/* Min Liquidity */}
                    <div>
                        <div className="flex justify-between text-sm mb-1">
                            <span className="text-text-muted">Min Liquidity ($)</span>
                            <span className="font-mono text-accent-neon">${local.minLiquidity.toLocaleString()}</span>
                        </div>
                        <input
                            type="range"
                            min="1000"
                            max="100000"
                            step="1000"
                            value={local.minLiquidity}
                            onChange={(e) => setLocal(l => ({ ...l, minLiquidity: parseInt(e.target.value) }))}
                            className="w-full accent-accent-neon"
                        />
                    </div>

                    {/* Auto TP/SL */}
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <div className="flex justify-between text-sm mb-1">
                                <span className="text-text-muted">Auto TP %</span>
                                <span className="font-mono text-accent-success">{local.autoTP}%</span>
                            </div>
                            <input
                                type="range"
                                min="10"
                                max="200"
                                step="5"
                                value={local.autoTP}
                                onChange={(e) => setLocal(l => ({ ...l, autoTP: parseInt(e.target.value) }))}
                                className="w-full accent-accent-success"
                            />
                        </div>
                        <div>
                            <div className="flex justify-between text-sm mb-1">
                                <span className="text-text-muted">Auto SL %</span>
                                <span className="font-mono text-accent-danger">{local.autoSL}%</span>
                            </div>
                            <input
                                type="range"
                                min="5"
                                max="50"
                                step="5"
                                value={local.autoSL}
                                onChange={(e) => setLocal(l => ({ ...l, autoSL: parseInt(e.target.value) }))}
                                className="w-full accent-accent-danger"
                            />
                        </div>
                    </div>

                    {/* Auto Buy */}
                    <div className="flex items-center justify-between p-3 rounded-lg bg-accent-warning/10 border border-accent-warning/30">
                        <div>
                            <span className="text-sm text-text-muted font-bold">Auto-Buy</span>
                            <p className="text-xs text-text-muted">Automatically buy matching tokens</p>
                        </div>
                        <button
                            onClick={() => setLocal(l => ({ ...l, autoBuy: !l.autoBuy }))}
                            className={`
                                w-12 h-6 rounded-full transition-colors relative
                                ${local.autoBuy ? 'bg-accent-warning' : 'bg-bg-secondary/50 border border-border-primary'}
                            `}
                        >
                            <span className={`
                                absolute top-0.5 w-5 h-5 rounded-full transition-all
                                ${local.autoBuy ? 'left-6 bg-black' : 'left-0.5 bg-text-muted'}
                            `} />
                        </button>
                    </div>
                </div>

                <div className="flex gap-3 mt-6">
                    <button
                        onClick={onClose}
                        className="flex-1 py-3 rounded-lg border border-border-primary text-text-muted hover:bg-bg-secondary/50 transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        className="flex-1 py-3 rounded-lg bg-accent-neon text-black font-bold hover:brightness-110 transition-all"
                    >
                        Save Config
                    </button>
                </div>
            </div>
        </div>
    );
}

export function GraduationFeed() {
    const { graduations, loading, error, refresh, lastUpdated } = useBagsGraduations({
        limit: 30,
        refreshInterval: 15000, // 15 second refresh
    });

    const { info: toastInfo } = useToast();
    const algoParams = useAlgoParams();
    const [showConfig, setShowConfig] = useState(false);
    const [snipeConfig, setSnipeConfig] = useState<SnipeConfig>(loadSnipeConfig);
    const [sentiments, setSentiments] = useState<Map<string, TokenSentiment>>(new Map());
    const [expanded, setExpanded] = useState(true);
    const [filterTier, setFilterTier] = useState<ScoreTier | 'all'>('all');

    // Fetch sentiments for displayed tokens
    useEffect(() => {
        const fetchSentiments = async () => {
            const grok = getGrokSentimentClient();
            const tokensToAnalyze = graduations
                .slice(0, 10)
                .filter(g => !sentiments.has(g.mint))
                .map(g => ({
                    mint: g.mint,
                    symbol: g.symbol,
                    price: g.price_usd,
                    volume24h: g.market_cap * 0.1, // Estimate
                }));

            if (tokensToAnalyze.length > 0) {
                const result = await grok.analyzeBatch(tokensToAnalyze);
                if (result.tokens.length > 0) {
                    setSentiments(prev => {
                        const updated = new Map(prev);
                        result.tokens.forEach(t => updated.set(t.mint, t));
                        return updated;
                    });
                }
            }
        };

        if (graduations.length > 0) {
            fetchSentiments();
        }
    }, [graduations]);

    // Save snipe config
    const handleConfigChange = useCallback((config: SnipeConfig) => {
        setSnipeConfig(config);
        saveSnipeConfig(config);
    }, []);

    // Filter graduations
    const filteredGraduations = useMemo(() => {
        let filtered = graduations;

        if (filterTier !== 'all') {
            filtered = filtered.filter(g => getScoreTier(g.score) === filterTier);
        }

        // Sort by score descending
        return filtered.sort((a, b) => b.score - a.score);
    }, [graduations, filterTier]);

    // Count by tier
    const tierCounts = useMemo(() => {
        const counts: Record<ScoreTier, number> = {
            exceptional: 0,
            strong: 0,
            average: 0,
            weak: 0,
            poor: 0,
        };
        graduations.forEach(g => {
            counts[getScoreTier(g.score)]++;
        });
        return counts;
    }, [graduations]);

    // Algo matches
    const algoMatches = useMemo(() => {
        return graduations.filter(g =>
            g.score >= algoParams.params.graduationScoreCutoff &&
            g.market_cap >= algoParams.params.minLiquidityUsd
        ).length;
    }, [graduations, algoParams.params]);

    const handleSnipe = useCallback((grad: BagsGraduation) => {
        toastInfo(`Snipe ${grad.symbol} — navigate to Trade page to execute`);
    }, [toastInfo]);

    return (
        <div className="card-glass overflow-hidden">
            {/* Header */}
            <div
                className="p-4 border-b border-border-primary/30 cursor-pointer"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-accent-neon/20 flex items-center justify-center">
                            <Rocket className="w-4 h-4 text-accent-neon" />
                        </div>
                        <div>
                            <h3 className="font-display font-bold text-lg text-text-primary">
                                Graduation Feed
                            </h3>
                            <p className="text-xs text-text-muted">
                                bags.fm launches • {graduations.length} tokens
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        {/* Algo Match Count */}
                        {algoMatches > 0 && (
                            <div className="px-2 py-1 rounded-full bg-accent-neon/20 text-accent-neon text-xs font-mono">
                                {algoMatches} MATCH{algoMatches !== 1 ? 'ES' : ''}
                            </div>
                        )}

                        {/* Sniper Status */}
                        <div className={`
                            w-2 h-2 rounded-full
                            ${snipeConfig.enabled ? 'bg-accent-neon animate-pulse' : 'bg-text-muted'}
                        `} />

                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setShowConfig(true);
                            }}
                            className="p-2 rounded-lg hover:bg-bg-secondary/50 transition-colors"
                        >
                            <Settings2 className="w-4 h-4 text-text-muted" />
                        </button>

                        {expanded ? (
                            <ChevronUp className="w-5 h-5 text-text-muted" />
                        ) : (
                            <ChevronDown className="w-5 h-5 text-text-muted" />
                        )}
                    </div>
                </div>

                {/* Tier Filter Pills */}
                {expanded && (
                    <div className="flex gap-2 mt-3 overflow-x-auto pb-1">
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setFilterTier('all');
                            }}
                            className={`
                                px-3 py-1 rounded-full text-xs font-mono whitespace-nowrap transition-all
                                ${filterTier === 'all'
                                    ? 'bg-accent-neon text-black'
                                    : 'bg-bg-secondary/50 text-text-muted hover:bg-bg-secondary'}
                            `}
                        >
                            All ({graduations.length})
                        </button>
                        {(['exceptional', 'strong', 'average', 'weak', 'poor'] as ScoreTier[]).map(tier => {
                            const colors = TIER_COLORS[tier];
                            return (
                                <button
                                    key={tier}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setFilterTier(tier);
                                    }}
                                    className={`
                                        px-3 py-1 rounded-full text-xs font-mono whitespace-nowrap transition-all
                                        ${filterTier === tier
                                            ? `${colors.bg} ${colors.text} border ${colors.border}`
                                            : 'bg-bg-secondary/50 text-text-muted hover:bg-bg-secondary'}
                                    `}
                                >
                                    {tier.charAt(0).toUpperCase() + tier.slice(1)} ({tierCounts[tier]})
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Content */}
            {expanded && (
                <div className="p-4">
                    {loading && graduations.length === 0 ? (
                        <div className="text-center py-8">
                            <div className="w-8 h-8 border-2 border-accent-neon border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                            <p className="text-sm text-text-muted font-mono">Loading graduations...</p>
                        </div>
                    ) : error && graduations.length === 0 ? (
                        <div className="text-center py-8">
                            <p className="text-sm text-accent-danger">{error}</p>
                            <button
                                onClick={refresh}
                                className="mt-2 text-xs text-accent-neon hover:underline"
                            >
                                Retry
                            </button>
                        </div>
                    ) : (
                        <>
                            {/* Historical Performance Summary */}
                            <div className="grid grid-cols-5 gap-2 mb-4">
                                {DEMO_TIER_PERFORMANCE.map(perf => {
                                    const colors = TIER_COLORS[perf.tier];
                                    return (
                                        <div
                                            key={perf.tier}
                                            className={`p-2 rounded-lg ${colors.bg} border ${colors.border} text-center`}
                                        >
                                            <p className={`text-[10px] ${colors.text} font-bold uppercase`}>
                                                {perf.tier}
                                            </p>
                                            <p className={`text-xs font-mono ${perf.avgReturn24h >= 0 ? 'text-accent-success' : 'text-accent-danger'}`}>
                                                {perf.avgReturn24h >= 0 ? '+' : ''}{perf.avgReturn24h}%
                                            </p>
                                            <p className="text-[10px] text-text-muted">
                                                {perf.winRate}% win
                                            </p>
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Graduation Cards */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[600px] overflow-y-auto pr-1 custom-scrollbar">
                                {filteredGraduations.map(grad => (
                                    <GraduationCard
                                        key={grad.mint}
                                        graduation={grad}
                                        sentiment={sentiments.get(grad.mint)}
                                        onSnipe={handleSnipe}
                                        algoParams={algoParams}
                                    />
                                ))}
                            </div>

                            {/* Last Updated */}
                            {lastUpdated && (
                                <div className="mt-3 text-center">
                                    <p className="text-[10px] text-text-muted font-mono">
                                        Updated {lastUpdated.toLocaleTimeString()} •
                                        <button
                                            onClick={refresh}
                                            className="ml-1 text-accent-neon hover:underline"
                                        >
                                            Refresh
                                        </button>
                                    </p>
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}

            {/* Snipe Config Modal */}
            {showConfig && (
                <SnipeConfigPanel
                    config={snipeConfig}
                    onChange={handleConfigChange}
                    onClose={() => setShowConfig(false)}
                />
            )}
        </div>
    );
}

export default GraduationFeed;
