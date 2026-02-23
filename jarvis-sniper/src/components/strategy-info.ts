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
    summary: 'Experimental: mean-reversion dip-buy with wider TP. Currently losing in backtest.',
    optimal: 'Only worth testing when conditions are choppy and you expect sharp bounces.',
    risk: 'Losing in backtest at current friction assumptions. Excluded from auto-selection.',
    params: 'SL 10% | TP 25% | Trail OFF (99) | Liq $5K+ | Score 30+ | Age <200h',
    bestFor: 'Power users experimenting with dip-buy behavior',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: 1-8 hours',
  },
  hybrid_b: {
    summary: 'Experimental: hybrid dip entry. Currently losing in backtest.',
    optimal: 'Best tested during mean-reverting conditions (not straight-line pumps).',
    risk: 'Losing in backtest at current settings. Excluded from auto-selection.',
    params: 'SL 10% | TP 25% | Trail OFF (99) | Liq $5K+ | Score 30+ | Age <200h',
    bestFor: 'Power users testing alt entry behavior',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: 1-8 hours',
  },
  let_it_ride: {
    summary: 'Experimental: wider hold window. Currently losing in backtest.',
    optimal: 'Only worth testing when you expect longer bounces (not quick scalps).',
    risk: 'Losing in backtest at current settings. Excluded from auto-selection.',
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
    summary: 'Experimental: established volume surges. Currently losing in backtest.',
    optimal: 'Only worth testing when you trust the surge source (listing/news/rotation).',
    risk: 'Volume spikes can be exit liquidity. Losing in backtest; excluded from auto-selection.',
    params: 'SL 8% | TP 15% | Trail OFF (99) | Liq $20K+ | Score 35+ | V/L 0.3+ | Established',
    bestFor: 'Advanced users testing volume-surge behavior',
    riskLevel: 'HIGH',
    holdTime: 'Usually exits within: 1-8 hours',
  },
  established_breakout: {
    summary: 'Experimental: established breakout signals. Currently losing in backtest.',
    optimal: 'Best tested when the market is trending and breakouts actually follow through.',
    risk: 'Breakouts often fake out. Losing in backtest; excluded from auto-selection.',
    params: 'SL 8% | TP 15% | Trail OFF (99) | Liq $10K+ | Score 30+ | Established',
    bestFor: 'Breakout traders experimenting with established tokens',
    riskLevel: 'HIGH',
    holdTime: 'Usually exits within: 2-12 hours',
  },

  // ─── BLUE CHIP SOLANA ────────────────────────────────────────────────────
  bluechip_trend_follow: {
    summary: 'Higher-liquidity Solana blue chips with wider realistic exits.',
    optimal: 'Best when the broad market is trending and majors have clear continuation.',
    risk: 'Blue chips move slower than memes; expect fewer trades and longer holds.',
    params: 'SL 10% | TP 25% | Trail OFF (99) | Liq $200K+ | Score 55+ | Established',
    bestFor: 'Users who want less chaos and can hold longer',
    riskLevel: 'MEDIUM',
    holdTime: 'Usually exits within: 1-8 hours',
  },
  bluechip_breakout: {
    summary: 'Blue chip breakout catcher using the same realistic exit philosophy.',
    optimal: 'Best when majors compress and then expand with real volume follow-through.',
    risk: 'False breakouts happen. Don’t oversize.',
    params: 'SL 10% | TP 25% | Trail OFF (99) | Liq $200K+ | Score 65+ | Established',
    bestFor: 'Traders who like breakouts but want blue-chip liquidity',
    riskLevel: 'MEDIUM',
    holdTime: 'Usually exits within: 1-8 hours',
  },

  // ─── xSTOCK / PRESTOCK / INDEX (Status) ─────────────────────────────────
  xstock_intraday: {
    summary: 'Disabled: xStocks dataset/backtest is not production-valid yet.',
    optimal: 'We will re-enable after a real tokenized-equities candle dataset is wired into the backtest pipeline.',
    risk: 'Do not rely on the shown backtest stats for TradFi presets yet. This area is still being rebuilt.',
    params: 'SL 4% | TP 10% | Trail OFF (99) | (TradFi dataset pending)',
    bestFor: 'Not recommended until TradFi backtesting is fixed',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: TBD',
  },
  xstock_swing: {
    summary: 'Disabled: xStocks dataset/backtest is not production-valid yet.',
    optimal: 'Pending real xStocks candle ingestion and parameter retuning.',
    risk: 'TradFi presets are disabled until the data is correct.',
    params: 'SL 4% | TP 10% | Trail OFF (99) | (TradFi dataset pending)',
    bestFor: 'Not recommended until TradFi backtesting is fixed',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: TBD',
  },
  prestock_speculative: {
    summary: 'Disabled: prestock dataset/backtest is not production-valid yet.',
    optimal: 'Pending real prestock candle ingestion and parameter retuning.',
    risk: 'Disabled until data + scoring are verified end-to-end.',
    params: 'SL 4% | TP 10% | Trail OFF (99) | (TradFi dataset pending)',
    bestFor: 'Not recommended until TradFi backtesting is fixed',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: TBD',
  },
  index_intraday: {
    summary: 'Disabled: index dataset/backtest is not production-valid yet.',
    optimal: 'Pending real index-token candle ingestion and parameter retuning.',
    risk: 'Disabled until we have a real dataset and validated edge.',
    params: 'SL 4% | TP 10% | Trail OFF (99) | (TradFi dataset pending)',
    bestFor: 'Not recommended until TradFi backtesting is fixed',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: TBD',
  },
  index_leveraged: {
    summary: 'Disabled: leveraged index dataset/backtest is not production-valid yet.',
    optimal: 'Pending real leveraged-index candle ingestion and parameter retuning.',
    risk: 'Disabled until data is correct and edge is proven.',
    params: 'SL 4% | TP 10% | Trail OFF (99) | (TradFi dataset pending)',
    bestFor: 'Not recommended until TradFi backtesting is fixed',
    riskLevel: 'EXTREME',
    holdTime: 'Usually exits within: TBD',
  },

  // ─── BAGS.FM ────────────────────────────────────────────────────────────
  bags_fresh_snipe: {
    summary: 'Fresh Bags launches with a wider TP (Bags can move fast, but liquidity is structured).',
    optimal: 'Best right after launch when attention is high and volume is real.',
    risk: 'Early launches still dump. Keep sizing small.',
    params: 'SL 10% | TP 30% | Trail OFF (99) | Score 35+ | Age <48h',
    bestFor: 'Users who want early Bags opportunities with clear exits',
    riskLevel: 'MEDIUM',
    holdTime: 'Usually exits within: 30-180 minutes',
  },
  bags_momentum: {
    summary: 'Experimental: post-launch momentum on Bags. Currently losing in backtest.',
    optimal: 'Only worth testing when you see persistent bids and momentum is sustained.',
    risk: 'Borderline/losing in backtest at current settings. Excluded from auto-selection.',
    params: 'SL 10% | TP 30% | Trail OFF (99) | Score 30+ | Age <168h | Mom 5%+',
    bestFor: 'Power users experimenting with momentum on Bags',
    riskLevel: 'HIGH',
    holdTime: 'Usually exits within: 1-6 hours',
  },
  bags_value: {
    summary: 'Higher-quality Bags filter with tight risk and fast exits.',
    optimal: 'Best when scores are high and price action is stable enough for tight exits.',
    risk: 'Smaller TP means you need clean execution; don’t run on illiquid conditions.',
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
    summary: 'Conservative Bags setup focused on survival and repeatability.',
    optimal: 'Best when the feed is mixed and you want tighter control of drawdowns.',
    risk: 'Tight exits can reduce upside in strong trends.',
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
    summary: 'Elite Bags filter: very tight exits with strict scoring.',
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
