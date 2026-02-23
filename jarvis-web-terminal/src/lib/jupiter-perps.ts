/**
 * Jupiter Perpetuals — Constants & Helpers
 *
 * Program: PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu
 * Model:   Keeper-fulfillment (request → keeper executes)
 * Max leverage: 250× UI / 500× on-chain
 *
 * MVP: Deep-link to jup.ag/perps with correct market pre-selected.
 * Full on-chain integration (Anchor IDL) is a future phase.
 */

import { PublicKey } from '@solana/web3.js';

// ── Program & Pool ──────────────────────────────────────────────
export const PERPS_PROGRAM = new PublicKey('PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu');
export const JLP_POOL     = new PublicKey('5BUwFW4nRbftYTDMbgxykoFWqWHPzahFSNAaaaJtVKsq');

// ── Custody Accounts ────────────────────────────────────────────
export const CUSTODY = {
  SOL:  new PublicKey('7xS2gz2bTp3fwCC7knJvUWTEU9Tycczu6VhJYKgi1wdz'),
  ETH:  new PublicKey('AQCGyheWPLeo764u9FMaPkJiyqdpVfRdiHGVHwJ6JBWL'),
  BTC:  new PublicKey('5Pv3gM9JrFFH883SWAhvJC9RPYmo8UNxuFtv5bMMALkm'),
  USDC: new PublicKey('G18jKKXQwBbrHeiK3C9MRXhkHsLHf7XgCSisykV46EZa'),
  USDT: new PublicKey('4vkNeXiYEUizLdrpdPS1eC2mccyM4NUPRtERrk6ZETkk'),
} as const;

// ── Token Mints ─────────────────────────────────────────────────
export const MINTS = {
  SOL:  new PublicKey('So11111111111111111111111111111111111111112'),
  USDC: new PublicKey('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'),
  ETH:  new PublicKey('7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs'),
  BTC:  new PublicKey('3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh'),
  USDT: new PublicKey('Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'),
} as const;

// ── Perps Markets ───────────────────────────────────────────────
export type PerpsMarket = 'SOL' | 'ETH' | 'BTC';

export const PERPS_MARKETS: Record<PerpsMarket, {
  label: string;
  maxLeverage: number;
  collateralLong: keyof typeof MINTS;
  collateralShort: keyof typeof MINTS;
}> = {
  SOL: { label: 'SOL-PERP', maxLeverage: 250, collateralLong: 'SOL', collateralShort: 'USDC' },
  ETH: { label: 'ETH-PERP', maxLeverage: 250, collateralLong: 'ETH', collateralShort: 'USDC' },
  BTC: { label: 'BTC-PERP', maxLeverage: 250, collateralLong: 'BTC', collateralShort: 'USDC' },
};

// ── Deep-link builder ───────────────────────────────────────────
export function getPerpsDeepLink(market: PerpsMarket): string {
  return `https://jup.ag/perps/${market}-PERP`;
}

// ── Fee constants ───────────────────────────────────────────────
export const FEES = {
  openCloseBps: 6,          // 0.06% each way
  // Borrow fees are per-hour, variable by utilisation
  // Price impact is dynamic based on position size vs pool depth
} as const;
