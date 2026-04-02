import { PublicKey } from '@solana/web3.js';

// ─── Solana Program IDs ──────────────────────────────────────
export const RAYDIUM_AMM_V4 = new PublicKey('675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8');
export const PUMPFUN_PROGRAM = new PublicKey('6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P');
export const TOKEN_PROGRAM_ID = new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA');
export const ASSOCIATED_TOKEN_PROGRAM = new PublicKey('ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL');

// ─── Token Mints ─────────────────────────────────────────────
export const WSOL_MINT = new PublicKey('So11111111111111111111111111111111111111112');
export const USDC_MINT = new PublicKey('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v');
export const USDT_MINT = new PublicKey('Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB');

// ─── API Endpoints ───────────────────────────────────────────
export const JUPITER_QUOTE_API = 'https://quote-api.jup.ag/v6';
export const JUPITER_PRICE_API = 'https://price.jup.ag/v6';
export const RUGCHECK_API = 'https://api.rugcheck.xyz/v1';
export const GOPLUS_API = 'https://api.gopluslabs.io/api/v1';
export const BIRDEYE_API = 'https://public-api.birdeye.so';
export const DEXSCREENER_API = 'https://api.dexscreener.com/latest/dex';
export const PUMPPORTAL_WS = 'wss://pumpportal.fun/api/data';
export const JITO_BLOCK_ENGINE = 'https://mainnet.block-engine.jito.wtf';
export const XAI_API = 'https://api.x.ai/v1';

// ─── Jito Tip Accounts ──────────────────────────────────────
export const JITO_TIP_ACCOUNTS = [
  '96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5',
  'HFqU5x63VTqvQss8hp11i4bPuNjRBpLFTa4OEZBpskuR',
  'Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY',
  'ADaUMid9yfUytqMBgopwjb2DTLSl8hLFaw5GiiFqeMww',
  'DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh',
  'ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt',
  'DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL',
  '3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT',
];

// ─── Trading Defaults ────────────────────────────────────────
export const DEFAULT_SLIPPAGE_BPS = 300; // 3%
export const DEFAULT_PRIORITY_FEE_LAMPORTS = 100_000; // 0.0001 SOL
export const JITO_TIP_LAMPORTS = 100_000; // 0.0001 SOL
export const SOL_DECIMALS = 9;
export const LAMPORTS_PER_SOL = 1_000_000_000;

// ─── Risk Tier Config ────────────────────────────────────────
export const RISK_TIERS = {
  ESTABLISHED: { positionPct: 1.0, tpPct: 30, slPct: 15 },
  MID:         { positionPct: 0.5, tpPct: 50, slPct: 25 },
  MICRO:       { positionPct: 0.25, tpPct: 100, slPct: 40 },
  HIGH_RISK:   { positionPct: 0.15, tpPct: 150, slPct: 50 },
} as const;

// ─── Safety Thresholds ───────────────────────────────────────
export const SAFETY_WEIGHTS = {
  mintAuthority: 0.18,
  freezeAuthority: 0.12,
  lpBurned: 0.18,
  holderConcentration: 0.12,
  liquidity: 0.10,
  honeypot: 0.10,
  metadataImmutable: 0.05,
  jupiterVerified: 0.05,
  deployerHistory: 0.10,
} as const;

export const SAFETY_PASS_THRESHOLD = 0.6;
export const MIN_LP_BURNED_PCT = 90;
export const MAX_TOP10_HOLDER_PCT = 50;
export const MIN_HOLDER_COUNT = 10;
