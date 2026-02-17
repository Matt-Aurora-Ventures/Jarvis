'use client';

import { useState } from 'react';
import { BagsGraduation, getScoreTier, ScoreTier } from '@/lib/bags-api';
import {
  TrendingUp, Users, Clock, MessageCircle, ExternalLink,
  ChevronDown, ChevronUp, Globe, Hammer, BarChart3, Sparkles,
  LineChart,
} from 'lucide-react';

interface GraduationCardProps {
  graduation: BagsGraduation;
}

const TIER_STYLES: Record<ScoreTier, { ring: string; badge: string; glow: string; accent: string }> = {
  exceptional: {
    ring: 'ring-emerald-500',
    badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    glow: 'shadow-emerald-500/20',
    accent: 'text-emerald-400',
  },
  strong: {
    ring: 'ring-accent-success',
    badge: 'bg-accent-success/10 text-accent-success border-accent-success/30',
    glow: 'shadow-accent-success/20',
    accent: 'text-accent-success',
  },
  average: {
    ring: 'ring-accent-warning',
    badge: 'bg-accent-warning/10 text-text-muted border-accent-warning/30',
    glow: 'shadow-accent-warning/20',
    accent: 'text-accent-warning',
  },
  weak: {
    ring: 'ring-accent-warning',
    badge: 'bg-accent-warning/10 text-accent-warning border-accent-warning/30',
    glow: 'shadow-accent-warning/20',
    accent: 'text-accent-warning',
  },
  poor: {
    ring: 'ring-accent-error',
    badge: 'bg-accent-error/10 text-accent-error border-accent-error/30',
    glow: 'shadow-accent-error/20',
    accent: 'text-accent-error',
  },
};

interface ScoreBarProps {
  value: number;
  max: number;
  label: string;
}

function ScoreBar({ value, max, label }: ScoreBarProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-text-muted w-16 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-accent-neon/60 transition-all"
          style={{ width: `${Math.min(100, (value / max) * 100)}%` }}
        />
      </div>
      <span className="text-[10px] font-mono text-text-muted w-6 text-right">{value}</span>
    </div>
  );
}

export function GraduationCard({ graduation }: GraduationCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [showChart, setShowChart] = useState(false);
  const tier = getScoreTier(graduation.score);
  const styles = TIER_STYLES[tier];

  const formatPrice = (price: number) => {
    if (price === 0) return '--';
    if (price < 0.0001) return `$${price.toExponential(2)}`;
    if (price < 1) return `$${price.toFixed(6)}`;
    return `$${price.toFixed(2)}`;
  };

  const formatMarketCap = (mc: number) => {
    if (mc === 0) return '--';
    if (mc >= 1_000_000) return `$${(mc / 1_000_000).toFixed(2)}M`;
    if (mc >= 1_000) return `$${(mc / 1_000).toFixed(1)}K`;
    return `$${mc.toFixed(0)}`;
  };

  const formatVolume = (v: number) => {
    if (!v) return '--';
    if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
    if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
    return `$${v.toFixed(0)}`;
  };

  const formatAge = (hours?: number) => {
    if (!hours) return '--';
    if (hours < 1) return `${Math.floor(hours * 60)}m`;
    if (hours < 24) return `${Math.floor(hours)}h`;
    if (hours < 168) return `${Math.floor(hours / 24)}d`;
    if (hours < 720) return `${Math.floor(hours / 168)}w`;
    return `${Math.floor(hours / 720)}mo`;
  };

  const bd = graduation.scoreBreakdown;

  return (
    <div className={`card-glass p-4 hover:ring-2 ${styles.ring} hover:${styles.glow} hover:shadow-lg transition-all duration-300 group`}>
      {/* Header Row */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0">
          {/* Token Logo */}
          <div className="w-11 h-11 rounded-xl bg-bg-tertiary flex items-center justify-center text-base font-bold text-text-primary border border-border-primary shrink-0 overflow-hidden">
            {graduation.logo_uri ? (
              <img
                src={graduation.logo_uri}
                alt={graduation.symbol}
                className="w-full h-full object-cover"
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
            ) : (
              graduation.symbol.slice(0, 2).toUpperCase()
            )}
          </div>
          <div className="min-w-0">
            <h3 className="font-display font-bold text-base text-text-primary truncate">
              {graduation.symbol}
            </h3>
            <p className="text-[11px] text-text-muted truncate max-w-[140px]">
              {graduation.name}
            </p>
          </div>
        </div>

        {/* Score Badge */}
        <div className={`flex flex-col items-center px-2.5 py-1 rounded-xl border ${styles.badge}`}>
          <span className="text-xl font-bold font-mono leading-tight">{graduation.score}</span>
          <span className="text-[9px] uppercase tracking-wider leading-none">{tier}</span>
        </div>
      </div>

      {/* Tags Row - Age, Holders, Volume */}
      <div className="flex items-center gap-1.5 mb-3 flex-wrap">
        {graduation.isNewLaunch && (
          <span className="px-2 py-0.5 rounded-full bg-accent-neon/10 text-accent-neon text-[10px] font-semibold border border-accent-neon/20">
            NEW
          </span>
        )}
        {graduation.isEstablished && (
          <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-semibold border border-emerald-500/20">
            ESTABLISHED
          </span>
        )}
        <span className="px-2 py-0.5 rounded-full bg-bg-tertiary text-text-muted text-[10px] flex items-center gap-1">
          <Clock className="w-2.5 h-2.5" /> {formatAge(graduation.ageHours)}
        </span>
        {graduation.holderCount ? (
          <span className="px-2 py-0.5 rounded-full bg-bg-tertiary text-text-muted text-[10px] flex items-center gap-1">
            <Users className="w-2.5 h-2.5" /> {graduation.holderCount.toLocaleString()}
          </span>
        ) : null}
        {graduation.volume_24h ? (
          <span className="px-2 py-0.5 rounded-full bg-bg-tertiary text-text-muted text-[10px] flex items-center gap-1">
            <BarChart3 className="w-2.5 h-2.5" /> {formatVolume(graduation.volume_24h)}
          </span>
        ) : null}
      </div>

      {/* Creator Row */}
      {graduation.creator?.username && (
        <div className="flex items-center gap-2 mb-3 px-2 py-1.5 rounded-lg bg-bg-secondary/50 border border-border-primary">
          {graduation.creator.pfp ? (
            <img src={graduation.creator.pfp} alt="" className="w-5 h-5 rounded-full" />
          ) : (
            <Hammer className="w-3.5 h-3.5 text-text-muted" />
          )}
          <span className="text-[11px] text-text-secondary truncate">
            by <span className="text-text-primary font-medium">{graduation.creator.username}</span>
          </span>
          {graduation.creator.royaltyBps ? (
            <span className="text-[10px] text-text-muted ml-auto">
              {(graduation.creator.royaltyBps / 100).toFixed(1)}% royalty
            </span>
          ) : null}
        </div>
      )}

      {/* Social Links */}
      {(graduation.twitterUrl || graduation.websiteUrl) && (
        <div className="flex items-center gap-2 mb-3">
          {graduation.twitterUrl && (
            <a
              href={graduation.twitterUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 px-2 py-1 rounded-lg bg-bg-tertiary hover:bg-bg-secondary text-[10px] text-text-muted hover:text-text-primary transition-colors"
            >
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
              Twitter
            </a>
          )}
          {graduation.websiteUrl && (
            <a
              href={graduation.websiteUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 px-2 py-1 rounded-lg bg-bg-tertiary hover:bg-bg-secondary text-[10px] text-text-muted hover:text-text-primary transition-colors"
            >
              <Globe className="w-3 h-3" />
              Website
            </a>
          )}
        </div>
      )}

      {/* Price / MCap / Bags Link Row */}
      <div className="flex items-center justify-between pt-2 border-t border-border-primary">
        <div className="flex flex-col">
          <span className="text-[10px] text-text-muted">Price</span>
          <span className="font-mono text-sm text-text-primary">{formatPrice(graduation.price_usd)}</span>
        </div>
        <div className="flex flex-col text-center">
          <span className="text-[10px] text-text-muted">MCap</span>
          <span className="font-mono text-sm text-text-primary">{formatMarketCap(graduation.market_cap)}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1.5 rounded-lg bg-bg-tertiary hover:bg-bg-secondary text-text-muted hover:text-text-primary transition-all"
          >
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          <a
            href={`https://bags.fm/token/${graduation.mint}`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 rounded-lg bg-bg-tertiary hover:bg-accent-neon hover:text-black transition-all"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* Expanded Detail Panel */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-border-primary space-y-3">
          {/* Description */}
          {graduation.description && (
            <p className="text-[11px] text-text-secondary leading-relaxed">
              {graduation.description}
            </p>
          )}

          {/* Chart Toggle */}
          <div>
            <button
              onClick={() => setShowChart(!showChart)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-semibold uppercase
                         bg-bg-tertiary hover:bg-bg-secondary border border-border-primary
                         text-text-muted hover:text-text-primary transition-all w-full justify-center"
            >
              <LineChart className="w-3.5 h-3.5" />
              {showChart ? 'Hide Chart' : 'Show Chart'}
            </button>
            {showChart && (
              <div className="mt-2 rounded-lg overflow-hidden border border-border-primary bg-black">
                <iframe
                  src={`https://dexscreener.com/solana/${graduation.mint}?embed=1&theme=dark&trades=0&info=0`}
                  className="w-full h-[300px] border-0"
                  title={`${graduation.symbol} chart`}
                  loading="lazy"
                  sandbox="allow-scripts allow-same-origin"
                />
              </div>
            )}
          </div>

          {/* Score Breakdown */}
          {bd && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-1 mb-1">
                <Sparkles className="w-3 h-3 text-accent-neon" />
                <span className="text-[10px] font-semibold text-text-primary">KR8TIV Score Breakdown</span>
              </div>
              <ScoreBar value={bd.community} max={25} label="Community" />
              <ScoreBar value={bd.momentum} max={25} label="Momentum" />
              <ScoreBar value={bd.longevity} max={20} label="Longevity" />
              <ScoreBar value={bd.social} max={15} label="Social" />
              <ScoreBar value={bd.builder} max={15} label="Builder" />
            </div>
          )}

          {/* Detailed Metrics */}
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="flex justify-between">
              <span className="text-text-muted">24h Volume</span>
              <span className="font-mono text-text-primary">{formatVolume(graduation.volume_24h || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Holders</span>
              <span className="font-mono text-text-primary">{graduation.holderCount?.toLocaleString() || '--'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Age</span>
              <span className="font-mono text-text-primary">{formatAge(graduation.ageHours)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Liquidity</span>
              <span className="font-mono text-emerald-400">Locked</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
