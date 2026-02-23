import WebSocket from 'ws';
import { EventEmitter } from 'events';
import { config } from '../config/index.js';
import { createModuleLogger } from '../utils/logger.js';
import type { NewPoolEvent } from '../types/index.js';

const log = createModuleLogger('pumpfun-listener');

interface PumpFunNewTokenEvent {
  signature: string;
  mint: string;
  traderPublicKey: string;
  txType: 'create';
  initialBuy: number;
  bondingCurveKey: string;
  vTokensInBondingCurve: number;
  vSolInBondingCurve: number;
  marketCapSol: number;
  name: string;
  symbol: string;
  uri: string;
}

interface PumpFunTradeEvent {
  signature: string;
  mint: string;
  traderPublicKey: string;
  txType: 'buy' | 'sell';
  tokenAmount: number;
  newTokenBalance: number;
  bondingCurveKey: string;
  vTokensInBondingCurve: number;
  vSolInBondingCurve: number;
  marketCapSol: number;
}

export class PumpFunListener extends EventEmitter {
  private ws: WebSocket | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnects: number = 10;
  private reconnectDelay: number = 1000;
  private isRunning: boolean = false;
  private seenTokens: Set<string> = new Set();
  private tokenTrades: Map<string, { buys: number; sells: number; volume: number }> = new Map();

  async start(): Promise<void> {
    this.isRunning = true;
    this.connect();
  }

  private connect(): void {
    if (!this.isRunning) return;

    const wsUrl = config.pumpPortalWsUrl;
    log.info('Connecting to PumpPortal WebSocket...', { url: wsUrl });

    this.ws = new WebSocket(wsUrl);

    this.ws.on('open', () => {
      log.info('PumpPortal WebSocket connected');
      this.reconnectAttempts = 0;

      // Subscribe to new token creations
      this.ws?.send(JSON.stringify({
        method: 'subscribeNewToken',
      }));

      log.info('Subscribed to new token events');
    });

    this.ws.on('message', (data: WebSocket.Data) => {
      try {
        const msg = JSON.parse(data.toString());
        this.handleMessage(msg);
      } catch (err) {
        log.error('Failed to parse WebSocket message', { error: (err as Error).message });
      }
    });

    this.ws.on('close', (code, reason) => {
      log.warn('PumpPortal WebSocket closed', { code, reason: reason.toString() });
      this.attemptReconnect();
    });

    this.ws.on('error', (err) => {
      log.error('PumpPortal WebSocket error', { error: err.message });
    });
  }

  private handleMessage(msg: PumpFunNewTokenEvent | PumpFunTradeEvent | { method?: string }): void {
    if ('txType' in msg) {
      if (msg.txType === 'create') {
        this.handleNewToken(msg as PumpFunNewTokenEvent);
      } else {
        this.handleTrade(msg as PumpFunTradeEvent);
      }
    }
  }

  private handleNewToken(token: PumpFunNewTokenEvent): void {
    if (this.seenTokens.has(token.mint)) return;
    this.seenTokens.add(token.mint);

    log.info('New pump.fun token detected', {
      mint: token.mint.slice(0, 8),
      name: token.name,
      symbol: token.symbol,
      marketCapSol: token.marketCapSol.toFixed(2),
      initialBuy: token.initialBuy,
    });

    // Subscribe to trades for this token to track momentum
    this.ws?.send(JSON.stringify({
      method: 'subscribeTokenTrade',
      keys: [token.mint],
    }));

    const event: NewPoolEvent = {
      type: 'pumpfun_launch',
      mint: token.mint,
      poolAddress: token.bondingCurveKey,
      baseMint: token.mint,
      quoteMint: 'So11111111111111111111111111111111111111112',
      baseVault: '',
      quoteVault: '',
      lpMint: '',
      timestamp: Date.now(),
      raw: token,
    };

    this.emit('newToken', event);
  }

  private handleTrade(trade: PumpFunTradeEvent): void {
    const existing = this.tokenTrades.get(trade.mint) ?? { buys: 0, sells: 0, volume: 0 };

    if (trade.txType === 'buy') {
      existing.buys++;
    } else {
      existing.sells++;
    }
    existing.volume += trade.vSolInBondingCurve;
    this.tokenTrades.set(trade.mint, existing);

    // Emit momentum signal when buy pressure is strong
    if (existing.buys >= 5 && existing.buys > existing.sells * 2) {
      this.emit('momentum', {
        mint: trade.mint,
        buys: existing.buys,
        sells: existing.sells,
        ratio: existing.buys / Math.max(1, existing.sells),
        marketCapSol: trade.marketCapSol,
      });
    }
  }

  private attemptReconnect(): void {
    if (!this.isRunning) return;
    if (this.reconnectAttempts >= this.maxReconnects) {
      log.error('Max reconnect attempts reached, stopping PumpFun listener');
      this.isRunning = false;
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    log.info('Reconnecting in ' + delay + 'ms', { attempt: this.reconnectAttempts });

    setTimeout(() => this.connect(), delay);
  }

  async stop(): Promise<void> {
    this.isRunning = false;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    log.info('PumpFun listener stopped');
  }

  getStats(): { seenTokens: number; trackedTrades: number } {
    return {
      seenTokens: this.seenTokens.size,
      trackedTrades: this.tokenTrades.size,
    };
  }

  getTokenMomentum(mint: string): { buys: number; sells: number; ratio: number } | null {
    const data = this.tokenTrades.get(mint);
    if (!data) return null;
    return {
      buys: data.buys,
      sells: data.sells,
      ratio: data.buys / Math.max(1, data.sells),
    };
  }
}
