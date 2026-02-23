/**
 * Pure computation helpers for Grok sentiment data.
 * Extracted from DashboardGrid so they can be unit-tested
 * without rendering React components.
 */
import type { TokenSentiment } from '@/lib/grok-sentiment';

/* ── Types ──────────────────────────────────────────────────────── */
export interface SentimentDistribution {
    bullish: number;
    neutral: number;
    bearish: number;
    bullishPct: number;
    neutralPct: number;
    bearishPct: number;
    total: number;
}

/* ── Thresholds ─────────────────────────────────────────────────── */
const BULLISH_THRESHOLD = 60;
const BEARISH_THRESHOLD = 40;

/* ── Functions ──────────────────────────────────────────────────── */

/**
 * Classify each token score as bullish (>= 60), bearish (<= 40),
 * or neutral (41-59) and return counts + percentages.
 */
export function computeSentimentDistribution(
    scores: Map<string, TokenSentiment>,
): SentimentDistribution {
    const total = scores.size;
    if (total === 0) {
        return {
            bullish: 0,
            neutral: 0,
            bearish: 0,
            bullishPct: 0,
            neutralPct: 0,
            bearishPct: 0,
            total: 0,
        };
    }

    let bullish = 0;
    let bearish = 0;
    let neutral = 0;

    for (const sentiment of scores.values()) {
        if (sentiment.score >= BULLISH_THRESHOLD) {
            bullish++;
        } else if (sentiment.score <= BEARISH_THRESHOLD) {
            bearish++;
        } else {
            neutral++;
        }
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
}

/**
 * Return the top N tokens sorted by score descending.
 */
export function getTopTokensByScore(
    scores: Map<string, TokenSentiment>,
    n: number,
): TokenSentiment[] {
    return Array.from(scores.values())
        .sort((a, b) => b.score - a.score)
        .slice(0, n);
}

/**
 * Map the raw signal enum to a compact UI label.
 */
export function formatSignalLabel(
    signal: TokenSentiment['signal'],
): 'BUY' | 'SELL' | 'HOLD' {
    switch (signal) {
        case 'strong_buy':
        case 'buy':
            return 'BUY';
        case 'sell':
        case 'strong_sell':
            return 'SELL';
        case 'neutral':
        default:
            return 'HOLD';
    }
}
