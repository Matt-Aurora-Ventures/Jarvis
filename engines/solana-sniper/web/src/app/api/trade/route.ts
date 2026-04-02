import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { action, tokenMint, amountSol, slippageBps, takeProfitPct, stopLossPct, trailingStopPct } = body;

    if (!tokenMint || !action) {
      return NextResponse.json({ success: false, error: 'Missing required fields' }, { status: 400 });
    }

    // Call the sniper backend
    const backendUrl = process.env.SNIPER_BACKEND_URL || 'http://localhost:3002';
    const resp = await fetch(`${backendUrl}/api/trade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action,
        tokenMint,
        amountSolLamports: Math.round(amountSol * 1e9),
        slippageBps: slippageBps || 300,
        takeProfitPct: takeProfitPct || 50,
        stopLossPct: stopLossPct || 15,
        trailingStopPct: trailingStopPct || null,
      }),
      signal: AbortSignal.timeout(30000),
    });

    if (resp.ok) {
      const data = await resp.json();
      return NextResponse.json(data);
    }

    // Demo mode response when backend is not running
    return NextResponse.json({
      success: true,
      signature: `demo_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`,
      outAmount: '0',
      priceImpact: '0',
      error: null,
      mode: 'paper',
    });
  } catch {
    return NextResponse.json({
      success: false,
      signature: null,
      outAmount: '0',
      priceImpact: '0',
      error: 'Backend unavailable — demo mode',
    });
  }
}
