import type { TradeTelemetryIngest } from './types';

/**
 * Best-effort client telemetry. Never blocks trading UX.
 *
 * Notes:
 * - Firebase Hosting does NOT store swaps/trades. Without this, only the browser that
 *   executed a trade knows about it (localStorage Zustand persist).
 * - We intentionally keep this "fire-and-forget" and skip entirely in tests/SSR.
 */
export function postTradeTelemetry(payload: TradeTelemetryIngest): void {
  if (typeof window === 'undefined') return;
  if (process.env.NODE_ENV === 'test') return;

  try {
    const body = JSON.stringify(payload);
    // Prefer beacon so we still transmit when the user navigates away.
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      const blob = new Blob([body], { type: 'application/json' });
      navigator.sendBeacon('/api/autonomy/telemetry/trade', blob);
      return;
    }

    void fetch('/api/autonomy/telemetry/trade', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    });
  } catch {
    // ignore
  }
}

