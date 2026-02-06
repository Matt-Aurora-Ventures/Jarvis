/**
 * Library Exports Index
 *
 * Core API clients and utilities for the Sentiment Trading Terminal
 */

// Trading
export {
    BagsTradingClient,
    getBagsTradingClient,
    type SwapResult,
    type TradeQuote
} from './bags-trading';

// Sentiment Analysis
export {
    GrokSentimentClient,
    getGrokSentimentClient,
    type TokenSentiment,
    type SentimentBatchResult
} from './grok-sentiment';

// Market Intelligence
export {
    DexterIntelClient,
    getDexterIntelClient,
    type MarketNews,
    type StockAnalysis,
    type MarketRegime,
    type SectorAnalysis
} from './dexter-intel';

// Bags.fm API
export {
    BagsClient,
    bagsClient,
    getScoreTier,
    TIER_COLORS,
    type BagsToken,
    type BagsCandle,
    type BagsGraduation,
    type ScoreTier
} from './bags-api';

// Solana RPC (Helius with fallback)
export {
    HeliusClient,
    getHeliusClient,
    type HeliusClientConfig,
    type TokenAccount,
    type TokenBalanceResponse
} from './helius-client';
