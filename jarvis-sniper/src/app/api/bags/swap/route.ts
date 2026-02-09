/**
 * Server-side Bags SDK proxy — Swap endpoint
 *
 * 1. Gets quote (if needed) + builds swap transaction via Bags SDK
 * 2. Injects priority fees (ComputeBudgetProgram) to prevent timeouts
 * 3. Passes partner key for referral revenue
 * 4. Returns serialized VersionedTransaction as base64 for client signing
 *
 * Rate limiting: 20 req/min per IP (involves transaction building).
 * No caching — swap transactions are unique per user/nonce.
 */
import { NextResponse } from 'next/server';
import { BagsSDK } from '@bagsfm/bags-sdk';
import {
  Connection,
  PublicKey,
  VersionedTransaction,
  TransactionMessage,
  AddressLookupTableAccount,
  ComputeBudgetProgram,
} from '@solana/web3.js';
import { swapRateLimiter, getClientIp } from '@/lib/rate-limiter';

const RPC_URL = process.env.SOLANA_RPC_URL || process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com';
const BAGS_API_KEY = process.env.BAGS_API_KEY || '';
const REFERRAL_ACCOUNT = process.env.BAGS_REFERRAL_ACCOUNT || '';

let _sdk: BagsSDK | null = null;
let _connection: Connection | null = null;

function getConnection(): Connection {
  if (!_connection) {
    _connection = new Connection(RPC_URL, 'confirmed');
  }
  return _connection;
}

function getSDK(): BagsSDK {
  if (!_sdk) {
    if (!BAGS_API_KEY) throw new Error('BAGS_API_KEY not configured');
    _sdk = new BagsSDK(BAGS_API_KEY, getConnection());
  }
  return _sdk;
}

/**
 * Inject ComputeBudgetProgram.setComputeUnitPrice into a VersionedTransaction.
 * Requires fetching ALTs to decompile the v0 message.
 */
async function injectPriorityFee(
  txBytes: Uint8Array,
  microLamports: number,
  connection: Connection,
): Promise<Uint8Array> {
  const tx = VersionedTransaction.deserialize(txBytes);

  // Fetch Address Lookup Tables required for decompilation
  const altAccounts: AddressLookupTableAccount[] = await Promise.all(
    tx.message.addressTableLookups.map(async (lookup) => {
      const res = await connection.getAddressLookupTable(lookup.accountKey);
      if (!res.value) throw new Error(`ALT not found: ${lookup.accountKey.toBase58()}`);
      return new AddressLookupTableAccount({
        key: lookup.accountKey,
        state: res.value.state,
      });
    }),
  );

  // Decompile → inject → recompile
  const message = TransactionMessage.decompile(tx.message, {
    addressLookupTableAccounts: altAccounts,
  });

  // Check if ComputeBudgetProgram instructions already exist
  const hasPriorityFee = message.instructions.some(
    (ix) => ix.programId.equals(ComputeBudgetProgram.programId),
  );

  if (!hasPriorityFee) {
    message.instructions.unshift(
      ComputeBudgetProgram.setComputeUnitPrice({ microLamports }),
    );
  }

  const newMessage = message.compileToV0Message(altAccounts);
  const newTx = new VersionedTransaction(newMessage);
  return newTx.serialize();
}

export async function POST(request: Request) {
  try {
    // Rate limit — swap involves transaction building, strict limit
    const ip = getClientIp(request);
    const limit = swapRateLimiter.check(ip);
    if (!limit.allowed) {
      return NextResponse.json(
        { error: 'Rate limit exceeded. Try again shortly.' },
        {
          status: 429,
          headers: {
            'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)),
            'X-RateLimit-Remaining': '0',
          },
        },
      );
    }

    const body = await request.json();
    const {
      userPublicKey,
      quote: preQuote,
      inputMint,
      outputMint,
      amount,
      slippageBps,
      priorityFeeMicroLamports,
    } = body;

    if (!userPublicKey) {
      return NextResponse.json({ error: 'Missing userPublicKey' }, { status: 400 });
    }

    const sdk = getSDK();
    const connection = getConnection();

    // Get quote if not pre-supplied
    let quote = preQuote;
    if (!quote) {
      if (!inputMint || !outputMint || !amount) {
        return NextResponse.json(
          { error: 'Must provide either quote or inputMint/outputMint/amount' },
          { status: 400 },
        );
      }
      quote = await sdk.trade.getQuote({
        inputMint: new PublicKey(inputMint),
        outputMint: new PublicKey(outputMint),
        amount: Number(amount),
        slippageMode: slippageBps ? 'manual' : 'auto',
        ...(slippageBps ? { slippageBps: Number(slippageBps) } : {}),
      });
    }

    // Build swap transaction with partner referral
    const swapParams = {
      quoteResponse: quote,
      userPublicKey: new PublicKey(userPublicKey),
      ...(REFERRAL_ACCOUNT ? { referralAccount: new PublicKey(REFERRAL_ACCOUNT) } : {}),
    };

    const result = await sdk.trade.createSwapTransaction(swapParams as Parameters<typeof sdk.trade.createSwapTransaction>[0]);

    // Serialize base transaction
    let txBytes = result.transaction.serialize();

    // Inject priority fee to prevent timeout (default 200k microLamports ≈ $0.0002)
    const fee = priorityFeeMicroLamports ?? 200_000;
    if (fee > 0) {
      try {
        txBytes = await injectPriorityFee(txBytes, fee, connection);
        console.log(`[API /bags/swap] Injected priority fee: ${fee} microLamports`);
      } catch (feeErr) {
        // Non-fatal: send original tx if fee injection fails
        console.warn('[API /bags/swap] Priority fee injection failed, using original tx:', feeErr);
      }
    }

    const txBase64 = Buffer.from(txBytes).toString('base64');
    return NextResponse.json({ transaction: txBase64, quote });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Swap failed';
    console.error('[API /bags/swap]', msg);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
