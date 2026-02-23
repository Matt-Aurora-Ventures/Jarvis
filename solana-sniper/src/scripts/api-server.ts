/**
 * Sniper API Server
 *
 * Lightweight HTTP API that the web dashboard calls for:
 * - Safety analysis
 * - Trade execution via Bags API
 * - Stop order monitoring
 * - Trading stats
 *
 * Usage: npx tsx src/scripts/api-server.ts
 */
import http from 'http';
import { URL } from 'url';
import fs from 'fs';
import path from 'path';
import { runSafetyPipeline } from '../safety/composite-scorer.js';
import {
  buyTokenViaBags,
  sellTokenViaBags,
  createStopOrder,
  getActiveOrders,
  cancelOrder,
  checkStopOrders,
} from '../trading/bags-client.js';
import { createModuleLogger } from '../utils/logger.js';
import type { TokenInfo } from '../types/index.js';

const log = createModuleLogger('api-server');
const PORT = parseInt(process.env.SNIPER_API_PORT || '3002', 10);

// ─── Helpers ──────────────────────────────────────────────
function json(res: http.ServerResponse, data: unknown, status = 200): void {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  });
  res.end(JSON.stringify(data));
}

function error(res: http.ServerResponse, msg: string, status = 400): void {
  json(res, { error: msg }, status);
}

async function readBody(req: http.IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(chunk as Buffer);
  return Buffer.concat(chunks).toString('utf8');
}

// ─── Price fetcher for stop order monitoring ──────────────
async function fetchCurrentPrice(mint: string): Promise<number> {
  try {
    const resp = await fetch(
      `https://api.dexscreener.com/latest/dex/tokens/${mint}`,
      { signal: AbortSignal.timeout(8000) },
    );
    const data = await resp.json() as { pairs?: Array<{ priceUsd?: string }> };
    const price = parseFloat(data.pairs?.[0]?.priceUsd ?? '0');
    return price;
  } catch {
    return 0;
  }
}

// ─── Route handlers ───────────────────────────────────────
async function handleSafety(req: http.IncomingMessage, res: http.ServerResponse, url: URL): Promise<void> {
  const mint = url.searchParams.get('mint');
  if (!mint || mint.length < 32) {
    return error(res, 'Invalid mint address');
  }

  try {
    const token: TokenInfo = {
      mint,
      symbol: mint.slice(0, 6),
      name: 'Unknown',
      decimals: 9,
      supply: 0,
      source: 'manual',
      discoveredAt: Date.now(),
    };

    const result = await runSafetyPipeline(token);

    json(res, {
      mint: result.mint,
      symbol: token.symbol,
      overall: result.overallScore,
      passed: result.passed,
      mintAuthority: result.mintCheck.mintAuthorityRevoked ? 1.0 : 0.0,
      freezeAuthority: result.mintCheck.freezeAuthorityRevoked ? 1.0 : 0.0,
      lpBurned: result.lpAnalysis ? (result.lpAnalysis.lpBurnedPct / 100) : 0.5,
      holderConcentration: result.holderAnalysis
        ? Math.max(0, 1 - result.holderAnalysis.top10ConcentrationPct / 100)
        : 0.5,
      honeypot: result.goPlus ? (result.goPlus.isHoneypot ? 0.0 : 1.0) : 0.5,
      rugcheck: result.rugCheck ? (result.rugCheck.score / 100) : 0.5,
      deployerHistory: 0.85, // TODO: extract from composite result
      failReasons: result.failReasons,
    });
  } catch (err) {
    log.error('Safety check failed', { mint, error: (err as Error).message });
    error(res, `Safety check failed: ${(err as Error).message}`, 500);
  }
}

async function handleTrade(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
  try {
    const body = JSON.parse(await readBody(req));
    const { action, tokenMint, amountSolLamports, slippageBps, takeProfitPct, stopLossPct, trailingStopPct } = body;

    if (!tokenMint || !action) {
      return error(res, 'Missing tokenMint or action');
    }

    if (action === 'buy') {
      const result = await buyTokenViaBags({
        tokenMint,
        amountSolLamports: amountSolLamports || 100000000, // 0.1 SOL default
        slippageBps: slippageBps || 300,
      });

      // Create stop order for TP/SL
      if (result.signature) {
        const entryPrice = await fetchCurrentPrice(tokenMint);
        createStopOrder({
          tokenMint,
          entryPriceUsd: entryPrice,
          amountTokenLamports: parseInt(result.outAmount, 10),
          takeProfitPct: takeProfitPct || 50,
          stopLossPct: stopLossPct || 15,
          trailingStopPct: trailingStopPct || undefined,
        });
      }

      json(res, {
        success: true,
        signature: result.signature,
        outAmount: result.outAmount,
        priceImpact: result.priceImpact,
        error: null,
        mode: 'live',
      });
    } else if (action === 'sell') {
      const result = await sellTokenViaBags({
        tokenMint,
        amountTokenLamports: amountSolLamports, // reused field for token amount
        slippageBps: slippageBps || 500,
      });

      // Cancel associated stop order
      cancelOrder(tokenMint);

      json(res, {
        success: true,
        signature: result.signature,
        outAmount: result.outAmount,
        priceImpact: result.priceImpact,
        error: null,
        mode: 'live',
      });
    } else {
      error(res, `Unknown action: ${action}`);
    }
  } catch (err) {
    log.error('Trade execution failed', { error: (err as Error).message });
    json(res, {
      success: false,
      signature: null,
      outAmount: '0',
      priceImpact: '0',
      error: (err as Error).message,
    });
  }
}

function handleOrders(_req: http.IncomingMessage, res: http.ServerResponse): void {
  const orders = getActiveOrders();
  json(res, { orders });
}

function handleCancelOrder(req: http.IncomingMessage, res: http.ServerResponse, url: URL): void {
  const mint = url.searchParams.get('mint');
  if (!mint) return error(res, 'Missing mint');
  const cancelled = cancelOrder(mint);
  json(res, { success: cancelled });
}

function handleBacktestResults(_req: http.IncomingMessage, res: http.ServerResponse): void {
  const winningDir = path.resolve(process.cwd(), 'winning');

  // Read BEST_EVER.json
  let bestEver = null;
  try {
    const bestPath = path.join(winningDir, 'BEST_EVER.json');
    if (fs.existsSync(bestPath)) {
      bestEver = JSON.parse(fs.readFileSync(bestPath, 'utf8'));
    }
  } catch { /* ignore */ }

  // Read all continuous run logs
  const agents: Record<string, unknown[]> = {};
  try {
    const files = fs.readdirSync(winningDir).filter(f => f.startsWith('continuous-run-log'));
    for (const file of files) {
      const agentId = file.replace('continuous-run-log-', '').replace('.json', '');
      try {
        agents[agentId || 'default'] = JSON.parse(fs.readFileSync(path.join(winningDir, file), 'utf8'));
      } catch { /* ignore */ }
    }
  } catch { /* ignore */ }

  // Read best-config.json
  let bestConfig = null;
  try {
    const cfgPath = path.join(winningDir, 'best-config.json');
    if (fs.existsSync(cfgPath)) {
      bestConfig = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
    }
  } catch { /* ignore */ }

  // Summary stats
  const allIterations = Object.values(agents).flat() as Array<{ bestWinRate?: number; bestPnl?: number }>;
  const totalIterations = allIterations.length;
  const avgWinRate = totalIterations > 0
    ? allIterations.reduce((sum, i) => sum + (i.bestWinRate ?? 0), 0) / totalIterations
    : 0;

  json(res, {
    bestEver,
    bestConfig,
    agents,
    summary: {
      totalIterations,
      activeAgents: Object.keys(agents).length,
      avgWinRate: (avgWinRate * 100).toFixed(1) + '%',
    },
  });
}

// ─── Server ───────────────────────────────────────────────
const server = http.createServer(async (req, res) => {
  // CORS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    });
    res.end();
    return;
  }

  const url = new URL(req.url || '/', `http://localhost:${PORT}`);
  const path = url.pathname;

  try {
    if (path === '/api/safety' && req.method === 'GET') {
      await handleSafety(req, res, url);
    } else if (path === '/api/trade' && req.method === 'POST') {
      await handleTrade(req, res);
    } else if (path === '/api/orders' && req.method === 'GET') {
      handleOrders(req, res);
    } else if (path === '/api/orders/cancel' && req.method === 'POST') {
      handleCancelOrder(req, res, url);
    } else if (path === '/api/backtest' && req.method === 'GET') {
      handleBacktestResults(req, res);
    } else if (path === '/health') {
      json(res, { status: 'ok', uptime: process.uptime(), orders: getActiveOrders().length });
    } else {
      error(res, 'Not found', 404);
    }
  } catch (err) {
    log.error('Request handler error', { path, error: (err as Error).message });
    error(res, 'Internal server error', 500);
  }
});

// ─── Stop order monitoring loop ───────────────────────────
let stopCheckInterval: ReturnType<typeof setInterval> | null = null;

function startStopOrderMonitor(): void {
  stopCheckInterval = setInterval(async () => {
    try {
      await checkStopOrders(fetchCurrentPrice);
    } catch (err) {
      log.warn('Stop order check failed', { error: (err as Error).message });
    }
  }, 15000); // Check every 15 seconds
  log.info('Stop order monitor started (15s interval)');
}

// ─── Start ────────────────────────────────────────────────
server.listen(PORT, () => {
  log.info(`Sniper API server running on http://localhost:${PORT}`);
  log.info('Endpoints:');
  log.info('  GET  /api/safety?mint=<address>');
  log.info('  POST /api/trade { action, tokenMint, amountSolLamports, ... }');
  log.info('  GET  /api/orders');
  log.info('  POST /api/orders/cancel?mint=<address>');
  log.info('  GET  /health');
  startStopOrderMonitor();
});

// Graceful shutdown
process.on('SIGINT', () => {
  log.info('Shutting down...');
  if (stopCheckInterval) clearInterval(stopCheckInterval);
  server.close();
  process.exit(0);
});
