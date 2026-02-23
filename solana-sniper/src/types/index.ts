import { PublicKey } from '@solana/web3.js';

// ─── Token Info ───────────────────────────────────────────────
export interface TokenInfo {
  mint: string;
  symbol: string;
  name: string;
  decimals: number;
  supply: number;
  source: 'raydium' | 'pumpfun' | 'twitter' | 'manual';
  discoveredAt: number; // unix ms
  poolAddress?: string;
  pairAddress?: string;
  baseVault?: string;
  quoteVault?: string;
}

// ─── Safety Analysis ──────────────────────────────────────────
export interface MintCheckResult {
  mintAuthorityRevoked: boolean;
  freezeAuthorityRevoked: boolean;
  mintAuthority: string | null;
  freezeAuthority: string | null;
}

export interface LPAnalysisResult {
  lpBurnedPct: number;
  lpLockedPct: number;
  totalLpSupply: number;
  isLpSafe: boolean;
}

export interface HolderAnalysisResult {
  topHolders: Array<{ address: string; pct: number }>;
  top10ConcentrationPct: number;
  holderCount: number;
  isSafe: boolean;
}

export interface RugCheckResult {
  score: number; // 0-100, higher = safer
  risks: string[];
  isVerified: boolean;
  reportUrl: string;
}

export interface GoPlusResult {
  isHoneypot: boolean;
  hasProxyContract: boolean;
  canTakeBackOwnership: boolean;
  hasMintFunction: boolean;
  isOpenSource: boolean;
  buyTax: number;
  sellTax: number;
  risks: string[];
}

export interface SafetyResult {
  mint: string;
  overallScore: number; // 0-1, higher = safer
  passed: boolean;
  mintCheck: MintCheckResult;
  lpAnalysis: LPAnalysisResult | null;
  holderAnalysis: HolderAnalysisResult | null;
  rugCheck: RugCheckResult | null;
  goPlus: GoPlusResult | null;
  failReasons: string[];
  checkedAt: number;
}

// ─── Trading ──────────────────────────────────────────────────
export type TradeSide = 'BUY' | 'SELL';
export type TradeStatus = 'PENDING' | 'EXECUTED' | 'FAILED' | 'SIMULATED';
export type PositionStatus = 'OPEN' | 'CLOSED' | 'STOPPED_OUT' | 'TP_HIT';

export interface TradeSignal {
  mint: string;
  symbol: string;
  action: TradeSide;
  confidence: number; // 0-1
  source: string;
  reasoning: string;
  safetyScore: number;
  timestamp: number;
}

export interface SwapQuote {
  inputMint: string;
  outputMint: string;
  inAmount: string;
  outAmount: string;
  priceImpactPct: number;
  slippageBps: number;
  routePlan: string;
  otherAmountThreshold: string;
}

export interface ExecutionResult {
  success: boolean;
  signature: string | null;
  error: string | null;
  side: TradeSide;
  mint: string;
  amountIn: number;
  amountOut: number;
  priceUsd: number;
  feeUsd: number;
  executedAt: number;
  mode: 'paper' | 'live';
  latencyMs: number;
}

export interface Position {
  id: string;
  mint: string;
  symbol: string;
  status: PositionStatus;
  side: TradeSide;
  entryPrice: number;
  currentPrice: number;
  amount: number;
  amountUsd: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  stopLossPct: number;
  takeProfitPct: number;
  entrySignature: string | null;
  exitSignature: string | null;
  safetyScore: number;
  openedAt: number;
  closedAt: number | null;
  exitReason: string | null;
}

// ─── Risk Management ──────────────────────────────────────────
export type RiskTier = 'ESTABLISHED' | 'MID' | 'MICRO' | 'HIGH_RISK';

export interface RiskParams {
  maxPositionUsd: number;
  maxConcurrentPositions: number;
  stopLossPct: number;
  takeProfitPct: number;
  circuitBreakerFloorUsd: number;
  minLiquidityUsd: number;
  maxDailyLossUsd: number;
}

export interface PositionSizeResult {
  recommendedUsd: number;
  riskTier: RiskTier;
  stopLossPct: number;
  takeProfitPct: number;
  reasoning: string;
}

// ─── Analysis ─────────────────────────────────────────────────
export interface SentimentResult {
  mint: string;
  symbol: string;
  score: number; // -1 to +1
  confidence: number;
  source: string;
  reasoning: string;
  analyzedAt: number;
}

export interface AggregatedSignal {
  mint: string;
  symbol: string;
  buyScore: number; // 0-1
  safetyScore: number;
  sentimentScore: number;
  liquidityUsd: number;
  volumeUsd24h: number;
  priceUsd: number;
  shouldBuy: boolean;
  reasoning: string;
  sources: string[];
  timestamp: number;
}

// ─── Listener Events ──────────────────────────────────────────
export interface NewPoolEvent {
  type: 'raydium_pool' | 'pumpfun_launch';
  mint: string;
  poolAddress: string;
  baseMint: string;
  quoteMint: string;
  baseVault: string;
  quoteVault: string;
  lpMint: string;
  timestamp: number;
  raw: unknown;
}

export interface TwitterSignalEvent {
  type: 'twitter_signal';
  mint: string | null;
  symbol: string | null;
  tweetId: string;
  author: string;
  text: string;
  sentiment: number;
  timestamp: number;
}

// ─── Config ───────────────────────────────────────────────────
export interface AppConfig {
  rpcUrl: string;
  heliusApiKey: string;
  walletPrivateKey: string;
  jupiterApiBase: string;
  rugcheckApiKey: string;
  goPlusApiKey: string;
  birdeyeApiKey: string;
  xaiApiKey: string;
  twitterBearerToken: string;
  jitoTipAccount: string;
  jitoBlockEngineUrl: string;
  pumpPortalWsUrl: string;
  bagsApiKey: string;
  tradingMode: 'paper' | 'live';
  risk: RiskParams;
}

// ─── Database ─────────────────────────────────────────────────
export interface TradeRecord {
  id: string;
  mint: string;
  symbol: string;
  side: TradeSide;
  amountUsd: number;
  amountToken: number;
  priceUsd: number;
  safetyScore: number;
  signature: string | null;
  status: TradeStatus;
  mode: 'paper' | 'live';
  pnlUsd: number | null;
  pnlPct: number | null;
  entryAt: number;
  exitAt: number | null;
  exitReason: string | null;
  metadata: string; // JSON
}
