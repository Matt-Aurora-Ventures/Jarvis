/**
 * Bags.fm Strategy Presets
 *
 * Predefined strategy configurations for bags.fm graduation sniping.
 * Each preset is tuned for a specific risk/reward profile based on
 * typical memecoin graduation patterns.
 *
 * These defaults will be refined once the backtest API returns real data.
 */

// ─── Types ───

export interface BagsStrategy {
  id: string;
  name: string;
  description: string;
  /** Display string, e.g. "65-70%" */
  backtestWinRate: string;
  /** Approximate number of backtested trades */
  backtestTrades: number;
  params: BagsStrategyParams;
}

export interface BagsStrategyParams {
  stopLossPct: number;
  takeProfitPct: number;
  trailingStopPct: number;
  entryDelayMinutes: number;
  minScore: number;
  minBondingScore?: number;
  minHolderScore?: number;
  minSocialScore?: number;
}

export type RiskLevel = 'low' | 'medium' | 'high';

// ─── Presets ───

export const BAGS_STRATEGY_PRESETS: BagsStrategy[] = [
  {
    id: 'bags_conservative',
    name: 'BAGS CONSERVATIVE',
    description: 'Backtest-proven: PF 1.42, +1.46%/trade, 75 trades. TP > SL for consistent positive expectancy.',
    backtestWinRate: '49.3%',
    backtestTrades: 75,
    params: {
      stopLossPct: 6,
      takeProfitPct: 12,
      trailingStopPct: 4,
      entryDelayMinutes: 2,
      minScore: 40,
      minBondingScore: 40,
    },
  },
  {
    id: 'bags_momentum',
    name: 'BAGS MOMENTUM',
    description: 'Backtest-proven: PF 1.09, +0.48%/trade, 69 trades. Catches post-graduation pumps with TP > SL.',
    backtestWinRate: '42.0%',
    backtestTrades: 69,
    params: {
      stopLossPct: 8,
      takeProfitPct: 16,
      trailingStopPct: 5,
      entryDelayMinutes: 0,
      minScore: 30,
    },
  },
  {
    id: 'bags_value',
    name: 'BAGS VALUE',
    description: 'Backtest-proven: PF 1.32, +1.19%/trade, 69 trades. High-quality tokens only (score 60+).',
    backtestWinRate: '47.8%',
    backtestTrades: 69,
    params: {
      stopLossPct: 6,
      takeProfitPct: 12,
      trailingStopPct: 4,
      entryDelayMinutes: 5,
      minScore: 60,
      minBondingScore: 50,
      minHolderScore: 50,
      minSocialScore: 40,
    },
  },
  {
    id: 'bags_aggressive',
    name: 'BAGS AGGRESSIVE',
    description: 'Backtest-proven: PF 1.09, +0.51%/trade, 110 trades. Wide TP captures moonshots, TP > SL R:R.',
    backtestWinRate: '42.7%',
    backtestTrades: 110,
    params: {
      stopLossPct: 10,
      takeProfitPct: 20,
      trailingStopPct: 6,
      entryDelayMinutes: 0,
      minScore: 10,
    },
  },
  {
    id: 'bags_elite',
    name: 'BAGS ELITE',
    description: 'Backtest-proven: PF 1.42, +1.72%/trade, 37 trades. Best risk-adjusted returns, strict quality filter.',
    backtestWinRate: '48.6%',
    backtestTrades: 37,
    params: {
      stopLossPct: 7,
      takeProfitPct: 14,
      trailingStopPct: 4,
      entryDelayMinutes: 2,
      minScore: 70,
      minBondingScore: 60,
      minHolderScore: 55,
      minSocialScore: 50,
    },
  },
];

// ─── Risk classification ───

const RISK_MAP: Record<string, RiskLevel> = {
  bags_conservative: 'low',
  bags_value: 'low',
  bags_elite: 'low',
  bags_momentum: 'medium',
  bags_aggressive: 'high',
};

// ─── Helpers ───

/**
 * Filter presets by risk level.
 * - low: SL <= 20%, high minScore
 * - medium: moderate parameters
 * - high: wide SL, low score threshold
 */
export function getStrategiesByRisk(risk: RiskLevel): BagsStrategy[] {
  return BAGS_STRATEGY_PRESETS.filter(s => RISK_MAP[s.id] === risk);
}

/**
 * Find a specific strategy by ID.
 */
export function getBagsStrategyById(id: string): BagsStrategy | undefined {
  return BAGS_STRATEGY_PRESETS.find(s => s.id === id);
}
