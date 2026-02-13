/**
 * GeckoTerminal fetch helpers (paced)
 *
 * GeckoTerminal free tier is rate-limited (~30 req/min). Strategy Validation and
 * universe discovery can easily exceed that, causing 429s and flaky results.
 *
 * This helper serializes GeckoTerminal requests on the server with a minimum
 * interval, and retries a few times on 429.
 */

// GeckoTerminal free tier is rate-limited and can 429 even at ~27 req/min.
// Be conservative for reliability (especially when paging OHLCV/universe).
const GECKO_MIN_INTERVAL_MS = 3000; // ~20 req/min with buffer
const GECKO_TIMEOUT_MS = 25_000;

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

let geckoChain: Promise<Response> = Promise.resolve(null as unknown as Response);
let geckoLastAt = 0;

async function doFetch(url: string): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), GECKO_TIMEOUT_MS);
  try {
    return await fetch(url, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

async function runPaced(url: string): Promise<Response> {
  const waitMs = Math.max(0, geckoLastAt + GECKO_MIN_INTERVAL_MS - Date.now());
  if (waitMs > 0) await sleep(waitMs);
  geckoLastAt = Date.now();

  for (let attempt = 0; attempt < 3; attempt++) {
    const res = await doFetch(url);
    if (res.status !== 429) return res;
    const ra = res.headers.get('retry-after');
    const retryAfterMs =
      ra && /^\d+$/.test(ra.trim()) ? Number.parseInt(ra.trim(), 10) * 1000 : 0;
    await sleep(Math.max(1500 + attempt * 1500, retryAfterMs));
    geckoLastAt = Date.now();
  }

  return doFetch(url);
}

export async function geckoFetchPaced(url: string): Promise<Response> {
  // On server: serialize to avoid 429. On client: don't globally serialize.
  if (typeof window === 'undefined') {
    geckoChain = geckoChain.then(() => runPaced(url), () => runPaced(url));
    return geckoChain;
  }

  return runPaced(url);
}
