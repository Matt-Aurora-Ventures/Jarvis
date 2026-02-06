'use client';

import { useState } from 'react';
import { useBagsGraduations } from '@/hooks/useBagsGraduations';
import { GraduationCard } from '@/components/features/GraduationCard';
import { getScoreTier, ScoreTier } from '@/lib/bags-api';
import { Zap, RefreshCw, TrendingUp, Users, Droplets, MessageCircle, Star, Check, Minus, AlertTriangle, XCircle } from 'lucide-react';
import { NeuralLattice } from '@/components/visuals/NeuralLattice';

type FilterTier = 'all' | ScoreTier;

const TIER_RANGES = {
    exceptional: { min: 85, max: 100, icon: Star, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    strong: { min: 70, max: 84, icon: Check, color: 'text-green-400', bg: 'bg-green-500/10' },
    average: { min: 50, max: 69, icon: Minus, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
    weak: { min: 30, max: 49, icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/10' },
    poor: { min: 0, max: 29, icon: XCircle, color: 'text-red-400', bg: 'bg-red-500/10' },
};

const HOW_WE_RATE = [
    {
        title: 'Bonding Curve Analysis',
        description: 'We analyze durations, unique buyers, and buy/sell patterns during the bonding curve phase.',
        icon: TrendingUp,
        color: 'text-accent-neon',
    },
    {
        title: 'Holder Distribution',
        description: 'Top holder concentration, wallet age, and distribution fairness are key indicators.',
        icon: Users,
        color: 'text-cyan-400',
    },
    {
        title: 'Liquidity Health',
        description: 'Market cap to liquidity ratio, burn status, and lock duration affect safety scores.',
        icon: Droplets,
        color: 'text-blue-400',
    },
    {
        title: 'Social Signals',
        description: 'Community engagement, social presence, and founder verification contribute to trust.',
        icon: MessageCircle,
        color: 'text-purple-400',
    },
];

export default function BagsIntelPage() {
    const { graduations, loading, error, refresh, lastUpdated } = useBagsGraduations({ limit: 50 });
    const [activeFilter, setActiveFilter] = useState<FilterTier>('all');
    const [isRefreshing, setIsRefreshing] = useState(false);

    const filteredGraduations = activeFilter === 'all'
        ? graduations
        : graduations.filter(g => getScoreTier(g.score) === activeFilter);

    const handleRefresh = async () => {
        setIsRefreshing(true);
        await refresh();
        setTimeout(() => setIsRefreshing(false), 500);
    };

    return (
        <div className="min-h-screen flex flex-col relative overflow-hidden">
            <NeuralLattice />

            <div className="relative z-10 pt-24 pb-12">
                {/* Hero Section */}
                <section className="text-center mb-12">
                    <p className="text-sm text-accent-neon font-mono mb-2">Built by KR8TIV AI</p>
                    <h1 className="font-display text-4xl md:text-5xl font-bold text-text-primary mb-4">
                        Bags.fm Graduations
                    </h1>
                    <p className="text-text-secondary text-lg max-w-2xl mx-auto">
                        Real-time intelligence on bonding curve completions — Ranked by KR8TIV Score
                    </p>
                </section>

                {/* How We Rate Section */}
                <section className="mb-12">
                    <div className="card-glass p-6 max-w-5xl mx-auto">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="font-display font-bold text-lg flex items-center gap-2 text-text-primary">
                                <Zap className="w-5 h-5 text-accent-neon" />
                                How We Rate Tokens
                            </h2>
                            <button
                                onClick={() => { }}
                                className="text-xs text-text-muted hover:text-text-primary transition-colors"
                            >
                                ▲
                            </button>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                            {HOW_WE_RATE.map((item) => (
                                <div
                                    key={item.title}
                                    className="p-4 rounded-xl border border-border-primary hover:border-border-hover transition-all bg-bg-secondary/50"
                                >
                                    <div className={`flex items-center gap-2 mb-2 ${item.color}`}>
                                        <item.icon className="w-4 h-4" />
                                        <h3 className="font-semibold text-sm">{item.title}</h3>
                                    </div>
                                    <p className="text-xs text-text-muted leading-relaxed">
                                        {item.description}
                                    </p>
                                </div>
                            ))}
                        </div>

                        {/* Score Tiers Legend */}
                        <div className="flex flex-wrap items-center gap-3 pt-4 border-t border-border-primary">
                            {Object.entries(TIER_RANGES).map(([tier, { min, max, icon: Icon, color, bg }]) => (
                                <div
                                    key={tier}
                                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${bg} border border-border-primary`}
                                >
                                    <Icon className={`w-3.5 h-3.5 ${color}`} />
                                    <span className={`text-xs font-medium capitalize ${color}`}>{tier}</span>
                                    <span className="text-xs text-text-muted">({min}-{max})</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                {/* Filter Tabs & Refresh */}
                <section className="mb-8 flex flex-col sm:flex-row items-center justify-between gap-4 max-w-7xl mx-auto px-4">
                    <div className="flex items-center gap-2 flex-wrap justify-center">
                        <button
                            onClick={() => setActiveFilter('all')}
                            className={`px-4 py-2 rounded-full text-sm font-medium transition-all border ${activeFilter === 'all'
                                    ? 'bg-text-primary text-bg-primary border-text-primary'
                                    : 'bg-transparent text-text-secondary border-border-primary hover:bg-bg-tertiary'
                                }`}
                        >
                            All Tokens
                        </button>
                        {(Object.keys(TIER_RANGES) as ScoreTier[]).map((tier) => {
                            const { icon: Icon, color, bg } = TIER_RANGES[tier];
                            return (
                                <button
                                    key={tier}
                                    onClick={() => setActiveFilter(tier)}
                                    className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all border ${activeFilter === tier
                                            ? `${bg} ${color} border-current`
                                            : 'bg-transparent text-text-secondary border-border-primary hover:bg-bg-tertiary'
                                        }`}
                                >
                                    <Icon className="w-3.5 h-3.5" />
                                    <span className="capitalize">{tier}</span>
                                </button>
                            );
                        })}
                    </div>

                    <div className="flex items-center gap-4">
                        {lastUpdated && (
                            <span className="text-xs text-text-muted font-mono">
                                Updated {lastUpdated.toLocaleTimeString()}
                            </span>
                        )}
                        <button
                            onClick={handleRefresh}
                            disabled={isRefreshing}
                            className="flex items-center gap-2 px-4 py-2 rounded-full bg-bg-tertiary hover:bg-bg-secondary border border-border-primary text-sm font-medium text-text-secondary hover:text-text-primary transition-all disabled:opacity-50"
                        >
                            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                            Refresh
                        </button>
                    </div>
                </section>

                {/* Error Banner */}
                {error && (
                    <div className="max-w-7xl mx-auto px-4 mb-6">
                        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 text-amber-400 text-sm font-mono">
                            {error}
                        </div>
                    </div>
                )}

                {/* Graduations Grid */}
                <section className="max-w-7xl mx-auto px-4">
                    {loading ? (
                        <div className="text-center py-20">
                            <div className="text-accent-neon font-mono animate-pulse text-lg">
                                Loading top graduations...
                            </div>
                        </div>
                    ) : filteredGraduations.length === 0 ? (
                        <div className="text-center py-20">
                            <div className="card-glass p-12 max-w-md mx-auto">
                                <Zap className="w-12 h-12 text-text-muted mx-auto mb-4" />
                                <h3 className="font-display font-bold text-xl mb-2 text-text-primary">No graduations yet</h3>
                                <p className="text-text-muted text-sm">
                                    Waiting for tokens to complete bonding curve...
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                            {filteredGraduations.map((graduation) => (
                                <GraduationCard
                                    key={graduation.mint}
                                    graduation={graduation}
                                />
                            ))}
                        </div>
                    )}
                </section>
            </div>
        </div>
    );
}
