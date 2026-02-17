import { config } from './config/index.js';
import { createModuleLogger } from './utils/logger.js';
import { getDb } from './utils/database.js';
import { getSolBalanceUsd } from './utils/wallet.js';
import { RaydiumListener } from './listeners/raydium-listener.js';
import { PumpFunListener } from './listeners/pumpfun-listener.js';
import { PumpSwapListener } from './listeners/pumpswap-listener.js';
import { TwitterListener } from './listeners/twitter-listener.js';
import { PositionManager } from './trading/position-manager.js';
import { StopLossMonitor } from './risk/stop-loss-monitor.js';
import { checkCircuitBreaker, recordTradeResult } from './risk/circuit-breaker.js';
import { aggregateSignal } from './analysis/signal-aggregator.js';
import { executeJupiterSwap } from './trading/jupiter-swap.js';
import { executePumpPortalBuy } from './trading/pumpportal-swap.js';
import { WSOL_MINT, LAMPORTS_PER_SOL } from './config/constants.js';
import { createApiServer } from './api/server.js';
import type { NewPoolEvent, TwitterSignalEvent, TokenInfo } from './types/index.js';

const log = createModuleLogger('supervisor');

class Supervisor {
  private raydiumListener: RaydiumListener;
  private pumpFunListener: PumpFunListener;
  private pumpSwapListener: PumpSwapListener;
  private twitterListener: TwitterListener;
  private positionManager: PositionManager;
  private stopLossMonitor: StopLossMonitor;
  private isRunning: boolean = false;
  private processedTokens: Set<string> = new Set();
  private static readonly MAX_PROCESSED_CACHE = 10_000;
  private statsInterval: ReturnType<typeof setInterval> | null = null;
  private apiServer: ReturnType<typeof createApiServer> | null = null;

  constructor() {
    this.raydiumListener = new RaydiumListener();
    this.pumpFunListener = new PumpFunListener();
    this.pumpSwapListener = new PumpSwapListener();
    this.twitterListener = new TwitterListener();
    this.positionManager = new PositionManager();
    this.stopLossMonitor = new StopLossMonitor(this.positionManager);
  }

  async start(): Promise<void> {
    log.info('═══════════════════════════════════════════');
    log.info('    SOLANA SNIPER - Starting Up');
    log.info('═══════════════════════════════════════════');
    log.info(`Mode: ${config.tradingMode.toUpperCase()}`);

    // Initialize database
    getDb();

    // Check wallet balance
    try {
      const balance = await getSolBalanceUsd();
      log.info(`Wallet balance: ${balance.sol.toFixed(4)} SOL ($${balance.usd.toFixed(2)})`);

      if (balance.usd < 5) {
        log.warn('LOW BALANCE WARNING — Consider adding more SOL');
      }
    } catch {
      log.warn('Could not fetch wallet balance (no key or RPC issue)');
    }

    // Load existing positions
    await this.positionManager.loadOpenPositions();

    // Wire up event handlers
    this.setupEventHandlers();

    // Start all listeners
    this.isRunning = true;

    await Promise.all([
      this.raydiumListener.start().catch(e => log.error('Raydium listener failed to start', { error: e.message })),
      this.pumpFunListener.start().catch(e => log.error('PumpFun listener failed to start', { error: e.message })),
      this.pumpSwapListener.start().catch(e => log.error('PumpSwap listener failed to start', { error: e.message })),
      this.twitterListener.start().catch(e => log.error('Twitter listener failed to start', { error: e.message })),
    ]);

    // Start monitoring
    this.positionManager.startPriceMonitor(2000);
    this.stopLossMonitor.start(2000);

    // Start API server for web dashboard
    this.apiServer = createApiServer(3001);

    // Stats reporting every 60s
    this.statsInterval = setInterval(() => this.reportStats(), 60_000);

    log.info('All systems online. Watching for opportunities...');
    log.info('═══════════════════════════════════════════');
  }

  private setupEventHandlers(): void {
    // Raydium new pool → process
    this.raydiumListener.on('newPool', (event: NewPoolEvent) => {
      this.processNewToken({
        mint: event.mint,
        symbol: 'UNKNOWN',
        name: 'Unknown Token',
        decimals: 9,
        supply: 0,
        source: 'raydium',
        discoveredAt: event.timestamp,
        poolAddress: event.poolAddress,
      });
    });

    // PumpFun new token → process
    this.pumpFunListener.on('newToken', (event: NewPoolEvent) => {
      const raw = event.raw as { name?: string; symbol?: string };
      this.processNewToken({
        mint: event.mint,
        symbol: raw?.symbol ?? 'PUMP',
        name: raw?.name ?? 'Pump Token',
        decimals: 6,
        supply: 0,
        source: 'pumpfun',
        discoveredAt: event.timestamp,
        poolAddress: event.poolAddress,
      });
    });

    // PumpFun momentum signal
    this.pumpFunListener.on('momentum', (data: { mint: string; buys: number; sells: number; ratio: number }) => {
      log.info('Momentum detected', {
        mint: data.mint.slice(0, 8),
        buys: data.buys,
        ratio: data.ratio.toFixed(1),
      });
    });

    // PumpSwap graduation → highest priority snipe
    this.pumpSwapListener.on('graduation', (event: { mint: string; symbol: string; name: string; poolAddress: string; liquidityUsd: number }) => {
      log.info('PUMPSWAP GRADUATION — Priority snipe!', {
        mint: event.mint.slice(0, 8),
        symbol: event.symbol,
        liquidity: '$' + event.liquidityUsd.toFixed(0),
      });
      this.processNewToken({
        mint: event.mint,
        symbol: event.symbol,
        name: event.name,
        decimals: 6,
        supply: 0,
        source: 'pumpfun',
        discoveredAt: Date.now(),
        poolAddress: event.poolAddress,
      });
    });

    // PumpSwap near-graduation signal (pre-positioning)
    this.pumpSwapListener.on('nearGraduation', (data: { mint: string; symbol: string; progressPct: number }) => {
      log.info('Near graduation', {
        mint: data.mint.slice(0, 8),
        symbol: data.symbol,
        progress: data.progressPct.toFixed(0) + '%',
      });
    });

    // Twitter signal → process
    this.twitterListener.on('signal', (event: TwitterSignalEvent) => {
      if (event.mint) {
        this.processNewToken({
          mint: event.mint,
          symbol: event.symbol ?? 'TWEET',
          name: 'Twitter Signal',
          decimals: 9,
          supply: 0,
          source: 'twitter',
          discoveredAt: event.timestamp,
        });
      }
    });

    // Stop loss events
    this.stopLossMonitor.on('stopLossExecuted', ({ position }: { position: { symbol: string; unrealizedPnl?: number } }) => {
      recordTradeResult(false);
      log.warn('Stop loss executed', { symbol: position.symbol });
      this.apiServer?.broadcast('exit', {
        symbol: position.symbol,
        reason: 'STOP_LOSS',
        pnl_usd: position.unrealizedPnl ?? 0,
        timestamp: Date.now(),
      });
    });

    this.stopLossMonitor.on('takeProfitExecuted', ({ position }: { position: { symbol: string; unrealizedPnl?: number } }) => {
      recordTradeResult(true);
      log.info('Take profit executed', { symbol: position.symbol });
      this.apiServer?.broadcast('exit', {
        symbol: position.symbol,
        reason: 'TAKE_PROFIT',
        pnl_usd: position.unrealizedPnl ?? 0,
        timestamp: Date.now(),
      });
    });
  }

  private async processNewToken(token: TokenInfo): Promise<void> {
    // Dedup with eviction
    if (this.processedTokens.has(token.mint)) return;
    this.processedTokens.add(token.mint);
    if (this.processedTokens.size > Supervisor.MAX_PROCESSED_CACHE) {
      const first = this.processedTokens.values().next().value;
      if (first) this.processedTokens.delete(first);
    }

    // Broadcast token detection
    this.apiServer?.broadcast('detection', {
      mint: token.mint,
      symbol: token.symbol,
      source: token.source,
      timestamp: Date.now(),
    });

    // Circuit breaker check
    const cb = await checkCircuitBreaker();
    if (cb.isTripped) {
      log.warn('Circuit breaker active — skipping', { reason: cb.reason });
      this.apiServer?.broadcast('circuit_breaker', {
        reason: cb.reason,
        timestamp: Date.now(),
      });
      return;
    }

    try {
      // Run full signal aggregation pipeline
      const result = await aggregateSignal(token);
      if (!result) return;

      if (!result.signal.shouldBuy) {
        log.info('Signal below threshold — skipping', {
          mint: token.mint.slice(0, 8),
          buyScore: (result.signal.buyScore * 100).toFixed(0) + '%',
        });
        this.apiServer?.broadcast('safety_fail', {
          mint: token.mint,
          symbol: token.symbol,
          reason: `Score ${(result.signal.buyScore * 100).toFixed(0)}% below threshold`,
          score: result.signal.buyScore,
          timestamp: Date.now(),
        });
        return;
      }

      // Safety passed — broadcast
      this.apiServer?.broadcast('safety_pass', {
        mint: token.mint,
        symbol: token.symbol,
        score: result.safety.overallScore,
        timestamp: Date.now(),
      });

      // EXECUTE TRADE
      log.info('EXECUTING BUY', {
        mint: token.mint.slice(0, 8),
        symbol: token.symbol,
        usd: result.positionSize.toFixed(2),
        source: token.source,
      });

      const solAmount = result.positionSize / 200; // rough USD->SOL
      const lamports = Math.floor(solAmount * LAMPORTS_PER_SOL);

      let execResult;
      if (token.source === 'pumpfun') {
        execResult = await executePumpPortalBuy(token.mint, solAmount);
      } else {
        execResult = await executeJupiterSwap(WSOL_MINT.toBase58(), token.mint, lamports);
      }

      if (execResult.success) {
        execResult.priceUsd = result.signal.priceUsd;

        await this.positionManager.openPosition(
          execResult,
          result.safety,
          token.symbol,
          result.stopLossPct,
          result.takeProfitPct,
        );

        log.info('TRADE OPENED', {
          mint: token.mint.slice(0, 8),
          symbol: token.symbol,
          sig: execResult.signature?.slice(0, 16),
          mode: execResult.mode,
        });

        // Broadcast to WebSocket clients
        this.apiServer?.broadcast('trade', {
          mint: token.mint,
          symbol: token.symbol,
          source: token.source,
          mode: execResult.mode,
          timestamp: Date.now(),
        });
      } else {
        log.error('TRADE FAILED', { error: execResult.error });
      }
    } catch (err) {
      log.error('Error processing token', { mint: token.mint.slice(0, 8), error: (err as Error).message });
    }
  }

  private reportStats(): void {
    const positions = this.positionManager.getAllOpen();
    const totalPnl = this.positionManager.getTotalUnrealizedPnl();
    const pumpStats = this.pumpFunListener.getStats();

    log.info('─── STATUS REPORT ───', {
      openPositions: positions.length,
      unrealizedPnl: '$' + totalPnl.toFixed(2),
      raydiumPools: this.raydiumListener.getSeenCount(),
      pumpTokens: pumpStats.seenTokens,
      processedTotal: this.processedTokens.size,
      mode: config.tradingMode,
    });
  }

  async stop(): Promise<void> {
    log.info('Shutting down...');
    this.isRunning = false;

    if (this.statsInterval) clearInterval(this.statsInterval);

    await Promise.all([
      this.raydiumListener.stop(),
      this.pumpFunListener.stop(),
      this.twitterListener.stop(),
    ]);

    this.stopLossMonitor.stop();
    this.positionManager.stopPriceMonitor();
    this.apiServer?.close();

    log.info('Shutdown complete');
  }
}

// ─── Main Entry Point ────────────────────────────────────────
async function main(): Promise<void> {
  const supervisor = new Supervisor();

  // Handle graceful shutdown
  process.on('SIGINT', async () => {
    log.info('Received SIGINT');
    await supervisor.stop();
    process.exit(0);
  });

  process.on('SIGTERM', async () => {
    log.info('Received SIGTERM');
    await supervisor.stop();
    process.exit(0);
  });

  process.on('uncaughtException', (err) => {
    log.error('Uncaught exception', { error: err.message, stack: err.stack });
  });

  process.on('unhandledRejection', (err) => {
    log.error('Unhandled rejection', { error: String(err) });
  });

  await supervisor.start();
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
