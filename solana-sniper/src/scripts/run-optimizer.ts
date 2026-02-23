#!/usr/bin/env node
/**
 * Run the genetic optimizer (self-improver) in deep mode.
 * Usage: npx tsx src/scripts/run-optimizer.ts
 */
import { runSelfImprovement } from '../analysis/self-improver.js';

async function main(): Promise<void> {
  console.log('Starting genetic optimizer v2 (deep mode: 8 gen, 30 pop)...');
  console.log('This will take several minutes.\n');

  const result = await runSelfImprovement(8, 30, true);

  console.log('\n=== GENETIC OPTIMIZER V2 RESULTS ===');
  console.log(`Best WR: ${(result.bestWinRate * 100).toFixed(1)}%`);
  console.log(`Best PnL: $${result.bestPnl.toFixed(2)}`);
  console.log(`Best Sharpe: ${result.bestSharpe.toFixed(3)}`);
  console.log(`Iterations: ${result.iterations}`);

  if (result.validationWinRate !== undefined) {
    console.log(`\nValidation WR: ${(result.validationWinRate * 100).toFixed(1)}%`);
    console.log(`Validation PnL: $${(result.validationPnl ?? 0).toFixed(2)}`);
    console.log(`Validation Sharpe: ${(result.validationSharpe ?? 0).toFixed(3)}`);
  }

  console.log('\nBest Config:');
  console.log(JSON.stringify(result.bestConfig, null, 2));

  console.log('\nTop 5 configs:');
  result.allResults
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)
    .forEach((r, i) => {
      console.log(
        `  #${i + 1}: WR=${(r.winRate * 100).toFixed(1)}%, PnL=$${r.pnl.toFixed(2)}, Score=${r.score.toFixed(3)}, Source=${r.config.source ?? 'all'}, Age=${r.config.ageCategory ?? 'all'}`,
      );
    });
}

main().catch(console.error);
