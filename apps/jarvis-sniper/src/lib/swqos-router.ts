/**
 * SWQoS (Solana Web Quality of Service) Multi-Provider Router
 *
 * Races transaction submission across multiple providers for faster
 * confirmation and resilience.  First successful confirmation wins.
 *
 * Architecture pattern inspired by dexbotsdev/sol-trade-sdk SWQoS design:
 *   https://github.com/dexbotsdev/sol-trade-sdk
 *
 * dexbotsdev implements 6+ concurrent SWQoS providers (Jito, NextBlock, Blox,
 * ZeroSlot, Temporal, Astralane) via a shared trait interface.  We adapt that
 * pattern for the browser-side TypeScript environment with Jito bundles as the
 * primary provider and direct RPC as fallback.
 */

// ─── Provider Interface ────────────────────────────────────────────────────

export interface SWQoSProvider {
  /** Human-readable name for logging / telemetry. */
  readonly name: string;

  /**
   * Submit one or more base64-encoded signed transactions.
   * Returns an opaque identifier (e.g. bundle ID, tx signature).
   */
  sendTransactions(encodedTxs: string[]): Promise<string>;
}

// ─── Jito Provider ─────────────────────────────────────────────────────────

/**
 * Submits via our `/api/jito/bundle` proxy which forwards to the Jito Block
 * Engine.  Atomic bundles — all-or-nothing execution.
 */
export class JitoProvider implements SWQoSProvider {
  readonly name = 'jito';

  async sendTransactions(encodedTxs: string[]): Promise<string> {
    const res = await fetch('/api/jito/bundle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transactions: encodedTxs }),
    });
    const json = await res.json();
    if (json.error) throw new Error(`Jito: ${json.error}`);
    return json.bundleId ?? 'jito-ok';
  }
}

// ─── Direct RPC Provider ───────────────────────────────────────────────────

/**
 * Falls back to the public RPC `sendTransaction` endpoint.
 * No MEV protection, but works when Jito is overloaded or unreachable.
 */
export class DirectRpcProvider implements SWQoSProvider {
  readonly name = 'rpc';
  private readonly rpcUrl: string;

  constructor(rpcUrl?: string) {
    this.rpcUrl = rpcUrl || (typeof window !== 'undefined'
      ? (window as any).__SOLANA_RPC_URL ?? ''
      : '') || '';
  }

  async sendTransactions(encodedTxs: string[]): Promise<string> {
    if (!this.rpcUrl) throw new Error('RPC URL not configured');

    // Send each TX individually (RPC doesn't support bundles).
    const results = await Promise.all(
      encodedTxs.map(async (tx) => {
        const res = await fetch(this.rpcUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0',
            id: 1,
            method: 'sendTransaction',
            params: [tx, { encoding: 'base64', skipPreflight: false }],
          }),
        });
        const json = await res.json();
        if (json.error) throw new Error(`RPC: ${json.error.message}`);
        return json.result as string;
      }),
    );
    return results[0] ?? 'rpc-ok';
  }
}

// ─── Router ────────────────────────────────────────────────────────────────

export interface SWQoSRouterOptions {
  /** Providers to race, in priority order. Default: [Jito, DirectRpc]. */
  providers?: SWQoSProvider[];
  /** Timeout per provider attempt in ms.  Default: 15_000 (15s). */
  timeoutMs?: number;
  /** Called on each provider result for telemetry. */
  onResult?: (provider: string, ok: boolean, durationMs: number, error?: string) => void;
}

/**
 * Race transaction submission across providers.
 *
 * Uses `Promise.any` — first provider to succeed wins, others are ignored.
 * If all fail, the aggregate error is thrown.
 */
export async function raceSubmit(
  encodedTxs: string[],
  opts: SWQoSRouterOptions = {},
): Promise<{ provider: string; result: string; durationMs: number }> {
  const providers = opts.providers ?? [new JitoProvider(), new DirectRpcProvider()];
  const timeoutMs = opts.timeoutMs ?? 15_000;

  const attempts = providers.map(async (p) => {
    const start = Date.now();
    try {
      const result = await Promise.race([
        p.sendTransactions(encodedTxs),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error(`${p.name}: timeout (${timeoutMs}ms)`)), timeoutMs),
        ),
      ]);
      const durationMs = Date.now() - start;
      opts.onResult?.(p.name, true, durationMs);
      return { provider: p.name, result, durationMs };
    } catch (err) {
      const durationMs = Date.now() - start;
      const msg = err instanceof Error ? err.message : String(err);
      opts.onResult?.(p.name, false, durationMs, msg);
      throw err;
    }
  });

  return Promise.any(attempts);
}
