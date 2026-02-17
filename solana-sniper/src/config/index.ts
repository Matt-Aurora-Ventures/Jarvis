import dotenv from 'dotenv';
import path from 'path';
import type { AppConfig, RiskParams } from '../types/index.js';

dotenv.config({ path: path.resolve(process.cwd(), '.env') });

function env(key: string, fallback?: string): string {
  const val = process.env[key] ?? fallback;
  if (val === undefined) {
    throw new Error(`Missing required env var: ${key}`);
  }
  return val;
}

function envNum(key: string, fallback: number): number {
  const val = process.env[key];
  return val ? parseFloat(val) : fallback;
}

const risk: RiskParams = {
  maxPositionUsd: envNum('MAX_POSITION_USD', 2.50),
  maxConcurrentPositions: envNum('MAX_CONCURRENT_POSITIONS', 3),
  stopLossPct: envNum('STOP_LOSS_PCT', 30),
  takeProfitPct: envNum('TAKE_PROFIT_PCT', 100),
  circuitBreakerFloorUsd: envNum('CIRCUIT_BREAKER_FLOOR_USD', 30),
  minLiquidityUsd: envNum('MIN_LIQUIDITY_USD', 10000),
  maxDailyLossUsd: envNum('MAX_DAILY_LOSS_USD', 10),
};

export const config: AppConfig = {
  rpcUrl: env('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com'),
  heliusApiKey: env('HELIUS_API_KEY', ''),
  walletPrivateKey: env('WALLET_PRIVATE_KEY', ''),
  jupiterApiBase: env('JUPITER_API_BASE', 'https://quote-api.jup.ag/v6'),
  rugcheckApiKey: env('RUGCHECK_API_KEY', ''),
  goPlusApiKey: env('GOPLUS_API_KEY', ''),
  birdeyeApiKey: env('BIRDEYE_API_KEY', ''),
  xaiApiKey: env('XAI_API_KEY', ''),
  twitterBearerToken: env('TWITTER_BEARER_TOKEN', ''),
  jitoTipAccount: env('JITO_TIP_ACCOUNT', ''),
  jitoBlockEngineUrl: env('JITO_BLOCK_ENGINE_URL', 'https://mainnet.block-engine.jito.wtf'),
  pumpPortalWsUrl: env('PUMPPORTAL_WS_URL', 'wss://pumpportal.fun/api/data'),
  bagsApiKey: env('BAGS_API_KEY', ''),
  tradingMode: (process.env.TRADING_MODE as 'paper' | 'live') ?? 'paper',
  risk,
};

export default config;
