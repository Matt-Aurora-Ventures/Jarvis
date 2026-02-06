/**
 * Sentiment Intelligence API Client
 * 
 * Fetches real-time data from DexScreener, CoinGecko, and external APIs
 * for the Sentiment Intelligence Dashboard.
 */

import {
    TokenSentiment,
    MarketRegime,
    MacroAnalysis,
    StockPick,
    CommodityMover,
    PreciousMetalsOutlook,
    ConvictionPick,
    SentimentGrade,
    SentimentLabel,
    TokenRisk,
} from '@/types/sentiment-types';

// ============================================================================
// Constants
// ============================================================================

const DEXSCREENER_API = 'https://api.dexscreener.com';
const COINGECKO_API = 'https://api.coingecko.com/api/v3';

// Major tokens to exclude (we want microcaps, not blue chips)
const EXCLUDED_SYMBOLS = new Set([
    'SOL', 'WSOL', 'USDC', 'USDT', 'RAY', 'JUP', 'PYTH', 'JTO',
    'ORCA', 'MNGO', 'SRM', 'FIDA', 'STEP', 'COPE', 'MEDIA',
    'ETH', 'BTC', 'WBTC', 'WETH'
]);

// ============================================================================
// Token Sentiment Calculation (mirrors bot logic)
// ============================================================================

function calculateBuySellRatio(buys: number, sells: number): number {
    if (sells === 0) return buys > 0 ? 3.0 : 1.0;
    return buys / sells;
}

function classifyTokenRisk(mcap: number, liquidity: number): TokenRisk {
    if (mcap < 500000 || liquidity < 50000) return 'SHITCOIN';
    if (mcap < 5000000) return 'MICRO';
    if (mcap < 50000000) return 'MID';
    return 'ESTABLISHED';
}

function calculateSentiment(token: Partial<TokenSentiment>): {
    sentimentScore: number;
    sentimentLabel: SentimentLabel;
    grade: SentimentGrade;
    confidence: number;
} {
    let score = 0;
    let confidence = 0.5;

    const ratio = token.buySellRatio || 1;
    const change24h = token.change24h || 0;

    // Buy/sell ratio scoring
    if (ratio >= 2.0) {
        score += 0.35;
        confidence += 0.2;
    } else if (ratio >= 1.5) {
        score += 0.25;
        confidence += 0.15;
    } else if (ratio >= 1.2) {
        score += 0.15;
        confidence += 0.1;
    } else if (ratio < 0.8) {
        score -= 0.2;
        confidence -= 0.1;
    }

    // Momentum scoring
    if (change24h > 20 && change24h < 50) {
        score += 0.15;
    } else if (change24h >= 50) {
        score -= 0.1; // Chasing pump penalty
    } else if (change24h < -10) {
        score -= 0.15;
    }

    // Volume health
    const volume = token.volume24h || 0;
    const mcap = token.mcap || 1;
    const volumeToMcap = volume / mcap;
    if (volumeToMcap > 0.3) {
        score += 0.1;
        confidence += 0.1;
    }

    // Clamp values
    score = Math.max(-1, Math.min(1, score));
    confidence = Math.max(0.1, Math.min(1.0, confidence));

    // Determine label and grade
    let sentimentLabel: SentimentLabel;
    let grade: SentimentGrade;

    if (score > 0.55 && ratio >= 1.5) {
        sentimentLabel = 'BULLISH';
        grade = score > 0.65 ? 'A' : 'A-';
    } else if (score > 0.35 && ratio >= 1.2) {
        sentimentLabel = 'SLIGHTLY BULLISH';
        grade = score > 0.45 ? 'B+' : 'B';
    } else if (score > -0.2) {
        sentimentLabel = 'NEUTRAL';
        grade = score > 0.1 ? 'C+' : 'C';
    } else if (score > -0.4) {
        sentimentLabel = 'SLIGHTLY BEARISH';
        grade = score > -0.3 ? 'C-' : 'D+';
    } else {
        sentimentLabel = 'BEARISH';
        grade = score > -0.55 ? 'D' : 'F';
    }

    return { sentimentScore: score, sentimentLabel, grade, confidence };
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch trending Solana tokens from DexScreener
 */
export async function getTrendingTokens(limit = 10): Promise<TokenSentiment[]> {
    const tokens: TokenSentiment[] = [];
    const seenSymbols = new Set<string>();

    try {
        // Fetch boosted/trending tokens
        const trendingResp = await fetch(`${DEXSCREENER_API}/token-boosts/top/v1`);

        if (trendingResp.ok) {
            const data = await trendingResp.json();

            for (const item of data) {
                if (tokens.length >= limit) break;
                if (item.chainId !== 'solana') continue;

                const tokenAddr = item.tokenAddress;
                if (!tokenAddr) continue;

                // Fetch full pair data
                try {
                    const pairResp = await fetch(`${DEXSCREENER_API}/latest/dex/tokens/${tokenAddr}`);
                    if (!pairResp.ok) continue;

                    const pairData = await pairResp.json();
                    const pairs = pairData.pairs || [];

                    if (pairs.length > 0) {
                        const pair = pairs[0];
                        const base = pair.baseToken || {};
                        const symbol = (base.symbol || '').toUpperCase();

                        if (EXCLUDED_SYMBOLS.has(symbol) || seenSymbols.has(symbol)) continue;
                        seenSymbols.add(symbol);

                        const txns = pair.txns?.h24 || {};
                        const buys = txns.buys || 0;
                        const sells = txns.sells || 0;
                        const buySellRatio = calculateBuySellRatio(buys, sells);
                        const mcap = pair.marketCap || pair.fdv || 0;
                        const liquidity = pair.liquidity?.usd || 0;

                        const partialToken: Partial<TokenSentiment> = {
                            symbol: base.symbol || '???',
                            name: base.name || 'Unknown',
                            priceUsd: parseFloat(pair.priceUsd || '0'),
                            change1h: pair.priceChange?.h1 || 0,
                            change24h: pair.priceChange?.h24 || 0,
                            volume24h: pair.volume?.h24 || 0,
                            mcap,
                            buys24h: buys,
                            sells24h: sells,
                            liquidity,
                            contractAddress: base.address || tokenAddr,
                            buySellRatio,
                            tokenRisk: classifyTokenRisk(mcap, liquidity),
                        };

                        const sentiment = calculateSentiment(partialToken);

                        tokens.push({
                            ...partialToken,
                            ...sentiment,
                        } as TokenSentiment);
                    }

                    // Rate limit
                    await new Promise(r => setTimeout(r, 100));

                } catch (e) {
                    console.debug('Failed to fetch pair data:', e);
                }
            }
        }

        // If we don't have enough, supplement with search
        if (tokens.length < limit) {
            const searchResp = await fetch(`${DEXSCREENER_API}/latest/dex/search?q=solana`);
            if (searchResp.ok) {
                const data = await searchResp.json();
                const pairs = (data.pairs || [])
                    .filter((p: any) => p.chainId === 'solana')
                    .sort((a: any, b: any) => (b.priceChange?.h24 || 0) - (a.priceChange?.h24 || 0));

                for (const pair of pairs) {
                    if (tokens.length >= limit) break;

                    const base = pair.baseToken || {};
                    const symbol = (base.symbol || '').toUpperCase();

                    if (EXCLUDED_SYMBOLS.has(symbol) || seenSymbols.has(symbol)) continue;
                    seenSymbols.add(symbol);

                    const txns = pair.txns?.h24 || {};
                    const buys = txns.buys || 0;
                    const sells = txns.sells || 0;
                    const buySellRatio = calculateBuySellRatio(buys, sells);
                    const mcap = pair.marketCap || pair.fdv || 0;
                    const liquidity = pair.liquidity?.usd || 0;

                    const partialToken: Partial<TokenSentiment> = {
                        symbol: base.symbol || '???',
                        name: base.name || 'Unknown',
                        priceUsd: parseFloat(pair.priceUsd || '0'),
                        change1h: pair.priceChange?.h1 || 0,
                        change24h: pair.priceChange?.h24 || 0,
                        volume24h: pair.volume?.h24 || 0,
                        mcap,
                        buys24h: buys,
                        sells24h: sells,
                        liquidity,
                        contractAddress: base.address || '',
                        buySellRatio,
                        tokenRisk: classifyTokenRisk(mcap, liquidity),
                    };

                    const sentiment = calculateSentiment(partialToken);

                    tokens.push({
                        ...partialToken,
                        ...sentiment,
                    } as TokenSentiment);
                }
            }
        }

    } catch (e) {
        console.error('Failed to fetch trending tokens:', e);
    }

    return tokens;
}

/**
 * Fetch BTC/SOL market regime
 */
export async function getMarketRegime(): Promise<MarketRegime> {
    const regime: MarketRegime = {
        btcTrend: 'NEUTRAL',
        solTrend: 'NEUTRAL',
        btcChange24h: 0,
        solChange24h: 0,
        solPrice: 0,
        riskLevel: 'NORMAL',
        regime: 'NEUTRAL',
    };

    try {
        // Fetch SOL data
        const solResp = await fetch(`${DEXSCREENER_API}/latest/dex/tokens/So11111111111111111111111111111111111111112`);
        if (solResp.ok) {
            const data = await solResp.json();
            const pairs = data.pairs || [];
            if (pairs.length > 0) {
                regime.solChange24h = pairs[0].priceChange?.h24 || 0;
                regime.solPrice = parseFloat(pairs[0].priceUsd || '0');
            }
        }

        // Fetch BTC data via CoinGecko
        const btcResp = await fetch(`${COINGECKO_API}/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true`);
        if (btcResp.ok) {
            const data = await btcResp.json();
            regime.btcChange24h = data.bitcoin?.usd_24h_change || 0;
        }

        // Determine trends
        if (regime.btcChange24h > 3) regime.btcTrend = 'BULLISH';
        else if (regime.btcChange24h < -3) regime.btcTrend = 'BEARISH';

        if (regime.solChange24h > 3) regime.solTrend = 'BULLISH';
        else if (regime.solChange24h < -3) regime.solTrend = 'BEARISH';

        // Overall regime
        if (regime.btcChange24h < -5 || regime.solChange24h < -7) {
            regime.regime = 'BEAR';
            regime.riskLevel = 'HIGH';
        } else if (regime.btcChange24h > 5 && regime.solChange24h > 5) {
            regime.regime = 'BULL';
            regime.riskLevel = 'LOW';
        }

    } catch (e) {
        console.error('Failed to fetch market regime:', e);
    }

    return regime;
}

/**
 * Get macro analysis (placeholder - would call Grok API in production)
 */
export async function getMacroAnalysis(): Promise<MacroAnalysis> {
    // In production, this would call the Grok API
    // For now, return placeholder data
    return {
        shortTerm: 'Markets awaiting key economic data. Watch for volatility around announcements.',
        mediumTerm: 'Continued consolidation expected. Key support levels holding for now.',
        longTerm: 'Macro trends favor risk assets with easing monetary policy on the horizon.',
        keyEvents: ['FOMC Minutes', 'CPI Release', 'Jobs Report'],
    };
}

/**
 * Get stock picks (placeholder - would integrate backed.fi in production)
 */
export async function getStockPicks(): Promise<StockPick[]> {
    // Placeholder xStocks data
    return [
        { ticker: 'xNVDA', direction: 'LONG', reason: 'AI momentum continues', target: '+15%', stopLoss: '-5%', underlying: 'NVIDIA' },
        { ticker: 'xTSLA', direction: 'LONG', reason: 'EV sector rotation', target: '+12%', stopLoss: '-6%', underlying: 'Tesla' },
        { ticker: 'xMETA', direction: 'LONG', reason: 'AI integration boost', target: '+10%', stopLoss: '-5%', underlying: 'Meta' },
    ];
}

/**
 * Get commodity movers (placeholder)
 */
export async function getCommodityMovers(): Promise<CommodityMover[]> {
    return [
        { name: 'Gold', direction: 'LONG', change: '+1.2%', reason: 'Safe haven demand', outlook: 'Bullish near-term' },
        { name: 'Oil', direction: 'SHORT', change: '-0.8%', reason: 'Supply concerns easing', outlook: 'Sideways' },
        { name: 'Silver', direction: 'LONG', change: '+2.1%', reason: 'Industrial demand rising', outlook: 'Bullish' },
    ];
}

/**
 * Get precious metals outlook (placeholder)
 */
export async function getPreciousMetalsOutlook(): Promise<PreciousMetalsOutlook> {
    return {
        goldDirection: 'BULLISH',
        goldOutlook: 'Safe haven flows supporting price. Watch $2,100 resistance.',
        silverDirection: 'BULLISH',
        silverOutlook: 'Industrial demand + gold correlation driving higher.',
        platinumDirection: 'NEUTRAL',
        platinumOutlook: 'Range-bound near-term. Watch auto demand data.',
    };
}

/**
 * Get conviction picks (unified top 10)
 */
export async function getConvictionPicks(tokens: TokenSentiment[]): Promise<ConvictionPick[]> {
    // Sort tokens by sentiment score and take top picks
    const bullishTokens = tokens
        .filter(t => t.sentimentLabel === 'BULLISH' || t.sentimentLabel === 'SLIGHTLY BULLISH')
        .sort((a, b) => b.sentimentScore - a.sentimentScore)
        .slice(0, 5);

    const picks: ConvictionPick[] = bullishTokens.map((token, index) => ({
        rank: index + 1,
        symbol: token.symbol,
        assetType: 'TOKEN',
        direction: 'LONG',
        convictionScore: Math.round((token.sentimentScore + 1) * 50), // Convert -1,1 to 0-100
        entryPrice: token.priceUsd,
        targets: {
            safe: { takeProfit: token.priceUsd * 1.15, stopLoss: token.priceUsd * 0.95 },
            medium: { takeProfit: token.priceUsd * 1.30, stopLoss: token.priceUsd * 0.90 },
            degen: { takeProfit: token.priceUsd * 1.50, stopLoss: token.priceUsd * 0.85 },
        },
        reasoning: token.grokReasoning || `Strong buy/sell ratio of ${token.buySellRatio.toFixed(2)}x with ${token.change24h > 0 ? 'positive' : 'recovering'} momentum.`,
        grade: token.grade,
        contractAddress: token.contractAddress,
    }));

    // Add placeholder xStock picks
    picks.push(
        {
            rank: picks.length + 1,
            symbol: 'xNVDA',
            assetType: 'XSTOCK',
            direction: 'LONG',
            convictionScore: 75,
            entryPrice: 850,
            targets: {
                safe: { takeProfit: 935, stopLoss: 807.5 },
                medium: { takeProfit: 1020, stopLoss: 765 },
                degen: { takeProfit: 1105, stopLoss: 722.5 },
            },
            reasoning: 'AI sector leadership with strong earnings momentum.',
            grade: 'A-',
        },
        {
            rank: picks.length + 2,
            symbol: 'xTSLA',
            assetType: 'XSTOCK',
            direction: 'LONG',
            convictionScore: 68,
            entryPrice: 250,
            targets: {
                safe: { takeProfit: 275, stopLoss: 237.5 },
                medium: { takeProfit: 300, stopLoss: 225 },
                degen: { takeProfit: 325, stopLoss: 212.5 },
            },
            reasoning: 'EV sector rotation with autonomous driving catalysts.',
            grade: 'B+',
        }
    );

    return picks.slice(0, 10);
}

/**
 * Fetch all dashboard data in parallel
 */
export async function fetchAllSentimentData() {
    const [
        trendingTokens,
        marketRegime,
        macroAnalysis,
        stockPicks,
        commodityMovers,
        preciousMetals,
    ] = await Promise.all([
        getTrendingTokens(10),
        getMarketRegime(),
        getMacroAnalysis(),
        getStockPicks(),
        getCommodityMovers(),
        getPreciousMetalsOutlook(),
    ]);

    const convictionPicks = await getConvictionPicks(trendingTokens);

    return {
        lastUpdated: new Date(),
        marketRegime,
        trendingTokens,
        convictionPicks,
        macroAnalysis,
        stockPicks,
        commodityMovers,
        preciousMetals,
        isLoading: false,
        error: null,
    };
}
