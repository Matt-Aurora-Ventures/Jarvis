/**
 * Server-side Bags SDK proxy — Quote endpoint
 * Bypasses CORS by running SDK on the server.
 */
import { NextResponse } from 'next/server';
import { BagsSDK } from '@bagsfm/bags-sdk';
import { Connection, PublicKey } from '@solana/web3.js';

const RPC_URL = process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com';
const BAGS_API_KEY = process.env.BAGS_API_KEY || '';

let _sdk: BagsSDK | null = null;

function getSDK(): BagsSDK {
  if (!_sdk) {
    if (!BAGS_API_KEY) throw new Error('BAGS_API_KEY not configured');
    const connection = new Connection(RPC_URL, 'confirmed');
    _sdk = new BagsSDK(BAGS_API_KEY, connection);
  }
  return _sdk;
}

export async function POST(request: Request) {
  try {
    const { inputMint, outputMint, amount, slippageBps } = await request.json();

    if (!inputMint || !outputMint || !amount) {
      return NextResponse.json({ error: 'Missing required parameters' }, { status: 400 });
    }

    const sdk = getSDK();
    const quote = await sdk.trade.getQuote({
      inputMint: new PublicKey(inputMint),
      outputMint: new PublicKey(outputMint),
      amount: Number(amount),
      slippageMode: slippageBps ? 'manual' : 'auto',
      ...(slippageBps ? { slippageBps: Number(slippageBps) } : {}),
    });

    return NextResponse.json({ quote });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Quote failed';
    console.error('[API /bags/quote]', msg);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
