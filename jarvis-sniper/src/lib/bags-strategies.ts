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
    id: 'bags_fresh_snipe',
    name: 'BAGS FRESH SNIPE',
    description: 'R4: PF 1.27, +1.94%/trade, 48 trades. Fresh launches with realistic TP.',
    backtestWinRate: '37.5%',
    backtestTrades: 48,
    params: {
      stopLossPct: 10,
      takeProfitPct: 30,
      trailingStopPct: 99,
      entryDelayMinutes: 0,
      minScore: 35,
    },
  },
  {
    id: 'bags_momentum',
    name: 'BAGS MOMENTUM',
    description: 'R4: PF 0.88, -0.60%/trade, 61 trades (borderline). Post-launch momentum.',
    backtestWinRate: '29.5%',
    backtestTrades: 61,
    params: {
      stopLossPct: 10,
      takeProfitPct: 30,
      trailingStopPct: 99,
      entryDelayMinutes: 0,
      minScore: 30,
    },
  },
  {
    id: 'bags_value',
    name: 'BAGS VALUE',
    description: 'R4: PF 1.50, +1.41%/trade, 71 trades. High-quality tokens only.',
    backtestWinRate: '50.7%',
    backtestTrades: 71,
    params: {
      stopLossPct: 5,
      takeProfitPct: 10,
      trailingStopPct: 99,
      entryDelayMinutes: 5,
      minScore: 55,
      minBondingScore: 50,
      minHolderScore: 50,
      minSocialScore: 40,
    },
  },
  {
    id: 'bags_dip_buyer',
    name: 'BAGS DIP BUYER',
    description: 'R4: PF 1.34, +1.83%/trade, 110 trades. Post-dip recovery plays.',
    backtestWinRate: '36.4%',
    backtestTrades: 110,
    params: {
      stopLossPct: 8,
      takeProfitPct: 25,
      trailingStopPct: 99,
      entryDelayMinutes: 0,
      minScore: 25,
    },
  },
  {
    id: 'bags_bluechip',
    name: 'BAGS BLUE CHIP',
    description: 'R4: PF 1.52, +1.38%/trade, 66 trades. Established bags tokens.',
    backtestWinRate: '54.5%',
    backtestTrades: 66,
    params: {
      stopLossPct: 5,
      takeProfitPct: 9,
      trailingStopPct: 99,
      entryDelayMinutes: 5,
      minScore: 60,
      minBondingScore: 50,
    },
  },
  {
    id: 'bags_conservative',
    name: 'BAGS CONSERVATIVE',
    description: 'R4: PF 1.51, +1.43%/trade, 78 trades. Conservative survival strategy.',
    backtestWinRate: '51.3%',
    backtestTrades: 78,
    params: {
      stopLossPct: 5,
      takeProfitPct: 10,
      trailingStopPct: 99,
      entryDelayMinutes: 2,
      minScore: 40,
      minBondingScore: 40,
    },
  },
  {
    id: 'bags_aggressive',
    name: 'BAGS AGGRESSIVE',
    description: 'R4: PF 1.14, +0.74%/trade, 105 trades. High-conviction plays.',
    backtestWinRate: '33.3%',
    backtestTrades: 105,
    params: {
      stopLossPct: 7,
      takeProfitPct: 25,
      trailingStopPct: 99,
      entryDelayMinutes: 0,
      minScore: 10,
    },
  },
  {
    id: 'bags_elite',
    name: 'BAGS ELITE',
    description: 'R4: PF 1.45, +1.25%/trade, 40 trades. Best risk-adjusted returns.',
    backtestWinRate: '55.0%',
    backtestTrades: 40,
    params: {
      stopLossPct: 5,
      takeProfitPct: 9,
      trailingStopPct: 99,
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
  bags_bluechip: 'low',
  bags_momentum: 'medium',
  bags_dip_buyer: 'medium',
  bags_fresh_snipe: 'high',
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
