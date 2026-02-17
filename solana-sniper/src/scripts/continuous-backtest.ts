/**
 * Continuous Backtest Runner
 *
 * Runs the genetic optimizer in an infinite loop, fetching fresh data each iteration,
 * evolving strategies, and persisting winning configs.
 *
 * Usage: npx tsx src/scripts/continuous-backtest.ts
 */
import { runSelfImprovement } from '../analysis/self-improver.js';
import { createModuleLogger } from '../utils/logger.js';
import fs from 'fs';
import path from 'path';

const log = createModuleLogger('continuous-backtest');

interface RunSummary {
  iteration: number;
  startedAt: string;
  completedAt: string;
  durationSec: number;
  bestWinRate: number;
  bestPnl: number;
  bestSharpe: number;
  totalConfigs: number;
  dataPoints: number;
  validationWinRate?: number;
  validationPnl?: number;
  validationSharpe?: number;
}

async function main(): Promise<void> {
  // CLI args: [instanceId] [generations] [populationSize] [maxIterations]
  const args = process.argv.slice(2);
  const instanceId = args[0] || 'default';
  const generations = parseInt(args[1] || '3', 10);
  const populationSize = parseInt(args[2] || '12', 10);
  const maxIterations = parseInt(args[3] || '0', 10); // 0 = infinite

  log.info(`=== CONTINUOUS BACKTEST RUNNER [${instanceId}] STARTED ===`);
  log.info(`Config: ${generations} gen, ${populationSize} pop, ${maxIterations || '∞'} iters`);
  log.info('Press Ctrl+C to stop');

  const winningDir = path.resolve(process.cwd(), 'winning');
  if (!fs.existsSync(winningDir)) fs.mkdirSync(winningDir, { recursive: true });

  const summaryPath = path.join(winningDir, `continuous-run-log-${instanceId}.json`);
  const summaries: RunSummary[] = fs.existsSync(summaryPath)
    ? JSON.parse(fs.readFileSync(summaryPath, 'utf8'))
    : [];

  // Read global best from BEST_EVER.json
  let iteration = summaries.length;
  let globalBestWinRate = 0;
  try {
    const bestEverPath = path.join(winningDir, 'BEST_EVER.json');
    if (fs.existsSync(bestEverPath)) {
      const bestEver = JSON.parse(fs.readFileSync(bestEverPath, 'utf8'));
      globalBestWinRate = bestEver.winRate ?? 0;
    }
  } catch { /* ignore */ }
  if (summaries.length > 0) {
    globalBestWinRate = Math.max(globalBestWinRate, ...summaries.map(s => s.bestWinRate));
  }

  // Loop — runs until killed or maxIterations reached
  while (maxIterations === 0 || iteration < maxIterations + summaries.length) {
    iteration++;
    const startTime = Date.now();
    log.info(`\n${'='.repeat(60)}`);
    log.info(`ITERATION ${iteration} — Global best: ${(globalBestWinRate * 100).toFixed(1)}%`);
    log.info(`${'='.repeat(60)}`);

    try {
      // Phase 1: Run genetic optimizer
      const optResult = await runSelfImprovement(generations, populationSize);

      log.info(`Optimizer complete:`, {
        winRate: (optResult.bestWinRate * 100).toFixed(1) + '%',
        pnl: '$' + optResult.bestPnl.toFixed(2),
        sharpe: optResult.bestSharpe.toFixed(2),
        configs: optResult.iterations,
        validationWR: optResult.validationWinRate != null ? (optResult.validationWinRate * 100).toFixed(1) + '%' : 'N/A',
        validationPnl: optResult.validationPnl != null ? '$' + optResult.validationPnl.toFixed(2) : 'N/A',
      });

      // Phase 2: Check for new global best using validation-aware scoring
      const valWR = optResult.validationWinRate ?? optResult.bestWinRate;
      const valPnl = optResult.validationPnl ?? optResult.bestPnl;

      // REQUIRE validation data — never write unvalidated configs to BEST_EVER
      if (optResult.validationWinRate == null) {
        log.warn('Skipping BEST_EVER — no validation data available');
      } else {
      const trainScore = optResult.allResults[0]?.score ?? 0;

      // Blend train + validation (60/40) to reward robust configs
      const blendedWR = optResult.bestWinRate * 0.6 + valWR * 0.4;
      const compositeScore = blendedWR * Math.min(1, trainScore * 2);
      const globalComposite = globalBestWinRate * 0.95; // tight gate — only truly better configs replace

      // Reject overfit: validation WR drops >50% from training
      const isOverfit = optResult.bestWinRate > 0 &&
        valWR < optResult.bestWinRate * 0.5;

      // Require minimum data quality: at least 10 trades total
      const tooFewTrades = (optResult.allResults[0]?.winRate ?? 0) >= 0 &&
        optResult.iterations < 5;

      if (!isOverfit && !tooFewTrades && (compositeScore > globalComposite || (blendedWR > globalBestWinRate && optResult.bestPnl > 0))) {
        globalBestWinRate = blendedWR;
        log.info(`NEW GLOBAL BEST: ${(blendedWR * 100).toFixed(1)}% blended WR (train: ${(optResult.bestWinRate * 100).toFixed(1)}%, val: ${(valWR * 100).toFixed(1)}%), $${optResult.bestPnl.toFixed(2)} PnL`);

        // Write prominent marker
        fs.writeFileSync(
          path.join(winningDir, 'BEST_EVER.json'),
          JSON.stringify({
            winRate: optResult.bestWinRate,
            pnl: optResult.bestPnl,
            sharpe: optResult.bestSharpe,
            config: optResult.bestConfig,
            achievedAt: new Date().toISOString(),
            iteration,
            instance: instanceId,
            validationWinRate: valWR,
            validationPnl: valPnl,
            validationSharpe: optResult.validationSharpe,
            blendedWinRate: blendedWR,
          }, null, 2)
        );
      } else if (isOverfit) {
        log.warn('Config rejected — overfit detected', {
          trainWR: (optResult.bestWinRate * 100).toFixed(1) + '%',
          valWR: (valWR * 100).toFixed(1) + '%',
        });
      }
      } // end validation check

      // Phase 3: Log iteration summary
      const duration = (Date.now() - startTime) / 1000;
      const summary: RunSummary = {
        iteration,
        startedAt: new Date(startTime).toISOString(),
        completedAt: new Date().toISOString(),
        durationSec: Math.round(duration),
        bestWinRate: optResult.bestWinRate,
        bestPnl: optResult.bestPnl,
        bestSharpe: optResult.bestSharpe,
        totalConfigs: optResult.iterations,
        dataPoints: optResult.allResults.length,
        validationWinRate: valWR,
        validationPnl: valPnl,
        validationSharpe: optResult.validationSharpe,
      };

      summaries.push(summary);
      fs.writeFileSync(summaryPath, JSON.stringify(summaries, null, 2));

      log.info(`Iteration ${iteration} complete in ${duration.toFixed(0)}s`);

      // Convergence check — if we're at 80%+ for 5 consecutive runs, slow down
      const recent5 = summaries.slice(-5);
      if (recent5.length >= 5 && recent5.every(s => s.bestWinRate >= 0.80)) {
        log.info('TARGET ACHIEVED: 80%+ win rate sustained for 5 iterations!');
        log.info('Slowing iteration cadence — waiting 5 minutes before next run');
        await sleep(5 * 60 * 1000);
      } else {
        // Wait 30s between iterations to allow fresh API data
        log.info('Waiting 30s for fresh data...');
        await sleep(30_000);
      }

    } catch (err) {
      log.error(`Iteration ${iteration} failed:`, { error: (err as Error).message });
      // Wait 60s on error then retry
      await sleep(60_000);
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Handle graceful shutdown
process.on('SIGINT', () => {
  log.info('\nShutting down continuous backtest runner...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  log.info('\nShutting down continuous backtest runner...');
  process.exit(0);
});

main().catch(err => {
  log.error('Fatal error:', { error: (err as Error).message });
  process.exit(1);
});
