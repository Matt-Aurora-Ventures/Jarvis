/**
 * Jito Bundle Infrastructure
 *
 * Enables atomic batching of up to 5 transactions per bundle.
 * Used for: Close All (batch sells), rent reclamation (burn+close).
 *
 * How it works:
 * 1. Build swap TXs for each position via Bags API
 * 2. Add a tip TX (SOL transfer to random Jito validator)
 * 3. User signs all TXs in one Phantom popup (signAllTransactions)
 * 4. Send bundle to Jito Block Engine via server proxy
 *
 * Benefits:
 * - Atomic: all succeed or all revert (no partial fills)
 * - No wasted fees: tip only paid if bundle lands
 * - Speed: bypasses public mempool congestion
 */

import { PublicKey } from '@solana/web3.js';

/** Jito Block Engine URL (US-East) */
export const JITO_BLOCK_ENGINE_URL = 'https://mainnet.block-engine.jito.wtf/api/v1/bundles';

/** Official Jito Tip Accounts — randomize to avoid write-lock contention */
export const JITO_TIP_ACCOUNTS = [
  '96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5',
  'HFqU5x63VTqvQss8hp11i4wVV8bD44PuyBrYKsLCZbCj',
  'Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLwU9j',
  'ADaUMid9yfUytqMBgopXSjbCpRGRUEHVNAq11zXkd5f',
  'DfXygSm4jCyNCyb3qzK6966vG9T0m8sxb9q4dE5Q469',
  '3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnIzKZ6jJ',
  'DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL',
].map((addr) => new PublicKey(addr));

/** Pick a random tip account to avoid contention */
export function getRandomTipAccount(): PublicKey {
  return JITO_TIP_ACCOUNTS[Math.floor(Math.random() * JITO_TIP_ACCOUNTS.length)];
}

/** Default tip: 0.001 SOL — enough for fast inclusion */
export const DEFAULT_TIP_LAMPORTS = 1_000_000;

/** Max transactions per Jito bundle (5 total: 4 swaps + 1 tip) */
export const MAX_BUNDLE_SIZE = 5;
export const MAX_SWAPS_PER_BUNDLE = MAX_BUNDLE_SIZE - 1; // Reserve 1 slot for tip

/**
 * Submit a bundle of signed, base64-encoded transactions to Jito Block Engine
 * via our Next.js API proxy (avoids CORS issues).
 */
export async function submitJitoBundle(
  encodedTransactions: string[],
): Promise<{ bundleId?: string; error?: string }> {
  try {
    const res = await fetch('/api/jito/bundle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transactions: encodedTransactions }),
    });
    return await res.json();
  } catch (err: any) {
    return { error: err.message || 'Failed to submit Jito bundle' };
  }
}
