/**
 * Weight Calibration - Dynamic Signal Optimization
 * 
 * Correlates signals with outcomes to auto-adjust scoring weights:
 * - Tracks trade outcomes with their input signals
 * - Calculates correlation coefficients
 * - Adjusts weights based on predictive power
 * - Persists calibrated weights to localStorage
 */

export interface TradeOutcome {
    timestamp: number;
    mint: string;
    symbol: string;

    // Entry signals at time of trade
    signals: {
        bondingCurve: number;
        market: number;
        creator: number;
        social: number;
        distribution: number;
        overall: number;
    };

    // Outcome metrics
    entryPrice: number;
    exitPrice: number;
    pnlPercent: number;
    holdTimeMs: number;
    exitReason: 'take-profit' | 'stop-loss' | 'manual' | 'auto-exit';
}

export interface CalibrationResult {
    correlations: Record<string, number>;
    adjustedWeights: Record<string, number>;
    sampleSize: number;
    calibratedAt: number;
    recommendations: string[];
}

const STORAGE_KEY = 'jarvis_weight_calibration';
const OUTCOMES_KEY = 'jarvis_trade_outcomes';
const MIN_SAMPLES = 10; // Minimum trades for meaningful calibration

/**
 * WeightCalibrator - Adjusts scoring weights based on trade outcomes
 */
export class WeightCalibrator {
    private outcomes: TradeOutcome[] = [];
    private currentWeights: Record<string, number>;

    constructor() {
        this.currentWeights = this.loadWeights();
        this.outcomes = this.loadOutcomes();
    }

    /**
     * Record a trade outcome for calibration
     */
    recordOutcome(outcome: TradeOutcome): void {
        this.outcomes.push(outcome);

        // Keep last 100 trades for calibration
        if (this.outcomes.length > 100) {
            this.outcomes = this.outcomes.slice(-100);
        }

        this.saveOutcomes();
    }

    /**
     * Run calibration to adjust weights
     */
    calibrate(): CalibrationResult {
        const recommendations: string[] = [];

        if (this.outcomes.length < MIN_SAMPLES) {
            return {
                correlations: {},
                adjustedWeights: this.currentWeights,
                sampleSize: this.outcomes.length,
                calibratedAt: Date.now(),
                recommendations: [`Need ${MIN_SAMPLES - this.outcomes.length} more trades for calibration`],
            };
        }

        // Calculate correlations for each signal
        const signalNames = ['bondingCurve', 'market', 'creator', 'social', 'distribution'];
        const correlations: Record<string, number> = {};

        for (const signal of signalNames) {
            const correlation = this.calculateCorrelation(
                this.outcomes.map(o => o.signals[signal as keyof typeof o.signals] as number),
                this.outcomes.map(o => o.pnlPercent)
            );
            correlations[signal] = correlation;
        }

        // Adjust weights based on correlations
        const adjustedWeights: Record<string, number> = {};
        let totalPositiveCorrelation = 0;

        // Sum positive correlations for normalization
        for (const signal of signalNames) {
            const corr = Math.max(0, correlations[signal]); // Only positive correlations
            totalPositiveCorrelation += corr;
        }

        // Calculate new weights
        for (const signal of signalNames) {
            const corr = Math.max(0, correlations[signal]);

            if (totalPositiveCorrelation > 0) {
                // Weight based on correlation strength
                adjustedWeights[signal] = corr / totalPositiveCorrelation;
            } else {
                // Fallback to equal weights
                adjustedWeights[signal] = 0.2;
            }

            // Generate recommendations
            if (correlations[signal] < 0.1) {
                recommendations.push(`${signal} signal has low predictive power (${(correlations[signal] * 100).toFixed(1)}%)`);
            }
            if (correlations[signal] < 0) {
                recommendations.push(`⚠️ ${signal} signal is inversely correlated - consider inverting`);
            }
        }

        // Save calibrated weights
        this.currentWeights = adjustedWeights;
        this.saveWeights();

        return {
            correlations,
            adjustedWeights,
            sampleSize: this.outcomes.length,
            calibratedAt: Date.now(),
            recommendations,
        };
    }

    /**
     * Get current calibrated weights
     */
    getWeights(): Record<string, number> {
        return { ...this.currentWeights };
    }

    /**
     * Reset to default weights
     */
    resetWeights(): void {
        this.currentWeights = {
            bondingCurve: 0.25,
            market: 0.25,
            creator: 0.20,
            social: 0.15,
            distribution: 0.15,
        };
        this.saveWeights();
    }

    /**
     * Calculate Pearson correlation coefficient
     */
    private calculateCorrelation(x: number[], y: number[]): number {
        const n = x.length;
        if (n === 0) return 0;

        const sumX = x.reduce((a, b) => a + b, 0);
        const sumY = y.reduce((a, b) => a + b, 0);
        const sumXY = x.reduce((acc, xi, i) => acc + xi * y[i], 0);
        const sumX2 = x.reduce((acc, xi) => acc + xi * xi, 0);
        const sumY2 = y.reduce((acc, yi) => acc + yi * yi, 0);

        const numerator = n * sumXY - sumX * sumY;
        const denominator = Math.sqrt(
            (n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY)
        );

        if (denominator === 0) return 0;
        return numerator / denominator;
    }

    /**
     * Load weights from storage
     */
    private loadWeights(): Record<string, number> {
        if (typeof window === 'undefined') {
            return {
                bondingCurve: 0.25,
                market: 0.25,
                creator: 0.20,
                social: 0.15,
                distribution: 0.15,
            };
        }

        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                return JSON.parse(stored);
            }
        } catch {
            // Ignore errors
        }

        return {
            bondingCurve: 0.25,
            market: 0.25,
            creator: 0.20,
            social: 0.15,
            distribution: 0.15,
        };
    }

    /**
     * Save weights to storage
     */
    private saveWeights(): void {
        if (typeof window === 'undefined') return;

        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(this.currentWeights));
        } catch {
            // Ignore errors
        }
    }

    /**
     * Load outcomes from storage
     */
    private loadOutcomes(): TradeOutcome[] {
        if (typeof window === 'undefined') return [];

        try {
            const stored = localStorage.getItem(OUTCOMES_KEY);
            if (stored) {
                return JSON.parse(stored);
            }
        } catch {
            // Ignore errors
        }

        return [];
    }

    /**
     * Save outcomes to storage
     */
    private saveOutcomes(): void {
        if (typeof window === 'undefined') return;

        try {
            localStorage.setItem(OUTCOMES_KEY, JSON.stringify(this.outcomes));
        } catch {
            // Ignore errors
        }
    }

    /**
     * Get calibration stats
     */
    getStats(): {
        totalTrades: number;
        winRate: number;
        avgPnl: number;
        lastCalibration: number | null;
    } {
        const wins = this.outcomes.filter(o => o.pnlPercent > 0);
        const winRate = this.outcomes.length > 0
            ? (wins.length / this.outcomes.length) * 100
            : 0;
        const avgPnl = this.outcomes.length > 0
            ? this.outcomes.reduce((acc, o) => acc + o.pnlPercent, 0) / this.outcomes.length
            : 0;

        return {
            totalTrades: this.outcomes.length,
            winRate,
            avgPnl,
            lastCalibration: null, // Would be stored separately
        };
    }
}

// Singleton instance
export const weightCalibrator = new WeightCalibrator();
