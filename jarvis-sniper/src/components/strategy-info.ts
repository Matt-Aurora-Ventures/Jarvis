/** Risk level indicator for each strategy */
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'EXTREME';

/** Rich strategy descriptions shown in the breakdown panel */
export const STRATEGY_INFO: Record<string, {
  summary: string;
  optimal: string;
  risk: string;
  params: string;
  /** One-line "Best for:" description aimed at beginners */
  bestFor: string;
  /** Risk level: LOW / MEDIUM / HIGH / EXTREME */
  riskLevel: RiskLevel;
  /** Expected hold time, e.g. "Usually exits within: 1-4 hours" */
  holdTime: string;
}> = {
  // ─── MEMECOIN ─────────────────────────────────────────────────────────────
  elite: {
    summary: 'Strict filter for higher-liquidity, higher-momentum meme setups.',
    optimal: 'Best when the feed shows multiple strong-liquidity tokens and momentum is clearly positive.',
    risk: 'Fewer trades. If you lower gates to “force” entries, expect worse fills and more rugs.',
    params: 'SL 10% | TP 20% | Trail OFF (99) | Liq $100K+ | Mom 10%+ | V/L 2.0+ | Age <100h',
    bestFor: 'Patient snipers who want fewer, higher-quality entries',
    riskLevel: 'LOW',
    holdTime: 'Usually exits within: 30-120 minutes',
  },
  pump_fresh_tight: {
    summary: 'Default fresh-launch preset: realistic exits and fast recycle of capital.',
    optimal: 'Best on brand-new launches with enough liquidity to actually exit without huge spread.',
    risk: 'Fresh tokens can rug or dump immediately after graduation. Keep sizing tiny.',
    params: 'SL 10% | TP 20% | Trail OFF (99) | Liq $5K+ | Score 40+ | Age <24h',
    bestFor: 'New users and general-purpose meme sniping',
    riskLevel: 'MEDIUM',
    holdTime: 'Usually exits within: 15-60 minutes',
  },
  micro_cap_surge: {
    summary: 'Micro-cap momentum for very early tokens with smaller liquidity.',
    optimal: 'Best when micro-caps are moving and the feed has many <24h tokens with active volume.',
    risk: 'Worse spreads and higher slippage than higher-liquidity tokens.',
    params: 'SL 10% | TP 20% | Trail OFF (99) | Liq $3K+ | Score 30+ | Age <24h',
    bestFor: 'Aggressive traders who accept more noise for more opportunities',
    riskLevel: 'HIGH',
    holdTime: 'Usually exits within: 15-90 minutes',
  },
  momentum: {
    summary: 'Mean-reversion dip-buy with wider TP. Profitable in the latest run, but still volatile.',
    optimal: 'Works best in choppy conditions where sharp bounces keep printing.',
    risk: 'Lower win rate than conservative presets. Keep size controlled and monitor slippage.',
    params: 'SL 10% | TP 25% | Trail OFF (99) | Liq $5K+ | Score 30+ | Age <200h',
    bestFor: 'Power users experimenting with dip-buy behavior',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: 1-8 hours',
  },
  hybrid_b: {
    summary: 'Hybrid dip entry variant tuned for bounce conditions.',
    optimal: 'Best during mean-reverting phases (not straight-line pumps).',
    risk: 'Can underperform in trend days; not suitable for fully passive operation.',
    params: 'SL 10% | TP 25% | Trail OFF (99) | Liq $5K+ | Score 30+ | Age <200h',
    bestFor: 'Power users testing alt entry behavior',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: 1-8 hours',
  },
  let_it_ride: {
    summary: 'Wider hold window for runners and slower reversals.',
    optimal: 'Best when bounces extend over multiple candles, not just quick scalps.',
    risk: 'Wider hold time raises exposure to reversals and liquidity shifts.',
    params: 'SL 10% | TP 25% | Trail OFF (99) | Liq $3K+ | Score 20+ | Age <500h',
    bestFor: 'Experienced users experimenting with longer holds',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: 1-12 hours',
  },

  // ─── ESTABLISHED TOKENS ──────────────────────────────────────────────────
  utility_swing: {
    summary: 'Utility/governance majors (JUP/RAY/PYTH style). Swing-friendly, less chaotic than memes.',
    optimal: 'Best when established tokens dip and recover with healthy liquidity.',
    risk: 'Lower volatility means fewer giant wins. Focus is consistency, not moonshots.',
    params: 'SL 8% | TP 15% | Trail OFF (99) | Liq $10K+ | Score 55+ | Established',
    bestFor: 'Users who prefer “real tokens” with deeper liquidity',
    riskLevel: 'MEDIUM',
    holdTime: 'Usually exits within: 3-24 hours',
  },
  meme_classic: {
    summary: 'Established memes with survival history (BONK/WIF style) using realistic exits.',
    optimal: 'Best when big memes dip and reclaim levels with steady volume.',
    risk: 'Still meme-driven. Expect sudden wicks and narrative pumps/dumps.',
    params: 'SL 8% | TP 15% | Trail OFF (99) | Liq $5K+ | Score 40+ | Established',
    bestFor: 'Meme traders who want more stability than fresh launches',
    riskLevel: 'MEDIUM',
    holdTime: 'Usually exits within: 3-48 hours',
  },
  sol_veteran: {
    summary: 'Higher-liquidity established Solana tokens with tighter exits.',
    optimal: 'Best when majors are trending and liquidity is deep enough for clean exits.',
    risk: 'Can chop sideways and grind time. Keep expectations realistic.',
    params: 'SL 8% | TP 15% | Trail OFF (99) | Liq $50K+ | Score 40+ | Established',
    bestFor: 'Traders who want liquidity-first filtering on established tokens',
    riskLevel: 'LOW',
    holdTime: 'Usually exits within: 3-24 hours',
  },
  volume_spike: {
    summary: 'Experimental: established volume surges with positive but less-stable consistency.',
    optimal: 'Use when you trust the surge source (listing/news/rotation).',
    risk: 'Volume spikes can be exit liquidity; currently kept out of auto-selection.',
    params: 'SL 8% | TP 15% | Trail OFF (99) | Liq $20K+ | Score 35+ | V/L 0.3+ | Established',
    bestFor: 'Advanced users testing volume-surge behavior',
    riskLevel: 'HIGH',
    holdTime: 'Usually exits within: 1-8 hours',
  },
  established_breakout: {
    summary: 'Experimental: established breakout signals with low sample size.',
    optimal: 'Best when the market is trending and breakouts are following through cleanly.',
    risk: 'Breakouts still fake out often; excluded from auto-selection pending larger sample.',
    params: 'SL 8% | TP 15% | Trail OFF (99) | Liq $10K+ | Score 30+ | Established',
    bestFor: 'Breakout traders experimenting with established tokens',
    riskLevel: 'HIGH',
    holdTime: 'Usually exits within: 2-12 hours',
  },

  // ─── BLUE CHIP SOLANA ────────────────────────────────────────────────────
  bluechip_trend_follow: {
    summary: 'Experimental: higher-liquidity Solana blue chips with wider realistic exits.',
    optimal: 'Best when the broad market is trending and majors have clear continuation.',
    risk: 'Current run is positive but low-sample; treated as experimental for now.',
    params: 'SL 10% | TP 25% | Trail OFF (99) | Liq $200K+ | Score 55+ | Established',
    bestFor: 'Users who want less chaos and can hold longer',
    riskLevel: 'MEDIUM',
    holdTime: 'Usually exits within: 1-8 hours',
  },
  bluechip_breakout: {
    summary: 'Experimental: blue chip breakout catcher with low-sample validation.',
    optimal: 'Best when majors compress and then expand with real volume follow-through.',
    risk: 'False breakouts happen and sample is still thin. Keep it experimental.',
    params: 'SL 10% | TP 25% | Trail OFF (99) | Liq $200K+ | Score 65+ | Established',
    bestFor: 'Traders who like breakouts but want blue-chip liquidity',
    riskLevel: 'MEDIUM',
    holdTime: 'Usually exits within: 1-8 hours',
  },

  // ─── xSTOCK / PRESTOCK / INDEX (Status) ─────────────────────────────────
  xstock_intraday: {
    summary: 'Experimental TradFi preset. Latest run is profitable but sample size is still small.',
    optimal: 'Use only for manual experimentation while dataset depth is still growing.',
    risk: 'TradFi presets are excluded from auto-selection and may drift quickly.',
    params: 'SL 4% | TP 10% | Trail OFF (99) | TradFi experimental',
    bestFor: 'Advanced users validating TradFi behavior manually',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: TBD',
  },
  xstock_swing: {
    summary: 'Disabled: currently unprofitable in the latest run.',
    optimal: 'Do not use until retuned with better data quality and larger sample.',
    risk: 'Negative expectancy and low win rate. Disabled by default.',
    params: 'SL 4% | TP 10% | Trail OFF (99) | Disabled (losing)',
    bestFor: 'Not recommended',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: TBD',
  },
  prestock_speculative: {
    summary: 'Experimental TradFi preset with strong WR in a small sample.',
    optimal: 'Use only for controlled manual tests while data depth is expanded.',
    risk: 'Low trade count means high variance; excluded from auto-selection.',
    params: 'SL 4% | TP 10% | Trail OFF (99) | TradFi experimental',
    bestFor: 'Advanced users validating prestock behavior',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: TBD',
  },
  index_intraday: {
    summary: 'Experimental index preset with tiny sample size.',
    optimal: 'Only for manual testing while additional index history is collected.',
    risk: 'Too few trades for production confidence; excluded from auto-selection.',
    params: 'SL 4% | TP 10% | Trail OFF (99) | TradFi experimental',
    bestFor: 'Advanced users only',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: TBD',
  },
  index_leveraged: {
    summary: 'Experimental leveraged index preset with tiny sample size.',
    optimal: 'Manual testing only while dataset quality and size improve.',
    risk: 'Insufficient sample for production confidence; excluded from auto-selection.',
    params: 'SL 4% | TP 10% | Trail OFF (99) | TradFi experimental',
    bestFor: 'Advanced users only',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: TBD',
  },

  // ─── BAGS.FM ────────────────────────────────────────────────────────────
  bags_fresh_snipe: {
    summary: 'Experimental: fresh Bags launches with a wider TP.',
    optimal: 'Best right after launch when attention is high and volume is real.',
    risk: 'Small sample. Early launches still dump hard; keep sizing small.',
    params: 'SL 10% | TP 30% | Trail OFF (99) | Score 35+ | Age <48h',
    bestFor: 'Users who want early Bags opportunities with clear exits',
    riskLevel: 'MEDIUM',
    holdTime: 'Usually exits within: 30-180 minutes',
  },
  bags_momentum: {
    summary: 'Experimental: post-launch momentum on Bags.',
    optimal: 'Test when you see persistent bids and sustained momentum.',
    risk: 'Small sample and high variance. Excluded from auto-selection.',
    params: 'SL 10% | TP 30% | Trail OFF (99) | Score 30+ | Age <168h | Mom 5%+',
    bestFor: 'Power users experimenting with momentum on Bags',
    riskLevel: 'HIGH',
    holdTime: 'Usually exits within: 1-6 hours',
  },
  bags_value: {
    summary: 'Experimental: higher-quality Bags filter with tight risk and fast exits.',
    optimal: 'Best when scores are high and price action is stable enough for tight exits.',
    risk: 'Current sample is limited; keep this in experimental workflows.',
    params: 'SL 5% | TP 10% | Trail OFF (99) | Score 55+ | Age <720h',
    bestFor: 'Conservative Bags users optimizing for consistency',
    riskLevel: 'LOW',
    holdTime: 'Usually exits within: 30-120 minutes',
  },
  bags_dip_buyer: {
    summary: 'Dip-buy behavior on Bags with realistic exits.',
    optimal: 'Best after an initial dump when the token stabilizes and rebounds.',
    risk: 'Dip buys can keep dipping. Size down.',
    params: 'SL 8% | TP 25% | Trail OFF (99) | Score 25+ | Age <336h',
    bestFor: 'Contrarian Bags traders who buy rebounds',
    riskLevel: 'MEDIUM',
    holdTime: 'Usually exits within: 1-4 hours',
  },
  bags_bluechip: {
    summary: 'Higher-score “blue chip” Bags setups with tight exits.',
    optimal: 'Best when scores are high and price action isn’t chaotic.',
    risk: 'Tight SL can get wicked out; avoid entries during pure noise.',
    params: 'SL 5% | TP 9% | Trail OFF (99) | Score 60+ | Established',
    bestFor: 'Users who want the tightest, quality-first Bags approach',
    riskLevel: 'LOW',
    holdTime: 'Usually exits within: 30-90 minutes',
  },
  bags_conservative: {
    summary: 'Experimental conservative Bags setup focused on survival and repeatability.',
    optimal: 'Best when the feed is mixed and you want tighter drawdown control.',
    risk: 'Current sample is limited; keep this in experimental workflows.',
    params: 'SL 5% | TP 10% | Trail OFF (99) | Score 40+ | Age <336h',
    bestFor: 'Conservative users who want a smoother ride on Bags',
    riskLevel: 'LOW',
    holdTime: 'Usually exits within: 30-120 minutes',
  },
  bags_aggressive: {
    summary: 'Aggressive Bags configuration with a wider TP and moderate SL.',
    optimal: 'Best when Bags narratives are hot and follow-through is strong.',
    risk: 'Lower win rate; do not oversize.',
    params: 'SL 7% | TP 25% | Trail OFF (99) | Score 20+ | Age <336h',
    bestFor: 'Risk-tolerant Bags traders chasing bigger moves',
    riskLevel: 'HIGH',
    holdTime: 'Usually exits within: 1-6 hours',
  },
  bags_elite: {
    summary: 'Experimental elite Bags filter with very tight exits and strict scoring.',
    optimal: 'Best when only the highest-score tokens are worth touching.',
    risk: 'Small sample sizes can lie. Treat results as directional, not guaranteed.',
    params: 'SL 5% | TP 9% | Trail OFF (99) | Score 70+ | Age <336h',
    bestFor: 'Selective traders who only want top-score Bags projects',
    riskLevel: 'LOW',
    holdTime: 'Usually exits within: 30-90 minutes',
  },
};

const STRATEGY_SEED_STATUS = 'Status: Seed (R4 params, trailing disabled).';
for (const strategyId of Object.keys(STRATEGY_INFO)) {
  const info = STRATEGY_INFO[strategyId];
  if (!info.optimal.startsWith(STRATEGY_SEED_STATUS)) {
    info.optimal = `${STRATEGY_SEED_STATUS} ${info.optimal}`;
  }
}
