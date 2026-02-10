/**
 * TradingView-Enhanced Equity Scoring
 *
 * Blends on-chain DexScreener data with off-chain TradingView indicators
 * (RSI, MACD, technical rating, SMA alignment, relative volume) to produce
 * cross-referenced equity scores.
 *
 * When TradingView data is unavailable, falls back to DexScreener-only
 * scoring (preserving existing behavior).
 *
 * Exports:
 *  - calcMomentumScore(tv)           -> 0-100 momentum score
 *  - calcVolumeConfirmation(tv, vol) -> { score: 0-100, volumeRatio }
 *  - calcTVEnhancedScore(...)        -> composite number
 *  - calcTVEnhancedScoreDetailed(...)-> full TVEnhancedScore breakdown
 *  - TVEnhancedScore interface
 */

import type { TVStockData } from '@/lib/tv-screener';
import type { TokenizedEquity } from '@/lib/xstocks-data';

// ============================================================================
// Types
// ============================================================================

export interface TVEnhancedScore {
  composite: number;
  momentum: number;
  volumeConfirmation: number;
  baseEquityScore: number;
  hasTVData: boolean;
}

// ============================================================================
// Momentum Score (0-100)
// ============================================================================

/**
 * Calculate a momentum score from TradingView indicators.
 *
 * Baseline: 50 (neutral).
 * Components:
 *   - RSI (30%):  >70 overbought penalty, 55-70 bullish, <30 oversold reversal, 30-45 weak
 *   - MACD (25%): macdLevel > macdSignal = bullish, else bearish
 *   - Technical Rating (25%): maps -1..+1 to -15..+15
 *   - SMA Trend (20%): uptrend/downtrend based on price vs SMA alignment
 *
 * If any indicator is null, that component is skipped and the baseline is
 * adjusted proportionally (score stays centered at 50 for missing data).
 */
export function calcMomentumScore(tv: TVStockData): number {
  let score = 0;
  let totalWeight = 0;

  // --- RSI (30% weight) ---
  if (tv.rsi14 !== null) {
    totalWeight += 30;
    if (tv.rsi14 > 70) {
      // Overbought penalty
      score += -15;
    } else if (tv.rsi14 >= 55) {
      // Bullish zone
      score += 10;
    } else if (tv.rsi14 >= 45) {
      // Neutral zone
      score += 0;
    } else if (tv.rsi14 >= 30) {
      // Weak
      score += -5;
    } else {
      // Oversold reversal potential (contrarian bullish)
      score += 15;
    }
  }

  // --- MACD (25% weight) ---
  if (tv.macdLevel !== null && tv.macdSignal !== null) {
    totalWeight += 25;
    if (tv.macdLevel > tv.macdSignal) {
      score += 12; // Bullish crossover / above signal
    } else {
      score += -8; // Bearish
    }
  }

  // --- Technical Rating (25% weight) ---
  if (tv.technicalRating !== null) {
    totalWeight += 25;
    // Maps -1..+1 range to -15..+15 contribution
    score += tv.technicalRating * 15;
  }

  // --- SMA Trend (20% weight) ---
  if (tv.sma20 !== null && tv.sma50 !== null) {
    totalWeight += 20;
    const price = tv.price;

    if (tv.sma200 !== null) {
      // Full SMA alignment check
      if (price > tv.sma20 && tv.sma20 > tv.sma50 && tv.sma50 > tv.sma200) {
        // Perfect uptrend
        score += 10;
      } else if (price < tv.sma20 && tv.sma20 < tv.sma50) {
        // Downtrend
        score += -10;
      } else {
        // Mixed
        score += 0;
      }
    } else {
      // Partial SMA data
      if (price > tv.sma20 && tv.sma20 > tv.sma50) {
        score += 7;
      } else if (price < tv.sma20 && tv.sma20 < tv.sma50) {
        score += -7;
      } else {
        score += 0;
      }
    }
  }

  // If no indicators are available, return baseline 50
  if (totalWeight === 0) return 50;

  // Normalize: scale contributions proportionally based on available weight,
  // then add to baseline 50
  const normalized = (score / totalWeight) * 100;
  const finalScore = 50 + normalized;

  return Math.max(0, Math.min(100, Math.round(finalScore)));
}

// ============================================================================
// Volume Confirmation (0-100)
// ============================================================================

/**
 * Calculate a volume confirmation score using TradingView relative volume
 * and DexScreener on-chain volume.
 *
 * Baseline: 50 (neutral).
 * Components:
 *   - Relative volume: >2.0 = +20, >1.5 = +10, <0.5 = -15
 *   - Tokenized interest: (dexVolume / dollarVolume) ratio scoring
 *
 * Returns both the score and the volumeRatio for display purposes.
 */
export function calcVolumeConfirmation(
  tv: TVStockData,
  dexVolume24h: number,
): { score: number; volumeRatio: number } {
  const dollarVolume = tv.volume * tv.price;

  // Guard against zero TV volume — return neutral
  if (dollarVolume === 0 && tv.relativeVolume === 0) {
    return { score: 50, volumeRatio: 0 };
  }

  let score = 50;

  // --- Relative Volume Component ---
  if (tv.relativeVolume >= 2.0) {
    score += 20;
  } else if (tv.relativeVolume >= 1.5) {
    score += 10;
  } else if (tv.relativeVolume < 0.5) {
    score -= 15;
  }
  // 0.5 - 1.5 = neutral, no adjustment

  // --- Tokenized Interest Component ---
  const volumeRatio = dollarVolume > 0 ? dexVolume24h / dollarVolume : 0;

  if (volumeRatio > 0.01) {
    score += 15; // Very high tokenized interest
  } else if (volumeRatio > 0.001) {
    score += 5;  // Moderate interest
  } else if (volumeRatio < 0.0001 && dollarVolume > 0) {
    score -= 10; // Very low tokenized interest
  }

  return {
    score: Math.max(0, Math.min(100, Math.round(score))),
    volumeRatio,
  };
}

// ============================================================================
// Base Equity Score (DexScreener-only, ported from xstocks/route.ts)
// ============================================================================

/**
 * Compute the base equity score using only DexScreener on-chain data.
 *
 * This is a standalone copy of the original `calcEquityScore()` from the
 * xstocks API route, so that scoring can work independently of the route.
 */
export function calcBaseEquityScore(
  token: TokenizedEquity,
  pair: any,
): number {
  if (!pair) return 35;

  const liq = parseFloat(pair.liquidity?.usd || '0');
  const vol24h = parseFloat(pair.volume?.h24 || '0');
  const change1h = pair.priceChange?.h1 || 0;
  const change24h = pair.priceChange?.h24 || 0;
  const buys1h = pair.txns?.h1?.buys || 0;
  const sells1h = pair.txns?.h1?.sells || 0;
  const totalTxns = buys1h + sells1h;
  const bsRatio = sells1h > 0 ? buys1h / sells1h : buys1h;
  const volLiqRatio = liq > 0 ? vol24h / liq : 0;

  let score = 0;

  // --- Trading Activity (0-30) ---
  if (volLiqRatio >= 2.0) score += 20;
  else if (volLiqRatio >= 1.0) score += 16;
  else if (volLiqRatio >= 0.5) score += 12;
  else if (volLiqRatio >= 0.2) score += 8;
  else score += 4;

  if (totalTxns >= 200) score += 10;
  else if (totalTxns >= 50) score += 7;
  else if (totalTxns >= 20) score += 5;
  else if (totalTxns >= 5) score += 3;
  else score += 1;

  // --- Price Momentum (0-30) ---
  const absChange1h = Math.abs(change1h);
  if (absChange1h >= 3) score += 15;
  else if (absChange1h >= 1.5) score += 12;
  else if (absChange1h >= 0.5) score += 8;
  else score += 4;

  if ((change1h > 0 && change24h > 0) || (change1h < 0 && change24h < 0)) {
    score += 10; // aligned trend
  } else if (Math.abs(change24h) < 1) {
    score += 5; // rangebound
  } else {
    score += 3; // mixed signals
  }

  if (absChange1h >= 5) score += 5;

  // --- Market Quality (0-20) ---
  if (liq >= 500_000) score += 8;
  else if (liq >= 100_000) score += 5;
  else if (liq >= 50_000) score += 3;
  else score += 1;

  if (bsRatio >= 1.0 && bsRatio <= 2.5 && totalTxns >= 10) {
    score += 7; // healthy buying
  } else if (bsRatio >= 0.5 && bsRatio <= 3.5) {
    score += 4;
  } else {
    score += 1;
  }

  if (liq > 200_000 && volLiqRatio > 0.3) score += 5;
  else score += 2;

  // --- Asset Class Bonus (0-20) ---
  const cat = token.category;
  const sector = token.sector.toLowerCase();
  if (cat === 'INDEX') {
    score += 15;
    if (token.ticker === 'TQQQx') score -= 3;
  } else if (cat === 'XSTOCK') {
    if (['technology', 'finance'].includes(sector)) score += 12;
    else if (['healthcare', 'consumer', 'energy'].includes(sector)) score += 10;
    else score += 8;
    if (['AAPLx', 'MSFTx', 'GOOGLx', 'AMZNx', 'NVDAx', 'METAx'].includes(token.ticker)) {
      score += 5;
    }
  } else if (cat === 'PRESTOCK') {
    score += 5;
  } else if (cat === 'COMMODITY') {
    score += 12;
  }

  return Math.max(10, Math.min(100, Math.round(score)));
}

// ============================================================================
// Composite Enhanced Score
// ============================================================================

/**
 * Compute a TV-enhanced equity score.
 *
 * Weighting when TV data is available:
 *   - 40% DexScreener base equity score
 *   - 35% TradingView momentum score
 *   - 25% Volume confirmation score
 *
 * When TV data is null, falls back to DexScreener-only scoring.
 *
 * Result is clamped to 10-100.
 */
export function calcTVEnhancedScore(
  tv: TVStockData | null,
  dexPair: any,
  token: TokenizedEquity,
): number {
  return calcTVEnhancedScoreDetailed(tv, dexPair, token).composite;
}

/**
 * Detailed version returning the full TVEnhancedScore breakdown.
 */
export function calcTVEnhancedScoreDetailed(
  tv: TVStockData | null,
  dexPair: any,
  token: TokenizedEquity,
): TVEnhancedScore {
  const baseScore = calcBaseEquityScore(token, dexPair);

  if (tv === null) {
    return {
      composite: baseScore,
      momentum: 50,
      volumeConfirmation: 50,
      baseEquityScore: baseScore,
      hasTVData: false,
    };
  }

  const momentumScore = calcMomentumScore(tv);
  const dexVolume = parseFloat(dexPair?.volume?.h24 || '0');
  const { score: volumeScore } = calcVolumeConfirmation(tv, dexVolume);

  const raw = baseScore * 0.4 + momentumScore * 0.35 + volumeScore * 0.25;
  const composite = Math.max(10, Math.min(100, Math.round(raw)));

  return {
    composite,
    momentum: momentumScore,
    volumeConfirmation: volumeScore,
    baseEquityScore: baseScore,
    hasTVData: true,
  };
}
