import {
  Connection,
  Keypair,
  VersionedTransaction,
  TransactionMessage,
  AddressLookupTableAccount,
} from '@solana/web3.js';
import axios from 'axios';
import { config } from '../config/index.js';
import { WSOL_MINT, DEFAULT_SLIPPAGE_BPS, LAMPORTS_PER_SOL } from '../config/constants.js';
import { getConnection, getWallet } from '../utils/wallet.js';
import { createModuleLogger } from '../utils/logger.js';
import { validateTransaction } from '../execution/tx-validator.js';
import type { SwapQuote, ExecutionResult } from '../types/index.js';

const log = createModuleLogger('jupiter');

interface JupiterQuoteResponse {
  inputMint: string;
  outputMint: string;
  inAmount: string;
  outAmount: string;
  otherAmountThreshold: string;
  priceImpactPct: string;
  routePlan: Array<{ swapInfo: { label: string } }>;
  contextSlot: number;
  timeTaken: number;
}

interface JupiterSwapResponse {
  swapTransaction: string;
  lastValidBlockHeight: number;
  prioritizationFeeLamports: number;
}

export async function getJupiterQuote(
  inputMint: string,
  outputMint: string,
  amountLamports: number,
  slippageBps: number = DEFAULT_SLIPPAGE_BPS,
): Promise<SwapQuote | null> {
  try {
    const url = `${config.jupiterApiBase}/quote`;
    const resp = await axios.get<JupiterQuoteResponse>(url, {
      params: {
        inputMint,
        outputMint,
        amount: amountLamports.toString(),
        slippageBps,
        restrictIntermediateTokens: true,
        maxAccounts: 64,
      },
      timeout: 5000,
    });

    const data = resp.data;
    const routeLabels = data.routePlan.map(r => r.swapInfo.label).join(' -> ');

    log.info('Jupiter quote received', {
      in: amountLamports,
      out: data.outAmount,
      impact: data.priceImpactPct,
      route: routeLabels,
    });

    return {
      inputMint: data.inputMint,
      outputMint: data.outputMint,
      inAmount: data.inAmount,
      outAmount: data.outAmount,
      priceImpactPct: parseFloat(data.priceImpactPct),
      slippageBps,
      routePlan: routeLabels,
      otherAmountThreshold: data.otherAmountThreshold,
    };
  } catch (err) {
    log.error('Jupiter quote failed', { error: (err as Error).message });
    return null;
  }
}

export async function executeJupiterSwap(
  inputMint: string,
  outputMint: string,
  amountLamports: number,
  slippageBps: number = DEFAULT_SLIPPAGE_BPS,
  priorityFeeLamports: number = 100_000,
): Promise<ExecutionResult> {
  const startTime = Date.now();
  const wallet = getWallet();
  const conn = getConnection();

  // Paper trade mode
  if (config.tradingMode === 'paper') {
    return executePaperTrade(inputMint, outputMint, amountLamports, startTime);
  }

  try {
    // 1. Get quote
    const quote = await getJupiterQuote(inputMint, outputMint, amountLamports, slippageBps);
    if (!quote) {
      return failResult('Failed to get quote', inputMint, outputMint, amountLamports, startTime);
    }

    // Check price impact
    if (quote.priceImpactPct > 10) {
      return failResult(`Price impact too high: ${quote.priceImpactPct.toFixed(2)}%`, inputMint, outputMint, amountLamports, startTime);
    }

    // 2. Get swap transaction
    const swapResp = await axios.post<JupiterSwapResponse>(
      `${config.jupiterApiBase}/swap`,
      {
        quoteResponse: quote,
        userPublicKey: wallet.publicKey.toBase58(),
        wrapAndUnwrapSol: true,
        prioritizationFeeLamports: {
          jitoTipLamports: priorityFeeLamports,
        },
        dynamicComputeUnitLimit: true,
      },
      { timeout: 10000 }
    );

    // 3. Deserialize, validate, sign, send
    const txBuf = Buffer.from(swapResp.data.swapTransaction, 'base64');
    const tx = VersionedTransaction.deserialize(txBuf);

    // Validate transaction before signing
    const validation = validateTransaction(tx);
    if (!validation.valid) {
      return failResult(`TX validation failed: ${validation.reason}`, inputMint, outputMint, amountLamports, startTime);
    }

    tx.sign([wallet]);

    const signature = await conn.sendRawTransaction(tx.serialize(), {
      skipPreflight: true,
      maxRetries: 3,
    });

    // 4. Confirm
    const confirmation = await conn.confirmTransaction(
      { signature, lastValidBlockHeight: swapResp.data.lastValidBlockHeight, blockhash: tx.message.recentBlockhash },
      'confirmed'
    );

    if (confirmation.value.err) {
      return failResult(`TX failed: ${JSON.stringify(confirmation.value.err)}`, inputMint, outputMint, amountLamports, startTime);
    }

    const latency = Date.now() - startTime;
    const side = inputMint === WSOL_MINT.toBase58() ? 'BUY' : 'SELL';
    const outAmount = parseInt(quote.outAmount);
    const inAmount = amountLamports;

    log.info('Jupiter swap executed', {
      sig: signature.slice(0, 16),
      side,
      in: inAmount,
      out: outAmount,
      latency: latency + 'ms',
    });

    return {
      success: true,
      signature,
      error: null,
      side: side as 'BUY' | 'SELL',
      mint: side === 'BUY' ? outputMint : inputMint,
      amountIn: inAmount / LAMPORTS_PER_SOL,
      amountOut: outAmount,
      priceUsd: 0, // Filled by caller
      feeUsd: priorityFeeLamports / LAMPORTS_PER_SOL * 200, // rough estimate
      executedAt: Date.now(),
      mode: 'live',
      latencyMs: latency,
    };
  } catch (err) {
    return failResult((err as Error).message, inputMint, outputMint, amountLamports, startTime);
  }
}

async function executePaperTrade(
  inputMint: string,
  outputMint: string,
  amountLamports: number,
  startTime: number,
): Promise<ExecutionResult> {
  // Get quote but don't execute
  const quote = await getJupiterQuote(inputMint, outputMint, amountLamports);
  const side = inputMint === WSOL_MINT.toBase58() ? 'BUY' : 'SELL';

  log.info('PAPER TRADE executed', {
    side,
    in: amountLamports,
    out: quote?.outAmount ?? '0',
  });

  return {
    success: true,
    signature: `paper_${Date.now()}`,
    error: null,
    side: side as 'BUY' | 'SELL',
    mint: side === 'BUY' ? outputMint : inputMint,
    amountIn: amountLamports / LAMPORTS_PER_SOL,
    amountOut: quote ? parseInt(quote.outAmount) : 0,
    priceUsd: 0,
    feeUsd: 0,
    executedAt: Date.now(),
    mode: 'paper',
    latencyMs: Date.now() - startTime,
  };
}

function failResult(error: string, inputMint: string, outputMint: string, amount: number, startTime: number): ExecutionResult {
  log.error('Swap failed', { error });
  const side = inputMint === WSOL_MINT.toBase58() ? 'BUY' : 'SELL';
  return {
    success: false,
    signature: null,
    error,
    side: side as 'BUY' | 'SELL',
    mint: side === 'BUY' ? outputMint : inputMint,
    amountIn: amount / LAMPORTS_PER_SOL,
    amountOut: 0,
    priceUsd: 0,
    feeUsd: 0,
    executedAt: Date.now(),
    mode: config.tradingMode,
    latencyMs: Date.now() - startTime,
  };
}

// ─── Price helpers ────────────────────────────────────────────
export async function getTokenPrice(mintAddress: string): Promise<number> {
  try {
    const resp = await axios.get(`https://price.jup.ag/v6/price`, {
      params: { ids: mintAddress },
      timeout: 3000,
    });
    const price = resp.data?.data?.[mintAddress]?.price;
    return price ?? 0;
  } catch {
    return 0;
  }
}

export async function getDexScreenerPrice(mintAddress: string): Promise<{ price: number; liquidity: number; volume24h: number }> {
  try {
    const resp = await axios.get(`https://api.dexscreener.com/latest/dex/tokens/${mintAddress}`, { timeout: 5000 });
    const pair = resp.data?.pairs?.[0];
    if (!pair) return { price: 0, liquidity: 0, volume24h: 0 };
    return {
      price: parseFloat(pair.priceUsd ?? '0'),
      liquidity: parseFloat(pair.liquidity?.usd ?? '0'),
      volume24h: parseFloat(pair.volume?.h24 ?? '0'),
    };
  } catch {
    return { price: 0, liquidity: 0, volume24h: 0 };
  }
}
