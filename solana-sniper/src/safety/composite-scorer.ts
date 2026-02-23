import { checkMintAuthority, scoreMintCheck } from './mint-checker.js';
import { analyzeLiquidity, scoreLpAnalysis } from './lp-analyzer.js';
import { analyzeHolders, scoreHolderAnalysis } from './holder-analyzer.js';
import { checkRugCheck, scoreRugCheck } from './rugcheck-client.js';
import { checkGoPlus, scoreGoPlus } from './goplus-client.js';
import { scanForRugDeployer, scoreRugDeployer } from './rug-deployer-scanner.js';
import { SAFETY_WEIGHTS, SAFETY_PASS_THRESHOLD } from '../config/constants.js';
import { createModuleLogger } from '../utils/logger.js';
import type { SafetyResult, TokenInfo } from '../types/index.js';

const log = createModuleLogger('safety');

export async function runSafetyPipeline(token: TokenInfo): Promise<SafetyResult> {
  const startTime = Date.now();
  const failReasons: string[] = [];

  log.info('Starting safety pipeline', { mint: token.mint.slice(0, 8), symbol: token.symbol });

  // Run all checks in parallel for speed
  const [mintCheck, rugCheck, goPlus, rugDeployer] = await Promise.all([
    checkMintAuthority(token.mint),
    checkRugCheck(token.mint),
    checkGoPlus(token.mint),
    scanForRugDeployer(token.mint),
  ]);

  // These are slower - run them but with timeout
  let lpAnalysis = null;
  let holderAnalysis = null;

  try {
    const [lp, holders] = await Promise.all([
      token.poolAddress ? analyzeLiquidity(token.poolAddress) : Promise.resolve(null),
      analyzeHolders(token.mint),
    ]);
    lpAnalysis = lp;
    holderAnalysis = holders;
  } catch (err) {
    log.warn('Secondary safety checks failed', { error: (err as Error).message });
  }

  // ─── HARD FAIL conditions (instant reject) ──────────────────
  if (goPlus.isHoneypot) {
    failReasons.push('HONEYPOT DETECTED BY GOPLUS');
  }
  if (goPlus.canTakeBackOwnership) {
    failReasons.push('Owner can reclaim token');
  }
  if (!mintCheck.mintAuthorityRevoked && mintCheck.mintAuthority !== 'UNKNOWN') {
    failReasons.push('Mint authority not revoked - infinite mint risk');
  }
  if (rugDeployer.isKnownRugger) {
    failReasons.push(`DEPLOYER IS KNOWN RUGGER (${rugDeployer.rugCount} rugs from ${rugDeployer.deployer?.slice(0, 8)})`);
  }

  // ─── Weighted scoring ───────────────────────────────────────
  const scores: Record<string, number> = {};

  // Mint authority (20%)
  scores.mintAuthority = scoreMintCheck(mintCheck) * (mintCheck.mintAuthorityRevoked ? 1 : 0);

  // Freeze authority (15%)
  scores.freezeAuthority = mintCheck.freezeAuthorityRevoked ? 1.0 : 0.0;

  // LP burned (20%)
  scores.lpBurned = lpAnalysis ? scoreLpAnalysis(lpAnalysis) : 0.5; // neutral if unknown

  // Holder concentration (15%)
  scores.holderConcentration = holderAnalysis ? scoreHolderAnalysis(holderAnalysis) : 0.5;

  // Honeypot / GoPlus (10%)
  scores.honeypot = scoreGoPlus(goPlus);

  // RugCheck (10% - combines liquidity + metadata + verification)
  scores.rugcheck = rugCheck ? scoreRugCheck(rugCheck) : 0.5;

  // Deployer history (10% - known rugger detection)
  scores.deployerHistory = scoreRugDeployer(rugDeployer);

  // Compute weighted overall score
  const overallScore =
    scores.mintAuthority * SAFETY_WEIGHTS.mintAuthority +
    scores.freezeAuthority * SAFETY_WEIGHTS.freezeAuthority +
    scores.lpBurned * SAFETY_WEIGHTS.lpBurned +
    scores.holderConcentration * SAFETY_WEIGHTS.holderConcentration +
    scores.honeypot * SAFETY_WEIGHTS.honeypot +
    scores.rugcheck * (SAFETY_WEIGHTS.metadataImmutable + SAFETY_WEIGHTS.jupiterVerified + SAFETY_WEIGHTS.liquidity) +
    scores.deployerHistory * SAFETY_WEIGHTS.deployerHistory;

  // Additional fail reasons based on scores
  if (overallScore < SAFETY_PASS_THRESHOLD && failReasons.length === 0) {
    failReasons.push(`Safety score ${(overallScore * 100).toFixed(0)}% below threshold ${(SAFETY_PASS_THRESHOLD * 100).toFixed(0)}%`);
  }
  if (holderAnalysis && holderAnalysis.top10ConcentrationPct > 80) {
    failReasons.push(`Top 10 holders control ${holderAnalysis.top10ConcentrationPct.toFixed(0)}% of supply`);
  }

  const passed = failReasons.length === 0 && overallScore >= SAFETY_PASS_THRESHOLD;
  const elapsed = Date.now() - startTime;

  const result: SafetyResult = {
    mint: token.mint,
    overallScore,
    passed,
    mintCheck,
    lpAnalysis,
    holderAnalysis,
    rugCheck,
    goPlus,
    failReasons,
    checkedAt: Date.now(),
  };

  log.info('Safety pipeline complete', {
    mint: token.mint.slice(0, 8),
    score: (overallScore * 100).toFixed(0) + '%',
    passed,
    failReasons: failReasons.length,
    elapsed: elapsed + 'ms',
    scores: Object.fromEntries(Object.entries(scores).map(([k, v]) => [k, (v * 100).toFixed(0) + '%'])),
  });

  return result;
}
