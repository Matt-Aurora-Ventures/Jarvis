/**
 * Blue Chip Solana Tokens — Established, High-Liquidity, 2yr+ History
 *
 * Criteria:
 * - On Solana mainnet for 2+ years (since Feb 2024 or earlier)
 * - Consistent trading volume (not abandoned)
 * - $200K+ DEX liquidity minimum
 * - On Jupiter Strict List (verified, non-scam)
 * - NOT stablecoins (USDC, USDT, etc.)
 * - Reasonably volatile (enough price movement to trade)
 *
 * These tokens are the "blue chips" of Solana — well-established with
 * extensive historical data for backtesting. Trading strategies here
 * target smaller, more consistent wins (5-20%) vs moonshot meme plays.
 */
// ============================================================================
// TIER 1 — Core Solana Ecosystem ($1B+ market cap, massive liquidity)
// ============================================================================
export const BLUECHIP_TIER1 = [
    {
        ticker: 'SOL',
        name: 'Wrapped SOL',
        mintAddress: 'So11111111111111111111111111111111111111112',
        category: 'infra',
        description: 'Native Solana token — L1 blockchain, proof of stake',
        avgDailyVolatility: 4.5,
        mcapTier: 'mega',
        jupiterStrict: true,
        yearsSolana: 5,
    },
    {
        ticker: 'JUP',
        name: 'Jupiter',
        mintAddress: 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',
        category: 'defi',
        description: 'Leading Solana DEX aggregator — routes through all DEXes',
        avgDailyVolatility: 6.0,
        mcapTier: 'large',
        jupiterStrict: true,
        yearsSolana: 2,
    },
    {
        ticker: 'RAY',
        name: 'Raydium',
        mintAddress: '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R',
        category: 'defi',
        description: 'Solana AMM and concentrated liquidity DEX',
        avgDailyVolatility: 7.0,
        mcapTier: 'large',
        jupiterStrict: true,
        yearsSolana: 4,
    },
    {
        ticker: 'PYTH',
        name: 'Pyth Network',
        mintAddress: 'HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3',
        category: 'infra',
        description: 'Oracle network — real-time market data feeds for DeFi',
        avgDailyVolatility: 5.5,
        mcapTier: 'large',
        jupiterStrict: true,
        yearsSolana: 2,
    },
    {
        ticker: 'JTO',
        name: 'Jito',
        mintAddress: 'jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL',
        category: 'lsd',
        description: 'Liquid staking and MEV protocol on Solana',
        avgDailyVolatility: 6.5,
        mcapTier: 'large',
        jupiterStrict: true,
        yearsSolana: 2,
    },
    {
        ticker: 'RNDR',
        name: 'Render',
        mintAddress: 'rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof',
        category: 'infra',
        description: 'Decentralized GPU rendering network',
        avgDailyVolatility: 6.0,
        mcapTier: 'large',
        jupiterStrict: true,
        yearsSolana: 3,
    },
    {
        ticker: 'HNT',
        name: 'Helium',
        mintAddress: 'hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux',
        category: 'infra',
        description: 'Decentralized wireless network (migrated to Solana)',
        avgDailyVolatility: 5.0,
        mcapTier: 'large',
        jupiterStrict: true,
        yearsSolana: 2,
    },
    {
        ticker: 'W',
        name: 'Wormhole',
        mintAddress: '85VBFQZC9TZkfaptBWjvUw7YbZjy52A6mjtPGjstQAmQ',
        category: 'infra',
        description: 'Cross-chain messaging and bridging protocol',
        avgDailyVolatility: 5.5,
        mcapTier: 'large',
        jupiterStrict: true,
        yearsSolana: 2,
    },
];
// ============================================================================
// TIER 2 — DeFi & Infrastructure ($100M-$1B, strong liquidity)
// ============================================================================
export const BLUECHIP_TIER2 = [
    {
        ticker: 'ORCA',
        name: 'Orca',
        mintAddress: 'orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE',
        category: 'defi',
        description: 'Concentrated liquidity DEX on Solana',
        avgDailyVolatility: 6.5,
        mcapTier: 'mid',
        jupiterStrict: true,
        yearsSolana: 4,
    },
    {
        ticker: 'MNDE',
        name: 'Marinade',
        mintAddress: 'MNDEFzGvMt87ueuHvVU9VcTqsAP5b3fTGPsHuuPA5ey',
        category: 'lsd',
        description: 'Liquid staking protocol — mSOL',
        avgDailyVolatility: 6.0,
        mcapTier: 'mid',
        jupiterStrict: true,
        yearsSolana: 3,
    },
    {
        ticker: 'DRIFT',
        name: 'Drift Protocol',
        mintAddress: 'DriFtupJYLTosbwoN8koMbEYSx54aFAVLddWsbksjwg7',
        category: 'defi',
        description: 'Decentralized perpetuals exchange on Solana',
        avgDailyVolatility: 8.0,
        mcapTier: 'mid',
        jupiterStrict: true,
        yearsSolana: 2,
    },
    {
        ticker: 'TENSOR',
        name: 'Tensor',
        mintAddress: 'TNSRxcUxoT9xBG3de7PiJyTDYu7kskLqcpddxnEJAS6',
        category: 'infra',
        description: 'NFT marketplace and trading infrastructure',
        avgDailyVolatility: 7.0,
        mcapTier: 'mid',
        jupiterStrict: true,
        yearsSolana: 2,
    },
    {
        ticker: 'MOBILE',
        name: 'Helium Mobile',
        mintAddress: 'mb1eu7TzEc71KxDpsmsKoucSSuuoGLv1drys1oP2jh6',
        category: 'infra',
        description: 'Helium mobile network token',
        avgDailyVolatility: 7.5,
        mcapTier: 'mid',
        jupiterStrict: true,
        yearsSolana: 2,
    },
    {
        ticker: 'STEP',
        name: 'Step Finance',
        mintAddress: 'StepAscQoEioFxxWGnh2sLBDFp9d8rvKz2Yp39iDpyT',
        category: 'defi',
        description: 'Solana dashboard and portfolio management',
        avgDailyVolatility: 8.0,
        mcapTier: 'mid',
        jupiterStrict: true,
        yearsSolana: 4,
    },
];
// ============================================================================
// TIER 3 — Established Memes (2yr+, still actively traded, high volatility)
// ============================================================================
export const BLUECHIP_TIER3 = [
    {
        ticker: 'BONK',
        name: 'Bonk',
        mintAddress: 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
        category: 'meme_established',
        description: 'First Solana community dog meme — massive volume',
        avgDailyVolatility: 8.0,
        mcapTier: 'large',
        jupiterStrict: true,
        yearsSolana: 3,
    },
    {
        ticker: 'WIF',
        name: 'dogwifhat',
        mintAddress: 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm',
        category: 'meme_established',
        description: 'Dog with hat meme — top Solana meme by volume',
        avgDailyVolatility: 10.0,
        mcapTier: 'large',
        jupiterStrict: true,
        yearsSolana: 2,
    },
    {
        ticker: 'SAMO',
        name: 'Samoyedcoin',
        mintAddress: '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU',
        category: 'meme_established',
        description: 'OG Solana meme — Samoyed dog community',
        avgDailyVolatility: 9.0,
        mcapTier: 'mid',
        jupiterStrict: true,
        yearsSolana: 4,
    },
];
// ============================================================================
// Combined registry
// ============================================================================
export const ALL_BLUECHIPS = [
    ...BLUECHIP_TIER1,
    ...BLUECHIP_TIER2,
    ...BLUECHIP_TIER3,
];
export const BLUECHIP_BY_MINT = new Map(ALL_BLUECHIPS.map(t => [t.mintAddress, t]));
export const BLUECHIP_BY_TICKER = new Map(ALL_BLUECHIPS.map(t => [t.ticker, t]));
// Tier groupings for UI display
export const BLUECHIP_TIERS = {
    tier1: BLUECHIP_TIER1,
    tier2: BLUECHIP_TIER2,
    tier3: BLUECHIP_TIER3,
};
