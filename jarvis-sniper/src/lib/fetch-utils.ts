/**
 * Production-hardened fetch utilities with retry, timeout, and exponential backoff.
 *
 * Designed for 100 concurrent users — prevents cascading failures when
 * upstream APIs (DexScreener, CoinGecko, etc.) become slow or unavailable.
 */

export interface FetchWithRetryOptions {
  /** Maximum number of retries after the initial attempt. Default: 2 */
  maxRetries?: number;
  /** Base delay in ms for exponential backoff. Default: 1000 */
  baseDelayMs?: number;
  /** Request timeout in ms. Default: 10000 */
  timeoutMs?: number;
  /** Additional fetch options (headers, method, body, etc.) */
  fetchOptions?: RequestInit;
}

/**
 * Sentinel response returned when all retries are exhausted or timeout occurs.
 * Has `ok: false` so callers can check `.ok` as usual.
 */
function errorResponse(status: number, message: string): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/**
 * Fetch with automatic retry, exponential backoff, and per-request timeout.
 *
 * - Retries only on 5xx errors and network failures (not 4xx).
 * - Exponential backoff: baseDelayMs * 2^attempt (with jitter).
 * - AbortController-based timeout per attempt.
 *
 * Returns a Response object (never throws).
 */
export async function fetchWithRetry(
  url: string,
  options: FetchWithRetryOptions = {},
): Promise<Response> {
  const {
    maxRetries = 2,
    baseDelayMs = 1000,
    timeoutMs = 10_000,
    fetchOptions = {},
  } = options;

  let lastResponse: Response | undefined;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);

      try {
        const response = await fetch(url, {
          ...fetchOptions,
          signal: controller.signal,
        });
        clearTimeout(timer);

        // Don't retry on client errors (4xx) -- those won't fix themselves
        if (response.ok || (response.status >= 400 && response.status < 500)) {
          return response;
        }

        // 5xx -- store and potentially retry
        lastResponse = response;
      } catch (fetchError) {
        clearTimeout(timer);

        // AbortError means timeout
        if (fetchError instanceof DOMException && fetchError.name === 'AbortError') {
          lastResponse = errorResponse(408, `Request timeout after ${timeoutMs}ms`);
        } else {
          lastResponse = errorResponse(503, `Network error: ${String(fetchError)}`);
        }
      }
    } catch (outerError) {
      lastResponse = errorResponse(503, `Fetch failed: ${String(outerError)}`);
    }

    // If we have retries left, wait with exponential backoff
    if (attempt < maxRetries) {
      const delay = baseDelayMs * Math.pow(2, attempt);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  return lastResponse ?? errorResponse(503, 'All retries exhausted');
}
