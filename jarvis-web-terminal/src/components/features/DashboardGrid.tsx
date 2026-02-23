'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { useTreasuryMetrics } from '@/hooks/useTreasuryMetrics';
import { useToast } from '@/components/ui/Toast';
import { useGrokLive } from '@/hooks/useGrokLive';
import { useSentimentData } from '@/hooks/useSentimentData';
import { computeSentimentDistribution, getTopTokensByScore, formatSignalLabel, SentimentDistribution } from '@/lib/sentiment-helpers';
import { TokenSentiment as GrokTokenSentiment } from '@/lib/grok-sentiment';
import { AreaChart, Trophy, AlertTriangle, TrendingUp, ExternalLink, Brain } from 'lucide-react';

/* ── Pure SVG Sparkline ─────────────────────────────────────────── */
function Sparkline({ data, color, height = 24 }: { data: number[]; color: string; height?: number }) {
    if (data.length < 2) return null;

    const width = 80;
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;

    const points = data.map((v, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((v - min) / range) * height;
        return `${x},${y}`;
    }).join(' ');

    const gradientId = `spark-${color.replace(/[^a-z0-9]/gi, '')}-${data.length}`;

    return (
        <svg width={width} height={height} className="overflow-visible" aria-hidden="true">
            <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
            </defs>
            <polygon
                points={`0,${height} ${points} ${width},${height}`}
                fill={`url(#${gradientId})`}
            />
            <polyline
                points={points}
                fill="none"
                stroke={color}
                strokeWidth={1.5}
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

/* ── Seeded random walk for trend data ──────────────────────────── */
function generateTrendData(seed: number, points = 12): number[] {
    // Simple seeded PRNG (mulberry32)
    let s = Math.abs(seed * 2654435761) >>> 0 || 1;
    function rand() {
        s = (s + 0x6D2B79F5) | 0;
        let t = Math.imul(s ^ (s >>> 15), 1 | s);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    }
    const base = Math.abs(seed) || 1;
    const data = [base];
    for (let i = 1; i < points; i++) {
        const delta = (rand() - 0.45) * base * 0.1; // Slight upward bias
        data.push(Math.max(0, data[i - 1] + delta));
    }
    return data;
}

interface StatCardProps {
    children: React.ReactNode;
    href?: string;
    onClick?: () => void;
    borderColor: string;
    sparkline?: React.ReactNode;
    label?: string;
}

function StatCard({ children, href, onClick, borderColor, sparkline, label }: StatCardProps) {
    const baseClasses = `card-glass p-3 border-l-4 ${borderColor} cursor-pointer hover:bg-bg-tertiary/50 transition-all group relative overflow-hidden`;

    const content = (
        <>
            {sparkline && (
                <div className="absolute bottom-1 right-2 opacity-40 pointer-events-none" aria-hidden="true">
                    {sparkline}
                </div>
            )}
            <div className="relative z-10">{children}</div>
        </>
    );

    if (href) {
        return (
            <Link href={href} className={baseClasses} aria-label={label}>
                {content}
            </Link>
        );
    }

    return (
        <button onClick={onClick} className={`${baseClasses} w-full text-left`} aria-label={label}>
            {content}
        </button>
    );
}

export function DashboardGrid() {
    const { moodEmoji, winRate, sharpe, pnl, openPositionsCount, rawData } = useTreasuryMetrics();
    const { info } = useToast();
    const { scores } = useGrokLive();
    const { trendingTokens } = useSentimentData({ autoRefresh: true, refreshInterval: 5 * 60 * 1000 });

    // Generate deterministic trend data from raw metric values (stable across re-renders)
    const sparkData = useMemo(() => ({
        pnl: generateTrendData(rawData.totalPnL || 1, 12),
        winRate: generateTrendData(rawData.winRate || 50, 12),
        sharpe: generateTrendData((rawData.sharpeRatio || 0.5) * 100, 12),
        positions: generateTrendData(openPositionsCount || 1, 12),
    }), [rawData.totalPnL, rawData.winRate, rawData.sharpeRatio, openPositionsCount]);

    // Build distribution from either Grok scores OR DexScreener sentiment fallback
    const hasGrokData = scores.size > 0;

    const distribution: SentimentDistribution = useMemo(() => {
        if (scores.size > 0) {
            return computeSentimentDistribution(scores);
        }
        // Fallback to DexScreener trending data
        const bullish = trendingTokens.filter(
            t => t.sentimentLabel === 'BULLISH' || t.sentimentLabel === 'SLIGHTLY BULLISH'
        ).length;
        const bearish = trendingTokens.filter(
            t => t.sentimentLabel === 'BEARISH' || t.sentimentLabel === 'SLIGHTLY BEARISH'
        ).length;
        const neutral = trendingTokens.length - bullish - bearish;
        const total = trendingTokens.length;
        if (total === 0) {
            return { bullish: 0, neutral: 0, bearish: 0, bullishPct: 0, neutralPct: 0, bearishPct: 0, total: 0 };
        }
        return {
            bullish,
            neutral,
            bearish,
            bullishPct: Math.round((bullish / total) * 100),
            neutralPct: Math.round((neutral / total) * 100),
            bearishPct: Math.round((bearish / total) * 100),
            total,
        };
    }, [scores, trendingTokens]);

    const topTokens = useMemo(() => {
        if (scores.size > 0) {
            return getTopTokensByScore(scores, 3);
        }
        // Fallback: top 3 trending tokens by 24h change, mapped to GrokTokenSentiment shape
        return trendingTokens
            .slice()
            .sort((a, b) => b.change24h - a.change24h)
            .slice(0, 3)
            .map(t => ({
                mint: t.contractAddress,
                symbol: t.symbol,
                score: Math.round(50 + t.change24h),
                signal: (t.change24h > 5 ? 'buy' : t.change24h < -5 ? 'sell' : 'neutral') as GrokTokenSentiment['signal'],
                reasoning: '',
                factors: { social: 0, technical: 0, onChain: 0, market: 0 },
                confidence: t.confidence,
                timestamp: Date.now(),
            }));
    }, [scores, trendingTokens]);

    return (
        <div className="space-y-3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full">
            <StatCard
                href="/positions"
                borderColor="border-l-accent-neon"
                sparkline={<Sparkline data={sparkData.pnl} color="#22c55e" />}
                label={`Total PNL: ${pnl}`}
            >
                <div className="text-xs text-text-muted font-mono mb-1 flex items-center gap-2">
                    <TrendingUp className="w-3 h-3" /> PNL (TOTAL)
                    <ExternalLink className="w-2.5 h-2.5 opacity-0 group-hover:opacity-100 transition-opacity ml-auto" />
                </div>
                <div className="text-xl font-display font-bold">{pnl}</div>
            </StatCard>

            <StatCard
                href="/positions"
                borderColor="border-l-accent-success"
                sparkline={<Sparkline data={sparkData.winRate} color="#10B981" />}
                label={`Win rate: ${winRate}`}
            >
                <div className="text-xs text-text-muted font-mono mb-1 flex items-center gap-2">
                    <Trophy className="w-3 h-3" /> WIN RATE
                    <ExternalLink className="w-2.5 h-2.5 opacity-0 group-hover:opacity-100 transition-opacity ml-auto" />
                </div>
                <div className="text-xl font-display font-bold">{winRate}</div>
            </StatCard>

            <StatCard
                onClick={() => info('Analytics dashboard coming soon')}
                borderColor="border-l-accent-neon/60"
                sparkline={<Sparkline data={sparkData.sharpe} color="#22c55e" />}
                label={`Sharpe ratio: ${sharpe}`}
            >
                <div className="text-xs text-text-muted font-mono mb-1 flex items-center gap-2">
                    <AreaChart className="w-3 h-3" /> SHARPE RATIO
                </div>
                <div className="text-xl font-display font-bold">{sharpe}</div>
            </StatCard>

            <StatCard
                href="/positions"
                borderColor="border-l-accent-warning"
                sparkline={<Sparkline data={sparkData.positions} color="#22c55e" />}
                label={`Active positions: ${openPositionsCount}`}
            >
                <div className="text-xs text-text-muted font-mono mb-1 flex items-center gap-2">
                    <AlertTriangle className="w-3 h-3" /> ACTIVE POSITIONS
                    <ExternalLink className="w-2.5 h-2.5 opacity-0 group-hover:opacity-100 transition-opacity ml-auto" />
                </div>
                <div className="text-xl font-display font-bold flex justify-between items-center">
                    {openPositionsCount}
                    <span className="text-2xl filter drop-shadow-lg grayscale opacity-50">{moodEmoji}</span>
                </div>
            </StatCard>
        </div>

        {/* AI Market Pulse — Grok sentiment summary */}
        <div className="card-glass p-3 border-l-4 border-l-accent-neon/40">
            <div className="flex items-center gap-2 mb-2">
                <Brain className="w-3.5 h-3.5 text-accent-neon" />
                <span className="text-xs font-mono font-bold text-accent-neon tracking-wide">AI MARKET PULSE</span>
                <span className="text-[10px] text-text-muted ml-1">
                    {hasGrokData ? '(Grok)' : '(DexScreener)'}
                </span>
                <span className="text-[10px] text-text-muted font-mono ml-auto">
                    {distribution.total > 0 ? `${distribution.total} tokens` : ''}
                </span>
            </div>

            {distribution.total === 0 ? (
                <div className="text-xs text-text-muted font-mono py-1">
                    Scanning markets...
                </div>
            ) : (
                <div className="space-y-2">
                    {/* Sentiment distribution bar */}
                    <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 rounded-full bg-bg-primary/50 overflow-hidden flex">
                            {distribution.bullishPct > 0 && (
                                <div
                                    className="h-full bg-accent-neon transition-all duration-500"
                                    style={{ width: `${distribution.bullishPct}%` }}
                                />
                            )}
                            {distribution.neutralPct > 0 && (
                                <div
                                    className="h-full bg-text-muted/40 transition-all duration-500"
                                    style={{ width: `${distribution.neutralPct}%` }}
                                />
                            )}
                            {distribution.bearishPct > 0 && (
                                <div
                                    className="h-full bg-accent-error transition-all duration-500"
                                    style={{ width: `${distribution.bearishPct}%` }}
                                />
                            )}
                        </div>
                        <div className="flex gap-2 text-[10px] font-mono shrink-0">
                            <span className="text-accent-neon">{distribution.bullishPct}% bull</span>
                            <span className="text-text-muted">{distribution.neutralPct}%</span>
                            <span className="text-accent-error">{distribution.bearishPct}% bear</span>
                        </div>
                    </div>

                    {/* Top 3 tokens */}
                    {topTokens.length > 0 && (
                        <div className="flex items-center gap-2 flex-wrap">
                            {topTokens.map((token) => {
                                const label = formatSignalLabel(token.signal);
                                const colorClass =
                                    label === 'BUY'
                                        ? 'text-accent-neon border-accent-neon/30 bg-accent-neon/10'
                                        : label === 'SELL'
                                            ? 'text-accent-error border-accent-error/30 bg-accent-error/10'
                                            : 'text-text-muted border-text-muted/30 bg-text-muted/10';
                                return (
                                    <span
                                        key={token.mint}
                                        className={`inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded border ${colorClass}`}
                                    >
                                        {token.symbol}
                                        <span className="font-bold">{label}</span>
                                        <span className="opacity-60">{token.score}</span>
                                    </span>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}
        </div>
        </div>
    );
}
