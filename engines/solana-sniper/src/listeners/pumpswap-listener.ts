/**
 * PumpSwap Graduation Listener
 *
 * Monitors pump.fun tokens that graduate from the bonding curve to PumpSwap AMM.
 * Graduation is the optimal snipe window — token transitions from bonding curve
 * to a real liquidity pool with higher volume potential.
 *
 * Listens via:
 * 1. PumpPortal WebSocket for graduation events
 * 2. Helius WebSocket for PumpSwap pool creation txns (backup)
 *
 * Emits:
 * - 'graduation' — token graduated to PumpSwap pool
 * - 'migrationComplete' — liquidity migration finalized
 */
import WebSocket from 'ws';
import { EventEmitter } from 'events';
import { Connection, PublicKey } from '@solana/web3.js';
import axios from 'axios';
import { config } from '../config/index.js';
import { createModuleLogger } from '../utils/logger.js';
import type { NewPoolEvent } from '../types/index.js';

const log = createModuleLogger('pumpswap-listener');

// PumpSwap program IDs
const PUMPSWAP_PROGRAM = 'PSwapMdSai8tjrEXcxFeQth87xC4rRsa4VA5mhGhXkP';
const PUMP_MIGRATION_AUTHORITY = '39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg';

interface GraduationEvent {
  mint: string;
  symbol: string;
  name: string;
  poolAddress: string;
  liquidityUsd: number;
  marketCapUsd: number;
  bondingCurveProgressPct: number;
  migratedAt: number;
  initialBuyerCount: number;
  source: 'pumpportal' | 'helius' | 'polling';
}

interface PumpPortalGradMessage {
  txType: 'migration' | 'create';
  mint?: string;
  pool?: string;
  signature?: string;
  bondingCurveKey?: string;
  vTokensInBondingCurve?: number;
  vSolInBondingCurve?: number;
  marketCapSol?: number;
  name?: string;
  symbol?: string;
}

export class PumpSwapListener extends EventEmitter {
  private portalWs: WebSocket | null = null;
  private heliusWs: WebSocket | null = null;
  private isRunning = false;
  private reconnectAttempts = 0;
  private maxReconnects = 15;
  private seenGraduations: Set<string> = new Set();
  private graduationQueue: GraduationEvent[] = [];
  private pollingInterval: ReturnType<typeof setInterval> | null = null;

  async start(): Promise<void> {
    this.isRunning = true;
    log.info('Starting PumpSwap graduation listener');

    // Method 1: PumpPortal WebSocket (primary)
    this.connectPumpPortal();

    // Method 2: Helius WebSocket for PumpSwap program monitoring (backup)
    if (config.heliusApiKey) {
      this.connectHelius();
    }

    // Method 3: DexScreener polling for recently graduated tokens (fallback)
    this.startGraduationPolling();
  }

  stop(): void {
    this.isRunning = false;
    this.portalWs?.close();
    this.heliusWs?.close();
    if (this.pollingInterval) clearInterval(this.pollingInterval);
    log.info('PumpSwap listener stopped');
  }

  // ─── PumpPortal WebSocket ────────────────────────────────
  private connectPumpPortal(): void {
    if (!this.isRunning) return;

    const wsUrl = config.pumpPortalWsUrl;
    log.info('Connecting to PumpPortal for graduation events...');

    this.portalWs = new WebSocket(wsUrl);

    this.portalWs.on('open', () => {
      log.info('PumpPortal connected for graduation monitoring');
      this.reconnectAttempts = 0;

      // Subscribe to migration/graduation events
      this.portalWs?.send(JSON.stringify({
        method: 'subscribeNewToken',
      }));

      // Also subscribe to account changes for migration authority
      this.portalWs?.send(JSON.stringify({
        method: 'subscribeAccountTrade',
        keys: [PUMP_MIGRATION_AUTHORITY],
      }));
    });

    this.portalWs.on('message', (data: WebSocket.Data) => {
      try {
        const msg = JSON.parse(data.toString());
        this.handlePortalMessage(msg);
      } catch (err) {
        log.debug('Failed to parse PumpPortal message', { error: (err as Error).message });
      }
    });

    this.portalWs.on('close', () => {
      log.warn('PumpPortal WS closed, reconnecting...');
      this.reconnectPortal();
    });

    this.portalWs.on('error', (err) => {
      log.error('PumpPortal WS error', { error: err.message });
    });
  }

  private handlePortalMessage(msg: PumpPortalGradMessage & Record<string, unknown>): void {
    // Detect migration events (token graduating from bonding curve)
    if (msg.txType === 'migration' && msg.mint) {
      this.handleGraduation(msg);
    }

    // Also detect when bonding curve reaches ~100% (pre-graduation signal)
    if (msg.txType === 'create' && msg.vSolInBondingCurve && msg.marketCapSol) {
      // Bonding curve completion is typically around 85 SOL
      const progressPct = (msg.vSolInBondingCurve / 85) * 100;
      if (progressPct >= 90) {
        log.info('Token nearing graduation!', {
          mint: msg.mint?.slice(0, 8),
          progress: progressPct.toFixed(0) + '%',
          marketCap: msg.marketCapSol?.toFixed(1) + ' SOL',
        });
        this.emit('nearGraduation', {
          mint: msg.mint,
          symbol: msg.symbol,
          progressPct,
          marketCapSol: msg.marketCapSol,
        });
      }
    }
  }

  private handleGraduation(msg: PumpPortalGradMessage): void {
    const mint = msg.mint!;
    if (this.seenGraduations.has(mint)) return;
    this.seenGraduations.add(mint);

    const event: GraduationEvent = {
      mint,
      symbol: msg.symbol || mint.slice(0, 6),
      name: msg.name || 'Unknown',
      poolAddress: msg.pool || msg.bondingCurveKey || '',
      liquidityUsd: (msg.vSolInBondingCurve || 0) * 200, // rough SOL-to-USD
      marketCapUsd: (msg.marketCapSol || 0) * 200,
      bondingCurveProgressPct: 100,
      migratedAt: Date.now(),
      initialBuyerCount: 0,
      source: 'pumpportal',
    };

    log.info('TOKEN GRADUATED TO PUMPSWAP!', {
      mint: mint.slice(0, 8),
      symbol: event.symbol,
      liquidity: '$' + event.liquidityUsd.toFixed(0),
      marketCap: '$' + event.marketCapUsd.toFixed(0),
    });

    this.graduationQueue.push(event);
    this.emit('graduation', event);

    // Also emit as NewPoolEvent for the main pipeline
    const poolEvent: NewPoolEvent = {
      type: 'pumpfun_launch',
      mint,
      poolAddress: event.poolAddress,
      baseMint: mint,
      quoteMint: 'So11111111111111111111111111111111111111112',
      baseVault: '',
      quoteVault: '',
      lpMint: '',
      timestamp: Date.now(),
      raw: msg,
    };
    this.emit('newPool', poolEvent);
  }

  private reconnectPortal(): void {
    if (!this.isRunning) return;
    if (this.reconnectAttempts >= this.maxReconnects) {
      log.error('Max PumpPortal reconnect attempts reached');
      return;
    }
    this.reconnectAttempts++;
    const delay = Math.min(30000, 1000 * Math.pow(1.5, this.reconnectAttempts));
    log.info(`Reconnecting PumpPortal in ${(delay / 1000).toFixed(0)}s (attempt ${this.reconnectAttempts})`);
    setTimeout(() => this.connectPumpPortal(), delay);
  }

  // ─── Helius WebSocket (backup) ───────────────────────────
  private connectHelius(): void {
    if (!this.isRunning || !config.heliusApiKey) return;

    const wsUrl = `wss://atlas-mainnet.helius-rpc.com/?api-key=${config.heliusApiKey}`;
    log.info('Connecting to Helius for PumpSwap program monitoring...');

    this.heliusWs = new WebSocket(wsUrl);

    this.heliusWs.on('open', () => {
      log.info('Helius WebSocket connected');

      // Subscribe to PumpSwap program logs
      this.heliusWs?.send(JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'logsSubscribe',
        params: [
          { mentions: [PUMPSWAP_PROGRAM] },
          { commitment: 'confirmed' },
        ],
      }));
    });

    this.heliusWs.on('message', (data: WebSocket.Data) => {
      try {
        const msg = JSON.parse(data.toString());
        if (msg.method === 'logsNotification') {
          this.handleHeliusLog(msg.params?.result?.value);
        }
      } catch {
        // ignore parse errors
      }
    });

    this.heliusWs.on('close', () => {
      if (this.isRunning) {
        log.warn('Helius WS closed, reconnecting in 5s...');
        setTimeout(() => this.connectHelius(), 5000);
      }
    });

    this.heliusWs.on('error', (err) => {
      log.debug('Helius WS error', { error: err.message });
    });
  }

  private handleHeliusLog(logEntry: { signature?: string; logs?: string[] } | undefined): void {
    if (!logEntry?.logs) return;

    // Look for pool creation / migration logs
    const isPoolCreation = logEntry.logs.some(l =>
      l.includes('InitializePool') || l.includes('CreatePool') || l.includes('Migrate'),
    );

    if (isPoolCreation && logEntry.signature) {
      log.info('PumpSwap pool creation detected via Helius', {
        signature: logEntry.signature.slice(0, 16),
      });
      // Parse the transaction for details
      this.parseGraduationTx(logEntry.signature);
    }
  }

  private async parseGraduationTx(signature: string): Promise<void> {
    try {
      const conn = new Connection(config.rpcUrl);
      const tx = await conn.getParsedTransaction(signature, {
        maxSupportedTransactionVersion: 0,
      });

      if (!tx?.meta?.postTokenBalances) return;

      // Find the token mint from token balances
      const tokenMints = tx.meta.postTokenBalances
        .map(b => b.mint)
        .filter(m => m !== 'So11111111111111111111111111111111111111112');

      for (const mint of tokenMints) {
        if (!this.seenGraduations.has(mint)) {
          this.handleGraduation({ txType: 'migration', mint, signature });
        }
      }
    } catch (err) {
      log.debug('Failed to parse graduation tx', { error: (err as Error).message });
    }
  }

  // ─── DexScreener Polling (fallback) ──────────────────────
  private startGraduationPolling(): void {
    // Poll every 30 seconds for recently graduated tokens
    this.pollingInterval = setInterval(async () => {
      try {
        await this.pollRecentGraduations();
      } catch (err) {
        log.debug('Graduation polling failed', { error: (err as Error).message });
      }
    }, 30000);

    // Initial poll
    this.pollRecentGraduations().catch(() => {});
  }

  private async pollRecentGraduations(): Promise<void> {
    try {
      // DexScreener boosted tokens often includes fresh PumpSwap graduates
      const resp = await axios.get(
        'https://api.dexscreener.com/token-boosts/latest/v1',
        { timeout: 8000 },
      );

      const boosts = resp.data ?? [];
      for (const boost of boosts) {
        if (boost.chainId !== 'solana') continue;
        const mint = boost.tokenAddress;
        if (!mint || this.seenGraduations.has(mint)) continue;

        // Check if this is a recent PumpSwap graduation
        if (boost.description?.toLowerCase().includes('pump') || boost.url?.includes('pump.fun')) {
          this.seenGraduations.add(mint);

          const event: GraduationEvent = {
            mint,
            symbol: boost.name || mint.slice(0, 6),
            name: boost.name || 'Unknown',
            poolAddress: '',
            liquidityUsd: 0,
            marketCapUsd: 0,
            bondingCurveProgressPct: 100,
            migratedAt: Date.now(),
            initialBuyerCount: 0,
            source: 'polling',
          };

          log.info('Graduation detected via polling', {
            mint: mint.slice(0, 8),
            symbol: event.symbol,
          });

          this.emit('graduation', event);
        }
      }
    } catch {
      // Rate limited or down, ok
    }
  }

  // ─── Getters ─────────────────────────────────────────────
  getRecentGraduations(limit = 20): GraduationEvent[] {
    return this.graduationQueue.slice(-limit);
  }

  getGraduationCount(): number {
    return this.seenGraduations.size;
  }
}

// ─── Singleton export ──────────────────────────────────────
let instance: PumpSwapListener | null = null;

export function getPumpSwapListener(): PumpSwapListener {
  if (!instance) {
    instance = new PumpSwapListener();
  }
  return instance;
}
