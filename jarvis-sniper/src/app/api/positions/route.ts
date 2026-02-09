/**
 * Position persistence API — shared between browser UI and risk worker.
 *
 * GET  /api/positions → list all open positions
 * POST /api/positions → add/update a position
 * DELETE /api/positions?mint=xxx → close a position
 *
 * Stores to .positions.json in the project root.
 * The risk-worker.ts script reads this file to monitor SL/TP 24/7.
 */
import { NextResponse } from 'next/server';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';

export interface PersistedPosition {
  id: string;
  mint: string;
  symbol: string;
  amount: number;
  amountLamports?: string;
  solInvested: number;
  entryPrice: number;
  stopLossPct: number;
  takeProfitPct: number;
  txHash?: string;
  walletAddress: string;
  status: 'open' | 'closed' | 'sl_hit' | 'tp_hit';
  entryTime: number;
  closeTxHash?: string;
}

const POSITIONS_FILE = join(process.cwd(), '.positions.json');

function readPositions(): PersistedPosition[] {
  try {
    if (!existsSync(POSITIONS_FILE)) return [];
    const raw = readFileSync(POSITIONS_FILE, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

function writePositions(positions: PersistedPosition[]): void {
  writeFileSync(POSITIONS_FILE, JSON.stringify(positions, null, 2), 'utf-8');
}

export async function GET() {
  const positions = readPositions();
  const open = positions.filter((p) => p.status === 'open');
  return NextResponse.json({ positions: open, total: positions.length });
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const {
      mint, symbol, amount, amountLamports, solInvested,
      entryPrice, stopLossPct, takeProfitPct, txHash, walletAddress,
    } = body;

    if (!mint || !walletAddress) {
      return NextResponse.json({ error: 'Missing mint or walletAddress' }, { status: 400 });
    }

    const positions = readPositions();

    // Check if position already exists for this mint+wallet
    const existing = positions.findIndex(
      (p) => p.mint === mint && p.walletAddress === walletAddress && p.status === 'open',
    );

    const pos: PersistedPosition = {
      id: `pos-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      mint,
      symbol: symbol || mint.slice(0, 6),
      amount: amount || 0,
      amountLamports,
      solInvested: solInvested || 0,
      entryPrice: entryPrice || 0,
      stopLossPct: stopLossPct || 20,
      takeProfitPct: takeProfitPct || 50,
      txHash,
      walletAddress,
      status: 'open',
      entryTime: Date.now(),
    };

    if (existing >= 0) {
      // Update existing position
      positions[existing] = { ...positions[existing], ...pos, id: positions[existing].id };
    } else {
      positions.push(pos);
    }

    writePositions(positions);
    return NextResponse.json({ success: true, position: pos });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Failed to save position';
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const mint = searchParams.get('mint');
    const status = (searchParams.get('status') || 'closed') as PersistedPosition['status'];
    const closeTxHash = searchParams.get('txHash') || undefined;

    if (!mint) {
      return NextResponse.json({ error: 'Missing mint param' }, { status: 400 });
    }

    const positions = readPositions();
    const updated = positions.map((p) => {
      if (p.mint === mint && p.status === 'open') {
        return { ...p, status, closeTxHash };
      }
      return p;
    });

    writePositions(updated);
    return NextResponse.json({ success: true });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Failed to close position';
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
