/* eslint-disable no-restricted-globals */
/**
 * Jarvis Sniper Risk Worker (Web Worker)
 *
 * Runs price polling + SL/TP/trailing checks off the main UI thread so the
 * engine keeps ticking even when the tab is backgrounded.
 *
 * Notes:
 * - This is non-custodial. The worker never signs transactions.
 * - It only computes triggers and reports them to the main thread.
 */

type TriggerType = 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired';

export type WorkerPosition = {
  id: string;
  mint: string;
  entryPriceUsd: number;
  slPct: number;
  tpPct: number;
  trailPct: number;
  hwmPct: number;
  entryTime: number;
  maxAgeHours: number;
};

type SyncMessage = {
  type: 'SYNC';
  positions: WorkerPosition[];
  intervalMs?: number;
};

type StopMessage = { type: 'STOP' };

type Incoming = SyncMessage | StopMessage;

type PriceUpdate = { id: string; mint: string; priceUsd: number; pnlPct: number; hwmPct: number };

let positions: WorkerPosition[] = [];
let intervalMs = 1500;
let timer: number | null = null;

const triggered = new Map<string, { trigger: TriggerType; at: number }>();

const JUP_PRICE = 'https://api.jup.ag/price/v2';
const DEXSCREENER_TOKENS = 'https://api.dexscreener.com/tokens/v1/solana';

function uniq<T>(arr: T[]): T[] {
  return Array.from(new Set(arr));
}

function start() {
  if (timer != null) clearInterval(timer);
  timer = setInterval(() => void tick(), intervalMs) as unknown as number;
}

function stop() {
  if (timer != null) clearInterval(timer);
  timer = null;
}

self.onmessage = (event: MessageEvent<Incoming>) => {
  const msg = event.data;
  if (msg.type === 'STOP') {
    stop();
    positions = [];
    triggered.clear();
    return;
  }

  if (msg.type === 'SYNC') {
    positions = Array.isArray(msg.positions) ? msg.positions : [];
    if (typeof msg.intervalMs === 'number' && msg.intervalMs >= 500) {
      intervalMs = msg.intervalMs;
    }
    if (positions.length === 0) {
      stop();
    } else if (timer == null) {
      start();
      void tick(); // immediate run
    }
  }
};

async function fetchJupiterPrices(mints: string[]): Promise<Record<string, number>> {
  const priceMap: Record<string, number> = {};
  if (mints.length === 0) return priceMap;

  // Jupiter supports batching via comma-separated ids.
  const ids = encodeURIComponent(mints.join(','));
  const url = `${JUP_PRICE}?ids=${ids}`;

  try {
    const res = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!res.ok) return priceMap;
    const data = await res.json();
    const d = data?.data || {};
    for (const mint of mints) {
      const p = d?.[mint]?.price;
      const num = typeof p === 'string' ? Number.parseFloat(p) : typeof p === 'number' ? p : 0;
      if (Number.isFinite(num) && num > 0) priceMap[mint] = num;
    }
  } catch {
    // ignore
  }

  return priceMap;
}

async function fetchDexScreenerPrices(mints: string[]): Promise<Record<string, number>> {
  const priceMap: Record<string, number> = {};
  if (mints.length === 0) return priceMap;

  // DexScreener supports up to 30 addresses per call.
  for (let i = 0; i < mints.length; i += 30) {
    const batch = mints.slice(i, i + 30);
    try {
      const res = await fetch(`${DEXSCREENER_TOKENS}/${batch.join(',')}`, {
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) continue;
      const pairs: any[] = await res.json();

      // Group by baseToken.address, pick highest liquidity.
      const bestPair = new Map<string, any>();
      for (const pair of pairs) {
        const mint = pair?.baseToken?.address;
        if (!mint) continue;
        const liq = Number.parseFloat(pair?.liquidity?.usd || '0');
        const existing = bestPair.get(mint);
        if (!existing || liq > (existing._liq || 0)) {
          bestPair.set(mint, { ...pair, _liq: liq });
        }
      }

      for (const [mint, pair] of bestPair) {
        const price = Number.parseFloat(pair?.priceUsd || '0');
        if (Number.isFinite(price) && price > 0) priceMap[mint] = price;
      }
    } catch {
      // ignore batch failure
    }
  }

  return priceMap;
}

async function fetchPrices(mints: string[]): Promise<Record<string, number>> {
  // Prefer Jupiter (fast, cheap). Fallback to DexScreener for missing tokens.
  const jup = await fetchJupiterPrices(mints);
  const missing = mints.filter((m) => jup[m] == null);
  if (missing.length === 0) return jup;
  const dex = await fetchDexScreenerPrices(missing);
  return { ...jup, ...dex };
}

function computeTrigger(pos: WorkerPosition, pnlPct: number, hwmPct: number, now: number): TriggerType | null {
  const hitTp = pos.tpPct > 0 && pnlPct >= pos.tpPct;
  const hitSl = pos.slPct > 0 && pnlPct <= -pos.slPct;

  const trailActive = pos.trailPct > 0 && hwmPct >= pos.trailPct;
  const trailDrop = trailActive ? hwmPct - pnlPct : 0;
  const hitTrail = trailActive && trailDrop >= pos.trailPct;

  const hitExpiry = pos.maxAgeHours > 0 && now - pos.entryTime >= pos.maxAgeHours * 3600_000;

  if (!hitTp && !hitSl && !hitTrail && !hitExpiry) return null;

  // Priority: TP > Trail > Expiry > SL (matches main UI semantics)
  return hitTp ? 'tp_hit' : hitTrail ? 'trail_stop' : hitExpiry ? 'expired' : 'sl_hit';
}

async function tick() {
  if (positions.length === 0) return;
  const now = Date.now();

  const mints = uniq(positions.map((p) => p.mint));
  const prices = await fetchPrices(mints);

  const updates: PriceUpdate[] = [];
  const triggers: Array<{ id: string; mint: string; trigger: TriggerType; pnlPct: number; priceUsd: number; hwmPct: number }> = [];

  for (const pos of positions) {
    const priceUsd = prices[pos.mint];
    if (!Number.isFinite(priceUsd) || priceUsd <= 0) continue;
    if (!Number.isFinite(pos.entryPriceUsd) || pos.entryPriceUsd <= 0) continue;

    const pnlPct = ((priceUsd - pos.entryPriceUsd) / pos.entryPriceUsd) * 100;
    const hwmPct = Math.max(pos.hwmPct || 0, pnlPct);

    updates.push({ id: pos.id, mint: pos.mint, priceUsd, pnlPct, hwmPct });

    const trigger = computeTrigger(pos, pnlPct, hwmPct, now);
    if (!trigger) continue;

    const prev = triggered.get(pos.id);
    if (prev && prev.trigger === trigger && now - prev.at < 15_000) {
      // Debounce: same trigger within 15s
      continue;
    }

    triggered.set(pos.id, { trigger, at: now });
    triggers.push({ id: pos.id, mint: pos.mint, trigger, pnlPct, priceUsd, hwmPct });
  }

  if (updates.length > 0) {
    self.postMessage({ type: 'PRICE_UPDATE', updates });
  }
  for (const t of triggers) {
    self.postMessage({ type: 'TRIGGER', ...t });
  }
}

