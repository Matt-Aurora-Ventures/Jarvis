import { buildAutonomyTelemetryHeaders, getAutonomyTelemetryToken } from './client-auth';
export interface TradeTelemetryEvent {
  schemaVersion: number;
  eventType?: 'trade_closed' | 'sell_attempt';
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
  includedInExecutionStats?: boolean;
  executionOutcome?: 'confirmed' | 'failed' | 'unresolved' | 'no_route';
  failureCode?: string | null;
  failureReason?: string | null;
  attemptIndex?: number | null;
  manualOnly?: boolean;
  recoveredFrom?: string | null;
  tradeSignerMode?: string;
  sessionWalletPubkey?: string | null;
  activePreset?: string | null;
  trustLevel?: 'trusted' | 'untrusted';
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
    const telemetryToken = getAutonomyTelemetryToken();

    // sendBeacon cannot attach Authorization headers, so only use it when telemetry auth is not configured.
    if (!telemetryToken && typeof navigator !== 'undefined' && typeof (navigator as any).sendBeacon === 'function') {
      const blob = new Blob([body], { type: 'application/json' });
      (navigator as any).sendBeacon(url, blob);
      return;
    }

    if (typeof fetch === 'function') {
      const headers = buildAutonomyTelemetryHeaders({ 'content-type': 'application/json' });
      void fetch(url, {
        method: 'POST',
        headers,
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
