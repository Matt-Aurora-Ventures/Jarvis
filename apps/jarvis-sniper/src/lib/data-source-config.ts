/**
 * Data source feature flags for the sniper's real-time feed.
 *
 * Controls which WebSocket sources are active for token discovery.
 * All values are client-safe (NEXT_PUBLIC_ prefixed in .env).
 *
 * Options:
 *   - "pumpportal"      : PumpPortal WSS (free, primary — VoxForge approach)
 *   - "logs-subscribe"  : Helius logsSubscribe (standard WSS, $49/mo tier)
 *   - "poll-only"       : Existing DexScreener REST polling (fallback)
 */

export type DataSourceMode = 'pumpportal' | 'logs-subscribe' | 'poll-only';

export const DATA_SOURCE: DataSourceMode =
  (process.env.NEXT_PUBLIC_DATA_SOURCE as DataSourceMode) || 'pumpportal';

export const PUMPPORTAL_WS_URL =
  process.env.NEXT_PUBLIC_PUMPPORTAL_WS || 'wss://pumpportal.fun/api/data';

/** PumpFun program ID — verified on Solscan */
export const PUMPFUN_PROGRAM_ID = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P';
