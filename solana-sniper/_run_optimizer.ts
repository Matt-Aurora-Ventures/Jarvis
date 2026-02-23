import { runSelfImprovement } from './src/analysis/self-improver.ts';

async function main() {
  console.log('Starting deep genetic optimization...');
  console.log('Using biased population seeded with v2 backtest winners');
  console.log('8 generations, 30 population per gen');
  console.log('');
  
  const result = await runSelfImprovement(8, 30, true);
  
  console.log('');
  console.log('=== GENETIC OPTIMIZER RESULTS ===');
  console.log('Best Win Rate:', (result.bestWinRate * 100).toFixed(1) + '%');
  console.log('Best PnL:', '$' + result.bestPnl.toFixed(2));
  console.log('Best Sharpe:', result.bestSharpe.toFixed(3));
  console.log('Validation WR:', result.validationWinRate != null ? (result.validationWinRate * 100).toFixed(1) + '%' : 'N/A');
  console.log('Validation PnL:', result.validationPnl != null ? '$' + result.validationPnl.toFixed(2) : 'N/A');
  console.log('Total iterations:', result.iterations);
  console.log('');
  console.log('Best Config:', JSON.stringify(result.bestConfig, null, 2));
  console.log('');
  console.log('Top 5 configs:');
  result.allResults.slice(0, 5).forEach((r: any, i: number) => {
    console.log((i+1) + '. WR=' + (r.winRate*100).toFixed(1) + '% PnL=$' + r.pnl.toFixed(2) + ' Sharpe=' + r.sharpe.toFixed(2) + ' Score=' + r.score.toFixed(3));
    console.log('   Config: SL=' + r.config.stopLossPct + ' TP=' + r.config.takeProfitPct + ' Trail=' + r.config.trailingStopPct + ' Liq=' + r.config.minLiquidityUsd + ' Safety=' + (r.config.safetyScoreMin as number)?.toFixed(2) + ' Src=' + r.config.source + ' VolSurge=' + r.config.requireVolumeSurge);
  });
}

main().catch(err => {
  console.error('Optimizer failed:', err.message);
  process.exit(1);
});
