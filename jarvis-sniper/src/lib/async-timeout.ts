/**
 * Promise timeout helper that clears its timer on resolve/reject.
 *
 * IMPORTANT:
 * Avoid `Promise.race([promise, timeoutRejectPromise])` without cleanup.
 * If `promise` wins the race, the timeout promise can still reject later and
 * surface as an unhandled rejection in the browser (causing flaky hangs/locks).
 */

export async function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
  label: string,
): Promise<T> {
  const ms = Math.max(1_000, Math.floor(timeoutMs || 0));
  const name = label || 'operation';

  let timer: ReturnType<typeof setTimeout> | null = null;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error(`Timeout (${ms}ms): ${name}`)), ms);
  });

  try {
    return await Promise.race([promise, timeout]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

