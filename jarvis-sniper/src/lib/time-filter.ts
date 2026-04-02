/**
 * Time-of-Day Filter for Trading Strategies
 *
 * Purpose: Filter trades based on UTC hour analysis from backtesting.
 * Win rates vary significantly by hour — avoid low-WR hours to improve edge.
 *
 * Based on BACKTEST_RESULTS.md analysis:
 * - AVOID hours: 4:00, 5:00, 9:00, 14:00, 15:00, 19:00, 23:00 UTC (0% WR)
 * - PREFER hours: 10:00, 17:00, 22:00 UTC (100% WR)
 */

export type HourQuality = 'avoid' | 'neutral' | 'prefer';

// Hours with 0% win rate in backtest (skip trading)
const AVOID_HOURS = new Set([4, 5, 9, 14, 15, 19, 23]);

// Hours with 100% win rate in backtest (prefer)
const PREFER_HOURS = new Set([10, 17, 22]);

/**
 * Get the quality rating for a given UTC hour.
 */
export function getHourQuality(utcHour: number): HourQuality {
  if (AVOID_HOURS.has(utcHour)) return 'avoid';
  if (PREFER_HOURS.has(utcHour)) return 'prefer';
  return 'neutral';
}

/**
 * Check if the current hour is safe for trading.
 * Returns false during avoid hours.
 */
export function isSafeToTrade(now = new Date()): boolean {
  const utcHour = now.getUTCHours();
  return getHourQuality(utcHour) !== 'avoid';
}

/**
 * Check if the current hour is optimal for trading.
 * Returns true only during prefer hours.
 */
export function isOptimalTradingHour(now = new Date()): boolean {
  const utcHour = now.getUTCHours();
  return getHourQuality(utcHour) === 'prefer';
}

/**
 * Get the next safe trading hour.
 * Useful for delaying entries during avoid periods.
 */
export function getNextSafeHour(now = new Date()): { hour: number; minutesUntil: number } {
  const utcHour = now.getUTCHours();
  const minutes = now.getUTCMinutes();

  // Check next 24 hours
  for (let i = 0; i < 24; i++) {
    const checkHour = (utcHour + i) % 24;
    if (getHourQuality(checkHour) !== 'avoid') {
      const minutesUntil = i === 0 ? 0 : (i * 60 - minutes);
      return { hour: checkHour, minutesUntil: Math.max(0, minutesUntil) };
    }
  }

  // Should never reach here (not all 24 hours are avoided)
  return { hour: utcHour, minutesUntil: 0 };
}

/**
 * Get the next optimal trading hour.
 * Useful for high-conviction entries.
 */
export function getNextOptimalHour(now = new Date()): { hour: number; minutesUntil: number } | null {
  const utcHour = now.getUTCHours();
  const minutes = now.getUTCMinutes();

  // Check next 24 hours
  for (let i = 0; i < 24; i++) {
    const checkHour = (utcHour + i) % 24;
    if (getHourQuality(checkHour) === 'prefer') {
      const minutesUntil = i === 0 ? 0 : (i * 60 - minutes);
      return { hour: checkHour, minutesUntil: Math.max(0, minutesUntil) };
    }
  }

  return null;
}

/**
 * Filter a list of tokens based on current hour quality.
 * During 'avoid' hours, returns empty array.
 * During 'prefer' hours, returns all tokens.
 * During 'neutral' hours, applies stricter filtering.
 */
export function filterByHour<T extends { score: number }>(
  tokens: T[],
  minScoreNeutral = 50,
  now = new Date(),
): T[] {
  const quality = getHourQuality(now.getUTCHours());

  if (quality === 'avoid') {
    return [];
  }

  if (quality === 'prefer') {
    return tokens;
  }

  // Neutral: require higher score
  return tokens.filter(t => t.score >= minScoreNeutral);
}

/**
 * Get a human-readable trading window summary.
 */
export function getTradingWindowSummary(): string {
  const avoidList = [...AVOID_HOURS].sort((a, b) => a - b);
  const preferList = [...PREFER_HOURS].sort((a, b) => a - b);

  return [
    `PREFER hours (UTC): ${preferList.map(h => `${h}:00`).join(', ')}`,
    `AVOID hours (UTC): ${avoidList.map(h => `${h}:00`).join(', ')}`,
    `NEUTRAL hours: all others`,
  ].join('\n');
}
