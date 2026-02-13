/**
 * Build a Solana RPC URL compatible with @solana/web3.js Connection.
 * Connection requires an absolute http(s) URL (not a relative path).
 */
import { Connection, type Commitment } from '@solana/web3.js';

export function getRpcUrl(): string {
  if (typeof window !== 'undefined') {
    try {
      return new URL('/api/rpc', window.location.origin).toString();
    } catch {
      return `${window.location.origin}/api/rpc`;
    }
  }

  // SSR/test fallback only (no secrets in client bundles).
  return process.env.SOLANA_RPC_URL || process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com';
}

function httpToWsUrl(url: string): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith('wss://') || trimmed.startsWith('ws://')) return trimmed;
  if (trimmed.startsWith('https://')) return `wss://${trimmed.slice('https://'.length)}`;
  if (trimmed.startsWith('http://')) return `ws://${trimmed.slice('http://'.length)}`;
  return null;
}

export function getRpcWsUrl(): string {
  const explicitWs = httpToWsUrl(process.env.NEXT_PUBLIC_SOLANA_WS || '');
  if (explicitWs) return explicitWs;

  const fromPublicRpc = httpToWsUrl(process.env.NEXT_PUBLIC_SOLANA_RPC || '');
  if (fromPublicRpc) return fromPublicRpc;

  // Browser-safe default.
  return 'wss://api.mainnet-beta.solana.com';
}

/**
 * Create a Connection configured for the current environment.
 * Client-side: uses /api/rpc proxy for HTTP RPC and a valid WS endpoint for subscriptions.
 * Server-side: uses SOLANA_RPC_URL directly.
 */
export function getConnection(commitment: Commitment = 'confirmed'): Connection {
  const url = getRpcUrl();
  const isProxy = typeof window !== 'undefined'; // client uses the proxy

  if (isProxy) {
    // Keep HTTP RPC on the local proxy, but point WS to a real endpoint so
    // web3 subscriptions don't emit noisy "ws error: undefined" logs.
    return new Connection(url, {
      commitment,
      // We handle upstream retry/backoff inside /api/rpc. Keep client-side
      // rate-limit retry disabled to avoid noisy console "429 retry" logs.
      disableRetryOnRateLimit: true,
      wsEndpoint: getRpcWsUrl(),
    });
  }

  return new Connection(url, commitment);
}
