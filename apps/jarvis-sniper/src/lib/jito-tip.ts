const JITO_TIP_FLOOR_URL = 'https://bundles.jito.wtf/api/v1/bundles/tip_floor';
const CACHE_TTL_MS = 60_000;
const FALLBACK_TIP_LAMPORTS = 1_000_000; // 0.001 SOL

let cachedTip: { lamports: number; fetchedAt: number } | null = null;

/**
 * Fetch the current Jito tip floor with 60s cache.
 * Returns the 50th percentile (landed_tips_50th_percentile) in lamports.
 * Falls back to 0.001 SOL if the API is unreachable.
 */
export async function getJitoTipFloor(): Promise<number> {
  const now = Date.now();
  if (cachedTip && now - cachedTip.fetchedAt < CACHE_TTL_MS) {
    return cachedTip.lamports;
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5_000);
    let res: Response;
    try {
      res = await fetch(JITO_TIP_FLOOR_URL, { signal: controller.signal });
    } finally {
      clearTimeout(timeout);
    }

    if (!res.ok) throw new Error(`Jito tip floor API ${res.status}`);

    const data = await res.json();
    // Response is an array; take the first entry.
    const entry = Array.isArray(data) ? data[0] : data;
    const solTip = Number(entry?.landed_tips_50th_percentile ?? 0);

    if (solTip > 0 && solTip < 1) {
      const lamports = Math.ceil(solTip * 1e9);
      cachedTip = { lamports, fetchedAt: now };
      return lamports;
    }
  } catch {
    // Use cached value if available, otherwise fallback
  }

  return cachedTip?.lamports ?? FALLBACK_TIP_LAMPORTS;
}
