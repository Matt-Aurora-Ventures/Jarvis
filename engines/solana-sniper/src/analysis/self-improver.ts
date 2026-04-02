import { runEnhancedBacktest, fetchBacktestData, type EnhancedBacktestConfig, type EnhancedBacktestResult, type PumpFunHistoricalToken } from './historical-data.js';
import { getDb } from '../utils/database.js';
import { createModuleLogger } from '../utils/logger.js';
import fs from 'fs';
import path from 'path';

const log = createModuleLogger('self-improver');

interface OptimizationResult {
  bestConfig: Partial<EnhancedBacktestConfig>;
  bestWinRate: number;
  bestPnl: number;
  bestSharpe: number;
  iterations: number;
  // Walk-forward validation results (test set performance)
  validationWinRate?: number;
  validationPnl?: number;
  validationSharpe?: number;
  allResults: Array<{
    config: Partial<EnhancedBacktestConfig>;
    winRate: number;
    pnl: number;
    sharpe: number;
    profitFactor: number;
    score: number;
  }>;
}

// ─── Genetic Algorithm-inspired optimizer ────────────────────
export async function runSelfImprovement(
  generations: number = 5,
  populationSize: number = 20,
  deepMode: boolean = false,
): Promise<OptimizationResult> {
  // Deep mode: more thorough search (8 generations, 30 population)
  if (deepMode) {
    generations = 8;
    populationSize = 30;
  }
  log.info('Starting self-improvement cycle', { generations, populationSize });

  const allResults: OptimizationResult['allResults'] = [];

  // Load previous best from DB if exists
  const previousBest = loadBestConfig();

  // Generate initial population — biased toward v1 backtest winning ranges
  // 60% biased toward known winners, 40% random for diversity
  let population = generateBiasedPopulation(populationSize, previousBest);

  for (let gen = 0; gen < generations; gen++) {
    log.info(`Generation ${gen + 1}/${generations}`);

    // Fetch data ONCE per generation — all configs reuse this data
    const cachedData = await fetchBacktestData(deepMode ? 5000 : 2000, deepMode);
    log.info(`Fetched ${cachedData.length} tokens for generation ${gen + 1}`);

    const scored: Array<{ config: Partial<EnhancedBacktestConfig>; result: EnhancedBacktestResult; score: number }> = [];

    for (const config of population) {
      try {
        const result = await runEnhancedBacktest({ ...config, useOhlcv: false }, cachedData);

        // Multi-objective scoring
        const score = computeFitnessScore(result);

        scored.push({ config, result, score });
        allResults.push({
          config,
          winRate: result.winRate,
          pnl: result.totalPnlUsd,
          sharpe: result.sharpeRatio,
          profitFactor: result.profitFactor,
          score,
        });
      } catch (err) {
        log.warn('Backtest failed for config', { error: (err as Error).message });
      }
    }

    // Sort by score (higher = better)
    scored.sort((a, b) => b.score - a.score);

    // Log generation results
    if (scored.length > 0) {
      const best = scored[0];
      log.info(`Gen ${gen + 1} best`, {
        winRate: (best.result.winRate * 100).toFixed(1) + '%',
        pnl: '$' + best.result.totalPnlUsd.toFixed(2),
        sharpe: best.result.sharpeRatio.toFixed(2),
        score: best.score.toFixed(3),
        config: JSON.stringify(best.config),
      });
    }

    // Evolve: top 30% survive + mutations + crossovers
    const survivors = scored.slice(0, Math.ceil(scored.length * 0.3));
    population = evolvePopulation(survivors.map(s => s.config), populationSize);
  }

  // Sort all results
  allResults.sort((a, b) => b.score - a.score);

  const best = allResults[0];
  let validationWinRate: number | undefined;
  let validationPnl: number | undefined;
  let validationSharpe: number | undefined;

  if (best) {
    // ── Walk-forward validation ────────────────────────────────
    // Fetch fresh data and split into train/test to detect overfitting.
    // The optimizer trained on whatever data was cached; now we validate
    // against a held-out subset of the full dataset.
    try {
      const fullData = await fetchBacktestData(1000);
      if (fullData.length >= 10) {
        // Shuffle deterministically based on token addresses
        const shuffled = [...fullData].sort((a, b) =>
          a.mint.localeCompare(b.mint)
        );
        const splitIdx = Math.floor(shuffled.length * 0.7);
        const testSet = shuffled.slice(splitIdx);

        if (testSet.length >= 5) {
          const valResult = await runEnhancedBacktest({ ...best.config, useOhlcv: false }, testSet);
          validationWinRate = valResult.winRate;
          validationPnl = valResult.totalPnlUsd;
          validationSharpe = valResult.sharpeRatio;

          const overfit = best.winRate > 0 && validationWinRate < best.winRate * 0.5;
          log.info('Walk-forward validation', {
            trainWR: (best.winRate * 100).toFixed(1) + '%',
            testWR: (validationWinRate * 100).toFixed(1) + '%',
            trainPnl: '$' + best.pnl.toFixed(2),
            testPnl: '$' + validationPnl.toFixed(2),
            testTokens: testSet.length,
            overfit: overfit ? 'YES - possible overfit' : 'NO',
          });
        }
      }
    } catch (err) {
      log.warn('Walk-forward validation failed', { error: (err as Error).message });
    }

    // Save best config
    saveBestConfig(best.config, best.winRate, best.pnl, best.sharpe);

    // Write to winning folder
    writeImprovementLog(allResults);
  }

  const result: OptimizationResult = {
    bestConfig: best?.config ?? {},
    bestWinRate: best?.winRate ?? 0,
    bestPnl: best?.pnl ?? 0,
    bestSharpe: best?.sharpe ?? 0,
    iterations: allResults.length,
    validationWinRate,
    validationPnl,
    validationSharpe,
    allResults,
  };

  log.info('Self-improvement complete', {
    iterations: result.iterations,
    bestWinRate: (result.bestWinRate * 100).toFixed(1) + '%',
    bestPnl: '$' + result.bestPnl.toFixed(2),
    bestSharpe: result.bestSharpe.toFixed(2),
    validationWR: validationWinRate != null ? (validationWinRate * 100).toFixed(1) + '%' : 'N/A',
    validationPnl: validationPnl != null ? '$' + validationPnl.toFixed(2) : 'N/A',
  });

  return result;
}

export function computeFitnessScore(result: EnhancedBacktestResult): number {
  // Zero trades = useless config
  if (result.totalTrades === 0) return 0.01;

  // With 5000+ token pool, require more trades for significance
  // 1 trade = 0.10x, 3 = 0.10x, 10 = 0.33x, 20 = 0.67x, 30+ = 1.0x
  const tradeSignificance = Math.min(1.0, Math.max(0.10, result.totalTrades / 30));

  // Multi-objective scoring components
  const wrScore = result.winRate; // 0-1
  const pnlScore = Math.min(1, Math.max(-1, result.totalPnlPct / 100));
  const sharpeScore = Math.min(1, Math.max(0, result.sharpeRatio / 3));
  const ddPenalty = Math.min(1, result.maxDrawdownPct / 50);
  const rugAvoidScore = result.rugsAvoided / Math.max(1, result.rugsAvoided + result.rugsHit);
  const pfScore = Math.min(1, Math.max(0, (result.profitFactor - 1) / 5));

  // Volume bonus: more trades = more confident (up to 0.15 bonus)
  const volumeBonus = Math.min(0.15, result.totalTrades / 30 * 0.15);

  // Diversity bonus: configs that can trade multiple token categories get a bonus
  // (prevents overfitting to just one niche)
  const sources = new Set(result.trades.map(t => t.source));
  const diversityBonus = Math.min(0.10, sources.size * 0.03);

  // Raw quality score (win rate still heavily weighted)
  const rawScore =
    wrScore * 0.30 +
    pnlScore * 0.20 +
    sharpeScore * 0.12 +
    (1 - ddPenalty) * 0.08 +
    rugAvoidScore * 0.08 +
    pfScore * 0.07 +
    volumeBonus +
    diversityBonus;

  // Apply significance multiplier — 1-trade 100% WR: 0.85 * 0.10 = 0.085
  // vs 20-trade 65% WR w/ $7 PnL: 0.60 * 0.67 = 0.402
  return rawScore * tradeSignificance;
}

function generatePopulation(
  size: number,
  seed?: Partial<EnhancedBacktestConfig> | null,
): Array<Partial<EnhancedBacktestConfig>> {
  const population: Array<Partial<EnhancedBacktestConfig>> = [];

  // Include seed if available
  if (seed) population.push(seed);

  // Generate random configs — wide search space
  while (population.length < size) {
    population.push({
      stopLossPct: pick([5, 8, 10, 12, 15, 20, 25, 30, 35, 40, 50]),
      takeProfitPct: pick([25, 30, 40, 45, 50, 75, 100, 125, 150, 200, 300, 500]),
      trailingStopPct: pick([5, 10, 12, 15, 20, 25, 30]),
      minLiquidityUsd: pick([1000, 3000, 5000, 10000, 15000, 25000, 50000]),
      minBuySellRatio: pick([0.0, 0.3, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0]),
      safetyScoreMin: pick([0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7, 0.8]),
      maxConcurrentPositions: pick([2, 3, 4, 5, 8, 10]),
      maxPositionUsd: pick([0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0]),
      partialExitPct: pick([25, 33, 40, 50, 60, 75]),
      source: pick(['all', 'pumpfun', 'raydium', 'pumpswap'] as const),
      // Age-based filtering
      minTokenAgeHours: pick([0, 1, 6, 24, 168, 720]),  // 0=any, 1h, 6h, 1d, 7d, 30d
      maxTokenAgeHours: pick([0, 24, 168, 720, 2160, 5000]),  // 0=no max
      ageCategory: pick(['all', 'fresh', 'young', 'established', 'veteran'] as const),
      // Volume surge
      requireVolumeSurge: pick([true, false, false]),  // 33% chance of requiring surge
      minVolumeSurgeRatio: pick([0, 1.5, 2.0, 3.0, 5.0]),
      // Asset type
      assetType: pick(['all', 'memecoin', 'xstock', 'bluechip'] as const),
      // Adaptive exits
      adaptiveExits: pick([true, false]),
      // Macro regime filter
      macroRegime: pick(['all', 'risk_on', 'risk_off', 'neutral'] as const),
    } as Partial<EnhancedBacktestConfig>);
  }

  return population;
}

// ─── Biased population from v1 massive backtest findings ─────
// Encodes discovered winning parameter ranges so the optimizer
// starts closer to known good regions while retaining diversity.
export function generateBiasedPopulation(
  size: number,
  seed?: Partial<EnhancedBacktestConfig> | null,
): Array<Partial<EnhancedBacktestConfig>> {
  const population: Array<Partial<EnhancedBacktestConfig>> = [];

  // Include seed if available
  if (seed) population.push(seed);

  // Inject known winners as explicit starting points
  // DEGEN x volume_surge combo (47.1% WR in v1)
  population.push({
    stopLossPct: 35, takeProfitPct: 150, trailingStopPct: 15,
    minLiquidityUsd: 5000, safetyScoreMin: 0.40,
    requireVolumeSurge: true, minVolumeSurgeRatio: 2.5,
    source: 'all', ageCategory: 'all', adaptiveExits: false,
    maxConcurrentPositions: 5, maxPositionUsd: 2.5, partialExitPct: 50,
    minBuySellRatio: 0.0, minTokenAgeHours: 0, maxTokenAgeHours: 2160,
    assetType: 'memecoin',
  } as Partial<EnhancedBacktestConfig>);

  // Pumpswap momentum combo (24% WR in v1)
  population.push({
    stopLossPct: 30, takeProfitPct: 120, trailingStopPct: 12,
    minLiquidityUsd: 10000, safetyScoreMin: 0.45,
    source: 'pumpswap', ageCategory: 'all', adaptiveExits: false,
    maxConcurrentPositions: 5, maxPositionUsd: 2.5, partialExitPct: 50,
    requireVolumeSurge: false, minVolumeSurgeRatio: 0,
    minBuySellRatio: 0.0, minTokenAgeHours: 0, maxTokenAgeHours: 2160,
    assetType: 'all',
  } as Partial<EnhancedBacktestConfig>);

  // Established + momentum combo (28.6% WR)
  population.push({
    stopLossPct: 20, takeProfitPct: 75, trailingStopPct: 10,
    minLiquidityUsd: 25000, safetyScoreMin: 0.50,
    ageCategory: 'established', adaptiveExits: true,
    maxConcurrentPositions: 4, maxPositionUsd: 3.0, partialExitPct: 50,
    source: 'all', requireVolumeSurge: false, minVolumeSurgeRatio: 0,
    minBuySellRatio: 0.5, minTokenAgeHours: 168, maxTokenAgeHours: 2160,
    assetType: 'all',
  } as Partial<EnhancedBacktestConfig>);

  // Fill remaining with biased random (favor winning ranges from v1 findings)
  while (population.length < size) {
    population.push({
      stopLossPct: pick([20, 25, 30, 35, 40, 45]),              // bias toward 25-40
      takeProfitPct: pick([75, 100, 120, 150, 175, 200]),        // bias toward 100-200
      trailingStopPct: pick([8, 10, 12, 15, 18, 20]),            // bias toward 12-18
      minLiquidityUsd: pick([3000, 5000, 8000, 10000, 15000, 25000]), // bias toward 5K-25K
      minBuySellRatio: pick([0.0, 0.0, 0.3, 0.5, 0.8]),         // bias toward 0 (disabled)
      safetyScoreMin: pick([0.30, 0.35, 0.40, 0.45, 0.50]),     // bias toward 0.35-0.50
      maxConcurrentPositions: pick([3, 4, 5, 6, 8]),
      maxPositionUsd: pick([1.5, 2.0, 2.5, 3.0, 4.0]),
      partialExitPct: pick([33, 40, 50, 60]),
      source: pick(['all', 'all', 'pumpswap', 'pumpswap'] as const),  // 50% pumpswap bias
      minTokenAgeHours: pick([0, 0, 0, 24, 168]),               // mostly no min
      maxTokenAgeHours: pick([0, 720, 2160, 2160]),              // mostly exclude super-old veterans
      ageCategory: pick(['all', 'all', 'fresh', 'young', 'established'] as const), // never 'veteran' alone
      requireVolumeSurge: pick([true, true, false, false, false]), // 40% chance
      minVolumeSurgeRatio: pick([0, 1.5, 2.0, 2.5, 3.0]),
      assetType: pick(['all', 'all', 'memecoin'] as const),     // skip xstock/bluechip most of the time
      adaptiveExits: pick([true, false, false]),                 // bias toward fixed exits
      macroRegime: pick(['all', 'all', 'all', 'risk_on'] as const), // mostly 'all'
    } as Partial<EnhancedBacktestConfig>);
  }

  return population;
}

function evolvePopulation(
  survivors: Array<Partial<EnhancedBacktestConfig>>,
  targetSize: number,
): Array<Partial<EnhancedBacktestConfig>> {
  const newPop: Array<Partial<EnhancedBacktestConfig>> = [...survivors];

  while (newPop.length < targetSize) {
    // 30% crossover, 50% mutation, 20% fresh random
    const roll = Math.random();

    if (roll < 0.3 && survivors.length >= 2) {
      // Crossover: mix two parents
      const p1 = survivors[Math.floor(Math.random() * survivors.length)];
      const p2 = survivors[Math.floor(Math.random() * survivors.length)];
      const child: Partial<EnhancedBacktestConfig> = {};
      const keys = Object.keys(p1) as Array<keyof EnhancedBacktestConfig>;
      for (const k of keys) {
        (child as Record<string, unknown>)[k] = Math.random() < 0.5
          ? (p1 as Record<string, unknown>)[k]
          : (p2 as Record<string, unknown>)[k];
      }
      newPop.push(child);
    } else if (roll < 0.8) {
      // Mutation: tweak parent parameters
      const parent = survivors[Math.floor(Math.random() * survivors.length)];
      const mutated = { ...parent };
      const mutations: Array<() => void> = [
        () => { mutated.stopLossPct = clamp((mutated.stopLossPct ?? 30) + randInt(-15, 15), 5, 70); },
        () => { mutated.takeProfitPct = clamp((mutated.takeProfitPct ?? 100) + randInt(-30, 80), 20, 500); },
        () => { mutated.trailingStopPct = clamp((mutated.trailingStopPct ?? 15) + randInt(-5, 10), 3, 40); },
        () => { mutated.minLiquidityUsd = clamp((mutated.minLiquidityUsd ?? 10000) + randInt(-5000, 15000), 500, 100000); },
        () => { mutated.safetyScoreMin = clamp((mutated.safetyScoreMin ?? 0.6) + (Math.random() - 0.5) * 0.3, 0.2, 0.9); },
        () => { mutated.minBuySellRatio = clamp((mutated.minBuySellRatio ?? 1.0) + (Math.random() - 0.5) * 1.0, 0.0, 5); },
        () => { mutated.partialExitPct = clamp((mutated.partialExitPct ?? 50) + randInt(-15, 15), 15, 85); },
        () => { mutated.maxPositionUsd = clamp((mutated.maxPositionUsd ?? 2.0) + (Math.random() - 0.5) * 2.0, 0.25, 10); },
        () => { (mutated as any).minTokenAgeHours = clamp(((mutated as any).minTokenAgeHours ?? 0) + randInt(-24, 168), 0, 2160); },
        () => { (mutated as any).adaptiveExits = Math.random() < 0.5; },
        () => { (mutated as any).assetType = pick(['all', 'memecoin', 'xstock'] as const); },
        () => { (mutated as any).requireVolumeSurge = Math.random() < 0.3; },
        () => { (mutated as any).macroRegime = pick(['all', 'risk_on', 'risk_off', 'neutral'] as const); },
        // v1 backtest: pumpswap >> raydium, bias source mutation toward pumpswap
        () => { (mutated as Record<string, unknown>).source = pick(['all', 'pumpswap', 'pumpswap'] as const); },
        // v1 backtest: veterans (>90d) are toxic, cap max age to exclude them
        () => { (mutated as Record<string, unknown>).maxTokenAgeHours = pick([0, 720, 2160]); },
      ];

      // Apply 1-3 mutations
      const numMutations = Math.random() < 0.2 ? 3 : Math.random() < 0.4 ? 2 : 1;
      for (let i = 0; i < numMutations; i++) {
        mutations[Math.floor(Math.random() * mutations.length)]();
      }
      newPop.push(mutated);
    } else {
      // Fresh random individual for diversity
      newPop.push({
        stopLossPct: pick([5, 8, 10, 12, 15, 20, 25, 30, 35, 40, 50]),
        takeProfitPct: pick([25, 30, 40, 45, 50, 75, 100, 125, 150, 200, 300, 500]),
        trailingStopPct: pick([5, 10, 12, 15, 20, 25, 30]),
        minLiquidityUsd: pick([1000, 3000, 5000, 10000, 15000, 25000, 50000]),
        minBuySellRatio: pick([0.0, 0.3, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0]),
        safetyScoreMin: pick([0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7, 0.8]),
        maxConcurrentPositions: pick([2, 3, 4, 5, 8, 10]),
        maxPositionUsd: pick([0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0]),
        partialExitPct: pick([25, 33, 40, 50, 60, 75]),
        source: pick(['all', 'pumpfun', 'raydium', 'pumpswap'] as const),
        minTokenAgeHours: pick([0, 1, 6, 24, 168, 720]),
        maxTokenAgeHours: pick([0, 24, 168, 720, 2160, 5000]),
        ageCategory: pick(['all', 'fresh', 'young', 'established', 'veteran'] as const),
        requireVolumeSurge: pick([true, false, false]),
        minVolumeSurgeRatio: pick([0, 1.5, 2.0, 3.0, 5.0]),
        assetType: pick(['all', 'memecoin', 'xstock', 'bluechip'] as const),
        adaptiveExits: pick([true, false]),
      } as Partial<EnhancedBacktestConfig>);
    }
  }

  return newPop;
}

// ─── Continuous Improvement Mode ─────────────────────────────
export async function runContinuousImprovement(
  maxIterations: number = 50,
  targetWinRate: number = 0.80,
): Promise<OptimizationResult> {
  let bestResult: OptimizationResult | null = null;
  let iteration = 0;

  while (iteration < maxIterations) {
    iteration++;
    const deep = iteration % 5 === 0; // every 5th iteration is deep
    const result = await runSelfImprovement(
      deep ? 8 : 5,
      deep ? 30 : 20,
    );

    if (!bestResult || result.bestWinRate > bestResult.bestWinRate) {
      bestResult = result;
      log.info(`New best at iteration ${iteration}`, {
        winRate: (result.bestWinRate * 100).toFixed(1) + '%',
        pnl: '$' + result.bestPnl.toFixed(2),
        sharpe: result.bestSharpe.toFixed(2),
      });

      // Save as BEST_EVER if it beats the threshold
      saveBestEver(result);
    }

    if (result.bestWinRate >= targetWinRate) {
      log.info(`Target win rate ${(targetWinRate * 100).toFixed(0)}% reached at iteration ${iteration}`);
      break;
    }
  }

  return bestResult!;
}

function saveBestEver(result: OptimizationResult): void {
  try {
    const filePath = path.resolve(process.cwd(), 'winning', 'BEST_EVER.json');
    const existing = fs.existsSync(filePath) ? JSON.parse(fs.readFileSync(filePath, 'utf8')) : null;

    if (!existing || result.bestWinRate > (existing.winRate || 0)) {
      fs.writeFileSync(filePath, JSON.stringify({
        config: result.bestConfig,
        winRate: result.bestWinRate,
        pnl: result.bestPnl,
        sharpe: result.bestSharpe,
        validationWinRate: result.validationWinRate,
        validationPnl: result.validationPnl,
        savedAt: new Date().toISOString(),
        iterations: result.iterations,
      }, null, 2));
      log.info('New BEST_EVER saved', { winRate: (result.bestWinRate * 100).toFixed(1) + '%' });
    }
  } catch (err) {
    log.warn('Failed to save BEST_EVER', { error: (err as Error).message });
  }
}

// ─── Persistence ─────────────────────────────────────────────
function saveBestConfig(cfg: Partial<EnhancedBacktestConfig>, winRate: number, pnl: number, sharpe: number): void {
  try {
    const filePath = path.resolve(process.cwd(), 'winning', 'best-config.json');
    fs.writeFileSync(filePath, JSON.stringify({
      config: cfg,
      winRate,
      pnl,
      sharpe,
      savedAt: new Date().toISOString(),
    }, null, 2));
    log.info('Best config saved', { path: filePath });
  } catch (err) {
    log.warn('Failed to save best config', { error: (err as Error).message });
  }
}

function loadBestConfig(): Partial<EnhancedBacktestConfig> | null {
  try {
    const filePath = path.resolve(process.cwd(), 'winning', 'best-config.json');
    if (!fs.existsSync(filePath)) return null;
    const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    log.info('Loaded previous best config', { winRate: (data.winRate * 100).toFixed(1) + '%' });
    return data.config;
  } catch {
    return null;
  }
}

function writeImprovementLog(results: OptimizationResult['allResults']): void {
  try {
    const filePath = path.resolve(process.cwd(), 'winning', 'improvement-log.json');
    const existing = fs.existsSync(filePath) ? JSON.parse(fs.readFileSync(filePath, 'utf8')) : [];
    existing.push({
      timestamp: new Date().toISOString(),
      iterations: results.length,
      bestWinRate: results[0]?.winRate ?? 0,
      bestPnl: results[0]?.pnl ?? 0,
      top5: results.slice(0, 5).map(r => ({
        winRate: r.winRate,
        pnl: r.pnl,
        sharpe: r.sharpe,
        config: r.config,
      })),
    });
    fs.writeFileSync(filePath, JSON.stringify(existing, null, 2));
  } catch (err) {
    log.warn('Failed to write improvement log', { error: (err as Error).message });
  }
}

// ─── Helpers ─────────────────────────────────────────────────
function pick<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}
