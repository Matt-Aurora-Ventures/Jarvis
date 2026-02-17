'use client';

/**
 * Jupiter Swap Service
 *
 * Minimal Jupiter V6 swap integration for executing trades.
 * Uses Jupiter Swap API v1 endpoints:
 *   - Quote: GET  https://api.jup.ag/swap/v1/quote
 *   - Swap:  POST https://api.jup.ag/swap/v1/swap
 *
 * This module does NOT sign or send transactions.
 * It returns serialized transactions for the wallet adapter to sign.
 */

// ── Constants ───────────────────────────────────────────────────────

export const SOL_MINT = 'So11111111111111111111111111111111111111112';

const JUPITER_QUOTE_URL = 'https://api.jup.ag/swap/v1/quote';
const JUPITER_SWAP_URL = 'https://api.jup.ag/swap/v1/swap';

// ── Types ───────────────────────────────────────────────────────────

export interface JupiterSwapInfo {
  ammKey: string;
  label: string;
  inputMint: string;
  outputMint: string;
  inAmount: string;
  outAmount: string;
  feeAmount: string;
  feeMint: string;
}

export interface JupiterRoutePlanStep {
  swapInfo: JupiterSwapInfo;
  percent: number;
}

export interface JupiterQuote {
  inputMint: string;
  outputMint: string;
  inAmount: string;
  outAmount: string;
  otherAmountThreshold: string;
  swapMode: string;
  slippageBps: number;
  priceImpactPct: string;
  routePlan: JupiterRoutePlanStep[];
}

export interface JupiterQuoteParams {
  inputMint: string;
  outputMint: string;
  /** Amount in lamports / smallest unit of the input token */
  amount: number;
  slippageBps: number;
}

export interface JupiterSwapParams {
  quoteResponse: JupiterQuote;
  userPublicKey: string;
}

// ── Functions ───────────────────────────────────────────────────────

/**
 * Get a swap quote from Jupiter.
 *
 * @param params - Quote parameters (inputMint, outputMint, amount in smallest unit, slippageBps)
 * @returns The Jupiter quote response
 * @throws On network error or non-200 response
 *
 * @example
 * ```ts
 * const quote = await getJupiterQuote({
 *   inputMint: SOL_MINT,
 *   outputMint: tokenMint,
 *   amount: 1_000_000_000, // 1 SOL in lamports
 *   slippageBps: 50,       // 0.5%
 * });
 * ```
 */
export async function getJupiterQuote(params: JupiterQuoteParams): Promise<JupiterQuote> {
  const { inputMint, outputMint, amount, slippageBps } = params;

  const searchParams = new URLSearchParams({
    inputMint,
    outputMint,
    amount: String(amount),
    slippageBps: String(slippageBps),
  });

  const url = `${JUPITER_QUOTE_URL}?${searchParams.toString()}`;

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(
      `Jupiter quote API error: ${response.status} ${response.statusText}`
    );
  }

  const data: JupiterQuote = await response.json();
  return data;
}

/**
 * Get a serialized swap transaction from Jupiter.
 *
 * The returned base64 string represents a VersionedTransaction that must be
 * deserialized, signed by the user's wallet, and then sent to the network.
 *
 * @param params - The quote response and user's public key
 * @returns Base64-encoded serialized transaction
 * @throws On network error or non-200 response
 *
 * @example
 * ```ts
 * const txBase64 = await getJupiterSwapTransaction({
 *   quoteResponse: quote,
 *   userPublicKey: wallet.publicKey.toBase58(),
 * });
 *
 * const txBuffer = Buffer.from(txBase64, 'base64');
 * const tx = VersionedTransaction.deserialize(txBuffer);
 * const signed = await wallet.signTransaction(tx);
 * const sig = await connection.sendRawTransaction(signed.serialize());
 * ```
 */
export async function getJupiterSwapTransaction(
  params: JupiterSwapParams
): Promise<string> {
  const { quoteResponse, userPublicKey } = params;

  const response = await fetch(JUPITER_SWAP_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      quoteResponse,
      userPublicKey,
      dynamicComputeUnitLimit: true,
      dynamicSlippage: true,
    }),
  });

  if (!response.ok) {
    throw new Error(
      `Jupiter swap API error: ${response.status} ${response.statusText}`
    );
  }

  const data = await response.json();
  return data.swapTransaction as string;
}
