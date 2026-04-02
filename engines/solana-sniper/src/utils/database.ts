import Database from 'better-sqlite3';
import path from 'path';
import { randomUUID } from 'crypto';
import type { TradeRecord, Position } from '../types/index.js';
import { createModuleLogger } from './logger.js';

const log = createModuleLogger('database');

let db: Database.Database;

export function getDb(): Database.Database {
  if (!db) {
    const dbPath = path.resolve(process.cwd(), 'winning', 'trades.db');
    db = new Database(dbPath);
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
    initSchema();
    log.info('Database initialized', { path: dbPath });
  }
  return db;
}

function initSchema(): void {
  const d = getDb();
  d.exec(`
    CREATE TABLE IF NOT EXISTS trades (
      id TEXT PRIMARY KEY,
      mint TEXT NOT NULL,
      symbol TEXT NOT NULL,
      side TEXT NOT NULL,
      amount_usd REAL NOT NULL,
      amount_token REAL NOT NULL,
      price_usd REAL NOT NULL,
      safety_score REAL NOT NULL,
      signature TEXT,
      status TEXT NOT NULL,
      mode TEXT NOT NULL,
      pnl_usd REAL,
      pnl_pct REAL,
      entry_at INTEGER NOT NULL,
      exit_at INTEGER,
      exit_reason TEXT,
      metadata TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS positions (
      id TEXT PRIMARY KEY,
      mint TEXT NOT NULL,
      symbol TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'OPEN',
      side TEXT NOT NULL,
      entry_price REAL NOT NULL,
      current_price REAL NOT NULL,
      amount REAL NOT NULL,
      amount_usd REAL NOT NULL,
      unrealized_pnl REAL DEFAULT 0,
      unrealized_pnl_pct REAL DEFAULT 0,
      stop_loss_pct REAL NOT NULL,
      take_profit_pct REAL NOT NULL,
      entry_signature TEXT,
      exit_signature TEXT,
      safety_score REAL NOT NULL,
      opened_at INTEGER NOT NULL,
      closed_at INTEGER,
      exit_reason TEXT
    );

    CREATE TABLE IF NOT EXISTS daily_stats (
      date TEXT PRIMARY KEY,
      total_trades INTEGER DEFAULT 0,
      wins INTEGER DEFAULT 0,
      losses INTEGER DEFAULT 0,
      total_pnl_usd REAL DEFAULT 0,
      total_volume_usd REAL DEFAULT 0,
      best_trade_pnl REAL DEFAULT 0,
      worst_trade_pnl REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS strategy_performance (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      strategy TEXT NOT NULL,
      signal_source TEXT NOT NULL,
      trades_count INTEGER DEFAULT 0,
      win_rate REAL DEFAULT 0,
      avg_pnl_pct REAL DEFAULT 0,
      total_pnl_usd REAL DEFAULT 0,
      sharpe_ratio REAL DEFAULT 0,
      max_drawdown_pct REAL DEFAULT 0,
      updated_at INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_trades_mint ON trades(mint);
    CREATE INDEX IF NOT EXISTS idx_trades_entry ON trades(entry_at);
    CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
    CREATE INDEX IF NOT EXISTS idx_positions_mint ON positions(mint);
  `);
}

// ─── Trade Operations ─────────────────────────────────────────
export function insertTrade(trade: Omit<TradeRecord, 'id'>): TradeRecord {
  const d = getDb();
  const id = randomUUID();
  d.prepare(`
    INSERT INTO trades (id, mint, symbol, side, amount_usd, amount_token, price_usd,
      safety_score, signature, status, mode, pnl_usd, pnl_pct, entry_at, exit_at, exit_reason, metadata)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    id, trade.mint, trade.symbol, trade.side, trade.amountUsd, trade.amountToken,
    trade.priceUsd, trade.safetyScore, trade.signature, trade.status, trade.mode,
    trade.pnlUsd, trade.pnlPct, trade.entryAt, trade.exitAt, trade.exitReason, trade.metadata
  );
  return { ...trade, id };
}

export function updateTradeExit(id: string, pnlUsd: number, pnlPct: number, exitReason: string, signature?: string): void {
  const d = getDb();
  d.prepare(`
    UPDATE trades SET pnl_usd = ?, pnl_pct = ?, exit_at = ?, exit_reason = ?, status = 'EXECUTED',
      signature = COALESCE(?, signature)
    WHERE id = ?
  `).run(pnlUsd, pnlPct, Date.now(), exitReason, signature ?? null, id);
}

export function getOpenPositions(): Position[] {
  const d = getDb();
  return d.prepare(`SELECT * FROM positions WHERE status = 'OPEN'`).all() as Position[];
}

export function insertPosition(pos: Omit<Position, 'id'>): Position {
  const d = getDb();
  const id = randomUUID();
  d.prepare(`
    INSERT INTO positions (id, mint, symbol, status, side, entry_price, current_price, amount,
      amount_usd, unrealized_pnl, unrealized_pnl_pct, stop_loss_pct, take_profit_pct,
      entry_signature, exit_signature, safety_score, opened_at, closed_at, exit_reason)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    id, pos.mint, pos.symbol, pos.status, pos.side, pos.entryPrice, pos.currentPrice,
    pos.amount, pos.amountUsd, pos.unrealizedPnl, pos.unrealizedPnlPct,
    pos.stopLossPct, pos.takeProfitPct, pos.entrySignature, pos.exitSignature,
    pos.safetyScore, pos.openedAt, pos.closedAt, pos.exitReason
  );
  return { ...pos, id };
}

export function updatePositionPrice(id: string, price: number, pnl: number, pnlPct: number): void {
  const d = getDb();
  d.prepare(`UPDATE positions SET current_price = ?, unrealized_pnl = ?, unrealized_pnl_pct = ? WHERE id = ?`)
    .run(price, pnl, pnlPct, id);
}

export function closePosition(id: string, reason: string, exitSig?: string): void {
  const d = getDb();
  const status = reason === 'STOP_LOSS' ? 'STOPPED_OUT' : reason === 'TAKE_PROFIT' ? 'TP_HIT' : 'CLOSED';
  d.prepare(`UPDATE positions SET status = ?, closed_at = ?, exit_reason = ?, exit_signature = ? WHERE id = ?`)
    .run(status, Date.now(), reason, exitSig ?? null, id);
}

// ─── Stats ────────────────────────────────────────────────────
export function getDailyPnl(): number {
  const d = getDb();
  const today = new Date().toISOString().split('T')[0];
  const row = d.prepare(`SELECT SUM(pnl_usd) as total FROM trades WHERE date(entry_at/1000, 'unixepoch') = ?`).get(today) as { total: number | null };
  return row?.total ?? 0;
}

export function getWinRate(): { total: number; wins: number; rate: number } {
  const d = getDb();
  const rows = d.prepare(`SELECT COUNT(*) as total, SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins FROM trades WHERE status = 'EXECUTED'`).get() as { total: number; wins: number };
  return { total: rows.total, wins: rows.wins ?? 0, rate: rows.total > 0 ? (rows.wins ?? 0) / rows.total : 0 };
}

export function getStrategyPerformance(): Array<{ strategy: string; winRate: number; avgPnl: number; trades: number }> {
  const d = getDb();
  return d.prepare(`SELECT strategy, win_rate as winRate, avg_pnl_pct as avgPnl, trades_count as trades FROM strategy_performance ORDER BY win_rate DESC`).all() as Array<{ strategy: string; winRate: number; avgPnl: number; trades: number }>;
}
