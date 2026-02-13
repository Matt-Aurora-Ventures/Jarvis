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
    description: 'High win rate with tight stop-loss. Targets consistent small wins on quality graduations. Best for capital preservation.',
    backtestWinRate: 'Unverified',
    backtestTrades: 0,
    params: {
      stopLossPct: 15,
      takeProfitPct: 40,
      trailingStopPct: 8,
      entryDelayMinutes: 2,
      minScore: 40,
      minBondingScore: 40,
    },
  },
  {
    id: 'bags_momentum',
    name: 'BAGS MOMENTUM',
    description: 'Catches post-graduation pumps with wider take-profit. Accepts more volatility for larger upside. Trailing stop locks in gains.',
    backtestWinRate: 'Unverified',
    backtestTrades: 0,
    params: {
      stopLossPct: 25,
      takeProfitPct: 150,
      trailingStopPct: 15,
      entryDelayMinutes: 0,
      minScore: 30,
    },
  },
  {
    id: 'bags_value',
    name: 'BAGS VALUE',
    description: 'Only enters high-quality tokens (score 60+). Patient entry with delay to avoid initial volatility. Tight risk management.',
    backtestWinRate: 'Unverified',
    backtestTrades: 0,
    params: {
      stopLossPct: 10,
      takeProfitPct: 30,
      trailingStopPct: 5,
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
    description: 'Low score threshold, wide stop-loss, massive take-profit. Bets on moonshots. Low win rate but outsized winners cover losses.',
    backtestWinRate: 'Unverified',
    backtestTrades: 0,
    params: {
      stopLossPct: 40,
      takeProfitPct: 300,
      trailingStopPct: 20,
      entryDelayMinutes: 0,
      minScore: 10,
    },
  },
  {
    id: 'bags_elite',
    name: 'BAGS ELITE',
    description: 'Highest quality filter (score 70+). Tight risk controls with moderate upside. Best risk-adjusted returns for patient traders.',
    backtestWinRate: 'Unverified',
    backtestTrades: 0,
    params: {
      stopLossPct: 12,
      takeProfitPct: 50,
      trailingStopPct: 8,
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
