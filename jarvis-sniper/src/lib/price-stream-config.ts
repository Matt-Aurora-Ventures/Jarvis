/**
 * Price stream feature flags.
 *
 * Controls whether the DexPaprika SSE stream is active for real-time P&L pricing.
 * When active, REST polling (DexScreener/Jupiter) drops to a 15s fallback.
 *
 * Options:
 *   - "dexpaprika"  : DexPaprika SSE (free, ~1s updates, primary)
 *   - "poll-only"   : Existing DexScreener/Jupiter REST polling (fallback)
 */

export type PriceStreamMode = 'dexpaprika' | 'poll-only';

export const PRICE_STREAM_MODE: PriceStreamMode =
  (process.env.NEXT_PUBLIC_PRICE_STREAM as PriceStreamMode) || 'dexpaprika';

export const DEXPAPRIKA_STREAM_URL =
  process.env.NEXT_PUBLIC_DEXPAPRIKA_URL || 'https://streaming.dexpaprika.com/stream';

/** When SSE is active, slow REST polling to this interval (fallback only). */
export const SSE_ACTIVE_POLL_MS = 15_000;

/** Default REST poll interval when SSE is inactive. */
export const DEFAULT_POLL_MS = 3_000;
