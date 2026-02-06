/**
 * Jupiter Price API Client
 *
 * Provides reliable token price data for Solana tokens.
 * Used as primary source for price charts when bags.fm doesn't have data.
 */

export interface JupiterPrice {
    id: string;
    mintSymbol: string;
    vsToken: string;
    vsTokenSymbol: string;
    price: number;
    timeTaken: number;
}

export interface JupiterPriceResponse {
    data: Record<string, JupiterPrice>;
    timeTaken: number;
}

export interface PriceCandle {
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

// Well-known token mints
export const TOKENS = {
    SOL: 'So11111111111111111111111111111111111111112',
    USDC: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
    USDT: 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
    RAY: '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R',
    JUP: 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',
    BONK: 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
};

// CoinGecko token ID mapping
const COINGECKO_IDS: Record<string, string> = {
    [TOKENS.SOL]: 'solana',
    [TOKENS.USDC]: 'usd-coin',
    [TOKENS.RAY]: 'raydium',
    [TOKENS.JUP]: 'jupiter-exchange-solana',
    [TOKENS.BONK]: 'bonk',
};

class JupiterPriceClient {
    private priceCache = new Map<string, { price: number; timestamp: number }>();
    private readonly CACHE_TTL = 10000; // 10 seconds

    /**
     * Get current price for a token using CoinGecko
     */
    async getPrice(mint: string): Promise<number | null> {
        // Check cache
        const cached = this.priceCache.get(mint);
        if (cached && Date.now() - cached.timestamp < this.CACHE_TTL) {
            return cached.price;
        }

        const coinId = COINGECKO_IDS[mint];
        if (!coinId) {
            console.warn(`No CoinGecko ID for mint: ${mint}`);
            return null;
        }

        try {
            const response = await fetch(
                `https://api.coingecko.com/api/v3/simple/price?ids=${coinId}&vs_currencies=usd`
            );
            if (!response.ok) {
                console.warn(`CoinGecko API: ${response.status}`);
                return null;
            }

            const data = await response.json();
            const price = data[coinId]?.usd;

            if (price) {
                this.priceCache.set(mint, { price, timestamp: Date.now() });
                return price;
            }

            return null;
        } catch (error) {
            console.error('CoinGecko Price API error:', error);
            return null;
        }
    }

    /**
     * Get prices for multiple tokens
     */
    async getPrices(mints: string[]): Promise<Map<string, number>> {
        const prices = new Map<string, number>();

        // Filter out cached prices and map to CoinGecko IDs
        const needsFetch: { mint: string; coinId: string }[] = [];
        for (const mint of mints) {
            const cached = this.priceCache.get(mint);
            if (cached && Date.now() - cached.timestamp < this.CACHE_TTL) {
                prices.set(mint, cached.price);
            } else {
                const coinId = COINGECKO_IDS[mint];
                if (coinId) {
                    needsFetch.push({ mint, coinId });
                }
            }
        }

        if (needsFetch.length === 0) return prices;

        try {
            const coinIds = needsFetch.map(f => f.coinId).join(',');
            const response = await fetch(
                `https://api.coingecko.com/api/v3/simple/price?ids=${coinIds}&vs_currencies=usd`
            );
            if (!response.ok) return prices;

            const data = await response.json();

            for (const { mint, coinId } of needsFetch) {
                const price = data[coinId]?.usd;
                if (price) {
                    prices.set(mint, price);
                    this.priceCache.set(mint, { price, timestamp: Date.now() });
                }
            }
        } catch (error) {
            console.error('CoinGecko batch price error:', error);
        }

        return prices;
    }

    /**
     * Get SOL price in USD
     */
    async getSolPrice(): Promise<number> {
        const price = await this.getPrice(TOKENS.SOL);
        return price || 0;
    }

    /**
     * Get real historical candle data from CoinGecko
     * Uses 14 days to get hourly granularity (7 days = 5min, 14+ days = hourly)
     */
    async getSimulatedCandles(mint: string, count: number = 100): Promise<PriceCandle[]> {
        const coinId = COINGECKO_IDS[mint];
        if (!coinId) {
            console.warn(`No CoinGecko ID for mint: ${mint}`);
            return [];
        }

        try {
            // Get 14 days of hourly data from CoinGecko (14-30 days = hourly granularity)
            const response = await fetch(
                `https://api.coingecko.com/api/v3/coins/${coinId}/market_chart?vs_currency=usd&days=14`
            );

            if (!response.ok) {
                console.warn(`CoinGecko market chart: ${response.status}`);
                return [];
            }

            const data = await response.json();
            const prices: [number, number][] = data.prices || [];

            if (prices.length === 0) return [];

            // Convert to OHLCV candles (group by hour)
            const candles: PriceCandle[] = [];
            const hourlyGroups = new Map<number, number[]>();

            for (const [timestamp, price] of prices) {
                // Round to hour
                const hourTs = Math.floor(timestamp / 3600000) * 3600;
                if (!hourlyGroups.has(hourTs)) {
                    hourlyGroups.set(hourTs, []);
                }
                hourlyGroups.get(hourTs)!.push(price);
            }

            // Convert groups to candles
            const sortedHours = Array.from(hourlyGroups.keys()).sort((a, b) => a - b);

            for (const hourTs of sortedHours.slice(-count)) {
                const hourPrices = hourlyGroups.get(hourTs)!;
                if (hourPrices.length === 0) continue;

                candles.push({
                    timestamp: hourTs,
                    open: hourPrices[0],
                    high: Math.max(...hourPrices),
                    low: Math.min(...hourPrices),
                    close: hourPrices[hourPrices.length - 1],
                    volume: 0, // CoinGecko doesn't provide volume in this endpoint
                });
            }

            console.log(`[Price] Got ${candles.length} candles from CoinGecko`);
            return candles;
        } catch (error) {
            console.error('CoinGecko market chart error:', error);
            return [];
        }
    }

    /**
     * Clear price cache
     */
    clearCache(): void {
        this.priceCache.clear();
    }
}

// Singleton
let instance: JupiterPriceClient | null = null;

export function getJupiterPriceClient(): JupiterPriceClient {
    if (!instance) {
        instance = new JupiterPriceClient();
    }
    return instance;
}

export { JupiterPriceClient };
