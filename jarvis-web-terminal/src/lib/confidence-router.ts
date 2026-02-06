/**
 * Confidence Router - Multi-Tier Price Validation Engine
 * 
 * Dispatches validation logic based on asset tiers:
 * - Established: Uses Pyth Hermes for high-confidence oracles
 * - Micro: Uses Bags.fm analytics for graduation tokens
 * - Synthetic: Aggregates Jupiter + Bags for unknown assets
 */

import { pythClient, PriceData, PYTH_PRICE_FEEDS } from './pyth-client';
import { bagsClient } from './bags-api';
import { getJupiterPriceClient, TOKENS } from './jupiter-price';

export type AssetTier = 'established' | 'micro' | 'unknown';

export interface ConfidenceResult {
    price: number;
    confidence: number;
    confidenceScore: number; // 0.0 - 1.0 (1.0 = highest confidence)
    tier: AssetTier;
    source: PriceData['source'];
    isSafeToTrade: boolean;
    reason?: string;
}

export interface CircuitBreakerStatus {
    isTripped: boolean;
    reason?: string;
    trippedAt?: number;
    cooldownEndsAt?: number;
}

// Threshold for confidence ratio (conf/price)
const CIRCUIT_BREAKER_THRESHOLD = 0.005; // 0.5%
const CIRCUIT_BREAKER_COOLDOWN = 60000; // 1 minute cooldown

// Known established assets that have Pyth feeds
const ESTABLISHED_SYMBOLS = new Set(Object.keys(PYTH_PRICE_FEEDS));

export class ConfidenceRouter {
    private circuitBreaker: CircuitBreakerStatus = { isTripped: false };

    /**
     * Determine the tier of an asset based on its characteristics
     */
    classifyAsset(symbol: string, mint?: string): AssetTier {
        const upperSymbol = symbol.toUpperCase();

        // Check if it's an established asset with Pyth feed
        if (ESTABLISHED_SYMBOLS.has(upperSymbol)) {
            return 'established';
        }

        // Check if it's a Bags.fm graduated token (micro tier)
        // In production, this would check against cached graduation list
        if (mint && mint.length === 44) {
            // Assume it's a valid Solana mint - treat as micro
            return 'micro';
        }

        return 'unknown';
    }

    /**
     * Get validated price with confidence scoring
     */
    async getValidatedPrice(
        symbol: string,
        mint?: string,
        options: { sigmaMultiplier?: number } = {}
    ): Promise<ConfidenceResult> {
        const tier = this.classifyAsset(symbol, mint);
        const { sigmaMultiplier = 2.0 } = options;

        // Check circuit breaker
        if (this.circuitBreaker.isTripped) {
            const now = Date.now();
            if (this.circuitBreaker.cooldownEndsAt && now < this.circuitBreaker.cooldownEndsAt) {
                return {
                    price: 0,
                    confidence: 0,
                    confidenceScore: 0,
                    tier,
                    source: 'synthetic',
                    isSafeToTrade: false,
                    reason: `Circuit breaker tripped: ${this.circuitBreaker.reason}`,
                };
            }
            // Reset circuit breaker after cooldown
            this.circuitBreaker = { isTripped: false };
        }

        switch (tier) {
            case 'established':
                return this.getEstablishedPrice(symbol, sigmaMultiplier);
            case 'micro':
                return this.getMicroPrice(mint!, sigmaMultiplier);
            default:
                return this.getSyntheticPrice(symbol, mint, sigmaMultiplier);
        }
    }

    /**
     * Get price from Pyth for established assets
     */
    private async getEstablishedPrice(symbol: string, sigmaMultiplier: number): Promise<ConfidenceResult> {
        const pythData = await pythClient.getPriceBySymbol(symbol);

        if (!pythData) {
            // Fallback to synthetic if Pyth fails
            return this.getSyntheticPrice(symbol, undefined, sigmaMultiplier);
        }

        // Check circuit breaker condition
        if (pythData.confidenceRatio > CIRCUIT_BREAKER_THRESHOLD) {
            this.tripCircuitBreaker(`High volatility: ${(pythData.confidenceRatio * 100).toFixed(2)}% conf ratio`);
        }

        // Calculate confidence score (1.0 = perfect, 0.0 = terrible)
        // Using inverse of confidence ratio, capped at 1.0
        const confidenceScore = Math.min(1.0, 1.0 - (pythData.confidenceRatio * 100));

        // Dynamic sigma check
        const sigmaThreshold = CIRCUIT_BREAKER_THRESHOLD * sigmaMultiplier;
        const isSafeToTrade = pythData.confidenceRatio <= sigmaThreshold && !this.circuitBreaker.isTripped;

        return {
            price: pythData.price,
            confidence: pythData.confidence,
            confidenceScore,
            tier: 'established',
            source: 'pyth',
            isSafeToTrade,
            reason: isSafeToTrade ? undefined : `Confidence ratio ${(pythData.confidenceRatio * 100).toFixed(3)}% exceeds ${sigmaMultiplier}σ threshold`,
        };
    }

    /**
     * Get price from Bags.fm for micro-cap graduated tokens
     */
    private async getMicroPrice(mint: string, sigmaMultiplier: number): Promise<ConfidenceResult> {
        const tokenInfo = await bagsClient.getTokenInfo(mint);

        if (!tokenInfo) {
            return {
                price: 0,
                confidence: 0,
                confidenceScore: 0,
                tier: 'micro',
                source: 'bags',
                isSafeToTrade: false,
                reason: 'Token not found in Bags.fm',
            };
        }

        // For micro assets, synthesize confidence from liquidity and volume
        const liquidityScore = Math.min(1.0, tokenInfo.liquidity / 100000); // $100k = 1.0
        const volumeScore = Math.min(1.0, tokenInfo.volume_24h / 50000); // $50k = 1.0

        // Synthesized confidence score
        const confidenceScore = (liquidityScore * 0.6) + (volumeScore * 0.4);

        // For micro assets, require higher confidence threshold
        const microThreshold = 0.4 * sigmaMultiplier; // 40% base confidence required
        const isSafeToTrade = confidenceScore >= microThreshold;

        return {
            price: tokenInfo.price_usd,
            confidence: tokenInfo.liquidity, // Use liquidity as proxy for confidence
            confidenceScore,
            tier: 'micro',
            source: 'bags',
            isSafeToTrade,
            reason: isSafeToTrade ? undefined : `Low confidence score: ${(confidenceScore * 100).toFixed(1)}% (need ${(microThreshold * 100).toFixed(1)}%)`,
        };
    }

    /**
     * Synthesize price from multiple sources for unknown assets
     */
    private async getSyntheticPrice(
        symbol: string,
        mint: string | undefined,
        sigmaMultiplier: number
    ): Promise<ConfidenceResult> {
        // Try Bags.fm first if we have a mint
        if (mint) {
            const bagsResult = await this.getMicroPrice(mint, sigmaMultiplier);
            if (bagsResult.price > 0) {
                return { ...bagsResult, source: 'synthetic' };
            }
        }

        // Fallback: Try CoinGecko via Jupiter price client
        const jupiterClient = getJupiterPriceClient();
        const tokenMint = mint || (symbol.toUpperCase() === 'SOL' ? TOKENS.SOL : undefined);

        if (tokenMint) {
            const coingeckoPrice = await jupiterClient.getPrice(tokenMint);
            if (coingeckoPrice && coingeckoPrice > 0) {
                // CoinGecko prices are reliable, give high confidence
                return {
                    price: coingeckoPrice,
                    confidence: coingeckoPrice * 0.001, // 0.1% confidence interval
                    confidenceScore: 0.85, // High confidence for CoinGecko
                    tier: 'established',
                    source: 'synthetic',
                    isSafeToTrade: true,
                    reason: undefined,
                };
            }
        }

        // Final fallback: return unsafe result
        return {
            price: 0,
            confidence: 0,
            confidenceScore: 0,
            tier: 'unknown',
            source: 'synthetic',
            isSafeToTrade: false,
            reason: 'No price source available for this asset',
        };
    }

    /**
     * Trip the circuit breaker to pause trading
     */
    private tripCircuitBreaker(reason: string): void {
        console.warn(`⚠️ Circuit Breaker Tripped: ${reason}`);
        this.circuitBreaker = {
            isTripped: true,
            reason,
            trippedAt: Date.now(),
            cooldownEndsAt: Date.now() + CIRCUIT_BREAKER_COOLDOWN,
        };
    }

    /**
     * Get current circuit breaker status
     */
    getCircuitBreakerStatus(): CircuitBreakerStatus {
        return { ...this.circuitBreaker };
    }

    /**
     * Manually reset circuit breaker (admin function)
     */
    resetCircuitBreaker(): void {
        this.circuitBreaker = { isTripped: false };
    }

    /**
     * Check if a trade should be blocked based on stop-loss with dynamic sigma
     * 
     * sigmaMultiplier:
     * - 1.0σ = tight (stable assets, low volatility)
     * - 2.0σ = normal (default)
     * - 3.0σ = wide (high volatility, news events)
     */
    async checkStopLoss(
        symbol: string,
        mint: string | undefined,
        entryPrice: number,
        currentPrice: number,
        stopLossPercent: number,
        options: { sigmaMultiplier?: number } = {}
    ): Promise<{ shouldTrigger: boolean; reason: string }> {
        const { sigmaMultiplier = 2.0 } = options;

        const validated = await this.getValidatedPrice(symbol, mint, { sigmaMultiplier });

        if (!validated.isSafeToTrade) {
            return {
                shouldTrigger: false,
                reason: `Trade validation failed: ${validated.reason}`,
            };
        }

        // Calculate effective stop loss with confidence buffer
        const confidenceBuffer = validated.confidence / validated.price;
        const effectiveStopLoss = stopLossPercent + (confidenceBuffer * sigmaMultiplier * 100);

        const priceChange = ((currentPrice - entryPrice) / entryPrice) * 100;
        const shouldTrigger = priceChange <= -effectiveStopLoss;

        return {
            shouldTrigger,
            reason: shouldTrigger
                ? `Stop loss triggered at ${priceChange.toFixed(2)}% (effective SL: ${effectiveStopLoss.toFixed(2)}%)`
                : `Price change ${priceChange.toFixed(2)}% within ${effectiveStopLoss.toFixed(2)}% threshold`,
        };
    }
}

export const confidenceRouter = new ConfidenceRouter();
