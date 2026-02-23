export interface CacheProvider<T> {
  mode: 'memory' | 'redis';
  get(key: string): Promise<T | null>;
  set(key: string, value: T, ttlMs: number): Promise<void>;
  invalidate(key: string): Promise<void>;
}

interface CacheProviderOptions {
  namespace: string;
}

interface CacheEntry<T> {
  value: T;
  expiresAt: number;
}

export interface CacheProviderDiagnostics {
  mode: 'memory' | 'redis';
  requestedMode: 'memory' | 'redis';
  distributedBacked: boolean;
  configPresent: boolean;
  warning: string | null;
}

let cacheProviderWarningEmitted = false;

function isRedisRequested(): boolean {
  const explicit = String(process.env.JARVIS_CACHE_PROVIDER || '').trim().toLowerCase();
  if (explicit === 'redis') return true;
  if (explicit === 'memory') return false;
  return String(process.env.REDIS_URL || '').trim().length > 0
    || String(process.env.UPSTASH_REDIS_REST_URL || '').trim().length > 0;
}

function shouldFailClosedForDistributedState(): boolean {
  const explicit = String(process.env.JARVIS_STRICT_DISTRIBUTED_STATE || '').trim().toLowerCase();
  if (explicit === 'true') return true;
  if (explicit === 'false') return false;
  return process.env.NODE_ENV === 'production';
}

function distributedConfigPresent(): boolean {
  return String(process.env.UPSTASH_REDIS_REST_URL || '').trim().length > 0
    && String(process.env.UPSTASH_REDIS_REST_TOKEN || '').trim().length > 0;
}

function createNamespacedKey(namespace: string, key: string): string {
  const safeNamespace = String(namespace || 'default').trim() || 'default';
  const safeKey = String(key || '').trim() || 'empty';
  return `jarvis:cache:${safeNamespace}:${safeKey}`;
}

function distributedStateWarning(): string {
  return 'Redis mode requested for cache-provider, but UPSTASH_REDIS_REST_URL/UPSTASH_REDIS_REST_TOKEN are not fully configured.';
}

function emitDistributedWarningOnce(message: string): void {
  if (cacheProviderWarningEmitted) return;
  cacheProviderWarningEmitted = true;
  console.warn(`[cache-provider] ${message}`);
}

class UpstashRestClient {
  private readonly baseUrl: string;
  private readonly token: string;

  constructor() {
    this.baseUrl = String(process.env.UPSTASH_REDIS_REST_URL || '').trim().replace(/\/+$/, '');
    this.token = String(process.env.UPSTASH_REDIS_REST_TOKEN || '').trim();
  }

  get configured(): boolean {
    return this.baseUrl.length > 0 && this.token.length > 0;
  }

  async exec(command: string[]): Promise<unknown> {
    if (!this.configured) {
      throw new Error('UPSTASH_REDIS_REST_URL/UPSTASH_REDIS_REST_TOKEN must be configured for redis cache mode');
    }

    const response = await fetch(`${this.baseUrl}/pipeline`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify([command]),
      cache: 'no-store',
    });

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      throw new Error(`Upstash cache command failed: ${response.status} ${text}`.trim());
    }

    const payload = (await response.json()) as Array<{ error?: string; result?: unknown }>;
    const first = payload?.[0];
    if (!first) {
      throw new Error('Upstash cache response was empty');
    }
    if (first.error) {
      throw new Error(`Upstash cache error: ${first.error}`);
    }
    return first.result ?? null;
  }
}

function resolveModeOrThrow(): 'memory' | 'redis' {
  if (!isRedisRequested()) return 'memory';

  if (!distributedConfigPresent()) {
    const message = distributedStateWarning();
    if (shouldFailClosedForDistributedState()) {
      throw new Error(`[cache-provider] ${message}`);
    }
    emitDistributedWarningOnce(message);
    return 'memory';
  }

  return 'redis';
}

function handleRedisMisconfigurationIfRequested(): void {
  if (!isRedisRequested()) return;
  if (distributedConfigPresent()) return;
  const message = distributedStateWarning();
  if (shouldFailClosedForDistributedState()) {
    throw new Error(`[cache-provider] ${message}`);
  }
  emitDistributedWarningOnce(message);
}

class InMemoryCacheProvider<T> implements CacheProvider<T> {
  readonly mode = 'memory' as const;
  private store = new Map<string, CacheEntry<T>>();

  async get(key: string): Promise<T | null> {
    const entry = this.store.get(key);
    if (!entry) return null;
    if (Date.now() >= entry.expiresAt) {
      this.store.delete(key);
      return null;
    }
    return entry.value;
  }

  async set(key: string, value: T, ttlMs: number): Promise<void> {
    this.store.set(key, {
      value,
      expiresAt: Date.now() + Math.max(1, Math.floor(ttlMs || 0)),
    });
  }

  async invalidate(key: string): Promise<void> {
    this.store.delete(key);
  }
}

class UpstashCacheProvider<T> implements CacheProvider<T> {
  readonly mode = 'redis' as const;
  private readonly namespace: string;
  private readonly client: UpstashRestClient;

  constructor(options: CacheProviderOptions) {
    this.namespace = String(options.namespace || 'default').trim() || 'default';
    this.client = new UpstashRestClient();
  }

  async get(key: string): Promise<T | null> {
    const result = await this.client.exec(['GET', createNamespacedKey(this.namespace, key)]);
    if (result === null || result === undefined) return null;
    if (typeof result !== 'string') return null;
    try {
      return JSON.parse(result) as T;
    } catch {
      return null;
    }
  }

  async set(key: string, value: T, ttlMs: number): Promise<void> {
    const serialized = JSON.stringify(value);
    const ttl = Math.max(1, Math.floor(ttlMs || 0));
    await this.client.exec(['SET', createNamespacedKey(this.namespace, key), serialized, 'PX', String(ttl)]);
  }

  async invalidate(key: string): Promise<void> {
    await this.client.exec(['DEL', createNamespacedKey(this.namespace, key)]);
  }
}

export function createCacheProvider<T>(options: CacheProviderOptions): CacheProvider<T> {
  const mode = resolveModeOrThrow();
  if (mode === 'redis') return new UpstashCacheProvider<T>(options);
  return new InMemoryCacheProvider<T>();
}

export function getCacheProviderMode(): 'memory' | 'redis' {
  return resolveModeOrThrow();
}

export function getCacheProviderDiagnostics(): CacheProviderDiagnostics {
  handleRedisMisconfigurationIfRequested();
  const redisRequested = isRedisRequested();
  const configPresent = distributedConfigPresent();
  const mode = redisRequested && configPresent ? 'redis' : 'memory';

  const warning = redisRequested && !configPresent
    ? distributedStateWarning()
    : null;

  return {
    mode,
    requestedMode: redisRequested ? 'redis' : 'memory',
    distributedBacked: mode === 'redis',
    configPresent,
    warning,
  };
}

export function __resetCacheProviderWarningForTests(): void {
  cacheProviderWarningEmitted = false;
}
