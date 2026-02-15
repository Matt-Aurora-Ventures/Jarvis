export interface TradeTelemetryEvent {
  schemaVersion: number;
  positionId: string;
  mint: string;
  status: string;
  symbol?: string;
  walletAddress?: string | null;
  strategyId?: string | null;
  entrySource?: 'auto' | 'manual' | null;
  entryTime?: number | null;
  exitTime?: number | null;
  solInvested?: number | null;
  exitSolReceived?: number | null;
  pnlSol?: number | null;
  pnlPercent?: number | null;
  buyTxHash?: string | null;
  sellTxHash?: string | null;
  includedInStats?: boolean;
  manualOnly?: boolean;
  recoveredFrom?: string | null;
  tradeSignerMode?: string;
  sessionWalletPubkey?: string | null;
  activePreset?: string | null;
}

/**
 * Best-effort telemetry client.
 *
 * This must never throw: trading execution should not be blocked by analytics.
 */
export function postTradeTelemetry(event: TradeTelemetryEvent): void {
  try {
    // Server-side / tests: no-op.
    if (typeof window === 'undefined') return;

    const url = '/api/autonomy/trade-telemetry';
    const body = JSON.stringify(event);

    // Prefer beacon for unload-safe delivery.
    if (typeof navigator !== 'undefined' && typeof (navigator as any).sendBeacon === 'function') {
      const blob = new Blob([body], { type: 'application/json' });
      (navigator as any).sendBeacon(url, blob);
      return;
    }

    if (typeof fetch === 'function') {
      void fetch(url, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body,
        keepalive: true,
      }).catch(() => {
        // ignore
      });
    }
  } catch {
    // ignore
  }
}
