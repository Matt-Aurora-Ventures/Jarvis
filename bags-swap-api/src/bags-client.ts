import { BagsSDK } from "@bagsfm/bags-sdk";
import { Connection, PublicKey } from "@solana/web3.js";

export interface QuoteParams {
  inputMint: string;
  outputMint: string;
  amount: number;
  slippageMode?: "auto" | "manual";
  slippageBps?: number;
}

export interface QuoteResponse {
  requestId: string;
  inAmount: string;
  outAmount: string;
  minOutAmount: string;
  priceImpactPct: string;
  slippageBps: number;
  routePlan: RouteLeg[];
  platformFee?: PlatformFee;
}

export interface RouteLeg {
  venue: string;
  inputMint: string;
  outputMint: string;
  inAmount: string;
  outAmount: string;
}

export interface PlatformFee {
  amount: string;
  feeBps: number;
  feeAccount: string;
}

export interface SwapParams {
  quoteResponse: QuoteResponse;
  userPublicKey: string;
}

export interface SwapResponse {
  transaction: string; // Base64 encoded transaction
  computeUnitLimit: number;
  prioritizationFeeLamports: number;
  lastValidBlockHeight: number;
}

export class BagsClient {
  private sdk: BagsSDK;
  private connection: Connection;

  constructor(apiKey: string, rpcUrl: string) {
    this.connection = new Connection(rpcUrl);
    this.sdk = new BagsSDK(apiKey, this.connection, "processed");
  }

  async getQuote(params: QuoteParams): Promise<QuoteResponse> {
    const quote = await this.sdk.trade.getQuote({
      inputMint: new PublicKey(params.inputMint),
      outputMint: new PublicKey(params.outputMint),
      amount: params.amount,
      slippageMode: params.slippageMode || "auto",
      slippageBps: params.slippageBps,
    });

    return {
      requestId: quote.requestId,
      inAmount: quote.inAmount,
      outAmount: quote.outAmount,
      minOutAmount: quote.minOutAmount,
      priceImpactPct: quote.priceImpactPct,
      slippageBps: quote.slippageBps,
      routePlan: quote.routePlan.map((leg: any) => ({
        venue: leg.venue,
        inputMint: leg.inputMint,
        outputMint: leg.outputMint,
        inAmount: leg.inAmount,
        outAmount: leg.outAmount,
      })),
      platformFee: quote.platformFee
        ? {
            amount: quote.platformFee.amount,
            feeBps: quote.platformFee.feeBps,
            feeAccount: quote.platformFee.feeAccount,
          }
        : undefined,
    };
  }

  async createSwapTransaction(params: SwapParams): Promise<SwapResponse> {
    const swapResult = await this.sdk.trade.createSwapTransaction({
      quoteResponse: params.quoteResponse as any,
      userPublicKey: new PublicKey(params.userPublicKey),
    });

    // Convert transaction to base64 for transport
    const txBase64 = Buffer.from(swapResult.transaction.serialize()).toString(
      "base64"
    );

    return {
      transaction: txBase64,
      computeUnitLimit: swapResult.computeUnitLimit,
      prioritizationFeeLamports: swapResult.prioritizationFeeLamports,
      lastValidBlockHeight: swapResult.lastValidBlockHeight,
    };
  }

  getConnection(): Connection {
    return this.connection;
  }
}
