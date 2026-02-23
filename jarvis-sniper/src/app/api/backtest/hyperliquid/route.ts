import { NextResponse } from 'next/server';
import {
  BacktestEngine,
  meanReversionEntry,
  trendFollowingEntry,
  breakoutEntry,
  momentumEntry,
  squeezeBreakoutEntry,
  generateBacktestReport,
  walkForwardTest,
  gridSearch,
  type BacktestConfig,
  type BacktestResult,
  type OHLCVCandle,
} from '@/lib/backtest-engine';
import { fetchHyperliquidCandles, type HyperliquidInterval } from '@/lib/hyperliquid-data';
import { apiRateLimiter, getClientIp } from '@/lib/rate-limiter';
import {
  putBacktestEvidence,
  type BacktestEvidenceBundle,
  type BacktestEvidenceDataset,
  type BacktestEvidenceTradeRow,
} from '@/lib/backtest-evidence';
import { persistBacktestArtifacts } from '@/lib/backtest-artifacts';
import { createHash } from 'crypto';

export const runtime = 'nodejs';

type BacktestMode = 'quick' | 'full' | 'grid';

function makeRunId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function hashCandlesHex(candles: OHLCVCandle[]): string {
  const h = createHash('sha256');
  for (const c of candles) {
    h.update(`${c.timestamp},${c.open},${c.high},${c.low},${c.close},${c.volume};`, 'utf8');
  }
  return h.digest('hex');
}

const HL_ENTRY_SIGNALS: Record<string, BacktestConfig['entrySignal']> = {
  hl_mean_revert: meanReversionEntry,
  hl_trend_follow: trendFollowingEntry,
  hl_breakout: breakoutEntry,
  hl_momentum: momentumEntry,
  hl_squeeze_breakout: squeezeBreakoutEntry,
};

const HL_STRATEGY_CONFIGS: Record<string, Omit<BacktestConfig, 'entrySignal'>> = {
  hl_mean_revert: {
    strategyId: 'hl_mean_revert',
    stopLossPct: 2.5,
    takeProfitPct: 5.5,
    trailingStopPct: 1.5,
    minScore: 0,
    minLiquidityUsd: 0,
    slippagePct: 0.05,
    feePct: 0.02,
    maxHoldCandles: 36,
  },
  hl_trend_follow: {
    strategyId: 'hl_trend_follow',
    stopLossPct: 3.5,
    takeProfitPct: 10,
    trailingStopPct: 2.5,
    minScore: 0,
    minLiquidityUsd: 0,
    slippagePct: 0.05,
    feePct: 0.02,
    maxHoldCandles: 120,
  },
  hl_breakout: {
    strategyId: 'hl_breakout',
    stopLossPct: 3,
    takeProfitPct: 8,
    trailingStopPct: 2,
    minScore: 0,
    minLiquidityUsd: 0,
    slippagePct: 0.05,
    feePct: 0.02,
    maxHoldCandles: 72,
  },
  hl_momentum: {
    strategyId: 'hl_momentum',
    stopLossPct: 2.5,
    takeProfitPct: 7,
    trailingStopPct: 2,
    minScore: 0,
    minLiquidityUsd: 0,
    slippagePct: 0.05,
    feePct: 0.02,
    maxHoldCandles: 48,
  },
  hl_squeeze_breakout: {
    strategyId: 'hl_squeeze_breakout',
    stopLossPct: 3,
    takeProfitPct: 9,
    trailingStopPct: 2.5,
    minScore: 0,
    minLiquidityUsd: 0,
    slippagePct: 0.05,
    feePct: 0.02,
    maxHoldCandles: 72,
  },
};

function wilsonBounds(wins: number, total: number, z = 1.96): [number, number] {
  if (total <= 0) return [0, 0];
  const p = wins / total;
  const z2 = z * z;
  const denom = 1 + z2 / total;
  const centre = p + z2 / (2 * total);
  const margin = z * Math.sqrt((p * (1 - p) + z2 / (4 * total)) / total);
  return [(centre - margin) / denom, (centre + margin) / denom];
}

function meanCi95(mean: number, std: number, n: number): [number, number] {
  if (n < 2 || !Number.isFinite(mean) || !Number.isFinite(std)) return [mean, mean];
  const margin = 1.96 * (std / Math.sqrt(n));
  return [mean - margin, mean + margin];
}

function aggregateBacktestResults(
  strategyId: string,
  fullConfig: BacktestConfig,
  tokenLabel: string,
  results: BacktestResult[],
): BacktestResult {
  let totalTrades = 0;
  let wins = 0;
  let losses = 0;
  let winningPnl = 0;
  let losingPnl = 0;
  let sumReturn = 0;
  let sumSquaresReturn = 0;
  let sumHoldCandles = 0;
  let bestTrade = Number.NEGATIVE_INFINITY;
  let worstTrade = Number.POSITIVE_INFINITY;

  let equity = 100;
  let peak = 100;
  let maxDrawdownPct = 0;
  const equityCurve: number[] = [equity];

  const tradeSamples: BacktestResult['trades'] = [];
  const MAX_TRADE_SAMPLES = 500;

  let dataStartTime = Number.POSITIVE_INFINITY;
  let dataEndTime = 0;
  let totalCandles = 0;

  for (const r of results) {
    dataStartTime = Math.min(dataStartTime, r.dataStartTime);
    dataEndTime = Math.max(dataEndTime, r.dataEndTime);
    totalCandles += r.totalCandles;

    for (const t of r.trades) {
      totalTrades += 1;
      sumReturn += t.pnlNet;
      sumSquaresReturn += t.pnlNet * t.pnlNet;
      sumHoldCandles += t.holdCandles;

      if (t.pnlNet > 0) {
        wins += 1;
        winningPnl += t.pnlNet;
      } else {
        losses += 1;
        losingPnl += Math.abs(t.pnlNet);
      }

      bestTrade = Math.max(bestTrade, t.pnlNet);
      worstTrade = Math.min(worstTrade, t.pnlNet);

      if (tradeSamples.length < MAX_TRADE_SAMPLES) {
        const logReturn = Number.isFinite((t as any).logReturn)
          ? Number((t as any).logReturn)
          : (t.entryPrice > 0 && t.exitPrice > 0 ? Math.log(t.exitPrice / t.entryPrice) : 0);
        tradeSamples.push({ ...t, logReturn });
      }

      // Pseudo equity across independent samples (not a portfolio sim).
      equity *= (1 + t.pnlNet / 100);
      equityCurve.push(equity);
      if (equityCurve.length > 100) equityCurve.shift();

      peak = Math.max(peak, equity);
      const dd = peak > 0 ? ((peak - equity) / peak) * 100 : 0;
      maxDrawdownPct = Math.max(maxDrawdownPct, dd);
    }
  }

  const winRate = totalTrades > 0 ? wins / totalTrades : 0;
  const rawPF = losingPnl > 0 ? winningPnl / losingPnl : (winningPnl > 0 ? 999 : 0);
  const profitFactor = Math.min(rawPF, 999);

  const avgReturnPct = totalTrades > 0 ? sumReturn / totalTrades : 0;
  const avgHold = totalTrades > 0 ? sumHoldCandles / totalTrades : 0;
  const expectancy = avgReturnPct;

  const variance = totalTrades > 1
    ? (sumSquaresReturn - totalTrades * avgReturnPct * avgReturnPct) / (totalTrades - 1)
    : 0;
  const stdReturn = Math.sqrt(Math.max(variance, 0));
  const MIN_STD = 0.001;
  const sharpeLike = (avgReturnPct / Math.max(stdReturn, MIN_STD)) * Math.sqrt(Math.max(totalTrades, 1));
  const sharpeRatio = Math.max(-10, Math.min(10, sharpeLike));
  const avgReturnCI95 = meanCi95(avgReturnPct, stdReturn, totalTrades);
  const winRateCI95 = wilsonBounds(wins, totalTrades);
  const sharpeCiHalfWidth = totalTrades > 1 ? (1.96 / Math.sqrt(totalTrades)) : 0;
  const sharpeCI95: [number, number] = [
    sharpeRatio - sharpeCiHalfWidth,
    sharpeRatio + sharpeCiHalfWidth,
  ];
  const cltReliable = totalTrades >= 50;
  const logReturns = tradeSamples.map((t) =>
    Number.isFinite((t as any).logReturn) ? Number((t as any).logReturn) : 0,
  );
  let ewmaVariance = logReturns.length > 0 ? logReturns[0] * logReturns[0] : 0;
  for (let i = 1; i < logReturns.length; i++) {
    ewmaVariance = 0.9 * ewmaVariance + 0.1 * logReturns[i] * logReturns[i];
  }
  const ewmaVol = Math.sqrt(Math.max(ewmaVariance, 0));
  const parkinsonVol = 0;
  const winRateDisplay = totalTrades > 0
    ? `${(winRate * 100).toFixed(1)}% [${(winRateCI95[0] * 100).toFixed(1)}-${(winRateCI95[1] * 100).toFixed(1)}%]`
    : '0.0% [0.0-0.0%]';

  return {
    strategyId,
    config: fullConfig,
    tokenSymbol: tokenLabel,
    totalTrades,
    wins,
    losses,
    winRate,
    profitFactor,
    avgReturnPct,
    bestTradePct: totalTrades > 0 ? bestTrade : 0,
    worstTradePct: totalTrades > 0 ? worstTrade : 0,
    maxDrawdownPct,
    sharpeRatio,
    avgHoldCandles: avgHold,
    expectancy,
    trades: tradeSamples,
    equityCurve,
    dataStartTime: Number.isFinite(dataStartTime) ? dataStartTime : 0,
    dataEndTime,
    totalCandles,
    avgReturnCI95,
    winRateCI95,
    sharpeCI95,
    cltReliable,
    parkinsonVol,
    ewmaVol,
    winRateDisplay,
  };
}

function runStrategy(
  sid: string,
  config: Omit<BacktestConfig, 'entrySignal'>,
  candles: OHLCVCandle[],
  tokenSymbol: string,
  mode: BacktestMode,
  entrySignal: BacktestConfig['entrySignal'],
): BacktestResult[] {
  const fullConfig: BacktestConfig = {
    ...config,
    entrySignal,
  };

  if (mode === 'full') {
    const wf = walkForwardTest(candles, fullConfig, tokenSymbol);
    return [wf.inSample, wf.outOfSample];
  }

  if (mode === 'grid') {
    const gridResults = gridSearch(
      candles,
      {
        strategyId: sid,
        minScore: config.minScore,
        minLiquidityUsd: config.minLiquidityUsd,
        slippagePct: config.slippagePct,
        feePct: config.feePct,
      },
      {
        stopLossPcts: [0.8, 1.2, 1.8, 2.5, 3.5, 5],
        takeProfitPcts: [1.5, 2.5, 4, 6, 8, 10, 15],
        trailingStopPcts: [0, 0.8, 1.2, 1.8, 2.5, 3.5],
        maxHoldCandles: [12, 24, 36, 48, 72, 120],
      },
      tokenSymbol,
      entrySignal,
    );
    return gridResults.slice(0, 25);
  }

  const engine = new BacktestEngine(candles, fullConfig);
  return [engine.run(tokenSymbol)];
}

export async function POST(request: Request): Promise<NextResponse> {
  const ip = getClientIp(request);
  const limit = apiRateLimiter.check(ip);
  if (!limit.allowed) {
    return NextResponse.json(
      { success: false, error: 'Rate limit exceeded' },
      {
        status: 429,
        headers: {
          'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)),
          'X-RateLimit-Remaining': '0',
        },
      },
    );
  }

  try {
    const body = await request.json();
    const {
      strategyId = 'all',
      coins = ['BTC', 'ETH', 'SOL', 'ATOM'],
      mode = 'quick' as BacktestMode,
      interval = '1h' as HyperliquidInterval,
      days = 60,
      startTime,
      endTime,
      includeReport = true,
      includeEvidence = false,
    } = body || {};

    const now = Date.now();
    const endMs = Number.isFinite(Number(endTime)) ? Number(endTime) : now;
    const startMs = Number.isFinite(Number(startTime))
      ? Number(startTime)
      : endMs - Math.max(1, Number(days) || 60) * 24 * 60 * 60 * 1000;

    const sids = strategyId === 'all' ? Object.keys(HL_STRATEGY_CONFIGS) : [String(strategyId)];
    const runCoins = Array.isArray(coins) ? coins.map((c: any) => String(c).toUpperCase()).filter(Boolean) : ['BTC'];

    const evidenceRunId = includeEvidence ? makeRunId() : null;
    const evidenceDatasets = new Map<string, BacktestEvidenceDataset>();
    const evidenceTrades: BacktestEvidenceTradeRow[] = [];

    const resultsOut: BacktestResult[] = [];

    // Fetch all coin datasets once, reuse across strategy runs.
    const coinData = new Map<string, OHLCVCandle[]>();
    for (const coin of runCoins) {
      const candles = await fetchHyperliquidCandles({
        coin,
        interval,
        startTime: startMs,
        endTime: endMs,
      });
      // Require a minimum candle count; otherwise results are meaningless.
      if (candles.length < 200) continue;
      coinData.set(coin, candles);

      if (includeEvidence && evidenceRunId) {
        const dsKey = `HL:${coin}:${interval}`;
        evidenceDatasets.set(dsKey, {
          tokenSymbol: `HL:${coin}`,
          mintAddress: `HL:${coin}`,
          pairAddress: interval,
          candles: candles.length,
          dataHash: hashCandlesHex(candles),
          dataStartTime: candles[0]?.timestamp ?? 0,
          dataEndTime: candles[candles.length - 1]?.timestamp ?? 0,
          fetchedAt: Date.now(),
          source: 'hyperliquid',
        });
      }
    }

    if (coinData.size === 0) {
      throw new Error('No Hyperliquid datasets available (insufficient candles)');
    }

    for (const sid of sids) {
      const baseConfig = HL_STRATEGY_CONFIGS[sid];
      if (!baseConfig) continue;

      const entrySignal = HL_ENTRY_SIGNALS[sid] || momentumEntry;
      const fullConfig: BacktestConfig = { ...baseConfig, entrySignal };

      // Grid mode: run on BTC only (exploratory + expensive).
      if (mode === 'grid') {
        const btc = coinData.get('BTC') || [...coinData.values()][0];
        const rows = runStrategy(sid, baseConfig, btc, 'HL:BTC', mode, entrySignal);
        resultsOut.push(...rows);
        continue;
      }

      if (mode === 'full') {
        const train: BacktestResult[] = [];
        const test: BacktestResult[] = [];

        for (const [coin, candles] of coinData.entries()) {
          const [inSample, outOfSample] = runStrategy(sid, baseConfig, candles, `HL:${coin}`, mode, entrySignal);
          if (inSample) train.push(inSample);
          if (outOfSample) test.push(outOfSample);

          if (includeEvidence && evidenceRunId) {
            const cfg = inSample.config;
            for (const t of inSample.trades) {
              evidenceTrades.push({
                strategyId: inSample.strategyId,
                mode,
                tokenSymbol: `HL:${coin}`,
                resultTokenSymbol: inSample.tokenSymbol,
                mintAddress: `HL:${coin}`,
                pairAddress: interval,
                source: 'hyperliquid',
                entryTime: t.entryTime,
                exitTime: t.exitTime,
                entryPrice: t.entryPrice,
                exitPrice: t.exitPrice,
                pnlPct: t.pnlPct,
                pnlNet: t.pnlNet,
                exitReason: t.exitReason,
                holdCandles: t.holdCandles,
                highWaterMark: t.highWaterMark,
                lowWaterMark: t.lowWaterMark,
                maxDrawdownPct: t.maxDrawdownPct,
                stopLossPct: cfg.stopLossPct,
                takeProfitPct: cfg.takeProfitPct,
                trailingStopPct: cfg.trailingStopPct,
                maxHoldCandles: cfg.maxHoldCandles,
                slippagePct: cfg.slippagePct,
                feePct: cfg.feePct,
                minScore: cfg.minScore,
                minLiquidityUsd: cfg.minLiquidityUsd,
              });
            }

            const cfg2 = outOfSample.config;
            for (const t of outOfSample.trades) {
              evidenceTrades.push({
                strategyId: outOfSample.strategyId,
                mode,
                tokenSymbol: `HL:${coin}`,
                resultTokenSymbol: outOfSample.tokenSymbol,
                mintAddress: `HL:${coin}`,
                pairAddress: interval,
                source: 'hyperliquid',
                entryTime: t.entryTime,
                exitTime: t.exitTime,
                entryPrice: t.entryPrice,
                exitPrice: t.exitPrice,
                pnlPct: t.pnlPct,
                pnlNet: t.pnlNet,
                exitReason: t.exitReason,
                holdCandles: t.holdCandles,
                highWaterMark: t.highWaterMark,
                lowWaterMark: t.lowWaterMark,
                maxDrawdownPct: t.maxDrawdownPct,
                stopLossPct: cfg2.stopLossPct,
                takeProfitPct: cfg2.takeProfitPct,
                trailingStopPct: cfg2.trailingStopPct,
                maxHoldCandles: cfg2.maxHoldCandles,
                slippagePct: cfg2.slippagePct,
                feePct: cfg2.feePct,
                minScore: cfg2.minScore,
                minLiquidityUsd: cfg2.minLiquidityUsd,
              });
            }
          }
        }

        resultsOut.push(
          aggregateBacktestResults(sid, fullConfig, `HL (train, n=${coinData.size})`, train),
          aggregateBacktestResults(sid, fullConfig, `HL (test, n=${coinData.size})`, test),
        );
        continue;
      }

      // quick
      const quickResults: BacktestResult[] = [];
      for (const [coin, candles] of coinData.entries()) {
        const [r] = runStrategy(sid, baseConfig, candles, `HL:${coin}`, 'quick', entrySignal);
        quickResults.push(r);

        if (includeEvidence && evidenceRunId) {
          const cfg = r.config;
          for (const t of r.trades) {
            evidenceTrades.push({
              strategyId: r.strategyId,
              mode: 'quick',
              tokenSymbol: `HL:${coin}`,
              resultTokenSymbol: r.tokenSymbol,
              mintAddress: `HL:${coin}`,
              pairAddress: interval,
              source: 'hyperliquid',
              entryTime: t.entryTime,
              exitTime: t.exitTime,
              entryPrice: t.entryPrice,
              exitPrice: t.exitPrice,
              pnlPct: t.pnlPct,
              pnlNet: t.pnlNet,
              exitReason: t.exitReason,
              holdCandles: t.holdCandles,
              highWaterMark: t.highWaterMark,
              lowWaterMark: t.lowWaterMark,
              maxDrawdownPct: t.maxDrawdownPct,
              stopLossPct: cfg.stopLossPct,
              takeProfitPct: cfg.takeProfitPct,
              trailingStopPct: cfg.trailingStopPct,
              maxHoldCandles: cfg.maxHoldCandles,
              slippagePct: cfg.slippagePct,
              feePct: cfg.feePct,
              minScore: cfg.minScore,
              minLiquidityUsd: cfg.minLiquidityUsd,
            });
          }
        }
      }

      resultsOut.push(
        aggregateBacktestResults(sid, fullConfig, `HL (n=${coinData.size})`, quickResults),
      );
    }

    const report = includeReport && resultsOut.length <= 250 ? generateBacktestReport(resultsOut) : null;
    const summary = resultsOut.map((r) => ({
      strategyId: r.strategyId,
      token: r.tokenSymbol,
      trades: r.totalTrades,
      winRate: `${(r.winRate * 100).toFixed(1)}%`,
      profitFactor: r.profitFactor.toFixed(2),
      sharpe: r.sharpeRatio.toFixed(2),
      maxDD: `${r.maxDrawdownPct.toFixed(1)}%`,
      expectancy: r.expectancy.toFixed(4),
      avgHold: `${r.avgHoldCandles.toFixed(0)}h`,
      validated: true,
      dataSource: 'hyperliquid',
    }));

    const meta = {
      source: 'hyperliquid',
      coins: [...coinData.keys()],
      interval,
      startTime: startMs,
      endTime: endMs,
      datasetsUsed: coinData.size,
      strategiesRun: sids.length,
    };

    if (includeEvidence && evidenceRunId) {
      const bundle: BacktestEvidenceBundle = {
        runId: evidenceRunId,
        generatedAt: new Date().toISOString(),
        request: {
          strategyId,
          coins: [...coinData.keys()],
          mode,
          interval,
          startTime: startMs,
          endTime: endMs,
        },
        meta,
        datasets: [...evidenceDatasets.values()],
        trades: evidenceTrades,
        reportMd: report,
        resultsSummary: summary,
      };
      putBacktestEvidence(bundle);
      persistBacktestArtifacts(bundle);
    }

    return NextResponse.json({
      meta,
      results: summary,
      report,
      evidence: includeEvidence && evidenceRunId
        ? {
            runId: evidenceRunId,
            datasetCount: evidenceDatasets.size,
            tradeCount: evidenceTrades.length,
          }
        : null,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Backtest failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
