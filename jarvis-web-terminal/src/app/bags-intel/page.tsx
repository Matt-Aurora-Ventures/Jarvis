'use client';

import { useState } from 'react';
import { useBagsGraduations } from '@/hooks/useBagsGraduations';
import { GraduationCard } from '@/components/features/GraduationCard';
import { getScoreTier, ScoreTier } from '@/lib/bags-api';
import {
  Zap, RefreshCw, TrendingUp, Users, Sparkles, Shield,
  Clock, Star, Check, Minus, AlertTriangle, XCircle,
  BarChart3, Rocket, Crown,
} from 'lucide-react';

type FilterTier = 'all' | ScoreTier;
type ViewMode = 'all' | 'new' | 'established';

const TIER_RANGES = {
  exceptional: { min: 85, max: 100, icon: Star, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  strong: { min: 70, max: 84, icon: Check, color: 'text-accent-success', bg: 'bg-accent-success/10' },
  average: { min: 50, max: 69, icon: Minus, color: 'text-text-muted', bg: 'bg-accent-warning/10' },
  weak: { min: 30, max: 49, icon: AlertTriangle, color: 'text-accent-warning', bg: 'bg-accent-warning/10' },
  poor: { min: 0, max: 29, icon: XCircle, color: 'text-accent-error', bg: 'bg-accent-error/10' },
};

const SCORE_DIMENSIONS = [
  {
    title: 'Community Strength',
    description: 'Holder count, distribution fairness, organic buyers, and Jupiter organic score.',
    icon: Users,
    weight: '25%',
  },
  {
    title: 'Market Momentum',
    description: 'Volume trends, buy/sell ratio, price action, and volume-to-mcap ratio.',
    icon: TrendingUp,
    weight: '25%',
  },
  {
    title: 'Longevity & Persistence',
    description: 'Token age, sustained trading activity over time, and volume persistence.',
    icon: Clock,
    weight: '20%',
  },
  {
    title: 'Social Presence',
    description: 'Twitter/X profile, website, Telegram, and creator social transparency.',
    icon: Sparkles,
    weight: '15%',
  },
  {
    title: 'Builder Credibility',
    description: 'Creator identity, royalty setup, project description quality, verification status.',
    icon: Shield,
    weight: '15%',
  },
];

export default function BagsIntelPage() {
  const { graduations, loading, error, refresh, lastUpdated, newLaunchCount, establishedCount } = useBagsGraduations({ limit: 200 });
  const [activeFilter, setActiveFilter] = useState<FilterTier>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('all');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showHowWeRate, setShowHowWeRate] = useState(false);

  // Apply filters
  let filteredGraduations = graduations;
  if (viewMode === 'new') {
    filteredGraduations = filteredGraduations.filter(g => g.isNewLaunch);
  } else if (viewMode === 'established') {
    filteredGraduations = filteredGraduations.filter(g => g.isEstablished);
  }
  if (activeFilter !== 'all') {
    filteredGraduations = filteredGraduations.filter(g => getScoreTier(g.score) === activeFilter);
  }

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refresh();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  // Tier distribution for stats
  const tierCounts: Record<ScoreTier, number> = {
    exceptional: 0, strong: 0, average: 0, weak: 0, poor: 0,
  };
  for (const g of graduations) {
    tierCounts[getScoreTier(g.score)]++;
  }

  return (
    <div className="min-h-screen flex flex-col relative overflow-hidden">
      {/* Ambient Background Orbs */}
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent-neon/[0.04] rounded-full blur-[128px]" />
        <div className="absolute bottom-1/3 right-1/4 w-80 h-80 bg-accent-neon/[0.03] rounded-full blur-[128px]" />
        <div className="absolute top-2/3 left-1/2 w-64 h-64 bg-accent-success/[0.02] rounded-full blur-[128px]" />
      </div>

      <div className="relative z-10 pt-24 pb-12 px-4">
        {/* Hero Section */}
        <section className="text-center mb-8">
          <p className="text-sm text-accent-neon font-mono mb-2">Built by KR8TIV AI</p>
          <h1 className="font-display text-4xl md:text-5xl font-bold text-text-primary mb-4">
            DeGen Intel
          </h1>
          <p className="text-text-secondary text-lg max-w-2xl mx-auto mb-4">
            Real-time analysis of {graduations.length.toLocaleString()}+ tokens — Ranked by KR8TIV Score
          </p>
          <p className="text-text-muted text-sm max-w-xl mx-auto">
            We assess projects like a VC: community, momentum, longevity, social presence, and builder credibility.
          </p>
        </section>

        {/* Stats Bar */}
        <section className="mb-8 max-w-5xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="card-glass p-3 text-center">
              <div className="text-2xl font-bold font-mono text-text-primary">{graduations.length}</div>
              <div className="text-[10px] text-text-muted uppercase tracking-wider">Total Tokens</div>
            </div>
            <div className="card-glass p-3 text-center">
              <div className="text-2xl font-bold font-mono text-accent-neon">{newLaunchCount}</div>
              <div className="text-[10px] text-text-muted uppercase tracking-wider">New (&lt;48h)</div>
            </div>
            <div className="card-glass p-3 text-center">
              <div className="text-2xl font-bold font-mono text-emerald-400">{establishedCount}</div>
              <div className="text-[10px] text-text-muted uppercase tracking-wider">Established</div>
            </div>
            <div className="card-glass p-3 text-center">
              <div className="text-2xl font-bold font-mono text-accent-success">{tierCounts.exceptional + tierCounts.strong}</div>
              <div className="text-[10px] text-text-muted uppercase tracking-wider">Strong+</div>
            </div>
            <div className="card-glass p-3 text-center">
              <div className="text-2xl font-bold font-mono text-text-primary">
                {graduations.length > 0 ? Math.round(graduations.reduce((s, g) => s + g.score, 0) / graduations.length) : 0}
              </div>
              <div className="text-[10px] text-text-muted uppercase tracking-wider">Avg Score</div>
            </div>
          </div>
        </section>

        {/* How We Rate Section (Collapsible) */}
        <section className="mb-8">
          <div className="card-glass max-w-5xl mx-auto overflow-hidden">
            <button
              onClick={() => setShowHowWeRate(!showHowWeRate)}
              className="w-full p-4 flex items-center justify-between hover:bg-bg-secondary/30 transition-colors"
            >
              <h2 className="font-display font-bold text-base flex items-center gap-2 text-text-primary">
                <Zap className="w-5 h-5 text-accent-neon" />
                How We Rate Tokens — KR8TIV Business Assessment
              </h2>
              <span className="text-text-muted text-sm">
                {showHowWeRate ? '▼' : '▶'}
              </span>
            </button>

            {showHowWeRate && (
              <div className="px-4 pb-4 pt-0">
                <p className="text-xs text-text-muted mb-4">
                  Like Y Combinator evaluates startups, we assess each bags token across 5 dimensions.
                  We focus on what actually differentiates winning projects.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
                  {SCORE_DIMENSIONS.map((item) => (
                    <div
                      key={item.title}
                      className="p-3 rounded-xl border border-border-primary hover:border-border-hover transition-all bg-bg-secondary/50"
                    >
                      <div className="flex items-center gap-2 mb-2 text-accent-neon">
                        <item.icon className="w-4 h-4" />
                        <h3 className="font-semibold text-xs">{item.title}</h3>
                      </div>
                      <span className="text-[10px] text-accent-neon/60 font-mono">{item.weight}</span>
                      <p className="text-[10px] text-text-muted leading-relaxed mt-1">
                        {item.description}
                      </p>
                    </div>
                  ))}
                </div>

                {/* Score Tiers Legend */}
                <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-border-primary">
                  {Object.entries(TIER_RANGES).map(([tier, { min, max, icon: Icon, color, bg }]) => (
                    <div
                      key={tier}
                      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full ${bg} border border-border-primary`}
                    >
                      <Icon className={`w-3 h-3 ${color}`} />
                      <span className={`text-[10px] font-medium capitalize ${color}`}>{tier}</span>
                      <span className="text-[10px] text-text-muted">({min}-{max})</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* View Mode Tabs (All / New Launches / Established) */}
        <section className="mb-4 max-w-7xl mx-auto">
          <div className="flex items-center gap-2 justify-center flex-wrap">
            <button
              onClick={() => setViewMode('all')}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold transition-all border ${
                viewMode === 'all'
                  ? 'bg-text-primary text-bg-primary border-text-primary'
                  : 'bg-transparent text-text-secondary border-border-primary hover:bg-bg-tertiary'
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              All Tokens
              <span className="text-xs opacity-60">{graduations.length}</span>
            </button>
            <button
              onClick={() => setViewMode('new')}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold transition-all border ${
                viewMode === 'new'
                  ? 'bg-accent-neon/10 text-accent-neon border-accent-neon/40'
                  : 'bg-transparent text-text-secondary border-border-primary hover:bg-bg-tertiary'
              }`}
            >
              <Rocket className="w-4 h-4" />
              New Launches
              <span className="text-xs opacity-60">{newLaunchCount}</span>
            </button>
            <button
              onClick={() => setViewMode('established')}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold transition-all border ${
                viewMode === 'established'
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/40'
                  : 'bg-transparent text-text-secondary border-border-primary hover:bg-bg-tertiary'
              }`}
            >
              <Crown className="w-4 h-4" />
              Established
              <span className="text-xs opacity-60">{establishedCount}</span>
            </button>
          </div>
        </section>

        {/* Tier Filter Tabs & Refresh */}
        <section className="mb-6 flex flex-col sm:flex-row items-center justify-between gap-4 max-w-7xl mx-auto">
          <div className="flex items-center gap-2 flex-wrap justify-center">
            <button
              onClick={() => setActiveFilter('all')}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all border ${
                activeFilter === 'all'
                  ? 'bg-text-primary text-bg-primary border-text-primary'
                  : 'bg-transparent text-text-secondary border-border-primary hover:bg-bg-tertiary'
              }`}
            >
              All Tiers
            </button>
            {(Object.keys(TIER_RANGES) as ScoreTier[]).map((tier) => {
              const { icon: Icon, color, bg } = TIER_RANGES[tier];
              return (
                <button
                  key={tier}
                  onClick={() => setActiveFilter(tier)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border ${
                    activeFilter === tier
                      ? `${bg} ${color} border-current`
                      : 'bg-transparent text-text-secondary border-border-primary hover:bg-bg-tertiary'
                  }`}
                >
                  <Icon className="w-3 h-3" />
                  <span className="capitalize">{tier}</span>
                  <span className="text-text-muted">({tierCounts[tier]})</span>
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-4">
            {lastUpdated && (
              <span className="text-[10px] text-text-muted font-mono">
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
          <div className="max-w-7xl mx-auto mb-6">
            <div className="bg-accent-neon/10 border border-accent-neon/30 rounded-xl p-4 text-accent-neon text-sm font-mono">
              {error}
            </div>
          </div>
        )}

        {/* Tokens Grid */}
        <section className="max-w-7xl mx-auto">
          {loading ? (
            <div className="text-center py-20">
              <div className="text-accent-neon font-mono animate-pulse text-lg">
                Loading tokens from Jupiter...
              </div>
              <p className="text-text-muted text-sm mt-2">Fetching 200+ tokens with full metadata</p>
            </div>
          ) : filteredGraduations.length === 0 ? (
            <div className="text-center py-20">
              <div className="card-glass p-12 max-w-md mx-auto">
                <Zap className="w-12 h-12 text-text-muted mx-auto mb-4" />
                <h3 className="font-display font-bold text-xl mb-2 text-text-primary">
                  No tokens match filters
                </h3>
                <p className="text-text-muted text-sm">
                  Try adjusting your view mode or tier filter.
                </p>
              </div>
            </div>
          ) : (
            <>
              <p className="text-xs text-text-muted mb-4 text-center">
                Showing {filteredGraduations.length} tokens
                {viewMode === 'new' && ' launched in the last 48 hours'}
                {viewMode === 'established' && ' with 7+ days of sustained activity'}
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {filteredGraduations.map((graduation) => (
                  <GraduationCard
                    key={graduation.mint}
                    graduation={graduation}
                  />
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
