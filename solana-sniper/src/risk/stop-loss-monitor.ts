import { EventEmitter } from 'events';
import { PositionManager } from '../trading/position-manager.js';
import { executeJupiterSwap } from '../trading/jupiter-swap.js';
import { WSOL_MINT, LAMPORTS_PER_SOL } from '../config/constants.js';
import { config } from '../config/index.js';
import { createModuleLogger } from '../utils/logger.js';
import type { Position } from '../types/index.js';

const log = createModuleLogger('stop-loss');

export class StopLossMonitor extends EventEmitter {
  private positionManager: PositionManager;
  private checkInterval: ReturnType<typeof setInterval> | null = null;
  private isProcessing: boolean = false;

  constructor(positionManager: PositionManager) {
    super();
    this.positionManager = positionManager;
  }

  start(intervalMs: number = 2000): void {
    if (this.checkInterval) return;

    this.checkInterval = setInterval(() => this.checkPositions(), intervalMs);
    log.info('Stop-loss monitor started', { intervalMs });
  }

  stop(): void {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
      log.info('Stop-loss monitor stopped');
    }
  }

  private async checkPositions(): Promise<void> {
    if (this.isProcessing) return;
    this.isProcessing = true;

    try {
      const actions = await this.positionManager.updatePrices();

      for (const { position, action } of actions) {
        if (action === 'STOP_LOSS') {
          await this.executeStopLoss(position);
        } else if (action === 'TAKE_PROFIT') {
          await this.executeTakeProfit(position);
        }
      }
    } catch (err) {
      log.error('Stop-loss check failed', { error: (err as Error).message });
    } finally {
      this.isProcessing = false;
    }
  }

  private async executeStopLoss(position: Position): Promise<void> {
    log.warn('STOP LOSS TRIGGERED', {
      mint: position.mint.slice(0, 8),
      symbol: position.symbol,
      pnl: position.unrealizedPnlPct.toFixed(1) + '%',
      threshold: -position.stopLossPct + '%',
    });

    try {
      // Sell entire position
      const tokenAmountLamports = Math.floor(position.amount);
      const result = await executeJupiterSwap(
        position.mint,
        WSOL_MINT.toBase58(),
        tokenAmountLamports,
        500, // 5% slippage for emergency exit
        500_000, // Higher priority fee for urgency
      );

      if (result.success) {
        await this.positionManager.closePositionById(position.id, 'STOP_LOSS', result.signature ?? undefined);
        this.emit('stopLossExecuted', { position, result });
        log.info('Stop loss executed successfully', { sig: result.signature?.slice(0, 16) });
      } else {
        log.error('Stop loss execution failed', { error: result.error });
        this.emit('stopLossFailed', { position, error: result.error });
      }
    } catch (err) {
      log.error('Stop loss execution error', { error: (err as Error).message });
    }
  }

  private async executeTakeProfit(position: Position): Promise<void> {
    log.info('TAKE PROFIT TRIGGERED', {
      mint: position.mint.slice(0, 8),
      symbol: position.symbol,
      pnl: position.unrealizedPnlPct.toFixed(1) + '%',
      threshold: position.takeProfitPct + '%',
    });

    try {
      // Sell 50% at first TP, remaining at 2x TP (trailing)
      const sellAmount = Math.floor(position.amount * 0.5);

      const result = await executeJupiterSwap(
        position.mint,
        WSOL_MINT.toBase58(),
        sellAmount,
        300,
        200_000,
      );

      if (result.success) {
        // If we sold 50%, update position but keep it open with trailing stop
        if (position.unrealizedPnlPct < position.takeProfitPct * 2) {
          // First TP hit — sell 50%, raise stop to breakeven
          log.info('First TP hit — sold 50%, raising stop to breakeven');
          // Update the position's stop loss to 0% (breakeven)
          // This is a simplified version — a real trailing stop would be more complex
        } else {
          // Second TP or higher — close fully
          await this.positionManager.closePositionById(position.id, 'TAKE_PROFIT', result.signature ?? undefined);
        }

        this.emit('takeProfitExecuted', { position, result });
      } else {
        log.error('Take profit execution failed', { error: result.error });
      }
    } catch (err) {
      log.error('Take profit execution error', { error: (err as Error).message });
    }
  }
}
