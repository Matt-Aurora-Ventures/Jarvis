import { NextResponse } from 'next/server';

const JITO_BLOCK_ENGINE_URL = 'https://mainnet.block-engine.jito.wtf/api/v1/bundles';

/**
 * Proxy for Jito Block Engine (avoids CORS from browser).
 * Accepts an array of signed, base64-encoded VersionedTransactions.
 */
export async function POST(request: Request) {
  try {
    const { transactions } = await request.json();

    if (!Array.isArray(transactions) || transactions.length === 0) {
      return NextResponse.json({ error: 'Empty bundle' }, { status: 400 });
    }

    if (transactions.length > 5) {
      return NextResponse.json({ error: 'Max 5 transactions per bundle' }, { status: 400 });
    }

    console.log(`[Jito] Submitting bundle of ${transactions.length} txs...`);

    const payload = {
      jsonrpc: '2.0',
      id: 1,
      method: 'sendBundle',
      params: [transactions],
    };

    const res = await fetch(JITO_BLOCK_ENGINE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (data.error) {
      console.error('[Jito] Error:', data.error);
      return NextResponse.json({ error: JSON.stringify(data.error) }, { status: 502 });
    }

    console.log(`[Jito] Bundle accepted: ${data.result}`);
    return NextResponse.json({ bundleId: data.result });
  } catch (err: any) {
    console.error('[Jito Proxy Error]', err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
