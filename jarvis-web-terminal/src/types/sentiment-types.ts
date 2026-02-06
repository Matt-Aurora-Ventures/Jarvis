/**
 * Sentiment Intelligence Dashboard Types
 * 
 * TypeScript interfaces matching the bot dataclasses from sentiment_report.py
 */

// ============================================================================
// Token Sentiment
// ============================================================================

export type SentimentGrade = 'A+' | 'A' | 'A-' | 'B+' | 'B' | 'B-' | 'C+' | 'C' | 'C-' | 'D+' | 'D' | 'F';
export type SentimentLabel = 'BULLISH' | 'SLIGHTLY BULLISH' | 'NEUTRAL' | 'SLIGHTLY BEARISH' | 'BEARISH';
export type TokenRisk = 'SHITCOIN' | 'MICRO' | 'MID' | 'ESTABLISHED';

export interface TokenSentiment {
    symbol: string;
    name: string;
    priceUsd: number;
    change1h: number;
    change24h: number;
    volume24h: number;
    mcap: number;
    buys24h: number;
    sells24h: number;
    liquidity: number;
    contractAddress: string;

    // Calculated sentiment
    sentimentScore: number;        // -1 to 1
    sentimentLabel: SentimentLabel;
    grade: SentimentGrade;
    confidence: number;            // 0 to 1
    tokenRisk: TokenRisk;
    buySellRatio: number;

    // Grok AI analysis
    grokScore?: number;
    grokVerdict?: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    grokReasoning?: string;
    grokTargetSafe?: string;
    grokTargetMed?: string;
    grokTargetDegen?: string;
    grokStopLoss?: string;
}

// ============================================================================
// Market Regime
// ============================================================================

export type RegimeTrend = 'BULLISH' | 'BEARISH' | 'NEUTRAL';
export type RiskLevel = 'LOW' | 'NORMAL' | 'HIGH';
export type RegimeType = 'BULL' | 'BEAR' | 'NEUTRAL';

export interface MarketRegime {
    btcTrend: RegimeTrend;
    solTrend: RegimeTrend;
    btcChange24h: number;
    solChange24h: number;
    solPrice: number;
    riskLevel: RiskLevel;
    regime: RegimeType;
}

// ============================================================================
// Macro Analysis
// ============================================================================

export interface MacroAnalysis {
    shortTerm: string;    // Next 24h
    mediumTerm: string;   // Next 3 days
    longTerm: string;     // 1 week to 1 month
    keyEvents: string[];
}

// ============================================================================
// Stock Picks (xStocks)
// ============================================================================

export type TradeDirection = 'LONG' | 'SHORT';

export interface StockPick {
    ticker: string;
    direction: TradeDirection;
    reason: string;
    target: string;
    stopLoss: string;
    underlying?: string;  // e.g., "Apple Inc."
}

// ============================================================================
// Commodities
// ============================================================================

export interface CommodityMover {
    name: string;
    direction: TradeDirection;
    change: string;
    reason: string;
    outlook: string;
}

export interface PreciousMetalsOutlook {
    goldDirection: RegimeTrend;
    goldOutlook: string;
    silverDirection: RegimeTrend;
    silverOutlook: string;
    platinumDirection: RegimeTrend;
    platinumOutlook: string;
}

// ============================================================================
// Conviction Picks (Unified Top 10)
// ============================================================================

export type AssetType = 'TOKEN' | 'XSTOCK' | 'INDEX' | 'WRAPPED' | 'LST' | 'DEFI';
export type RiskProfile = 'SAFE' | 'MEDIUM' | 'DEGEN';

export interface ConvictionPick {
    rank: number;
    symbol: string;
    assetType: AssetType;
    direction: TradeDirection;
    convictionScore: number;  // 0-100
    entryPrice: number;

    // Risk-tiered targets
    targets: {
        safe: { takeProfit: number; stopLoss: number };
        medium: { takeProfit: number; stopLoss: number };
        degen: { takeProfit: number; stopLoss: number };
    };

    reasoning: string;
    grade: SentimentGrade;
    contractAddress?: string;
}

// ============================================================================
// Dashboard State
// ============================================================================

export interface SentimentDashboardData {
    lastUpdated: Date;
    marketRegime: MarketRegime;
    trendingTokens: TokenSentiment[];
    convictionPicks: ConvictionPick[];
    macroAnalysis: MacroAnalysis;
    stockPicks: StockPick[];
    commodityMovers: CommodityMover[];
    preciousMetals: PreciousMetalsOutlook;
    isLoading: boolean;
    error: string | null;
}

// ============================================================================
// UI Helpers
// ============================================================================

export const GRADE_COLORS: Record<SentimentGrade, { text: string; bg: string; border: string }> = {
    'A+': { text: 'text-emerald-400', bg: 'bg-emerald-500/20', border: 'border-emerald-500/40' },
    'A': { text: 'text-emerald-400', bg: 'bg-emerald-500/15', border: 'border-emerald-500/30' },
    'A-': { text: 'text-green-400', bg: 'bg-green-500/15', border: 'border-green-500/30' },
    'B+': { text: 'text-lime-400', bg: 'bg-lime-500/15', border: 'border-lime-500/30' },
    'B': { text: 'text-yellow-400', bg: 'bg-yellow-500/15', border: 'border-yellow-500/30' },
    'B-': { text: 'text-yellow-500', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20' },
    'C+': { text: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
    'C': { text: 'text-orange-500', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
    'C-': { text: 'text-orange-600', bg: 'bg-orange-600/10', border: 'border-orange-600/20' },
    'D+': { text: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' },
    'D': { text: 'text-red-500', bg: 'bg-red-500/10', border: 'border-red-500/20' },
    'F': { text: 'text-red-600', bg: 'bg-red-600/15', border: 'border-red-600/30' },
};

export const REGIME_COLORS: Record<RegimeTrend, { text: string; bg: string }> = {
    'BULLISH': { text: 'text-emerald-400', bg: 'bg-emerald-500/20' },
    'NEUTRAL': { text: 'text-yellow-400', bg: 'bg-yellow-500/20' },
    'BEARISH': { text: 'text-red-400', bg: 'bg-red-500/20' },
};

export const ASSET_TYPE_LABELS: Record<AssetType, string> = {
    'TOKEN': '🪙 Token',
    'XSTOCK': '📈 xStock',
    'INDEX': '📊 Index',
    'WRAPPED': '🔗 Wrapped',
    'LST': '💧 LST',
    'DEFI': '🏦 DeFi',
};
