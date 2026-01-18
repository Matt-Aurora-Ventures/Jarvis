import express, { Request, Response, NextFunction } from "express";
import cors from "cors";
import dotenv from "dotenv";
import path from "path";
import { BagsClient, QuoteParams } from "./bags-client";

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, "../public")));

// Config
const PORT = process.env.PORT || 3000;
const BAGS_API_KEY = process.env.BAGS_API_KEY;
const SOLANA_RPC_URL =
  process.env.SOLANA_RPC_URL || "https://api.mainnet-beta.solana.com";
const SERVICE_FEE_BPS = parseInt(process.env.SERVICE_FEE_BPS || "50", 10); // 0.5% default

if (!BAGS_API_KEY) {
  console.error("BAGS_API_KEY is required");
  process.exit(1);
}

const bagsClient = new BagsClient(BAGS_API_KEY, SOLANA_RPC_URL);

// Track usage for analytics/billing
interface UsageRecord {
  timestamp: Date;
  inputMint: string;
  outputMint: string;
  amount: number;
  outAmount: string;
  userAddress?: string;
  ip: string;
}

const usageLog: UsageRecord[] = [];

// Middleware to log requests
app.use((req: Request, _res: Response, next: NextFunction) => {
  console.log(`${new Date().toISOString()} ${req.method} ${req.path}`);
  next();
});

// Health check
app.get("/health", (_req: Request, res: Response) => {
  res.json({ status: "ok", serviceFee: `${SERVICE_FEE_BPS / 100}%` });
});

// Get quote for a swap
app.post("/quote", async (req: Request, res: Response) => {
  try {
    const { inputMint, outputMint, amount, slippageMode, slippageBps } =
      req.body;

    if (!inputMint || !outputMint || !amount) {
      res
        .status(400)
        .json({ error: "inputMint, outputMint, and amount are required" });
      return;
    }

    const params: QuoteParams = {
      inputMint,
      outputMint,
      amount: parseInt(amount, 10),
      slippageMode: slippageMode || "auto",
      slippageBps: slippageBps ? parseInt(slippageBps, 10) : undefined,
    };

    const quote = await bagsClient.getQuote(params);

    // Calculate service fee display
    const serviceFeeAmount = Math.floor(
      (parseInt(quote.outAmount) * SERVICE_FEE_BPS) / 10000
    );

    res.json({
      ...quote,
      serviceFee: {
        bps: SERVICE_FEE_BPS,
        percentage: `${SERVICE_FEE_BPS / 100}%`,
        estimatedAmount: serviceFeeAmount.toString(),
      },
    });
  } catch (error: any) {
    console.error("Quote error:", error);
    res.status(500).json({ error: error.message || "Failed to get quote" });
  }
});

// Create swap transaction
app.post("/swap", async (req: Request, res: Response) => {
  try {
    const { quoteResponse, userPublicKey } = req.body;

    if (!quoteResponse || !userPublicKey) {
      res
        .status(400)
        .json({ error: "quoteResponse and userPublicKey are required" });
      return;
    }

    const swapResult = await bagsClient.createSwapTransaction({
      quoteResponse,
      userPublicKey,
    });

    // Log usage
    usageLog.push({
      timestamp: new Date(),
      inputMint: quoteResponse.routePlan?.[0]?.inputMint || "unknown",
      outputMint:
        quoteResponse.routePlan?.[quoteResponse.routePlan.length - 1]
          ?.outputMint || "unknown",
      amount: parseInt(quoteResponse.inAmount, 10),
      outAmount: quoteResponse.outAmount,
      userAddress: userPublicKey,
      ip: req.ip || "unknown",
    });

    res.json(swapResult);
  } catch (error: any) {
    console.error("Swap error:", error);
    res
      .status(500)
      .json({ error: error.message || "Failed to create swap transaction" });
  }
});

// Get popular token pairs (for UI suggestions)
app.get("/tokens/popular", (_req: Request, res: Response) => {
  // Common Solana tokens
  const popularTokens = [
    {
      symbol: "SOL",
      mint: "So11111111111111111111111111111111111111112",
      name: "Solana",
      decimals: 9,
    },
    {
      symbol: "USDC",
      mint: "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
      name: "USD Coin",
      decimals: 6,
    },
    {
      symbol: "USDT",
      mint: "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
      name: "Tether USD",
      decimals: 6,
    },
    {
      symbol: "BONK",
      mint: "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
      name: "Bonk",
      decimals: 5,
    },
    {
      symbol: "JUP",
      mint: "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
      name: "Jupiter",
      decimals: 6,
    },
    {
      symbol: "WIF",
      mint: "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
      name: "dogwifhat",
      decimals: 6,
    },
  ];

  res.json(popularTokens);
});

// Usage stats (for admin)
app.get("/admin/stats", (req: Request, res: Response) => {
  const adminKey = req.headers["x-admin-key"];

  // Simple admin auth - use a proper auth system in production
  if (adminKey !== process.env.ADMIN_KEY) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }

  const totalSwaps = usageLog.length;
  const totalVolume = usageLog.reduce((sum, r) => sum + r.amount, 0);
  const last24h = usageLog.filter(
    (r) => r.timestamp > new Date(Date.now() - 24 * 60 * 60 * 1000)
  );

  res.json({
    totalSwaps,
    totalVolume,
    swapsLast24h: last24h.length,
    volumeLast24h: last24h.reduce((sum, r) => sum + r.amount, 0),
    serviceFeesBps: SERVICE_FEE_BPS,
    recentSwaps: usageLog.slice(-10).reverse(),
  });
});

app.listen(PORT, () => {
  console.log(`
  ====================================
    Bags Swap API Server
  ====================================

  Server running on http://localhost:${PORT}

  Endpoints:
    GET  /health          - Health check
    POST /quote           - Get swap quote
    POST /swap            - Create swap transaction
    GET  /tokens/popular  - Popular token list
    GET  /admin/stats     - Usage statistics (requires x-admin-key header)

  Service Fee: ${SERVICE_FEE_BPS / 100}%

  ====================================
  `);
});
