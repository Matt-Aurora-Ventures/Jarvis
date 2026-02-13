/**
 * Session Export — Generate compact .md trading report
 *
 * Exports all trading activity from the current session:
 * - Manual trades, auto-snipes, SL/TP triggers
 * - Config used, strategy selected
 * - P&L summary, win/loss stats
 * - Position details with entry/exit info
 * - Execution log (chronological)
 */

import type { Position, ExecutionEvent, SniperConfig, BudgetState, CircuitBreakerState, AssetType } from '@/stores/useSniperStore';
import { isReliableTradeForStats } from '@/lib/position-reliability';

interface SessionExportData {
  config: SniperConfig;
  positions: Position[];
  executionLog: ExecutionEvent[];
  totalPnl: number;
  winCount: number;
  lossCount: number;
  totalTrades: number;
  budget: BudgetState;
  circuitBreaker: CircuitBreakerState;
  activePreset: string;
  assetFilter: AssetType;
  tradeSignerMode: string;
  sessionWalletPubkey: string | null;
  lastSolPriceUsd: number;
}

type VerificationState = 'confirmed' | 'failed' | 'unresolved';

function fmtDate(ts: number): string {
  return new Date(ts).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function fmtPct(n: number): string {
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

function fmtSol(n: number): string {
  return `${n >= 0 ? '+' : ''}${n.toFixed(4)} SOL`;
}

async function verifySignatures(signatures: string[]): Promise<Record<string, VerificationState>> {
  const unique = [...new Set(signatures.map((s) => String(s || '').trim()).filter(Boolean))];
  if (unique.length === 0) return {};

  try {
    const res = await fetch('/api/rpc', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: Date.now(),
        method: 'getSignatureStatuses',
        params: [unique, { searchTransactionHistory: true }],
      }),
    });

    if (!res.ok) {
      return Object.fromEntries(unique.map((sig) => [sig, 'unresolved' as const]));
    }

    const payload = await res.json().catch(() => null);
    const values = payload?.result?.value;
    const out: Record<string, VerificationState> = {};
    for (let i = 0; i < unique.length; i++) {
      const sig = unique[i];
      const status = values?.[i];
      if (status?.err) {
        out[sig] = 'failed';
      } else if (status?.confirmationStatus === 'confirmed' || status?.confirmationStatus === 'finalized') {
        out[sig] = 'confirmed';
      } else {
        out[sig] = 'unresolved';
      }
    }
    return out;
  } catch {
    return Object.fromEntries(unique.map((sig) => [sig, 'unresolved' as const]));
  }
}

function labelVerification(state: VerificationState | undefined): string {
  if (state === 'confirmed') return 'confirmed';
  if (state === 'failed') return 'failed';
  if (state === 'unresolved') return 'unresolved';
  return '-';
}

export async function generateSessionMarkdown(data: SessionExportData): Promise<string> {
  const {
    config, positions, executionLog, totalPnl, winCount, lossCount,
    totalTrades, budget, circuitBreaker, activePreset, assetFilter,
    tradeSignerMode, sessionWalletPubkey, lastSolPriceUsd,
  } = data;

  const now = new Date();
  const openPositions = positions.filter((p) => p.status === 'open');
  const closedPositions = positions.filter((p) => p.status !== 'open');
  const unrealizedPnl = openPositions.reduce((s, p) => s + p.pnlSol, 0);
  const realizedPnl = totalPnl;
  const combinedPnl = realizedPnl + unrealizedPnl;
  const allTrades = totalTrades + openPositions.length;
  const allWins = winCount + openPositions.filter((p) => p.pnlPercent > 0).length;
  const winRate = allTrades > 0 ? ((allWins / allTrades) * 100).toFixed(1) : '0';
  const solUsd = lastSolPriceUsd > 0 ? lastSolPriceUsd : 0;

  const signatures = executionLog
    .map((e) => String(e.txHash || '').trim())
    .filter(Boolean);
  const verifiedBySig = await verifySignatures(signatures);
  const verifyCounts = Object.values(verifiedBySig).reduce((acc, state) => {
    acc[state] = (acc[state] || 0) + 1;
    return acc;
  }, { confirmed: 0, failed: 0, unresolved: 0 } as Record<VerificationState, number>);

  const lines: string[] = [];

  // Header
  lines.push('# JARVIS SNIPER — Session Report');
  lines.push(`> Generated: ${now.toISOString()}`);
  lines.push('');

  // Summary
  lines.push('## Summary');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  lines.push(`| Strategy | ${activePreset} (${config.strategyMode}) |`);
  lines.push(`| Asset Filter | ${assetFilter} |`);
  lines.push(`| Signing Mode | ${tradeSignerMode}${sessionWalletPubkey ? ` (${sessionWalletPubkey.slice(0, 8)}...)` : ''} |`);
  lines.push(`| Total Trades | ${allTrades} |`);
  lines.push(`| Win Rate | ${winRate}% (${allWins}W / ${lossCount}L) |`);
  lines.push(`| Realized P&L | ${fmtSol(realizedPnl)}${solUsd > 0 ? ` ($${(realizedPnl * solUsd).toFixed(2)})` : ''} |`);
  lines.push(`| Unrealized P&L | ${fmtSol(unrealizedPnl)}${solUsd > 0 ? ` ($${(unrealizedPnl * solUsd).toFixed(2)})` : ''} |`);
  lines.push(`| **Combined P&L** | **${fmtSol(combinedPnl)}**${solUsd > 0 ? ` **($${(combinedPnl * solUsd).toFixed(2)})**` : ''} |`);
  lines.push(`| Budget | ${budget.budgetSol} SOL (spent: ${budget.spent.toFixed(4)}) |`);
  lines.push(`| SOL Price | $${solUsd.toFixed(2)} |`);
  lines.push(`| Tx Verification | ${verifyCounts.confirmed} confirmed, ${verifyCounts.failed} failed, ${verifyCounts.unresolved} unresolved |`);
  if (circuitBreaker.tripped) {
    lines.push(`| Circuit Breaker | TRIPPED: ${circuitBreaker.reason} |`);
  }
  lines.push('');

  // Config
  lines.push('## Strategy Config');
  lines.push('| Param | Value |');
  lines.push('|-------|-------|');
  lines.push(`| SL / TP / Trail | ${config.stopLossPct}% / ${config.takeProfitPct}% / ${config.trailingStopPct}% |`);
  lines.push(`| Position Size | ${config.maxPositionSol} SOL |`);
  lines.push(`| Max Concurrent | ${config.maxConcurrentPositions} |`);
  lines.push(`| Min Liquidity | $${config.minLiquidityUsd.toLocaleString()} |`);
  lines.push(`| Min Score | ${config.minScore} |`);
  lines.push(`| Min Momentum 1h | ${config.minMomentum1h}% |`);
  lines.push(`| Max Token Age | ${config.maxTokenAgeHours}h |`);
  lines.push(`| Vol/Liq Ratio | ≥${config.minVolLiqRatio} |`);
  lines.push(`| Trading Hours | ${config.tradingHoursGate ? 'ON' : 'OFF'} |`);
  lines.push(`| Auto Snipe | ${config.autoSnipe ? 'ON' : 'OFF'} |`);
  lines.push(`| Jito | ${config.useJito ? 'ON' : 'OFF'} |`);
  lines.push('');

  // Open Positions
  if (openPositions.length > 0) {
    lines.push(`## Open Positions (${openPositions.length})`);
    lines.push('| Symbol | Entry | Current | P&L | SOL Invested | Age | Strategy |');
    lines.push('|--------|-------|---------|-----|-------------|-----|----------|');
    for (const p of openPositions) {
      const ageMin = Math.round((Date.now() - p.entryTime) / 60000);
      const ageStr = ageMin < 60 ? `${ageMin}m` : `${(ageMin / 60).toFixed(1)}h`;
      lines.push(`| ${p.symbol} | $${p.entryPrice.toFixed(8)} | $${p.currentPrice.toFixed(8)} | ${fmtPct(p.pnlPercent)} (${fmtSol(p.pnlSol)}) | ${p.solInvested.toFixed(4)} | ${ageStr} | SL${p.recommendedSl}/TP${p.recommendedTp} |`);
    }
    lines.push('');
  }

  // Closed Positions
  if (closedPositions.length > 0) {
    lines.push(`## Closed Positions (${closedPositions.length})`);
    lines.push('| Symbol | Entry | Exit | P&L | SOL | Status | Duration |');
    lines.push('|--------|-------|------|-----|-----|--------|----------|');
    for (const p of closedPositions) {
      const dur = Math.round((Date.now() - p.entryTime) / 60000);
      const durStr = dur < 60 ? `${dur}m` : `${(dur / 60).toFixed(1)}h`;
      const reliable = isReliableTradeForStats(p);
      const pnlText = reliable
        ? `${fmtPct(p.realPnlPercent != null ? p.realPnlPercent : p.pnlPercent)} (${fmtSol(p.realPnlSol != null ? p.realPnlSol : p.pnlSol)})`
        : 'P&L excluded (no reliable cost basis)';
      lines.push(`| ${p.symbol} | $${p.entryPrice.toFixed(8)} | $${p.currentPrice.toFixed(8)} | ${pnlText} | ${p.solInvested.toFixed(4)} | ${p.status} | ${durStr} |`);
    }
    lines.push('');
  }

  // Execution Log (last 100)
  const logEntries = [...executionLog].sort((a, b) => b.timestamp - a.timestamp).slice(0, 100);
  if (logEntries.length > 0) {
    lines.push(`## Execution Log (${logEntries.length} events)`);
    lines.push('| Time | Type | Symbol | Verified | Details |');
    lines.push('|------|------|--------|----------|---------|');
    for (const e of logEntries) {
      const details: string[] = [];
      if (e.amount != null) details.push(`${e.amount.toFixed(4)} SOL`);
      if (e.pnlPercent != null) details.push(fmtPct(e.pnlPercent));
      if (e.reason) details.push(e.reason);
      if (e.txHash) details.push(`tx:${e.txHash.slice(0, 8)}...`);
      const verified = e.txHash ? labelVerification(verifiedBySig[e.txHash]) : '-';
      lines.push(`| ${fmtDate(e.timestamp)} | ${e.type} | ${e.symbol} | ${verified} | ${details.join(' · ')} |`);
    }
    lines.push('');
  }

  lines.push('---');
  lines.push('*JARVIS SNIPER by KR8TIV AI — [jarvislife.io](https://jarvislife.io)*');

  return lines.join('\n');
}

/** Trigger browser download of the session report */
export async function downloadSessionReport(data: SessionExportData): Promise<void> {
  const md = await generateSessionMarkdown(data);
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  a.download = `jarvis-session-${ts}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
