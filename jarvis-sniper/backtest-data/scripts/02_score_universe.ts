/**
 * Phase 2: Score Universe
 * 
 * Computes a local score (0-100) for every token in the universe,
 * matching the live system's scoring logic:
 *   1. Bonding Curve Quality (~25 pts)
 *   2. Holder Distribution (~25 pts)
 *   3. Social Presence (~25 pts)
 *   4. Liquidity (~25 pts)
 *   5. Interest / Source Confirmation (0-100, blended into final score)
 * 
 * Input:  universe/universe_raw.json
 * Output: universe/universe_scored.json, universe/universe_scored.csv
 * 
 * Run: npx tsx backtest-data/scripts/02_score_universe.ts
 */

import { log, logError, readJSON, writeJSON, writeCSV, dataPath } from './shared/utils';
import type { TokenRecord, ScoredToken } from './shared/types';

// ─── Score Component Calculators ───

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n));
}

function scoreBondingCurve(token: TokenRecord): number {
  let score = 0;

  // Duration on bonding curve (higher age = more mature = better, up to a point)
  const ageHours = token.creation_timestamp > 0
    ? (Date.now() / 1000 - token.creation_timestamp) / 3600
    : 0;
  if (ageHours > 0) {
    if (ageHours < 1) score += 2;       // very fresh
    else if (ageHours < 6) score += 4;
    else if (ageHours < 24) score += 6;
    else if (ageHours < 72) score += 7;
    else score += 5;                     // diminishing returns for very old
  }

  // Volume during bonding (higher volume = more interest)
  const vol = token.volume_24h_usd;
  if (vol > 500_000) score += 7;
  else if (vol > 100_000) score += 6;
  else if (vol > 50_000) score += 5;
  else if (vol > 10_000) score += 4;
  else if (vol > 1_000) score += 2;
  else score += 1;

  // Buyer count
  const buys = token.buy_txn_count_24h;
  if (buys > 1000) score += 6;
  else if (buys > 500) score += 5;
  else if (buys > 100) score += 4;
  else if (buys > 30) score += 3;
  else if (buys > 5) score += 2;
  else score += 0;

  // Buy/sell ratio
  const sells = token.sell_txn_count_24h || 1;
  const ratio = buys / sells;
  if (ratio > 3) score += 5;
  else if (ratio > 2) score += 4;
  else if (ratio > 1.2) score += 3;
  else if (ratio > 0.8) score += 2;
  else score += 1;

  return Math.min(25, score);
}

function scoreHolderDistribution(token: TokenRecord): number {
  let score = 0;

  // Total holder count
  const holders = token.holder_count;
  if (holders > 5000) score += 15;
  else if (holders > 1000) score += 12;
  else if (holders > 500) score += 10;
  else if (holders > 100) score += 7;
  else if (holders > 30) score += 5;
  else if (holders > 10) score += 3;
  else if (holders > 0) score += 1;
  else {
    // No holder data — estimate from buy/sell txn counts
    const totalTxns = token.buy_txn_count_24h + token.sell_txn_count_24h;
    if (totalTxns > 2000) score += 10;
    else if (totalTxns > 500) score += 7;
    else if (totalTxns > 100) score += 5;
    else if (totalTxns > 20) score += 3;
    else score += 1;
  }

  // Concentration proxy: buy/sell balance suggests distribution
  // Higher buy diversity (more buys relative to total) suggests less concentration
  const total = token.buy_txn_count_24h + token.sell_txn_count_24h;
  if (total > 0) {
    const buyPct = token.buy_txn_count_24h / total;
    if (buyPct > 0.4 && buyPct < 0.7) score += 10; // healthy distribution
    else if (buyPct > 0.3 && buyPct < 0.8) score += 7;
    else score += 3;
  }

  return Math.min(25, score);
}

function scoreSocialPresence(token: TokenRecord): number {
  let score = 0;
  if (token.has_twitter) score += 8;
  if (token.has_website) score += 8;
  if (token.has_telegram) score += 9;
  return Math.min(25, score);
}

function scoreLiquidity(token: TokenRecord): number {
  const liq = token.liquidity_usd;

  // For bags.fm tokens (liquidity is always 0 by design — locked liquidity)
  // We detect bags tokens by having 0 liquidity but active trading
  if (liq === 0 && token.volume_24h_usd > 0 && token.buy_txn_count_24h > 0) {
    return 25; // bags.fm — always max liquidity score
  }

  // Map liquidity to 0-25 scale
  if (liq >= 500_000) return 25;
  if (liq >= 200_000) return 22;
  if (liq >= 100_000) return 19;
  if (liq >= 50_000) return 16;
  if (liq >= 25_000) return 13;
  if (liq >= 10_000) return 10;
  if (liq >= 5_000) return 7;
  if (liq >= 1_000) return 4;
  if (liq > 0) return 2;
  return 0;
}

function scoreInterest(token: TokenRecord): number {
  let score = 0;

  const txns = (token.buy_txn_count_24h || 0) + (token.sell_txn_count_24h || 0);
  if (txns > 5000) score += 30;
  else if (txns > 2000) score += 25;
  else if (txns > 1000) score += 21;
  else if (txns > 500) score += 16;
  else if (txns > 100) score += 10;
  else if (txns > 20) score += 6;
  else if (txns > 0) score += 3;

  const liq = token.liquidity_usd || 0;
  const vol = token.volume_24h_usd || 0;
  const volLiq = liq > 0 ? vol / liq : (vol > 0 ? 2 : 0);
  if (volLiq > 5) score += 22;
  else if (volLiq > 3) score += 18;
  else if (volLiq > 1.5) score += 13;
  else if (volLiq > 0.8) score += 9;
  else if (volLiq > 0.3) score += 5;
  else if (volLiq > 0) score += 2;

  const absMove = Math.abs(token.price_change_1h || 0);
  if (absMove > 25) score += 12;
  else if (absMove > 15) score += 9;
  else if (absMove > 8) score += 6;
  else if (absMove > 3) score += 3;

  const sourceCount = token.source_count || 1;
  if (sourceCount >= 4) score += 18;
  else if (sourceCount === 3) score += 14;
  else if (sourceCount === 2) score += 9;
  else score += 3;

  if (token.interest_is_boosted) score += 9;
  if (token.interest_is_trending) score += 9;

  return clamp(Math.round(score), 0, 100);
}

function scoreToken(token: TokenRecord): ScoredToken {
  const score_bonding = scoreBondingCurve(token);
  const score_holders = scoreHolderDistribution(token);
  const score_social = scoreSocialPresence(token);
  const score_liquidity = scoreLiquidity(token);
  const score_core = score_bonding + score_holders + score_social + score_liquidity;
  const score_interest = scoreInterest(token);
  const score = Math.round((score_core * 0.75) + (score_interest * 0.25));

  return {
    ...token,
    score,
    score_interest,
    score_bonding,
    score_holders,
    score_social,
    score_liquidity,
  };
}

// ─── Main ───

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 2: Score Universe');
  log('═══════════════════════════════════════════════════════');

  const universe = readJSON<TokenRecord[]>('universe/universe_raw.json');
  if (!universe || universe.length === 0) {
    logError('No universe data found. Run 01_discover_universe.ts first.');
    process.exit(1);
  }

  log(`Scoring ${universe.length} tokens...`);

  const scored: ScoredToken[] = universe.map(scoreToken);

  // Stats
  const tiers = {
    exceptional: scored.filter(t => t.score >= 80).length,
    strong: scored.filter(t => t.score >= 65 && t.score < 80).length,
    average: scored.filter(t => t.score >= 50 && t.score < 65).length,
    weak: scored.filter(t => t.score >= 35 && t.score < 50).length,
    poor: scored.filter(t => t.score < 35).length,
  };

  log('');
  log('Score Distribution:');
  log(`  Exceptional (80+): ${tiers.exceptional} (${(tiers.exceptional / scored.length * 100).toFixed(1)}%)`);
  log(`  Strong (65-79):    ${tiers.strong} (${(tiers.strong / scored.length * 100).toFixed(1)}%)`);
  log(`  Average (50-64):   ${tiers.average} (${(tiers.average / scored.length * 100).toFixed(1)}%)`);
  log(`  Weak (35-49):      ${tiers.weak} (${(tiers.weak / scored.length * 100).toFixed(1)}%)`);
  log(`  Poor (<35):        ${tiers.poor} (${(tiers.poor / scored.length * 100).toFixed(1)}%)`);
  log('');

  const avgScore = scored.reduce((s, t) => s + t.score, 0) / scored.length;
  log(`Average score: ${avgScore.toFixed(1)}`);
  log(`Median score: ${scored.sort((a, b) => a.score - b.score)[Math.floor(scored.length / 2)].score}`);

  // Component averages
  const avgBonding = scored.reduce((s, t) => s + t.score_bonding, 0) / scored.length;
  const avgHolders = scored.reduce((s, t) => s + t.score_holders, 0) / scored.length;
  const avgSocial = scored.reduce((s, t) => s + t.score_social, 0) / scored.length;
  const avgLiquidity = scored.reduce((s, t) => s + t.score_liquidity, 0) / scored.length;
  const avgInterest = scored.reduce((s, t) => s + t.score_interest, 0) / scored.length;
  const sourceConfirmed = scored.filter(t => (t.source_count || 1) >= 2).length;
  const withTrend = scored.filter(t => t.interest_is_trending).length;
  const withBoost = scored.filter(t => t.interest_is_boosted).length;
  log(`  Bonding avg:   ${avgBonding.toFixed(1)}/25`);
  log(`  Holders avg:   ${avgHolders.toFixed(1)}/25`);
  log(`  Social avg:    ${avgSocial.toFixed(1)}/25`);
  log(`  Liquidity avg: ${avgLiquidity.toFixed(1)}/25`);
  log(`  Interest avg:  ${avgInterest.toFixed(1)}/100`);
  log(`  Multi-source (>=2): ${sourceConfirmed}`);
  log(`  Trending signal: ${withTrend}`);
  log(`  Boost signal: ${withBoost}`);

  // Sort by score descending for output
  scored.sort((a, b) => b.score - a.score);

  writeJSON('universe/universe_scored.json', scored);
  writeCSV('universe/universe_scored.csv', scored as unknown as Record<string, unknown>[]);

  log(`\n✓ Phase 2 complete: ${scored.length} tokens scored`);
  log(`  → universe/universe_scored.json`);
  log(`  → universe/universe_scored.csv`);
}

main().catch(err => {
  logError('Fatal error in scoring', err);
  process.exit(1);
});
