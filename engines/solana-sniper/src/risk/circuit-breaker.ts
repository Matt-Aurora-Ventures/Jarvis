import { config } from '../config/index.js';
import { getSolBalanceUsd } from '../utils/wallet.js';
import { getDailyPnl, getWinRate } from '../utils/database.js';
import { createModuleLogger } from '../utils/logger.js';

const log = createModuleLogger('circuit-breaker');

export interface CircuitBreakerState {
  isTripped: boolean;
  reason: string | null;
  balanceUsd: number;
  dailyPnl: number;
  consecutiveLosses: number;
  lastCheckAt: number;
}

let consecutiveLosses = 0;
let lastTradeWin = true;

export function recordTradeResult(win: boolean): void {
  if (win) {
    consecutiveLosses = 0;
    lastTradeWin = true;
  } else {
    consecutiveLosses++;
    lastTradeWin = false;
  }
}

export async function checkCircuitBreaker(): Promise<CircuitBreakerState> {
  const { risk } = config;

  // 1. Balance floor check
  const balance = await getSolBalanceUsd();
  if (balance.usd <= risk.circuitBreakerFloorUsd) {
    const reason = `BALANCE FLOOR: $${balance.usd.toFixed(2)} <= $${risk.circuitBreakerFloorUsd}`;
    log.error('CIRCUIT BREAKER TRIPPED', { reason });
    return {
      isTripped: true,
      reason,
      balanceUsd: balance.usd,
      dailyPnl: getDailyPnl(),
      consecutiveLosses,
      lastCheckAt: Date.now(),
    };
  }

  // 2. Daily loss limit
  const dailyPnl = getDailyPnl();
  if (dailyPnl <= -risk.maxDailyLossUsd) {
    const reason = `DAILY LOSS: $${Math.abs(dailyPnl).toFixed(2)} exceeds $${risk.maxDailyLossUsd} limit`;
    log.error('CIRCUIT BREAKER TRIPPED', { reason });
    return {
      isTripped: true,
      reason,
      balanceUsd: balance.usd,
      dailyPnl,
      consecutiveLosses,
      lastCheckAt: Date.now(),
    };
  }

  // 3. Consecutive loss limit (5 in a row = stop)
  if (consecutiveLosses >= 5) {
    const reason = `LOSING STREAK: ${consecutiveLosses} consecutive losses`;
    log.error('CIRCUIT BREAKER TRIPPED', { reason });
    return {
      isTripped: true,
      reason,
      balanceUsd: balance.usd,
      dailyPnl,
      consecutiveLosses,
      lastCheckAt: Date.now(),
    };
  }

  // 4. Win rate check — if we have 10+ trades and win rate < 20%, stop
  const stats = getWinRate();
  if (stats.total >= 10 && stats.rate < 0.20) {
    const reason = `LOW WIN RATE: ${(stats.rate * 100).toFixed(0)}% over ${stats.total} trades`;
    log.error('CIRCUIT BREAKER TRIPPED', { reason });
    return {
      isTripped: true,
      reason,
      balanceUsd: balance.usd,
      dailyPnl,
      consecutiveLosses,
      lastCheckAt: Date.now(),
    };
  }

  return {
    isTripped: false,
    reason: null,
    balanceUsd: balance.usd,
    dailyPnl,
    consecutiveLosses,
    lastCheckAt: Date.now(),
  };
}

export function resetCircuitBreaker(): void {
  consecutiveLosses = 0;
  lastTradeWin = true;
  log.info('Circuit breaker reset');
}
