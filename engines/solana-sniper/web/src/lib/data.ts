import Database from 'better-sqlite3';
import path from 'path';

function getDb() {
  const dbPath = path.resolve(process.cwd(), '..', 'winning', 'trades.db');
  const db = new Database(dbPath, { readonly: true });
  db.pragma('journal_mode = WAL');
  return db;
}

export interface DashboardStats {
  totalTrades: number;
  wins: number;
  losses: number;
  winRate: number;
  totalPnlUsd: number;
  openPositions: number;
  totalValueUsd: number;
  bestTradePnl: number;
  worstTradePnl: number;
  todayPnl: number;
  todayTrades: number;
}

export interface TradeRow {
  id: string;
  mint: string;
  symbol: string;
  side: string;
  amount_usd: number;
  price_usd: number;
  safety_score: number;
  status: string;
  mode: string;
  pnl_usd: number | null;
  pnl_pct: number | null;
  entry_at: number;
  exit_at: number | null;
  exit_reason: string | null;
}

export interface PositionRow {
  id: string;
  mint: string;
  symbol: string;
  status: string;
  entry_price: number;
  current_price: number;
  amount_usd: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  safety_score: number;
  opened_at: number;
}

export interface StrategyRow {
  strategy: string;
  win_rate: number;
  avg_pnl_pct: number;
  trades_count: number;
  total_pnl_usd: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
}

export function getStats(): DashboardStats {
  try {
    const db = getDb();

    const trades = db.prepare('SELECT COUNT(*) as total, SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins FROM trades WHERE status = ?').get('EXECUTED') as { total: number; wins: number } | undefined;
    const positions = db.prepare('SELECT COUNT(*) as count, SUM(amount_usd + unrealized_pnl) as value FROM positions WHERE status = ?').get('OPEN') as { count: number; value: number } | undefined;
    const pnl = db.prepare('SELECT SUM(pnl_usd) as total, MAX(pnl_usd) as best, MIN(pnl_usd) as worst FROM trades WHERE status = ?').get('EXECUTED') as { total: number; best: number; worst: number } | undefined;

    const today = new Date().toISOString().split('T')[0];
    const todayStats = db.prepare("SELECT COUNT(*) as trades, SUM(pnl_usd) as pnl FROM trades WHERE date(entry_at/1000, 'unixepoch') = ?").get(today) as { trades: number; pnl: number } | undefined;

    const total = trades?.total ?? 0;
    const wins = trades?.wins ?? 0;

    db.close();

    return {
      totalTrades: total,
      wins,
      losses: total - wins,
      winRate: total > 0 ? wins / total : 0,
      totalPnlUsd: pnl?.total ?? 0,
      openPositions: positions?.count ?? 0,
      totalValueUsd: positions?.value ?? 0,
      bestTradePnl: pnl?.best ?? 0,
      worstTradePnl: pnl?.worst ?? 0,
      todayPnl: todayStats?.pnl ?? 0,
      todayTrades: todayStats?.trades ?? 0,
    };
  } catch {
    return {
      totalTrades: 0, wins: 0, losses: 0, winRate: 0,
      totalPnlUsd: 0, openPositions: 0, totalValueUsd: 0,
      bestTradePnl: 0, worstTradePnl: 0, todayPnl: 0, todayTrades: 0,
    };
  }
}

export function getRecentTrades(limit: number = 20): TradeRow[] {
  try {
    const db = getDb();
    const rows = db.prepare('SELECT * FROM trades ORDER BY entry_at DESC LIMIT ?').all(limit) as TradeRow[];
    db.close();
    return rows;
  } catch {
    return [];
  }
}

export function getOpenPositions(): PositionRow[] {
  try {
    const db = getDb();
    const rows = db.prepare("SELECT * FROM positions WHERE status = 'OPEN' ORDER BY opened_at DESC").all() as PositionRow[];
    db.close();
    return rows;
  } catch {
    return [];
  }
}

export function getStrategyPerformance(): StrategyRow[] {
  try {
    const db = getDb();
    const rows = db.prepare('SELECT * FROM strategy_performance ORDER BY win_rate DESC').all() as StrategyRow[];
    db.close();
    return rows;
  } catch {
    return [];
  }
}

export interface BacktestRun {
  timestamp: string;
  iterations: number;
  bestWinRate: number;
  bestPnl: number;
  top5: Array<{
    winRate: number;
    pnl: number;
    sharpe: number;
    config: Record<string, unknown>;
  }>;
}

export interface BestConfig {
  config: Record<string, unknown>;
  winRate: number;
  pnl: number;
  sharpe: number;
  savedAt: string;
}

export function getBacktestHistory(): BacktestRun[] {
  try {
    const fs = require('fs');
    const p = require('path');
    const logPath = p.resolve(process.cwd(), '..', 'winning', 'improvement-log.json');
    if (fs.existsSync(logPath)) {
      return JSON.parse(fs.readFileSync(logPath, 'utf8'));
    }
    return [];
  } catch {
    return [];
  }
}

export function getBestConfig(): BestConfig | null {
  try {
    const fs = require('fs');
    const p = require('path');
    const cfgPath = p.resolve(process.cwd(), '..', 'winning', 'best-config.json');
    if (fs.existsSync(cfgPath)) {
      return JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
    }
    return null;
  } catch {
    return null;
  }
}

export function getOptimizationLog(): BacktestRun[] {
  return getBacktestHistory();
}

export function getPnlHistory(): Array<{ date: string; pnl: number; cumulative: number }> {
  try {
    const db = getDb();
    const rows = db.prepare(`
      SELECT date(entry_at/1000, 'unixepoch') as date, SUM(pnl_usd) as pnl
      FROM trades WHERE status = 'EXECUTED' AND pnl_usd IS NOT NULL
      GROUP BY date(entry_at/1000, 'unixepoch')
      ORDER BY date ASC
    `).all() as Array<{ date: string; pnl: number }>;
    db.close();

    let cumulative = 0;
    return rows.map(r => {
      cumulative += r.pnl;
      return { date: r.date, pnl: r.pnl, cumulative };
    });
  } catch {
    return [];
  }
}
