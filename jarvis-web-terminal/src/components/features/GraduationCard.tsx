'use client';

import { BagsGraduation, getScoreTier, ScoreTier } from '@/lib/bags-api';
import { TrendingUp, Users, Droplets, MessageCircle, ExternalLink } from 'lucide-react';

interface GraduationCardProps {
    graduation: BagsGraduation;
}

const TIER_STYLES: Record<ScoreTier, { ring: string; badge: string; glow: string }> = {
    exceptional: {
        ring: 'ring-emerald-500',
        badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
        glow: 'shadow-emerald-500/20',
    },
    strong: {
        ring: 'ring-accent-success',
        badge: 'bg-accent-success/10 text-accent-success border-accent-success/30',
        glow: 'shadow-accent-success/20',
    },
    average: {
        ring: 'ring-accent-warning',
        badge: 'bg-accent-warning/10 text-text-muted border-accent-warning/30',
        glow: 'shadow-accent-warning/20',
    },
    weak: {
        ring: 'ring-accent-warning',
        badge: 'bg-accent-warning/10 text-accent-warning border-accent-warning/30',
        glow: 'shadow-accent-warning/20',
    },
    poor: {
        ring: 'ring-accent-error',
        badge: 'bg-accent-error/10 text-accent-error border-accent-error/30',
        glow: 'shadow-accent-error/20',
    },
};

export function GraduationCard({ graduation }: GraduationCardProps) {
    const tier = getScoreTier(graduation.score);
    const styles = TIER_STYLES[tier];

    const formatPrice = (price: number) => {
        if (price < 0.0001) return `$${price.toExponential(2)}`;
        if (price < 1) return `$${price.toFixed(6)}`;
        return `$${price.toFixed(2)}`;
    };

    const formatMarketCap = (mc: number) => {
        if (mc >= 1000000) return `$${(mc / 1000000).toFixed(2)}M`;
        if (mc >= 1000) return `$${(mc / 1000).toFixed(1)}K`;
        return `$${mc.toFixed(0)}`;
    };

    const formatTime = (timestamp: number) => {
        const now = Date.now() / 1000;
        const diff = now - timestamp;

        if (diff < 60) return 'Just now';
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return `${Math.floor(diff / 86400)}d ago`;
    };

    const metrics = [
        { icon: TrendingUp, label: 'Bonding', value: graduation.bonding_curve_score },
        { icon: Users, label: 'Holders', value: graduation.holder_distribution_score },
        { icon: Droplets, label: 'Liquidity', value: graduation.liquidity_score },
        { icon: MessageCircle, label: 'Social', value: graduation.social_score },
    ];

    return (
        <div className={`card-glass p-5 hover:ring-2 ${styles.ring} hover:${styles.glow} hover:shadow-lg transition-all duration-300 group`}>
            {/* Header */}
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    {/* Token Logo/Avatar */}
                    <div className="w-12 h-12 rounded-xl bg-bg-tertiary flex items-center justify-center text-lg font-bold text-text-primary border border-border-primary">
                        {graduation.logo_uri ? (
                            <img
                                src={graduation.logo_uri}
                                alt={graduation.symbol}
                                className="w-full h-full object-cover rounded-xl"
                            />
                        ) : (
                            graduation.symbol.slice(0, 2)
                        )}
                    </div>
                    <div>
                        <h3 className="font-display font-bold text-lg text-text-primary">
                            {graduation.symbol}
                        </h3>
                        <p className="text-xs text-text-muted truncate max-w-[120px]">
                            {graduation.name}
                        </p>
                    </div>
                </div>

                {/* Score Badge */}
                <div className={`flex flex-col items-center px-3 py-1.5 rounded-xl border ${styles.badge}`}>
                    <span className="text-2xl font-bold font-mono">{graduation.score}</span>
                    <span className="text-[10px] uppercase tracking-wider">{tier}</span>
                </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-4 gap-2 mb-4">
                {metrics.map(({ icon: Icon, label, value }) => (
                    <div key={label} className="text-center">
                        <div className="flex items-center justify-center mb-1">
                            <Icon className="w-3.5 h-3.5 text-text-muted" />
                        </div>
                        <div className="text-sm font-mono font-bold text-text-primary">{value}</div>
                        <div className="text-[10px] text-text-muted uppercase">{label}</div>
                    </div>
                ))}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between pt-3 border-t border-border-primary">
                <div className="flex flex-col">
                    <span className="text-xs text-text-muted">Price</span>
                    <span className="font-mono text-sm text-text-primary">{formatPrice(graduation.price_usd)}</span>
                </div>
                <div className="flex flex-col text-right">
                    <span className="text-xs text-text-muted">MCap</span>
                    <span className="font-mono text-sm text-text-primary">{formatMarketCap(graduation.market_cap)}</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-xs text-text-muted">{formatTime(graduation.graduation_time)}</span>
                    <a
                        href={`https://bags.fm/token/${graduation.mint}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 rounded-lg bg-bg-tertiary hover:bg-accent-neon hover:text-black transition-all opacity-0 group-hover:opacity-100"
                    >
                        <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                </div>
            </div>
        </div>
    );
}
