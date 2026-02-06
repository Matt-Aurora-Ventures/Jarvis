/**
 * Graduation Tracker - Monitors Meteora pool migrations
 * 
 * Tracks tokens graduating from Bags.fm DBC to Meteora DAMM v2:
 * - Monitors graduation events
 * - Auto-promotes assets from "Shitcoin" to "Micro" tier
 * - Triggers position re-evaluation
 */

// Meteora program IDs
export const METEORA_PROGRAMS = {
    DBC: 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN',      // Dynamic Bonding Curve
    DAMM_V2: 'cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG', // DAMM v2
    DLMM: 'LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo',    // DLMM
};

export interface GraduationEvent {
    mint: string;
    symbol: string;
    name: string;
    timestamp: number;

    // Migration details
    fromProgram: string;
    toProgram: string;
    poolAddress: string;

    // Post-graduation metrics
    initialLiquidity: number;
    initialMarketCap: number;

    // Scoring
    graduationScore: number;
    newTier: 'micro' | 'mid';
}

export interface GraduationSubscription {
    unsubscribe: () => void;
}

type GraduationCallback = (event: GraduationEvent) => void;

/**
 * GraduationTracker - Polls for and tracks token graduations
 */
export class GraduationTracker {
    private callbacks: Set<GraduationCallback> = new Set();
    private pollingInterval: NodeJS.Timeout | null = null;
    private lastCheckedTimestamp = Date.now();
    private isPolling = false;

    /**
     * Start polling for graduations
     */
    startPolling(intervalMs = 30000): void {
        if (this.isPolling) return;

        this.isPolling = true;
        this.pollingInterval = setInterval(() => {
            this.checkForGraduations();
        }, intervalMs);

        // Initial check
        this.checkForGraduations();
    }

    /**
     * Stop polling
     */
    stopPolling(): void {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
        this.isPolling = false;
    }

    /**
     * Subscribe to graduation events
     */
    subscribe(callback: GraduationCallback): GraduationSubscription {
        this.callbacks.add(callback);

        return {
            unsubscribe: () => {
                this.callbacks.delete(callback);
            },
        };
    }

    /**
     * Check for new graduations from Bags API
     */
    private async checkForGraduations(): Promise<void> {
        try {
            // Try multiple endpoints for graduation data
            const endpoints = [
                'https://public-api-v2.bags.fm/api/graduations',
                'https://public-api-v2.bags.fm/api/tokens/graduated',
                'https://public-api-v2.bags.fm/api/events/graduations',
            ];

            for (const endpoint of endpoints) {
                try {
                    const response = await fetch(`${endpoint}?since=${this.lastCheckedTimestamp}&limit=50`);

                    if (!response.ok) continue;

                    const data = await response.json();
                    const graduations = data.data || data.graduations || data;

                    if (Array.isArray(graduations)) {
                        this.processGraduations(graduations);
                        this.lastCheckedTimestamp = Date.now();
                        return;
                    }
                } catch {
                    continue;
                }
            }
        } catch (error) {
            console.error('Failed to check graduations:', error);
        }
    }

    /**
     * Process graduation events
     */
    private processGraduations(graduations: unknown[]): void {
        for (const grad of graduations) {
            const event = this.parseGraduationEvent(grad);
            if (event) {
                this.notifySubscribers(event);
            }
        }
    }

    /**
     * Parse raw graduation data into structured event
     */
    private parseGraduationEvent(data: unknown): GraduationEvent | null {
        if (!data || typeof data !== 'object') return null;

        const d = data as Record<string, unknown>;

        // Required fields
        const mint = d.mint || d.token_mint || d.tokenMint;
        if (typeof mint !== 'string') return null;

        // Calculate graduation score based on available metrics
        const liquidity = Number(d.liquidity || d.initial_liquidity || 0);
        const marketCap = Number(d.market_cap || d.marketCap || 0);
        const holders = Number(d.holders || d.holder_count || 0);

        const graduationScore = this.calculateGraduationScore(liquidity, marketCap, holders);

        return {
            mint,
            symbol: String(d.symbol || d.ticker || 'UNKNOWN'),
            name: String(d.name || d.token_name || 'Unknown Token'),
            timestamp: Number(d.timestamp || d.graduated_at || Date.now()),
            fromProgram: METEORA_PROGRAMS.DBC,
            toProgram: METEORA_PROGRAMS.DAMM_V2,
            poolAddress: String(d.pool || d.pool_address || ''),
            initialLiquidity: liquidity,
            initialMarketCap: marketCap,
            graduationScore,
            newTier: marketCap >= 1000000 ? 'mid' : 'micro',
        };
    }

    /**
     * Calculate graduation score based on initial metrics
     */
    private calculateGraduationScore(
        liquidity: number,
        marketCap: number,
        holders: number
    ): number {
        // Score components
        const liquidityScore = Math.min(40, (liquidity / 50000) * 40);
        const marketCapScore = Math.min(30, (marketCap / 500000) * 30);
        const holdersScore = Math.min(30, (holders / 300) * 30);

        return Math.round(liquidityScore + marketCapScore + holdersScore);
    }

    /**
     * Notify all subscribers of graduation event
     */
    private notifySubscribers(event: GraduationEvent): void {
        console.log(`🎓 Graduation: ${event.symbol} (${event.newTier.toUpperCase()})`);

        for (const callback of this.callbacks) {
            try {
                callback(event);
            } catch (error) {
                console.error('Graduation callback error:', error);
            }
        }
    }

    /**
     * Get historical graduations
     */
    async getRecentGraduations(limit = 20): Promise<GraduationEvent[]> {
        try {
            const response = await fetch(
                `https://public-api-v2.bags.fm/api/graduations?limit=${limit}`
            );

            if (!response.ok) return [];

            const data = await response.json();
            const graduations = data.data || data.graduations || data;

            if (!Array.isArray(graduations)) return [];

            return graduations
                .map(g => this.parseGraduationEvent(g))
                .filter((g): g is GraduationEvent => g !== null);
        } catch {
            return [];
        }
    }
}

// Singleton instance
export const graduationTracker = new GraduationTracker();
