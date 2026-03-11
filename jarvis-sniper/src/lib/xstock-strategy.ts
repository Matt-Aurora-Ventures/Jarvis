/**
 * xStock Strategy - Tokenized Traditional Equities on Solana
 *
 * Handles the unique trading rules for tokenized stocks:
 * - Market hours gating (only trade during US market hours)
 * - Oracle staleness checks
 * - Higher slippage tolerance for thin pools
 *
 * @module xstock-strategy
 */

import { getUnixTime } from 'date-fns';

// US Market Hours: 9:30 AM - 4:00 PM ET, Monday-Friday
const MARKET_OPEN_HOUR = 9;
const MARKET_OPEN_MINUTE = 30;
const MARKET_CLOSE_HOUR = 16;
const MARKET_CLOSE_MINUTE = 0;

// Timezone
const US_EASTERN = 'America/New_York';

// Oracle staleness thresholds (in minutes)
const STALENESS_DEGRADED = 5;
const STALENESS_HALT = 30;

export interface XStockConfig {
  /** Symbol (e.g., 'TSLA', 'NVDA', 'AAPL') */
  symbol: string;
  /** Pool liquidity in USD */
  poolLiquidityUsd: number;
  /** Last oracle update timestamp */
  lastOracleUpdate: Date;
  /** Current SOL price for fee calculations */
  solPriceUsd: number;
}

/**
 * Check if market is open for trading
 *
 * Returns true ONLY if:
 * - Weekday (Mon-Fri)
 * - Between 9:30 AM and 4:00 PM Eastern
 * - Not a US market holiday
 */
export function isMarketHours(dt: Date): boolean {
  // Get day of week (0 = Sunday, 6 = Saturday)
  const day = dt.getDay();

  // Weekend check
  if (day === 0 || day === 6) {
    return false;
  }

  // Get hours and minutes in local time
  const hours = dt.getHours();
  const minutes = dt.getMinutes();

  // Convert to market time (simplified - assumes local is ET or handles via date-fns)
  // For simplicity, we use the input as-is assuming it's already in ET

  // Market open: 9:30
  const marketOpenMinutes = MARKET_OPEN_HOUR * 60 + MARKET_OPEN_MINUTE;
  // Market close: 16:00
  const marketCloseMinutes = MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MINUTE;

  const currentMinutes = hours * 60 + minutes;

  // Check if within market hours
  if (currentMinutes < marketOpenMinutes || currentMinutes >= marketCloseMinutes) {
    return false;
  }

  // Check for market holidays (simplified list)
  if (isMarketHoliday(dt)) {
    return false;
  }

  return true;
}

/**
 * Check if date is a US market holiday
 */
function isMarketHoliday(dt: Date): boolean {
  const month = dt.getMonth();
  const date = dt.getDate();
  const day = dt.getDay();

  // New Year's Day (Jan 1)
  if (month === 0 && date === 1) return true;

  // Martin Luther King Jr. Day (Third Monday of January)
  if (month === 0 && day === 1 && date >= 15 && date <= 21) return true;

  // Presidents' Day (Third Monday of February)
  if (month === 1 && day === 1 && date >= 15 && date <= 21) return true;

  // Good Friday (Friday before Easter - simplified check)
  // Memorial Day (Last Monday of May)
  if (month === 4 && day === 1 && date >= 25) return true;

  // Independence Day (July 4)
  if (month === 6 && date === 4) return true;

  // Labor Day (First Monday of September)
  if (month === 8 && day === 1 && date <= 7) return true;

  // Thanksgiving (Fourth Thursday of November)
  if (month === 10 && day === 4 && date >= 22 && date <= 28) return true;

  // Christmas (December 25)
  if (month === 11 && date === 25) return true;

  return false;
}

/**
 * Get oracle staleness in minutes
 */
export function getOracleStalenessMinutes(lastUpdate: Date, currentTime: Date = new Date()): number {
  const diffMs = currentTime.getTime() - lastUpdate.getTime();
  return diffMs / (1000 * 60); // Convert to minutes
}

/**
 * Check if oracle data is fresh enough to trade
 */
export function isOracleFresh(
  lastUpdate: Date,
  currentTime: Date = new Date()
): { fresh: boolean; degraded: boolean; halted: boolean; stalenessMinutes: number } {
  const staleness = getOracleStalenessMinutes(lastUpdate, currentTime);

  if (staleness > STALENESS_HALT) {
    return { fresh: false, degraded: true, halted: true, stalenessMinutes: staleness };
  }

  if (staleness > STALENESS_DEGRADED) {
    return { fresh: false, degraded: true, halted: false, stalenessMinutes: staleness };
  }

  return { fresh: true, degraded: false, halted: false, stalenessMinutes: staleness };
}

/**
 * Determine if we can trade an xStock
 */
export function canTradeXStock(config: XStockConfig): {
  canTrade: boolean;
  reason: string;
  slippageMultiplier: number;
} {
  const now = new Date();

  // Check market hours
  if (!isMarketHours(now)) {
    return {
      canTrade: false,
      reason: 'Market closed (outside US market hours)',
      slippageMultiplier: 1,
    };
  }

  // Check oracle freshness
  const oracleStatus = isOracleFresh(config.lastOracleUpdate, now);

  if (oracleStatus.halted) {
    return {
      canTrade: false,
      reason: `Oracle stale: ${oracleStatus.stalenessMinutes.toFixed(1)} minutes`,
      slippageMultiplier: 1,
    };
  }

  // Determine slippage multiplier based on liquidity
  let slippageMultiplier = 1;
  if (config.poolLiquidityUsd < 50000) {
    slippageMultiplier = 3; // Very thin
  } else if (config.poolLiquidityUsd < 100000) {
    slippageMultiplier = 2; // Thin
  } else if (config.poolLiquidityUsd < 500000) {
    slippageMultiplier = 1.5; // Moderate
  }

  // For degraded oracle, increase slippage further
  if (oracleStatus.degraded) {
    slippageMultiplier *= 2;
  }

  return {
    canTrade: true,
    reason: oracleStatus.degraded
      ? `Oracle degraded (${oracleStatus.stalenessMinutes.toFixed(1)} min), using wider slippage`
      : 'OK',
    slippageMultiplier,
  };
}

/**
 * Get recommended slippage for xStock based on liquidity
 */
export function getXStockSlippage(
  poolLiquidityUsd: number,
  isMarketOpen: boolean
): number {
  let baseSlippage: number;

  // Base slippage by liquidity
  if (poolLiquidityUsd > 1000000) {
    baseSlippage = 0.01; // 1%
  } else if (poolLiquidityUsd > 500000) {
    baseSlippage = 0.015; // 1.5%
  } else if (poolLiquidityUsd > 100000) {
    baseSlippage = 0.02; // 2%
  } else if (poolLiquidityUsd > 50000) {
    baseSlippage = 0.03; // 3%
  } else {
    baseSlippage = 0.05; // 5% - very thin
  }

  // Increase slippage when market closed
  if (!isMarketOpen) {
    baseSlippage *= 2;
  }

  return baseSlippage;
}

/**
 * Get position size limit for xStock
 */
export function getXStockMaxPositionSize(
  poolLiquidityUsd: number,
  accountBalanceUsd: number
): number {
  // Hard cap at 0.25% of portfolio for thin xStocks
  const portfolioLimit = accountBalanceUsd * 0.0025;

  // Liquidity-based limit (can't trade more than 5% of pool)
  const liquidityLimit = poolLiquidityUsd * 0.05;

  // Return the smaller limit
  return Math.min(portfolioLimit, liquidityLimit);
}

/**
 * High liquidity xStock tickers (from Backed Finance)
 */
export const HIGH_LIQUIDITY_XSTOCKS = [
  'TSLA', // Tesla
  'NVDA', // NVIDIA
  'AAPL', // Apple
  'MSFT', // Microsoft
  'AMZN', // Amazon
  'GOOGL', // Google
  'SPY',  // S&P 500 ETF
  'QQQ',  // Nasdaq ETF
];

export function isHighLiquidityXStock(symbol: string): boolean {
  return HIGH_LIQUIDITY_XSTOCKS.includes(symbol.toUpperCase());
}
