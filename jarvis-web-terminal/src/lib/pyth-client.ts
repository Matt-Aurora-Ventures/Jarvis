/**
 * Pyth Network Integration for Jarvis Trading Terminal
 * Uses Pyth Hermes API for high-confidence price feeds on established assets
 */

export interface PythPrice {
    id: string;
    price: {
        price: string;
        conf: string;
        expo: number;
        publish_time: number;
    };
    ema_price: {
        price: string;
        conf: string;
        expo: number;
    };
}

export interface PriceData {
    price: number;
    confidence: number;
    timestamp: number;
    source: 'pyth' | 'bags' | 'jupiter' | 'synthetic';
    confidenceRatio: number; // conf/price ratio - lower is better
}

// Pyth Price Feed IDs for common Solana assets
export const PYTH_PRICE_FEEDS: Record<string, string> = {
    SOL: 'ef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4c1c14a6e58a24',
    BTC: 'e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43',
    ETH: 'ff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace',
    USDC: 'eaa020c61cc479712813461ce153894a96a6c00b21ed0cfc2798d1f9a9e9c94a',
    USDT: '2b89b9dc8fdf9f34709a5b106b472f0f39bb6ca9ce04b0fd0a59b0b6d4d6e65f',
    BONK: '72b021217ca3fe68922a19aaf990109cb9d84e9ad004b4d2025ad6f529314419',
    JUP: '0a0408d619e9380abad35060f9192039ed5042fa6f82301d0e48a0c6406e6c2d',
};

// Pyth Hermes API (free, no auth required)
const PYTH_HERMES_URL = 'https://hermes.pyth.network';

export class PythClient {
    private cache: Map<string, { data: PriceData; timestamp: number }> = new Map();
    private cacheMaxAge = 1000; // 1 second cache

    /**
     * Get latest price from Pyth Hermes for a given feed ID
     */
    async getPrice(feedId: string): Promise<PriceData | null> {
        // Check cache
        const cached = this.cache.get(feedId);
        if (cached && Date.now() - cached.timestamp < this.cacheMaxAge) {
            return cached.data;
        }

        try {
            const response = await fetch(
                `${PYTH_HERMES_URL}/v2/updates/price/latest?ids[]=${feedId}`
            );

            if (!response.ok) {
                console.warn(`Pyth API error: ${response.status}`);
                return null;
            }

            const data = await response.json();
            const priceUpdate = data.parsed?.[0];

            if (!priceUpdate) return null;

            const price = parseFloat(priceUpdate.price.price) * Math.pow(10, priceUpdate.price.expo);
            const confidence = parseFloat(priceUpdate.price.conf) * Math.pow(10, priceUpdate.price.expo);

            const priceData: PriceData = {
                price,
                confidence,
                timestamp: priceUpdate.price.publish_time * 1000,
                source: 'pyth',
                confidenceRatio: confidence / price,
            };

            // Cache the result
            this.cache.set(feedId, { data: priceData, timestamp: Date.now() });

            return priceData;
        } catch (error) {
            console.error('Pyth price fetch failed:', error);
            return null;
        }
    }

    /**
     * Get price by symbol (SOL, BTC, etc.)
     */
    async getPriceBySymbol(symbol: string): Promise<PriceData | null> {
        const feedId = PYTH_PRICE_FEEDS[symbol.toUpperCase()];
        if (!feedId) return null;
        return this.getPrice(feedId);
    }

    /**
     * Check if price is within acceptable confidence bounds
     * Returns true if trading is safe, false if confidence interval is too wide
     */
    isConfidenceSafe(priceData: PriceData, maxRatio: number = 0.005): boolean {
        // Default: 0.5% max confidence ratio
        return priceData.confidenceRatio <= maxRatio;
    }

    /**
     * Get multiple prices in a single request
     */
    async getMultiplePrices(feedIds: string[]): Promise<Map<string, PriceData>> {
        const results = new Map<string, PriceData>();

        try {
            const idsParam = feedIds.map(id => `ids[]=${id}`).join('&');
            const response = await fetch(
                `${PYTH_HERMES_URL}/v2/updates/price/latest?${idsParam}`
            );

            if (!response.ok) return results;

            const data = await response.json();

            for (const priceUpdate of data.parsed || []) {
                const price = parseFloat(priceUpdate.price.price) * Math.pow(10, priceUpdate.price.expo);
                const confidence = parseFloat(priceUpdate.price.conf) * Math.pow(10, priceUpdate.price.expo);

                results.set(priceUpdate.id, {
                    price,
                    confidence,
                    timestamp: priceUpdate.price.publish_time * 1000,
                    source: 'pyth',
                    confidenceRatio: confidence / price,
                });
            }
        } catch (error) {
            console.error('Pyth batch price fetch failed:', error);
        }

        return results;
    }
}

export const pythClient = new PythClient();
