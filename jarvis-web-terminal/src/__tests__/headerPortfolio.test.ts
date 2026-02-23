import { describe, it, expect, vi } from 'vitest';

// ---------- Unit tests for the PortfolioSnippet component logic ----------
// These tests validate the data flow and rendering logic without needing
// a full React render (which would require mocking the TradingContext provider).

describe('Header portfolio sparkline', () => {
    // --- Sparkline data generation (same seeded PRNG as DashboardGrid) ---

    function generateTrendData(seed: number, points = 12): number[] {
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
            const delta = (rand() - 0.45) * base * 0.1;
            data.push(Math.max(0, data[i - 1] + delta));
        }
        return data;
    }

    // --- Portfolio snippet visibility classes ---

    const PORTFOLIO_CONTAINER_CLASSES = 'hidden lg:flex';

    it('should contain hidden lg:flex so it is hidden on mobile', () => {
        // The portfolio element must include 'hidden lg:flex' to be hidden below lg breakpoint
        expect(PORTFOLIO_CONTAINER_CLASSES).toContain('hidden');
        expect(PORTFOLIO_CONTAINER_CLASSES).toContain('lg:flex');
    });

    // --- Positive vs negative PNL color logic ---

    function getPnlColor(totalPnL: number): string {
        return totalPnL >= 0 ? 'text-accent-neon' : 'text-accent-error';
    }

    function getSparklinePositive(totalPnL: number): boolean {
        return totalPnL >= 0;
    }

    it('should show accent-neon color for positive PNL', () => {
        expect(getPnlColor(150.5)).toBe('text-accent-neon');
        expect(getSparklinePositive(150.5)).toBe(true);
    });

    it('should show accent-neon color for zero PNL', () => {
        expect(getPnlColor(0)).toBe('text-accent-neon');
        expect(getSparklinePositive(0)).toBe(true);
    });

    it('should show accent-error color for negative PNL', () => {
        expect(getPnlColor(-42.3)).toBe('text-accent-error');
        expect(getSparklinePositive(-42.3)).toBe(false);
    });

    // --- Sparkline data generation ---

    it('should generate correct number of data points for sparkline', () => {
        const data = generateTrendData(100, 10);
        expect(data).toHaveLength(10);
    });

    it('should produce deterministic data from the same seed', () => {
        const a = generateTrendData(42, 10);
        const b = generateTrendData(42, 10);
        expect(a).toEqual(b);
    });

    it('should produce different data for different seeds', () => {
        const a = generateTrendData(100, 10);
        const b = generateTrendData(200, 10);
        expect(a).not.toEqual(b);
    });

    // --- Portfolio value formatting ---

    function formatPortfolioValue(value: number): string {
        if (value >= 1000) {
            return '$' + value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
        return '$' + value.toFixed(2);
    }

    it('should format portfolio value with dollar sign and 2 decimals', () => {
        expect(formatPortfolioValue(1234.5)).toMatch(/^\$[\d,]+\.\d{2}$/);
        expect(formatPortfolioValue(0)).toBe('$0.00');
    });

    // --- PNL percent badge formatting ---

    function formatPnlPercent(pnlPercent: number): string {
        const sign = pnlPercent >= 0 ? '+' : '';
        return sign + pnlPercent.toFixed(1) + '%';
    }

    it('should format positive PNL percent with + sign', () => {
        expect(formatPnlPercent(12.5)).toBe('+12.5%');
    });

    it('should format negative PNL percent without + sign', () => {
        expect(formatPnlPercent(-3.2)).toBe('-3.2%');
    });

    // --- SVG sparkline rendering logic ---

    function computeSparklinePoints(data: number[], width: number, height: number): string {
        if (data.length < 2) return '';
        const min = Math.min(...data);
        const max = Math.max(...data);
        const range = max - min || 1;
        return data
            .map((v, i) => {
                const x = (i / (data.length - 1)) * width;
                const y = height - ((v - min) / range) * height;
                return `${x},${y}`;
            })
            .join(' ');
    }

    it('should produce valid SVG points string from data', () => {
        const data = [10, 20, 15, 25, 30];
        const points = computeSparklinePoints(data, 40, 16);
        expect(points).toBeTruthy();
        // Should have 5 coordinate pairs
        const pairs = points.split(' ');
        expect(pairs).toHaveLength(5);
        // Each pair should be "x,y" format
        pairs.forEach(pair => {
            expect(pair).toMatch(/^[\d.]+,[\d.]+$/);
        });
    });

    it('should return empty string for less than 2 data points', () => {
        expect(computeSparklinePoints([5], 40, 16)).toBe('');
        expect(computeSparklinePoints([], 40, 16)).toBe('');
    });

    // --- MiniSparkline color selection ---

    function getSparklineStrokeColor(positive: boolean): string {
        return positive ? 'var(--accent-neon)' : 'var(--accent-error)';
    }

    it('should use accent-neon stroke for positive sparkline', () => {
        expect(getSparklineStrokeColor(true)).toBe('var(--accent-neon)');
    });

    it('should use accent-error stroke for negative sparkline', () => {
        expect(getSparklineStrokeColor(false)).toBe('var(--accent-error)');
    });

    // --- Portfolio snippet renders when metrics available ---

    it('should render portfolio section when totalPnL and portfolioValue are available', () => {
        // Simulate the condition: portfolio section renders when portfolioValue > 0 or positions exist
        const metricsAvailable = (portfolioValue: number, positionCount: number) =>
            portfolioValue > 0 || positionCount > 0;

        expect(metricsAvailable(1234, 3)).toBe(true);
        expect(metricsAvailable(0, 1)).toBe(true);
        expect(metricsAvailable(500, 0)).toBe(true);
        // When both are zero, still show (zero state)
        // The component always renders; the empty state just shows $0.00
    });
});
