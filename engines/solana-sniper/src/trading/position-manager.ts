import { createModuleLogger } from '../utils/logger.js';
import { getOpenPositions, insertPosition, updatePositionPrice, closePosition } from '../utils/database.js';
import { getDexScreenerPrice, getTokenPrice } from './jupiter-swap.js';
import type { Position, ExecutionResult, SafetyResult } from '../types/index.js';

const log = createModuleLogger('positions');

export class PositionManager {
  private positions: Map<string, Position> = new Map();
  private priceUpdateInterval: ReturnType<typeof setInterval> | null = null;

  async loadOpenPositions(): Promise<void> {
    const positions = getOpenPositions();
    for (const pos of positions) {
      this.positions.set(pos.id, pos);
    }
    log.info('Loaded positions', { count: this.positions.size });
  }

  getOpenCount(): number {
    return this.positions.size;
  }

  getAllOpen(): Position[] {
    return Array.from(this.positions.values());
  }

  getByMint(mint: string): Position | undefined {
    return Array.from(this.positions.values()).find(p => p.mint === mint);
  }

  async openPosition(
    exec: ExecutionResult,
    safety: SafetyResult,
    symbol: string,
    stopLossPct: number,
    takeProfitPct: number,
  ): Promise<Position> {
    const priceData = await getDexScreenerPrice(exec.mint);
    const price = priceData.price || exec.priceUsd;

    const pos = insertPosition({
      mint: exec.mint,
      symbol,
      status: 'OPEN',
      side: 'BUY',
      entryPrice: price,
      currentPrice: price,
      amount: exec.amountOut,
      amountUsd: exec.amountIn * 200, // rough SOL->USD
      unrealizedPnl: 0,
      unrealizedPnlPct: 0,
      stopLossPct,
      takeProfitPct,
      entrySignature: exec.signature,
      exitSignature: null,
      safetyScore: safety.overallScore,
      openedAt: Date.now(),
      closedAt: null,
      exitReason: null,
    });

    this.positions.set(pos.id, pos);
    log.info('Position opened', {
      id: pos.id.slice(0, 8),
      mint: pos.mint.slice(0, 8),
      symbol: pos.symbol,
      usd: pos.amountUsd.toFixed(2),
      sl: stopLossPct + '%',
      tp: takeProfitPct + '%',
    });

    return pos;
  }

  async updatePrices(): Promise<Array<{ position: Position; action: 'STOP_LOSS' | 'TAKE_PROFIT' | null }>> {
    const actions: Array<{ position: Position; action: 'STOP_LOSS' | 'TAKE_PROFIT' | null }> = [];

    for (const [id, pos] of this.positions) {
      try {
        const price = await getTokenPrice(pos.mint);
        if (price <= 0) continue;

        const pnlPct = ((price - pos.entryPrice) / pos.entryPrice) * 100;
        const pnlUsd = pos.amountUsd * (pnlPct / 100);

        pos.currentPrice = price;
        pos.unrealizedPnl = pnlUsd;
        pos.unrealizedPnlPct = pnlPct;

        updatePositionPrice(id, price, pnlUsd, pnlPct);

        // Check stop loss
        if (pnlPct <= -pos.stopLossPct) {
          actions.push({ position: pos, action: 'STOP_LOSS' });
        }
        // Check take profit
        else if (pnlPct >= pos.takeProfitPct) {
          actions.push({ position: pos, action: 'TAKE_PROFIT' });
        } else {
          actions.push({ position: pos, action: null });
        }
      } catch (err) {
        log.warn('Price update failed', { mint: pos.mint.slice(0, 8), error: (err as Error).message });
      }
    }

    return actions;
  }

  async closePositionById(id: string, reason: string, exitSig?: string): Promise<void> {
    const pos = this.positions.get(id);
    if (!pos) return;

    closePosition(id, reason, exitSig);
    this.positions.delete(id);

    log.info('Position closed', {
      id: id.slice(0, 8),
      mint: pos.mint.slice(0, 8),
      symbol: pos.symbol,
      pnl: pos.unrealizedPnl.toFixed(2),
      pnlPct: pos.unrealizedPnlPct.toFixed(1) + '%',
      reason,
    });
  }

  startPriceMonitor(intervalMs: number = 2000): void {
    if (this.priceUpdateInterval) return;
    this.priceUpdateInterval = setInterval(async () => {
      if (this.positions.size === 0) return;
      await this.updatePrices();
    }, intervalMs);
    log.info('Price monitor started', { intervalMs });
  }

  stopPriceMonitor(): void {
    if (this.priceUpdateInterval) {
      clearInterval(this.priceUpdateInterval);
      this.priceUpdateInterval = null;
      log.info('Price monitor stopped');
    }
  }

  getTotalUnrealizedPnl(): number {
    return Array.from(this.positions.values()).reduce((sum, p) => sum + p.unrealizedPnl, 0);
  }

  getTotalValue(): number {
    return Array.from(this.positions.values()).reduce((sum, p) => sum + p.amountUsd + p.unrealizedPnl, 0);
  }
}
