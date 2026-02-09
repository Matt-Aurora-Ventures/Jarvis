/** Rich strategy descriptions shown in the breakdown panel */
export const STRATEGY_INFO: Record<string, { summary: string; optimal: string; risk: string; params: string }> = {
  momentum: {
    summary: 'Targets high-conviction tokens with strong volume activity and decent scores. Casts a wider net with no liquidity floor.',
    optimal: 'Best in active markets with many new graduates. High volume-to-liquidity ratios signal organic demand, not wash trading.',
    risk: 'No minimum liquidity means higher slippage risk on entry/exit. Use smaller position sizes.',
    params: 'SL 20% | TP 60% | Trail 8% | Score 50+ | Vol/Liq 3+',
  },
  insight_j: {
    summary: 'Strict quality filter requiring $25K+ liquidity, young tokens (<100h), and positive momentum. High selectivity = fewer but better trades.',
    optimal: 'Works best when you want quality over quantity. The 86% win rate comes from only touching tokens with real market depth.',
    risk: 'Very selective — may go long periods without a trade. Requires patience for the right setup.',
    params: 'SL 20% | TP 60% | Trail 8% | Liq $25K+ | Age <100h',
  },
  hot: {
    summary: 'Balanced approach: requires both a minimum score (60+) and liquidity ($10K+). Generates the most trades of any strategy.',
    optimal: 'Ideal for active trading sessions. More opportunities but a wider spread of outcomes. Volume-weighted for real activity.',
    risk: 'Lower win rate (49%) means you need discipline with stop losses. The volume of trades smooths returns over time.',
    params: 'SL 20% | TP 60% | Trail 8% | Score 60+ | Liq $10K+',
  },
  hybrid_b: {
    summary: 'The battle-tested default. Combines all HYBRID-B insight filters with a $40K liquidity floor. 100% WR in OHLCV validation.',
    optimal: 'The go-to for most sessions. Strong enough filters to avoid rugs, loose enough to still find trades regularly.',
    risk: 'Small sample size (10 trades in backtest). Performance may regress to mean, but the filter logic is sound.',
    params: 'SL 20% | TP 60% | Trail 8% | Liq $40K+ | All filters on',
  },
  let_it_ride: {
    summary: 'Aggressive mode with 100% take-profit and tight 5% trailing stop. Designed to capture large moves while protecting gains.',
    optimal: 'Perfect for bull markets or when scanning shows strong momentum. The tight trail locks in gains on any pullback.',
    risk: 'The 5% trail means early exits on normal volatility. Best when conviction is very high on a specific token.',
    params: 'SL 20% | TP 100% | Trail 5% | Liq $40K+ | Aggressive mode',
  },
  insight_i: {
    summary: 'The strictest preset: $50K liquidity, age under 200h, and B/S ratio in the 1-3 sweet spot. Maximum quality filter.',
    optimal: 'When you want to be extremely selective. Only trades tokens with institutional-grade liquidity and balanced order flow.',
    risk: 'Very few tokens pass all gates. You may see 0 trades for hours. Best combined with patience and larger position sizes.',
    params: 'SL 20% | TP 60% | Trail 8% | Liq $50K+ | B/S 1-3 | Age <200h',
  },
  pump_fresh_tight: {
    summary: 'Targets freshly graduated pumpswap tokens (<24h old). The v4 backtest champion with 88.2% win rate on 17 trades.',
    optimal: 'Best when pumpswap is actively graduating tokens. Fresh tokens have highest alpha before price discovery settles.',
    risk: 'Small sample (17 trades). Requires active pumpswap graduation flow. Dead hours = no trades.',
    params: 'SL 20% | TP 80% | Trail 8% | Liq $5K+ | Score 40+ | Age <24h',
  },
  micro_cap_surge: {
    summary: 'Targets micro-cap tokens with volume surges (3x Vol/Liq). Wide 45% SL and 250% TP for maximum expected value on small caps.',
    optimal: 'When micro-caps are surging and you want outsized returns. The volume filter ensures real buying pressure.',
    risk: 'Wide SL means large individual losses. High TP means many trades will stop out before reaching target. Needs strong stomach.',
    params: 'SL 45% | TP 250% | Trail 20% | Liq $3K+ | Score 30+ | Age <24h',
  },
  elite: {
    summary: 'The strictest automated filter: $100K+ liquidity, Vol/Liq >= 2, age < 100h, 10%+ momentum, and trading hours gate.',
    optimal: 'When you want maximum selectivity with proven hours. Only fires on the highest-conviction setups.',
    risk: 'Extremely selective. May not find any trades for extended periods. Requires patience.',
    params: 'SL 15% | TP 60% | Trail 8% | Liq $100K+ | V/L 2+ | Mom 10%+ | Hours Gate',
  },
  loose: {
    summary: 'The original wide-net strategy. Low liquidity floor ($25K), no momentum requirement, no hours gate. Catches everything.',
    optimal: 'When you want maximum trade volume. Good for data collection and understanding market flow.',
    risk: '49% win rate means nearly half of trades lose. The volume of trades is the edge, not individual conviction.',
    params: 'SL 20% | TP 60% | Trail 8% | Liq $25K+ | No gates',
  },
  genetic_best: {
    summary: 'Genetic algorithm optimized over 277 tokens. Wide SL (35%) and very high TP (200%) with 12% trail. Targets fresh micro-caps.',
    optimal: 'When fresh tokens are graduating with strong initial momentum. The GA optimizer found this as the highest EV config.',
    risk: 'Wide SL means significant per-trade risk. Requires strong conviction sizing and mental fortitude.',
    params: 'SL 35% | TP 200% | Trail 12% | Liq $3K+ | Score 43+ | Age <24h',
  },
  genetic_v2: {
    summary: 'Genetic algorithm v2 optimized over 277 tokens. Uses volume surge detection (2.5x min) with wide 45% SL and 207% TP for maximum expected value on memecoins.',
    optimal: 'When market is volatile and you want to catch big moves. The wide SL gives tokens room to breathe while the 207% TP captures massive runs.',
    risk: 'Wide SL (45%) means each loss is significant. Requires strong conviction sizing. Best with smaller position sizes.',
    params: 'SL 45% | TP 207% | Trail 10% | Liq $5K+ | Vol Surge 2.5x',
  },
  xstock_momentum: {
    summary: 'Designed for xStocks (tokenized stock proxies). Very tight exits since these track equities with lower vol than memecoins.',
    optimal: 'During US market hours (9:30am-4pm ET). xStocks follow equity market movements.',
    risk: 'Tight 3% SL means quick stops on normal volatility. Only use on confirmed xStock tokens.',
    params: 'SL 3% | TP 8% | Trail 2% | Liq $10K+',
  },
  prestock_speculative: {
    summary: 'Pre-IPO tokens have high reward potential but speculative nature. Wider risk tolerance with 50% TP target.',
    optimal: 'When pre-IPO hype is building. These tokens can move 50%+ on sentiment alone.',
    risk: 'Pre-IPO tokens are highly speculative. 15% SL provides buffer but losses can be sharp.',
    params: 'SL 15% | TP 50% | Trail 8% | Liq $5K+',
  },
  index_revert: {
    summary: 'Solana index tokens (SOL baskets, sector indexes) tend to mean-revert. Tight SL/TP captures small moves with high frequency.',
    optimal: 'When indexes are oscillating in a range. Mean reversion works best in sideways markets.',
    risk: 'Very tight 2% SL means many small losses in trending markets. Not for breakout conditions.',
    params: 'SL 2% | TP 5% | Trail 1.5% | Liq $20K+',
  },
};
