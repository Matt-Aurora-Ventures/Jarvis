import { createCacheProvider, type CacheProvider } from './cache-provider';

/**
 * Legacy synchronous in-memory cache used by callsites that cannot switch to
 * async semantics in one migration.
 */
export class ServerCache<T> {
  readonly mode = 'memory' as const;
  private readonly store = new Map<string, { value: T; expiresAt: number }>();

  constructor(_namespace: string = 'default') {}

  get(key: string): T | null {
    const item = this.store.get(key);
    if (!item) return null;
    if (Date.now() >= item.expiresAt) {
      this.store.delete(key);
      return null;
    }
    return item.value;
  }

  set(key: string, data: T, ttlMs: number): void {
    this.store.set(key, {
      value: data,
      expiresAt: Date.now() + Math.max(1, Math.floor(ttlMs || 0)),
    });
  }

  invalidate(key: string): void {
    this.store.delete(key);
  }
}

/**
 * Provider-backed async cache for distributed runtime paths.
 */
export class AsyncServerCache<T> {
  readonly mode: 'memory' | 'redis';
  private readonly provider: CacheProvider<T>;

  constructor(namespace: string = 'default') {
    this.provider = createCacheProvider<T>({ namespace });
    this.mode = this.provider.mode;
  }

  async get(key: string): Promise<T | null> {
    return this.provider.get(key);
  }

  async set(key: string, data: T, ttlMs: number): Promise<void> {
    await this.provider.set(key, data, ttlMs);
  }

  async invalidate(key: string): Promise<void> {
    await this.provider.invalidate(key);
  }
}

/** Shared cache for graduation feed data (TTL: 5 seconds). */
export const graduationCache = new AsyncServerCache<any>('graduation-feed');

/** Shared cache for quote responses (TTL: 3 seconds). */
export const quoteCache = new AsyncServerCache<any>('quote-feed');
