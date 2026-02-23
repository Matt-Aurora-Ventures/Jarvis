import http from 'http';
import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import { getDb } from '../utils/database.js';
import { createModuleLogger } from '../utils/logger.js';
import { config } from '../config/index.js';

const log = createModuleLogger('api-server');

// ─── Security: generate a session token if none configured ──
const API_TOKEN = process.env.API_TOKEN || crypto.randomBytes(32).toString('hex');

interface ApiServer {
  httpServer: http.Server;
  wss: WebSocketServer;
  broadcast: (event: string, data: unknown) => void;
  close: () => void;
  token: string;
}

// ─── Rate limiter ───────────────────────────────────────────
const rateLimitMap = new Map<string, { count: number; resetAt: number }>();
const RATE_LIMIT = 60; // requests per window
const RATE_WINDOW = 60_000; // 1 minute

function isRateLimited(ip: string): boolean {
  const now = Date.now();
  const entry = rateLimitMap.get(ip);
  if (!entry || now > entry.resetAt) {
    rateLimitMap.set(ip, { count: 1, resetAt: now + RATE_WINDOW });
    return false;
  }
  entry.count++;
  return entry.count > RATE_LIMIT;
}

// ─── Auth check ─────────────────────────────────────────────
function isAuthorized(req: http.IncomingMessage): boolean {
  // Bearer token in Authorization header
  const auth = req.headers.authorization;
  if (auth?.startsWith('Bearer ') && auth.slice(7) === API_TOKEN) return true;
  // Fallback: token query param
  const url = new URL(req.url ?? '/', `http://${req.headers.host}`);
  if (url.searchParams.get('token') === API_TOKEN) return true;
  return false;
}

// ─── REST API handlers ──────────────────────────────────────
function handleApi(req: http.IncomingMessage, res: http.ServerResponse): void {
  const clientIp = req.socket.remoteAddress ?? 'unknown';

  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', 'http://localhost:3000');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // Rate limiting
  if (isRateLimited(clientIp)) {
    res.writeHead(429);
    sendJson(res, { error: 'Too many requests' });
    return;
  }

  const url = new URL(req.url ?? '/', `http://${req.headers.host}`);
  const pathname = url.pathname;

  // Health endpoint is public
  if (pathname === '/api/health') {
    sendJson(res, { status: 'ok', timestamp: Date.now() });
    return;
  }

  // All other endpoints require auth
  if (!isAuthorized(req)) {
    res.writeHead(401);
    sendJson(res, { error: 'Unauthorized' });
    return;
  }

  try {
    const db = getDb();

    if (pathname === '/api/stats') {
      const trades = db.prepare(`SELECT COUNT(*) as total, SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins FROM trades WHERE status = 'EXECUTED'`).get() as { total: number; wins: number } | undefined;
      const positions = db.prepare(`SELECT COUNT(*) as count, SUM(amount_usd + unrealized_pnl) as value FROM positions WHERE status = 'OPEN'`).get() as { count: number; value: number } | undefined;
      const pnl = db.prepare(`SELECT SUM(pnl_usd) as total, MAX(pnl_usd) as best, MIN(pnl_usd) as worst FROM trades WHERE status = 'EXECUTED'`).get() as { total: number; best: number; worst: number } | undefined;
      const today = new Date().toISOString().split('T')[0];
      const todayStats = db.prepare(`SELECT COUNT(*) as trades, SUM(pnl_usd) as pnl FROM trades WHERE date(entry_at/1000, 'unixepoch') = ?`).get(today) as { trades: number; pnl: number } | undefined;

      const total = trades?.total ?? 0;
      const wins = trades?.wins ?? 0;

      sendJson(res, {
        totalTrades: total, wins, losses: total - wins,
        winRate: total > 0 ? wins / total : 0,
        totalPnlUsd: pnl?.total ?? 0,
        openPositions: positions?.count ?? 0,
        totalValueUsd: positions?.value ?? 0,
        bestTradePnl: pnl?.best ?? 0,
        worstTradePnl: pnl?.worst ?? 0,
        todayPnl: todayStats?.pnl ?? 0,
        todayTrades: todayStats?.trades ?? 0,
      });

    } else if (pathname === '/api/trades') {
      const rawLimit = parseInt(url.searchParams.get('limit') ?? '30', 10);
      const limit = Number.isFinite(rawLimit) ? Math.min(Math.max(1, rawLimit), 100) : 30;
      sendJson(res, db.prepare('SELECT * FROM trades ORDER BY entry_at DESC LIMIT ?').all(limit));

    } else if (pathname === '/api/positions') {
      sendJson(res, db.prepare(`SELECT * FROM positions WHERE status = 'OPEN' ORDER BY opened_at DESC`).all());

    } else if (pathname === '/api/strategies') {
      sendJson(res, db.prepare('SELECT * FROM strategy_performance ORDER BY win_rate DESC').all());

    } else if (pathname === '/api/pnl-history') {
      const rows = db.prepare(`
        SELECT date(entry_at/1000, 'unixepoch') as date, SUM(pnl_usd) as pnl
        FROM trades WHERE status = 'EXECUTED' AND pnl_usd IS NOT NULL
        GROUP BY date(entry_at/1000, 'unixepoch') ORDER BY date ASC
      `).all() as Array<{ date: string; pnl: number }>;
      let cumulative = 0;
      sendJson(res, rows.map(r => { cumulative += r.pnl; return { date: r.date, pnl: r.pnl, cumulative }; }));

    } else if (pathname === '/api/backtest-results') {
      sendJson(res, db.prepare('SELECT * FROM strategy_performance ORDER BY win_rate DESC LIMIT 50').all());

    } else if (pathname === '/api/optimization-log') {
      const logPath = path.resolve(process.cwd(), 'winning', 'improvement-log.json');
      if (fs.existsSync(logPath)) {
        sendJson(res, JSON.parse(fs.readFileSync(logPath, 'utf8')));
      } else {
        sendJson(res, []);
      }

    } else if (pathname === '/api/best-config') {
      const cfgPath = path.resolve(process.cwd(), 'winning', 'best-config.json');
      if (fs.existsSync(cfgPath)) {
        sendJson(res, JSON.parse(fs.readFileSync(cfgPath, 'utf8')));
      } else {
        sendJson(res, null);
      }

    } else {
      res.writeHead(404);
      sendJson(res, { error: 'Not found' });
    }
  } catch (err) {
    log.error('API error', { error: (err as Error).message, path: pathname });
    res.writeHead(500);
    sendJson(res, { error: 'Internal server error' });
  }
}

function sendJson(res: http.ServerResponse, data: unknown): void {
  if (!res.headersSent) res.writeHead(200);
  res.end(JSON.stringify(data));
}

// ─── WebSocket server ───────────────────────────────────────
const MAX_WS_CLIENTS = 10;

export function createApiServer(port: number = 3001): ApiServer {
  const httpServer = http.createServer(handleApi);

  const wss = new WebSocketServer({
    server: httpServer,
    maxPayload: 1024 * 64, // 64KB max message
  });

  const clients = new Set<WebSocket>();

  wss.on('connection', (ws, req) => {
    // Auth: check token in query string
    const url = new URL(req.url ?? '/', `http://${req.headers.host}`);
    if (url.searchParams.get('token') !== API_TOKEN) {
      ws.close(4001, 'Unauthorized');
      return;
    }

    // Connection limit
    if (clients.size >= MAX_WS_CLIENTS) {
      ws.close(4002, 'Max connections reached');
      return;
    }

    clients.add(ws);
    log.info('WebSocket client connected', { total: clients.size });

    // Heartbeat
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.ping();
    }, 30_000);

    ws.on('close', () => {
      clearInterval(pingInterval);
      clients.delete(ws);
    });

    ws.on('error', (err) => {
      log.warn('WebSocket error', { error: err.message });
      clearInterval(pingInterval);
      clients.delete(ws);
    });

    // Send initial positions
    try {
      const db = getDb();
      const positions = db.prepare(`SELECT * FROM positions WHERE status = 'OPEN'`).all();
      ws.send(JSON.stringify({ event: 'positions', data: positions }));
    } catch { /* ignore */ }
  });

  function broadcast(event: string, data: unknown): void {
    const msg = JSON.stringify({ event, data, timestamp: Date.now() });
    for (const client of clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(msg);
      }
    }
  }

  // Bind to localhost only
  httpServer.listen(port, '127.0.0.1', () => {
    log.info(`API server listening on 127.0.0.1:${port}`);
    log.info(`API token: ${API_TOKEN.slice(0, 8)}...`);
  });

  return {
    httpServer, wss, broadcast, token: API_TOKEN,
    close: () => {
      for (const client of clients) client.close();
      wss.close();
      httpServer.close();
    },
  };
}
