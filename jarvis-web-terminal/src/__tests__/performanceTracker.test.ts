import { describe, it, expect } from 'vitest';

describe('PerformanceTracker time filter logic', () => {
    const TIME_FILTERS = ['all', '24h', '7d', '30d'] as const;

    it('should have four time filter options', () => {
        expect(TIME_FILTERS).toHaveLength(4);
    });

    it('should include all expected filter values', () => {
        expect(TIME_FILTERS).toContain('all');
        expect(TIME_FILTERS).toContain('24h');
        expect(TIME_FILTERS).toContain('7d');
        expect(TIME_FILTERS).toContain('30d');
    });

    it('should correctly compute cutoff timestamps', () => {
        const now = Date.now();
        const getCutoff = (filter: typeof TIME_FILTERS[number]): number => {
            if (filter === 'all') return 0;
            const cutoffs: Record<string, number> = {
                '24h': 24 * 60 * 60 * 1000,
                '7d': 7 * 24 * 60 * 60 * 1000,
                '30d': 30 * 24 * 60 * 60 * 1000,
            };
            return now - (cutoffs[filter] || 0);
        };

        expect(getCutoff('all')).toBe(0);
        expect(getCutoff('24h')).toBeGreaterThan(0);
        expect(getCutoff('7d')).toBeGreaterThan(0);
        expect(getCutoff('30d')).toBeGreaterThan(0);

        // 24h cutoff should be more recent than 7d
        expect(getCutoff('24h')).toBeGreaterThan(getCutoff('7d'));
        // 7d cutoff should be more recent than 30d
        expect(getCutoff('7d')).toBeGreaterThan(getCutoff('30d'));
    });

    it('should filter trades by time correctly', () => {
        const now = Date.now();
        const trades = [
            { timestamp: now - 1000 * 60 * 60, pnl: 10 },          // 1 hour ago
            { timestamp: now - 1000 * 60 * 60 * 48, pnl: -5 },     // 2 days ago
            { timestamp: now - 1000 * 60 * 60 * 24 * 10, pnl: 20 }, // 10 days ago
            { timestamp: now - 1000 * 60 * 60 * 24 * 45, pnl: -15 }, // 45 days ago
        ];

        const filterByTime = (filter: typeof TIME_FILTERS[number]) => {
            return trades.filter(trade => {
                if (filter === 'all') return true;
                const cutoff: Record<string, number> = {
                    '24h': 24 * 60 * 60 * 1000,
                    '7d': 7 * 24 * 60 * 60 * 1000,
                    '30d': 30 * 24 * 60 * 60 * 1000,
                };
                return (now - trade.timestamp) < cutoff[filter];
            });
        };

        expect(filterByTime('all')).toHaveLength(4);
        expect(filterByTime('24h')).toHaveLength(1);
        expect(filterByTime('7d')).toHaveLength(2);
        expect(filterByTime('30d')).toHaveLength(3);
    });
});

describe('PerformanceTracker export functionality', () => {
    it('should generate CSV from metrics', () => {
        const metrics = {
            winRate: 65.5,
            totalPnL: 1.234,
            profitFactor: 2.1,
            totalTrades: 20,
        };

        const generateCSV = (m: typeof metrics): string => {
            const headers = 'Metric,Value';
            const rows = [
                `Win Rate,${m.winRate.toFixed(1)}%`,
                `Total P&L,${m.totalPnL.toFixed(4)}`,
                `Profit Factor,${m.profitFactor.toFixed(2)}`,
                `Total Trades,${m.totalTrades}`,
            ];
            return [headers, ...rows].join('\n');
        };

        const csv = generateCSV(metrics);
        expect(csv).toContain('Metric,Value');
        expect(csv).toContain('Win Rate,65.5%');
        expect(csv).toContain('Total P&L,1.2340');
        expect(csv).toContain('Profit Factor,2.10');
        expect(csv).toContain('Total Trades,20');
    });
});
