/**
 * Server-side Bags SDK proxy - Swap endpoint
 *
 * 1. Gets quote (if needed) + builds swap transaction via Bags SDK
 * 2. Injects priority fees (ComputeBudgetProgram) to prevent timeouts
 * 3. Uses server-side Bags API key (x-api-key) so partner/segmenter fees apply
 * 4. Returns serialized VersionedTransaction as base64 for client signing
 *
 * Rate limiting: 20 req/min per IP (involves transaction building).
 * No caching - swap transactions are unique per user/nonce.
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
import { checkSignerSolBalance } from '@/lib/solana-balance-guard';
import { resolveServerRpcConfig } from '@/lib/server-rpc-config';
import { upsertTradeEvidence } from '@/lib/execution/evidence';
import type { TradeEvidenceV2 } from '@/lib/data-plane/types';

function readBagsApiKey(): string {
  // Secret Manager values can include trailing newlines/whitespace; Node will reject such values
  // when used as HTTP header content (x-api-key). Sanitize defensively.
  return String(process.env.BAGS_API_KEY || '')
    .replace(/[\x00-\x20\x7f]/g, '')
    .trim();
}

const BAGS_API_KEY = readBagsApiKey();
const SOL_MINT = 'So11111111111111111111111111111111111111112';
const SOL_RESERVE_LAMPORTS = 3_000_000;

let _sdk: BagsSDK | null = null;
let _connection: Connection | null = null;
let _rpcUrl: string | null = null;

function getConnection(rpcUrl: string): Connection {
  if (!_connection || _rpcUrl !== rpcUrl) {
    _connection = new Connection(rpcUrl, 'confirmed');
    _rpcUrl = rpcUrl;
    _sdk = null;
  }
  return _connection;
}

function getSDK(connection: Connection): BagsSDK {
  if (!_sdk) {
    if (!BAGS_API_KEY) throw new Error('BAGS_API_KEY not configured');
    _sdk = new BagsSDK(BAGS_API_KEY, connection);
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

  // Decompile -> inject -> recompile
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
  let evidenceTradeId = `swap-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  let evidenceSurface: TradeEvidenceV2['surface'] = 'unknown';
  let evidenceStrategyId = 'unknown';
  let evidenceInputMint = '';
  let evidenceOutputMint = '';
  let evidencePriorityFeeMicroLamports = 0;
  let evidenceSlippageBps: number | null = null;

  try {
    // Rate limit - swap involves transaction building, strict limit
    const ip = getClientIp(request);
    const limit = await swapRateLimiter.check(ip);
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
      tradeId,
      strategyId,
      surface,
    } = body;

    evidenceInputMint = String(inputMint || '');
    evidenceOutputMint = String(outputMint || '');
    evidencePriorityFeeMicroLamports = Number(priorityFeeMicroLamports || 0);
    evidenceSlippageBps = Number.isFinite(Number(slippageBps)) ? Number(slippageBps) : null;
    evidenceTradeId = String(tradeId || evidenceTradeId).trim() || evidenceTradeId;
    evidenceSurface =
      surface === 'main' || surface === 'bags' || surface === 'tradfi'
        ? surface
        : 'unknown';
    evidenceStrategyId = String(strategyId || 'unknown').trim() || 'unknown';

    const persistEvidence = async (args: {
      outcome: TradeEvidenceV2['outcome'];
      expectedPrice?: number | null;
      slippageBpsValue?: number | null;
      metadata?: Record<string, unknown>;
    }) => {
      await upsertTradeEvidence({
        tradeId: evidenceTradeId,
        surface: evidenceSurface,
        strategyId: evidenceStrategyId,
        decisionTs: new Date().toISOString(),
        route: 'bags_sdk_proxy',
        expectedPrice: Number.isFinite(Number(args.expectedPrice)) ? Number(args.expectedPrice) : null,
        executedPrice: null,
        slippageBps: Number.isFinite(Number(args.slippageBpsValue)) ? Number(args.slippageBpsValue) : null,
        priorityFeeLamports: null,
        jitoUsed: false,
        mevRiskTag: 'unknown',
        datasetRefs: [],
        outcome: args.outcome,
        metadata: {
          inputMint: evidenceInputMint,
          outputMint: evidenceOutputMint,
          priorityFeeMicroLamports: evidencePriorityFeeMicroLamports,
          ...args.metadata,
        },
      }).catch(() => undefined);
    };

    if (!userPublicKey) {
      await persistEvidence({ outcome: 'failed', metadata: { error: 'Missing userPublicKey' } });
      return NextResponse.json({ error: 'Missing userPublicKey' }, { status: 400 });
    }

    const rpcConfig = resolveServerRpcConfig();
    if (!rpcConfig.ok || !rpcConfig.url) {
      await persistEvidence({
        outcome: 'failed',
        metadata: {
          code: 'RPC_PROVIDER_UNAVAILABLE',
          diagnostic: rpcConfig.diagnostic,
          source: rpcConfig.source,
        },
      });
      return NextResponse.json(
        {
          code: 'RPC_PROVIDER_UNAVAILABLE',
          error: 'RPC provider unavailable',
          diagnostic: rpcConfig.diagnostic,
          source: rpcConfig.source,
        },
        { status: 503 },
      );
    }

    const connection = getConnection(rpcConfig.url);

    // Server-side fail-closed guard for SOL-funded buys.
    // Prevents wasted swap builds when the signer wallet cannot cover buy amount + fee reserve.
    const amountLamports = Number(amount);
    const isSolInputBuy = String(inputMint || '') === SOL_MINT && Number.isFinite(amountLamports) && amountLamports > 0;
    if (isSolInputBuy) {
      const balance = await checkSignerSolBalance(
        connection,
        userPublicKey,
        amountLamports,
        SOL_RESERVE_LAMPORTS,
      );
      if (!balance.ok) {
        console.warn(
          `[API /bags/swap] INSUFFICIENT_SIGNER_SOL wallet=${userPublicKey} available=${balance.availableLamports} required=${balance.requiredLamports}`,
        );
        await persistEvidence({
          outcome: 'failed',
          metadata: {
            code: 'INSUFFICIENT_SIGNER_SOL',
            availableLamports: balance.availableLamports,
            requiredLamports: balance.requiredLamports,
          },
        });
        return NextResponse.json(
          {
            code: 'INSUFFICIENT_SIGNER_SOL',
            error: 'Signer SOL balance is below required amount for this buy.',
            availableLamports: balance.availableLamports,
            requiredLamports: balance.requiredLamports,
            availableSol: balance.availableSol,
            requiredSol: balance.requiredSol,
          },
          { status: 409 },
        );
      }
    }

    const sdk = getSDK(connection);

    // Get quote if not pre-supplied
    let quote = preQuote;
    if (!quote) {
      if (!inputMint || !outputMint || !amount) {
        await persistEvidence({
          outcome: 'failed',
          metadata: { error: 'Missing quote inputs' },
        });
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

    // Build swap transaction via Bags SDK.
    // Note: partner/segmenter attribution is tied to the server-side `x-api-key`.
    const result = await sdk.trade.createSwapTransaction({
      quoteResponse: quote,
      userPublicKey: new PublicKey(userPublicKey),
    });

    // Serialize base transaction
    let txBytes = result.transaction.serialize();

    // Inject priority fee to prevent timeout (default 200k microLamports ~ $0.0002)
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
    const expectedPrice = Number(quote?.inAmount || 0) > 0 && Number(quote?.outAmount || 0) > 0
      ? Number(quote.inAmount) / Number(quote.outAmount)
      : null;
    await persistEvidence({
      outcome: 'unresolved',
      expectedPrice,
      slippageBpsValue: Number(slippageBps || quote?.slippageBps || 0),
      metadata: {
        stage: 'swap_tx_built',
        quoteInAmount: quote?.inAmount || null,
        quoteOutAmount: quote?.outAmount || null,
      },
    });
    return NextResponse.json({ transaction: txBase64, quote, tradeId: evidenceTradeId });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Swap failed';
    console.error('[API /bags/swap]', msg);
    await upsertTradeEvidence({
      tradeId: evidenceTradeId,
      surface: evidenceSurface,
      strategyId: evidenceStrategyId,
      decisionTs: new Date().toISOString(),
      route: 'bags_sdk_proxy',
      expectedPrice: null,
      executedPrice: null,
      slippageBps: evidenceSlippageBps,
      priorityFeeLamports: null,
      jitoUsed: false,
      mevRiskTag: 'unknown',
      datasetRefs: [],
      outcome: 'failed',
      metadata: { error: msg, inputMint: evidenceInputMint, outputMint: evidenceOutputMint },
    }).catch(() => undefined);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
