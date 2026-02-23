// ---------------------------------------------------------------------------
// Risk Score Calculator
// ---------------------------------------------------------------------------
// Pure function that computes a risk assessment for a trading position
// based on multiple factors. Score ranges from 0 (safest) to 100 (riskiest).
// ---------------------------------------------------------------------------

export interface RiskAssessment {
  score: number;         // 0-100 (0=safest, 100=riskiest)
  level: 'LOW' | 'MEDIUM' | 'HIGH' | 'EXTREME';
  factors: string[];     // Human-readable risk factors
}

export interface RiskScoreParams {
  pnlPercent: number;        // Current P&L %
  holdDurationMs: number;    // How long position has been held
  hasStopLoss: boolean;      // Whether SL is set
  hasTakeProfit: boolean;    // Whether TP is set
  positionSizeSol: number;   // Size in SOL
  volatility24h?: number;    // Optional 24h price change %
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ONE_DAY_MS = 24 * 60 * 60 * 1000;
const SEVEN_DAYS_MS = 7 * ONE_DAY_MS;

// ---------------------------------------------------------------------------
// Main function
// ---------------------------------------------------------------------------

export function computeRiskScore(params: RiskScoreParams): RiskAssessment {
  let score = 0;
  const factors: string[] = [];

  // --- No stop loss: +30 ---
  if (!params.hasStopLoss) {
    score += 30;
    factors.push('No stop loss set');
  }

  // --- No take profit: +10 ---
  if (!params.hasTakeProfit) {
    score += 10;
    factors.push('No take profit set');
  }

  // --- Holding > 24h with negative P&L: +15 ---
  if (params.holdDurationMs > ONE_DAY_MS && params.pnlPercent < 0) {
    const days = Math.floor(params.holdDurationMs / ONE_DAY_MS);
    score += 15;
    factors.push(
      `Holding for ${days} day${days !== 1 ? 's' : ''} at ${params.pnlPercent.toFixed(1)}%`,
    );
  }

  // --- Holding > 7 days: +10 ---
  if (params.holdDurationMs > SEVEN_DAYS_MS) {
    const days = Math.floor(params.holdDurationMs / ONE_DAY_MS);
    score += 10;
    factors.push(`Position held for ${days} days`);
  }

  // --- P&L below -10%: +20 ---
  if (params.pnlPercent < -10) {
    score += 20;
    factors.push(`P&L at ${params.pnlPercent.toFixed(1)}%`);
  }

  // --- P&L below -25%: +10 more (cumulative with above) ---
  if (params.pnlPercent < -25) {
    score += 10;
    factors.push(`Deep loss at ${params.pnlPercent.toFixed(1)}%`);
  }

  // --- Position > 1 SOL: +5 ---
  if (params.positionSizeSol > 1) {
    score += 5;
    factors.push(`Large position: ${params.positionSizeSol.toFixed(2)} SOL`);
  }

  // --- Position > 5 SOL: +10 more ---
  if (params.positionSizeSol > 5) {
    score += 10;
    factors.push(`Very large position: ${params.positionSizeSol.toFixed(2)} SOL`);
  }

  // --- High volatility (>20% 24h): +10 ---
  if (params.volatility24h !== undefined && params.volatility24h > 20) {
    score += 10;
    factors.push(`High 24h volatility: ${params.volatility24h.toFixed(1)}%`);
  }

  // Clamp score to [0, 100]
  score = Math.max(0, Math.min(100, score));

  // Determine level
  let level: RiskAssessment['level'];
  if (score <= 25) {
    level = 'LOW';
  } else if (score <= 50) {
    level = 'MEDIUM';
  } else if (score <= 75) {
    level = 'HIGH';
  } else {
    level = 'EXTREME';
  }

  return { score, level, factors };
}
