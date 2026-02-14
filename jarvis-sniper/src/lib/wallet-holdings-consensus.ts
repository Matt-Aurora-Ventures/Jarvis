import { Connection, PublicKey } from '@solana/web3.js';
import { Buffer } from 'buffer';
import { ServerCache } from '@/lib/server-cache';
import { fetchWithRetry } from '@/lib/fetch-utils';
import { resolveServerRpcConfig } from './server-rpc-config';
import { safeImageUrl } from './safe-url';
const SOLSCAN_BASE = 'https://pro-api.solscan.io/v2.0';

let _connection: Connection | null = null;
let _connectionUrl: string | null = null;

function getServerRpcUrl(): string {
  const rpcConfig = resolveServerRpcConfig();
  if (!rpcConfig.ok || !rpcConfig.url) {
    throw new Error(`RPC_PROVIDER_UNAVAILABLE: ${rpcConfig.diagnostic}`);
  }
  return rpcConfig.url;
}

function getServerConnection(): Connection {
  const rpcUrl = getServerRpcUrl();
  if (!_connection || _connectionUrl !== rpcUrl) {
    _connection = new Connection(rpcUrl, 'confirmed');
    _connectionUrl = rpcUrl;
  }
  return _connection;
}

const TOKEN_PROGRAM_ID = new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA');
const TOKEN_2022_PROGRAM_ID = new PublicKey('TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb');

const RPC_PARSED_TTL_MS = 20_000;
const RPC_RAW_TTL_MS = 20_000;
const DAS_TTL_MS = 45_000;
const SOLSCAN_TTL_MS = 180_000;

const sourceCacheRpcParsed = new ServerCache<SourceResult>();
const sourceCacheRpcRaw = new ServerCache<SourceResult>();
const sourceCacheDas = new ServerCache<SourceResult>();
const sourceCacheSolscan = new ServerCache<SourceResult>();

let solscanQueue: Promise<void> = Promise.resolve();
let solscanNextAllowedAt = 0;
let solscanBackoffUntil = 0;
let solscanConsecutiveFailures = 0;

const SOLSCAN_MIN_GAP_MS = 1_200;
const SOLSCAN_MAX_BACKOFF_MS = 10 * 60_000;
const SOLSCAN_AUTH_BACKOFF_MS = 10 * 60_000;

export type HoldingSourceName = 'rpcParsed' | 'rpcRaw' | 'heliusDas' | 'solscan';

export type HoldingAccountEvidence = {
  tokenAccount: string;
  amountLamports: string;
  decimals: number;
};

export type WalletConsensusHolding = {
  mint: string;
  symbol: string;
  name: string;
  icon?: string;
  decimals: number;
  amountLamports: string;
  uiAmount: number;
  priceUsd: number;
  valueUsd: number;
  sources: HoldingSourceName[];
  accountCount: number;
  accounts: HoldingAccountEvidence[];
  riskTags?: string[];
};

type SourceTokenRecord = {
  mint: string;
  tokenAccount: string;
  amountLamports: string;
  decimals: number;
  symbol?: string;
  name?: string;
  icon?: string;
  priceUsd?: number;
  valueUsd?: number;
};

type SourceStatus = {
  ok: boolean;
  statusCode?: number;
  error?: string;
  durationMs: number;
  skipped?: boolean;
};

type SourceResult = {
  source: HoldingSourceName;
  records: SourceTokenRecord[];
  status: SourceStatus;
};

export type WalletConsensusDiagnostics = {
  sourceStatus: Record<HoldingSourceName, SourceStatus>;
  countsBySource: Record<HoldingSourceName, number>;
  consensusTokenCount: number;
  tokensOnlyIn: Record<HoldingSourceName, string[]>;
};

export type WalletHoldingsConsensus = {
  wallet: string;
  source: 'rpc' | 'solscan' | 'hybrid';
  fetchedAt: number;
  holdings: WalletConsensusHolding[];
  summary: {
    tokenCount: number;
    totalValueUsd: number;
    pricedCount: number;
    unpricedCount: number;
  };
  diagnostics: WalletConsensusDiagnostics;
  warnings: string[];
};

type BuildConsensusOpts = {
  forceFullScan?: boolean;
};

type MutableHolding = {
  mint: string;
  symbol?: string;
  name?: string;
  icon?: string;
  decimals: number;
  amountLamports: bigint;
  sources: Set<HoldingSourceName>;
  accounts: Map<string, { amountLamports: bigint; decimals: number; source: HoldingSourceName; synthetic: boolean }>;
  priceUsd: number;
  valueUsd: number;
};

function nowMs(): number {
  return Date.now();
}

function asNumber(v: unknown, fallback = 0): number {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function asString(v: unknown, fallback = ''): string {
  return typeof v === 'string' ? v : fallback;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeWallet(wallet: string): string {
  return String(wallet || '').trim();
}

function parseLamportsString(raw: unknown): string {
  const s = String(raw ?? '').trim();
  if (!s) return '0';
  if (/^\d+$/.test(s)) return s;
  return '0';
}

function decimalToLamportsString(value: unknown, decimals: number): string {
  const raw = String(value ?? '').trim();
  if (!raw) return '0';
  if (/^\d+$/.test(raw)) return raw;
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return '0';
  const scale = 10 ** Math.max(0, decimals);
  if (!Number.isFinite(scale) || scale <= 0) return '0';
  return Math.round(n * scale).toString();
}

function chunk<T>(arr: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

function bigintToUiAmount(amount: bigint, decimals: number): number {
  if (amount <= BigInt(0)) return 0;
  if (decimals <= 0) return Number(amount);
  const base = BigInt(10) ** BigInt(decimals);
  const whole = amount / base;
  const frac = amount % base;
  const fracStr = frac.toString().padStart(decimals, '0').slice(0, 8);
  const out = Number(`${whole.toString()}.${fracStr}`);
  return Number.isFinite(out) ? out : 0;
}

function readU64LE(bytes: Uint8Array, offset: number): bigint {
  if (bytes.length < offset + 8) return BigInt(0);
  let value = BigInt(0);
  for (let i = 0; i < 8; i++) {
    value += BigInt(bytes[offset + i]) << BigInt(8 * i);
  }
  return value;
}

function decodeBase64AccountData(value: unknown): Buffer | null {
  if (Buffer.isBuffer(value)) return value;
  if (Array.isArray(value) && typeof value[0] === 'string') {
    try {
      return Buffer.from(value[0], 'base64');
    } catch {
      return null;
    }
  }
  const maybeObj = value as Record<string, unknown> | null;
  if (maybeObj && typeof maybeObj === 'object') {
    const dataField = maybeObj.data;
    if (Array.isArray(dataField) && typeof dataField[0] === 'string') {
      try {
        return Buffer.from(dataField[0], 'base64');
      } catch {
        return null;
      }
    }
  }
  return null;
}

function getSourceCacheKey(prefix: string, wallet: string): string {
  return `${prefix}:${wallet}`;
}

async function withSolscanGlobalPace<T>(fn: () => Promise<T>): Promise<T> {
  const run = async (): Promise<T> => {
    const waitForBackoff = Math.max(0, solscanBackoffUntil - nowMs());
    const waitForGap = Math.max(0, solscanNextAllowedAt - nowMs());
    const waitMs = Math.max(waitForBackoff, waitForGap);
    if (waitMs > 0) await sleep(waitMs);
    solscanNextAllowedAt = nowMs() + SOLSCAN_MIN_GAP_MS;
    return fn();
  };

  const prior = solscanQueue.catch(() => undefined);
  const task = prior.then(run, run);
  solscanQueue = task.then(() => undefined, () => undefined);
  return task;
}

function applySolscanFailureBackoff(statusCode?: number): void {
  solscanConsecutiveFailures += 1;
  if (statusCode === 401 || statusCode === 403) {
    solscanBackoffUntil = nowMs() + SOLSCAN_AUTH_BACKOFF_MS;
    return;
  }
  if (statusCode === 429) {
    const backoff = Math.min(2 ** Math.min(solscanConsecutiveFailures, 8) * 1_000, SOLSCAN_MAX_BACKOFF_MS);
    solscanBackoffUntil = nowMs() + backoff;
    return;
  }
  const genericBackoff = Math.min(2 ** Math.min(solscanConsecutiveFailures, 6) * 500, 60_000);
  solscanBackoffUntil = nowMs() + genericBackoff;
}

function clearSolscanBackoff(): void {
  solscanConsecutiveFailures = 0;
  solscanBackoffUntil = 0;
}

async function sourceRpcParsed(connection: Connection, wallet: string, forceFullScan = false): Promise<SourceResult> {
  const cacheKey = getSourceCacheKey('rpcParsed', wallet);
  if (!forceFullScan) {
    const cached = sourceCacheRpcParsed.get(cacheKey);
    if (cached) return cached;
  }

  const startedAt = nowMs();
  try {
    const owner = new PublicKey(wallet);
    const [legacy, token2022] = await Promise.all([
      connection.getParsedTokenAccountsByOwner(owner, { programId: TOKEN_PROGRAM_ID }),
      connection.getParsedTokenAccountsByOwner(owner, { programId: TOKEN_2022_PROGRAM_ID }),
    ]);
    const merged = [...legacy.value, ...token2022.value];
    const records: SourceTokenRecord[] = [];
    for (const row of merged) {
      const tokenAccount = row.pubkey.toBase58();
      const info = (row.account.data as any)?.parsed?.info;
      const mint = asString(info?.mint, '').trim();
      const tokenAmount = info?.tokenAmount || {};
      const amountLamports = parseLamportsString(tokenAmount.amount);
      const decimals = Math.max(0, Math.floor(asNumber(tokenAmount.decimals, 0)));
      if (!mint || amountLamports === '0') continue;
      records.push({
        mint,
        tokenAccount,
        amountLamports,
        decimals,
      });
    }
    const result: SourceResult = {
      source: 'rpcParsed',
      records,
      status: {
        ok: true,
        durationMs: nowMs() - startedAt,
      },
    };
    sourceCacheRpcParsed.set(cacheKey, result, RPC_PARSED_TTL_MS);
    return result;
  } catch (error) {
    const result: SourceResult = {
      source: 'rpcParsed',
      records: [],
      status: {
        ok: false,
        durationMs: nowMs() - startedAt,
        error: error instanceof Error ? error.message : 'RPC parsed source failed',
      },
    };
    sourceCacheRpcParsed.set(cacheKey, result, 5_000);
    return result;
  }
}

async function sourceRpcRaw(connection: Connection, wallet: string, forceFullScan = false): Promise<SourceResult> {
  const cacheKey = getSourceCacheKey('rpcRaw', wallet);
  if (!forceFullScan) {
    const cached = sourceCacheRpcRaw.get(cacheKey);
    if (cached) return cached;
  }

  const startedAt = nowMs();
  try {
    const owner = new PublicKey(wallet);
    const [legacy, token2022] = await Promise.all([
      connection.getTokenAccountsByOwner(owner, { programId: TOKEN_PROGRAM_ID }),
      connection.getTokenAccountsByOwner(owner, { programId: TOKEN_2022_PROGRAM_ID }),
    ]);
    const merged = [...legacy.value, ...token2022.value];
    const records: SourceTokenRecord[] = [];
    for (const row of merged) {
      const tokenAccount = row.pubkey.toBase58();
      const buf = decodeBase64AccountData((row.account as any).data);
      if (!buf || buf.length < 72) continue;
      const mint = new PublicKey(buf.subarray(0, 32)).toBase58();
      const amount = readU64LE(buf, 64);
      if (!mint || amount <= BigInt(0)) continue;
      records.push({
        mint,
        tokenAccount,
        amountLamports: amount.toString(),
        decimals: 0,
      });
    }
    const result: SourceResult = {
      source: 'rpcRaw',
      records,
      status: {
        ok: true,
        durationMs: nowMs() - startedAt,
      },
    };
    sourceCacheRpcRaw.set(cacheKey, result, RPC_RAW_TTL_MS);
    return result;
  } catch (error) {
    const result: SourceResult = {
      source: 'rpcRaw',
      records: [],
      status: {
        ok: false,
        durationMs: nowMs() - startedAt,
        error: error instanceof Error ? error.message : 'RPC raw source failed',
      },
    };
    sourceCacheRpcRaw.set(cacheKey, result, 5_000);
    return result;
  }
}

function tryExtractDasRecords(items: any[]): SourceTokenRecord[] {
  const records: SourceTokenRecord[] = [];
  for (const item of items) {
    const tokenInfo = item?.token_info || item?.tokenInfo || {};
    const mint = asString(item?.id ?? tokenInfo?.mint ?? item?.mint, '').trim();
    if (!mint) continue;

    const decimals = Math.max(0, Math.floor(asNumber(tokenInfo?.decimals, 0)));
    const balanceField = tokenInfo?.balance ?? tokenInfo?.amount ?? tokenInfo?.ui_amount ?? 0;
    const amountLamports = decimalToLamportsString(balanceField, decimals);
    if (amountLamports === '0') continue;

    const symbol =
      asString(tokenInfo?.symbol, '').trim() ||
      asString(item?.content?.metadata?.symbol, '').trim() ||
      undefined;
    const name =
      asString(item?.content?.metadata?.name, '').trim() ||
      asString(tokenInfo?.name, '').trim() ||
      symbol;
    const icon =
      asString(item?.content?.links?.image, '').trim() ||
      asString(item?.content?.files?.[0]?.uri, '').trim() ||
      undefined;
    const priceUsd = asNumber(tokenInfo?.price_info?.price_per_token ?? tokenInfo?.price, 0);
    const valueUsd = asNumber(tokenInfo?.price_info?.total_price, priceUsd > 0 ? bigintToUiAmount(BigInt(amountLamports), decimals) * priceUsd : 0);
    records.push({
      mint,
      // Mark DAS-derived rows as "synthetic" so merge logic never double-counts when
      // real on-chain token accounts (rpcParsed/rpcRaw) are present for the same mint.
      tokenAccount: `heliusDas:${mint}:${records.length}`,
      amountLamports,
      decimals,
      symbol,
      name,
      icon,
      priceUsd,
      valueUsd,
    });
  }
  return records;
}

async function sourceHeliusDas(wallet: string, forceFullScan = false): Promise<SourceResult> {
  const cacheKey = getSourceCacheKey('heliusDas', wallet);
  if (!forceFullScan) {
    const cached = sourceCacheDas.get(cacheKey);
    if (cached) return cached;
  }

  const startedAt = nowMs();
  const records: SourceTokenRecord[] = [];
  try {
    // Helius-specific method; expected to fail gracefully on non-Helius RPC nodes.
    for (let page = 1; page <= 4; page++) {
      const res = await fetchWithRetry(getServerRpcUrl(), {
        maxRetries: 1,
        baseDelayMs: 300,
        timeoutMs: 10_000,
        fetchOptions: {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0',
            id: `das-${page}`,
            method: 'getAssetsByOwner',
            params: {
              ownerAddress: wallet,
              page,
              limit: 1000,
              displayOptions: {
                showFungible: true,
                showNativeBalance: false,
              },
            },
          }),
        },
      });
      if (!res.ok) {
        const result: SourceResult = {
          source: 'heliusDas',
          records: [],
          status: {
            ok: false,
            durationMs: nowMs() - startedAt,
            statusCode: res.status,
            error: `DAS HTTP ${res.status}`,
          },
        };
        sourceCacheDas.set(cacheKey, result, 10_000);
        return result;
      }
      const json = (await res.json()) as any;
      if (json?.error) {
        const result: SourceResult = {
          source: 'heliusDas',
          records: [],
          status: {
            ok: false,
            durationMs: nowMs() - startedAt,
            error: asString(json.error?.message, 'DAS method unavailable'),
          },
        };
        sourceCacheDas.set(cacheKey, result, 10_000);
        return result;
      }
      const items = Array.isArray(json?.result?.items) ? json.result.items : [];
      if (items.length === 0) break;
      records.push(...tryExtractDasRecords(items));
      const total = asNumber(json?.result?.total, 0);
      if (total > 0 && page * 1000 >= total) break;
      if (items.length < 1000) break;
    }

    const result: SourceResult = {
      source: 'heliusDas',
      records,
      status: {
        ok: true,
        durationMs: nowMs() - startedAt,
      },
    };
    sourceCacheDas.set(cacheKey, result, DAS_TTL_MS);
    return result;
  } catch (error) {
    const result: SourceResult = {
      source: 'heliusDas',
      records: [],
      status: {
        ok: false,
        durationMs: nowMs() - startedAt,
        error: error instanceof Error ? error.message : 'DAS source failed',
      },
    };
    sourceCacheDas.set(cacheKey, result, 10_000);
    return result;
  }
}

function parseSolscanTokenRecords(payload: any): SourceTokenRecord[] {
  const raw =
    (Array.isArray(payload?.data?.tokenInfo) && payload.data.tokenInfo) ||
    (Array.isArray(payload?.data?.items) && payload.data.items) ||
    (Array.isArray(payload?.data) && payload.data) ||
    [];
  const records: SourceTokenRecord[] = [];
  for (const token of raw) {
    const mint = asString(token.tokenAddress ?? token.token_address ?? token.address ?? token.mint, '').trim();
    if (!mint) continue;
    const decimals = Math.max(0, Math.floor(asNumber(token.token_decimals ?? token.decimals ?? token.tokenAmount?.decimals, 0)));
    const amountRaw = token.amount ?? token.raw_amount ?? token.rawAmount ?? token.tokenAmount?.amount;
    const uiAmount = asNumber(
      token.tokenAmount?.uiAmountString ??
        token.tokenAmount?.uiAmount ??
        token.uiAmountString ??
        token.uiAmount,
      0,
    );
    const amountLamports = parseLamportsString(amountRaw) !== '0'
      ? parseLamportsString(amountRaw)
      : decimalToLamportsString(uiAmount, decimals);
    if (amountLamports === '0') continue;
    const priceUsd = asNumber(token.priceUsdt ?? token.price_usdt ?? token.price ?? token.tokenPrice, 0);
    const valueUsd = asNumber(token.value ?? token.usdValue ?? token.amountUsd, 0);
    records.push({
      mint,
      tokenAccount: `solscan:${mint}:${records.length}`,
      amountLamports,
      decimals,
      symbol: asString(token.tokenSymbol ?? token.token_symbol ?? token.symbol, '').trim() || undefined,
      name: asString(token.tokenName ?? token.token_name ?? token.name, '').trim() || undefined,
      icon: asString(token.tokenIcon ?? token.token_icon ?? token.icon, '').trim() || undefined,
      priceUsd,
      valueUsd,
    });
  }
  return records;
}

async function sourceSolscan(wallet: string, forceFullScan = false): Promise<SourceResult> {
  const cacheKey = getSourceCacheKey('solscan', wallet);
  if (!forceFullScan) {
    const cached = sourceCacheSolscan.get(cacheKey);
    if (cached) return cached;
  }
  const startedAt = nowMs();
  const apiKey = String(process.env.SOLSCAN_API_KEY || '')
    .replace(/[\x00-\x20\x7f]/g, '')
    .trim();
  if (!apiKey) {
    const result: SourceResult = {
      source: 'solscan',
      records: [],
      status: {
        // Treat as an optional source: missing key should not degrade overall portfolio sync.
        ok: true,
        durationMs: nowMs() - startedAt,
        skipped: true,
        error: 'SOLSCAN_API_KEY is not configured',
      },
    };
    sourceCacheSolscan.set(cacheKey, result, 30_000);
    return result;
  }

  if (solscanBackoffUntil > nowMs()) {
    const result: SourceResult = {
      source: 'solscan',
      records: [],
      status: {
        ok: false,
        durationMs: nowMs() - startedAt,
        skipped: true,
        error: `Solscan backoff active (${Math.ceil((solscanBackoffUntil - nowMs()) / 1000)}s)`,
      },
    };
    sourceCacheSolscan.set(cacheKey, result, 10_000);
    return result;
  }

  try {
    const endpoint = `${SOLSCAN_BASE}/account/portfolio?address=${encodeURIComponent(wallet)}&hide_zero=true&remove_spam=false`;
    const res = await withSolscanGlobalPace(() =>
      fetchWithRetry(endpoint, {
        maxRetries: 1,
        baseDelayMs: 600,
        timeoutMs: 12_000,
        fetchOptions: {
          headers: {
            Accept: 'application/json',
            token: apiKey,
            Authorization: `Bearer ${apiKey}`,
          },
        },
      }),
    );
    if (!res.ok) {
      applySolscanFailureBackoff(res.status);
      const result: SourceResult = {
        source: 'solscan',
        records: [],
        status: {
          ok: false,
          durationMs: nowMs() - startedAt,
          statusCode: res.status,
          error: `Solscan HTTP ${res.status}`,
        },
      };
      sourceCacheSolscan.set(cacheKey, result, 15_000);
      return result;
    }
    clearSolscanBackoff();
    const json = await res.json();
    const records = parseSolscanTokenRecords(json);
    const result: SourceResult = {
      source: 'solscan',
      records,
      status: {
        ok: true,
        durationMs: nowMs() - startedAt,
      },
    };
    sourceCacheSolscan.set(cacheKey, result, SOLSCAN_TTL_MS);
    return result;
  } catch (error) {
    applySolscanFailureBackoff();
    const result: SourceResult = {
      source: 'solscan',
      records: [],
      status: {
        ok: false,
        durationMs: nowMs() - startedAt,
        error: error instanceof Error ? error.message : 'Solscan source failed',
      },
    };
    sourceCacheSolscan.set(cacheKey, result, 15_000);
    return result;
  }
}

function upsertMergedRecord(
  merged: Map<string, MutableHolding>,
  source: HoldingSourceName,
  rec: SourceTokenRecord,
): void {
  const mint = rec.mint.trim();
  if (!mint) return;
  let amount: bigint;
  try {
    amount = BigInt(rec.amountLamports);
  } catch {
    return;
  }
  if (amount <= BigInt(0)) return;

  const existing = merged.get(mint);
  const tokenAccount = rec.tokenAccount || `${source}:${mint}`;
  const synthetic = tokenAccount.startsWith(`${source}:`);
  const decSafe = Math.max(0, rec.decimals || 0);
  if (!existing) {
    const accounts = new Map<string, { amountLamports: bigint; decimals: number; source: HoldingSourceName; synthetic: boolean }>();
    accounts.set(tokenAccount, { amountLamports: amount, decimals: decSafe, source, synthetic });
    merged.set(mint, {
      mint,
      symbol: rec.symbol,
      name: rec.name,
      icon: rec.icon,
      decimals: decSafe,
      amountLamports: amount,
      sources: new Set([source]),
      accounts,
      priceUsd: asNumber(rec.priceUsd, 0),
      valueUsd: asNumber(rec.valueUsd, 0),
    });
    return;
  }

  existing.sources.add(source);
  const dec = Math.max(existing.decimals, decSafe);
  existing.decimals = dec;
  if (!existing.symbol && rec.symbol) existing.symbol = rec.symbol;
  if (!existing.name && rec.name) existing.name = rec.name;
  if (!existing.icon && rec.icon) existing.icon = rec.icon;
  if (asNumber(rec.priceUsd, 0) > 0) existing.priceUsd = asNumber(rec.priceUsd, 0);
  if (asNumber(rec.valueUsd, 0) > 0) existing.valueUsd = asNumber(rec.valueUsd, 0);

  const hasRealAccount = [...existing.accounts.values()].some((acc) => !acc.synthetic);

  // Synthetic records (DAS/Solscan token-level totals) are fallback-only evidence.
  // Never stack them on top of real RPC account balances for the same mint.
  if (synthetic && hasRealAccount) {
    return;
  }

  // Once we see a real account for this mint, drop synthetic fallback rows to avoid double counting.
  if (!synthetic && existing.accounts.size > 0) {
    for (const [k, acc] of existing.accounts.entries()) {
      if (acc.synthetic) existing.accounts.delete(k);
    }
  }

  const prevAcc = existing.accounts.get(tokenAccount);
  if (!prevAcc) {
    existing.accounts.set(tokenAccount, { amountLamports: amount, decimals: decSafe, source, synthetic });
  } else if (amount > prevAcc.amountLamports) {
    existing.accounts.set(tokenAccount, {
      amountLamports: amount,
      decimals: Math.max(prevAcc.decimals, decSafe),
      source,
      synthetic,
    });
  }

  // If we only have synthetic records across sources, use the highest synthetic amount
  // as fallback truth (don't sum duplicate aggregate snapshots from different providers).
  const onlySynthetic = [...existing.accounts.values()].every((acc) => acc.synthetic);
  let sum = BigInt(0);
  if (onlySynthetic) {
    for (const acc of existing.accounts.values()) {
      if (acc.amountLamports > sum) sum = acc.amountLamports;
    }
    existing.amountLamports = sum;
    return;
  }

  for (const acc of existing.accounts.values()) {
    if (!acc.synthetic) sum += acc.amountLamports;
  }
  existing.amountLamports = sum > BigInt(0) ? sum : existing.amountLamports;
}

function computeDiagnostics(
  merged: Map<string, MutableHolding>,
  results: SourceResult[],
): WalletConsensusDiagnostics {
  const sourceSets: Record<HoldingSourceName, Set<string>> = {
    rpcParsed: new Set(),
    rpcRaw: new Set(),
    heliusDas: new Set(),
    solscan: new Set(),
  };
  const sourceStatus: Record<HoldingSourceName, SourceStatus> = {
    rpcParsed: { ok: false, durationMs: 0, error: 'not run' },
    rpcRaw: { ok: false, durationMs: 0, error: 'not run' },
    heliusDas: { ok: false, durationMs: 0, error: 'not run' },
    solscan: { ok: false, durationMs: 0, error: 'not run' },
  };
  for (const r of results) {
    sourceStatus[r.source] = r.status;
    for (const rec of r.records) sourceSets[r.source].add(rec.mint);
  }
  const countsBySource: Record<HoldingSourceName, number> = {
    rpcParsed: sourceSets.rpcParsed.size,
    rpcRaw: sourceSets.rpcRaw.size,
    heliusDas: sourceSets.heliusDas.size,
    solscan: sourceSets.solscan.size,
  };

  const tokensOnlyIn: Record<HoldingSourceName, string[]> = {
    rpcParsed: [],
    rpcRaw: [],
    heliusDas: [],
    solscan: [],
  };
  const allSources: HoldingSourceName[] = ['rpcParsed', 'rpcRaw', 'heliusDas', 'solscan'];
  for (const src of allSources) {
    const otherUnion = new Set<string>();
    for (const other of allSources) {
      if (other === src) continue;
      for (const mint of sourceSets[other]) otherUnion.add(mint);
    }
    for (const mint of sourceSets[src]) {
      if (!otherUnion.has(mint)) tokensOnlyIn[src].push(mint);
    }
    tokensOnlyIn[src].sort();
  }

  return {
    sourceStatus,
    countsBySource,
    consensusTokenCount: merged.size,
    tokensOnlyIn,
  };
}

async function hydrateMissingDecimalsFromMints(
  connection: Connection,
  merged: Map<string, MutableHolding>,
): Promise<void> {
  const needs = [...merged.values()].filter((h) => h.decimals <= 0).map((h) => h.mint);
  if (needs.length === 0) return;
  const unique = [...new Set(needs)];
  const chunks = chunk(unique, 100);
  for (const c of chunks) {
    try {
      const pks = c.map((mint) => new PublicKey(mint));
      const infos = await connection.getMultipleAccountsInfo(pks, 'confirmed');
      infos.forEach((info, idx) => {
        if (!info?.data || info.data.length < 45) return;
        const mint = c[idx];
        const decimals = info.data[44] ?? 0;
        const item = merged.get(mint);
        if (!item) return;
        const safeDecimals = Math.max(0, Number(decimals) || 0);
        if (safeDecimals <= 0) return;
        item.decimals = safeDecimals;
        for (const [k, acc] of item.accounts.entries()) {
          if ((acc.decimals || 0) <= 0) {
            item.accounts.set(k, { ...acc, decimals: safeDecimals });
          }
        }
      });
    } catch {
      // best effort
    }
  }
}

export async function buildWalletHoldingsConsensus(
  walletInput: string,
  opts?: BuildConsensusOpts,
): Promise<WalletHoldingsConsensus> {
  const wallet = normalizeWallet(walletInput);
  const forceFullScan = opts?.forceFullScan ?? false;
  const connection = getServerConnection();

  const [rpcParsed, rpcRaw, heliusDas, solscan] = await Promise.all([
    sourceRpcParsed(connection, wallet, forceFullScan),
    sourceRpcRaw(connection, wallet, forceFullScan),
    sourceHeliusDas(wallet, forceFullScan),
    sourceSolscan(wallet, forceFullScan),
  ]);
  const sourceResults = [rpcParsed, rpcRaw, heliusDas, solscan];

  const merged = new Map<string, MutableHolding>();
  for (const result of sourceResults) {
    for (const rec of result.records) upsertMergedRecord(merged, result.source, rec);
  }
  await hydrateMissingDecimalsFromMints(connection, merged);

  const diagnostics = computeDiagnostics(merged, sourceResults);
  const warnings: string[] = [];
  for (const [source, status] of Object.entries(diagnostics.sourceStatus) as Array<[HoldingSourceName, SourceStatus]>) {
    if (!status.ok) {
      warnings.push(
        status.error
          ? `${source}: ${status.error}`
          : `${source}: unavailable`,
      );
    }
  }

  const holdings: WalletConsensusHolding[] = [];
  for (const item of merged.values()) {
    if (item.amountLamports <= BigInt(0)) continue;
    const decimals = Math.max(0, item.decimals || 0);
    const uiAmount = bigintToUiAmount(item.amountLamports, decimals);
    if (uiAmount <= 0) continue;

    const priceUsd = Number.isFinite(item.priceUsd) && item.priceUsd > 0 ? item.priceUsd : 0;
    const valueUsd = Number.isFinite(item.valueUsd) && item.valueUsd > 0
      ? item.valueUsd
      : (priceUsd > 0 ? uiAmount * priceUsd : 0);
    const riskTags: string[] = [];
    if (uiAmount > 0 && uiAmount < 0.0001) riskTags.push('dust');
    if (item.sources.has('solscan') && !item.sources.has('rpcParsed') && !item.sources.has('rpcRaw')) {
      riskTags.push('explorer-only');
    }

    holdings.push({
      mint: item.mint,
      symbol: item.symbol || item.mint.slice(0, 6),
      name: item.name || item.symbol || item.mint.slice(0, 6),
      icon: safeImageUrl(item.icon),
      decimals,
      amountLamports: item.amountLamports.toString(),
      uiAmount,
      priceUsd,
      valueUsd,
      sources: [...item.sources].sort() as HoldingSourceName[],
      accountCount: item.accounts.size,
      accounts: [...item.accounts.entries()].map(([tokenAccount, acc]) => ({
        tokenAccount,
        amountLamports: acc.amountLamports.toString(),
        decimals: acc.decimals,
      })),
      ...(riskTags.length > 0 ? { riskTags } : {}),
    });
  }

  holdings.sort((a, b) => b.valueUsd - a.valueUsd || b.uiAmount - a.uiAmount);

  const pricedCount = holdings.filter((h) => h.priceUsd > 0).length;
  const totalValueUsd = holdings.reduce((sum, h) => sum + (Number.isFinite(h.valueUsd) ? h.valueUsd : 0), 0);
  const hasRpcEvidence = diagnostics.countsBySource.rpcParsed > 0 || diagnostics.countsBySource.rpcRaw > 0 || diagnostics.countsBySource.heliusDas > 0;
  const hasSolscanEvidence = diagnostics.countsBySource.solscan > 0;
  const source: 'rpc' | 'solscan' | 'hybrid' =
    hasRpcEvidence && hasSolscanEvidence ? 'hybrid' : hasRpcEvidence ? 'rpc' : 'solscan';

  return {
    wallet,
    source,
    fetchedAt: nowMs(),
    holdings,
    summary: {
      tokenCount: holdings.length,
      totalValueUsd: Number(totalValueUsd.toFixed(2)),
      pricedCount,
      unpricedCount: Math.max(0, holdings.length - pricedCount),
    },
    diagnostics,
    warnings,
  };
}
