import { describe, it, expect } from 'vitest';

/**
 * Tests for the sentiment aggregation logic used by DashboardGrid's
 * "AI Market Pulse" section. We test the pure computation functions
 * that are extracted into a helper so they can be unit-tested without
 * rendering React components.
 */
import {
    computeSentimentDistribution,
    getTopTokensByScore,
    formatSignalLabel,
    type SentimentDistribution,
} from '@/lib/sentiment-helpers';
import type { TokenSentiment } from '@/lib/grok-sentiment';

/* ── Factory helper ─────────────────────────────────────────────── */
function makeSentiment(overrides: Partial<TokenSentiment> = {}): TokenSentiment {
    return {
        mint: 'So11111111111111111111111111111111111111111',
        symbol: 'SOL',
        score: 50,
        signal: 'neutral',
        reasoning: 'test',
        factors: { social: 50, technical: 50, onChain: 50, market: 50 },
        confidence: 80,
        timestamp: Date.now(),
        ...overrides,
    };
}

/* ────────────────────────────────────────────────────────────────── */
describe('computeSentimentDistribution', () => {
    it('returns zeroes when the scores map is empty', () => {
        const result = computeSentimentDistribution(new Map());
        expect(result).toEqual<SentimentDistribution>({
            bullish: 0,
            neutral: 0,
            bearish: 0,
            bullishPct: 0,
            neutralPct: 0,
            bearishPct: 0,
            total: 0,
        });
    });

    it('classifies scores >= 60 as bullish', () => {
        const scores = new Map<string, TokenSentiment>([
            ['a', makeSentiment({ mint: 'a', score: 75, signal: 'buy' })],
            ['b', makeSentiment({ mint: 'b', score: 90, signal: 'strong_buy' })],
        ]);
        const result = computeSentimentDistribution(scores);
        expect(result.bullish).toBe(2);
        expect(result.bearish).toBe(0);
        expect(result.neutral).toBe(0);
        expect(result.bullishPct).toBe(100);
    });

    it('classifies scores <= 40 as bearish', () => {
        const scores = new Map<string, TokenSentiment>([
            ['a', makeSentiment({ mint: 'a', score: 20, signal: 'strong_sell' })],
            ['b', makeSentiment({ mint: 'b', score: 35, signal: 'sell' })],
        ]);
        const result = computeSentimentDistribution(scores);
        expect(result.bearish).toBe(2);
        expect(result.bullish).toBe(0);
        expect(result.bearishPct).toBe(100);
    });

    it('classifies scores between 41-59 as neutral', () => {
        const scores = new Map<string, TokenSentiment>([
            ['a', makeSentiment({ mint: 'a', score: 50, signal: 'neutral' })],
            ['b', makeSentiment({ mint: 'b', score: 45, signal: 'neutral' })],
        ]);
        const result = computeSentimentDistribution(scores);
        expect(result.neutral).toBe(2);
        expect(result.neutralPct).toBe(100);
    });

    it('computes correct percentages for a mixed set', () => {
        const scores = new Map<string, TokenSentiment>([
            ['a', makeSentiment({ mint: 'a', score: 80, signal: 'buy' })],       // bullish
            ['b', makeSentiment({ mint: 'b', score: 70, signal: 'buy' })],       // bullish
            ['c', makeSentiment({ mint: 'c', score: 50, signal: 'neutral' })],   // neutral
            ['d', makeSentiment({ mint: 'd', score: 20, signal: 'sell' })],      // bearish
        ]);
        const result = computeSentimentDistribution(scores);
        expect(result.total).toBe(4);
        expect(result.bullish).toBe(2);
        expect(result.neutral).toBe(1);
        expect(result.bearish).toBe(1);
        expect(result.bullishPct).toBe(50);
        expect(result.neutralPct).toBe(25);
        expect(result.bearishPct).toBe(25);
    });
});

/* ────────────────────────────────────────────────────────────────── */
describe('getTopTokensByScore', () => {
    it('returns empty array when no scores', () => {
        expect(getTopTokensByScore(new Map(), 3)).toEqual([]);
    });

    it('returns top N tokens sorted by score descending', () => {
        const scores = new Map<string, TokenSentiment>([
            ['a', makeSentiment({ mint: 'a', symbol: 'ALPHA', score: 60 })],
            ['b', makeSentiment({ mint: 'b', symbol: 'BETA', score: 90 })],
            ['c', makeSentiment({ mint: 'c', symbol: 'GAMMA', score: 75 })],
            ['d', makeSentiment({ mint: 'd', symbol: 'DELTA', score: 40 })],
        ]);
        const top = getTopTokensByScore(scores, 3);
        expect(top).toHaveLength(3);
        expect(top[0].symbol).toBe('BETA');
        expect(top[1].symbol).toBe('GAMMA');
        expect(top[2].symbol).toBe('ALPHA');
    });

    it('returns all tokens when fewer than N exist', () => {
        const scores = new Map<string, TokenSentiment>([
            ['a', makeSentiment({ mint: 'a', symbol: 'ONLY', score: 55 })],
        ]);
        const top = getTopTokensByScore(scores, 3);
        expect(top).toHaveLength(1);
        expect(top[0].symbol).toBe('ONLY');
    });
});

/* ────────────────────────────────────────────────────────────────── */
describe('formatSignalLabel', () => {
    it('maps strong_buy to BUY', () => {
        expect(formatSignalLabel('strong_buy')).toBe('BUY');
    });

    it('maps buy to BUY', () => {
        expect(formatSignalLabel('buy')).toBe('BUY');
    });

    it('maps neutral to HOLD', () => {
        expect(formatSignalLabel('neutral')).toBe('HOLD');
    });

    it('maps sell to SELL', () => {
        expect(formatSignalLabel('sell')).toBe('SELL');
    });

    it('maps strong_sell to SELL', () => {
        expect(formatSignalLabel('strong_sell')).toBe('SELL');
    });
});
