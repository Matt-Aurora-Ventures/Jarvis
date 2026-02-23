/**
 * Simple in-memory server-side cache for API responses.
 *
 * Designed for single-process Next.js deployments with 50-100 concurrent users.
 * All users share the same cached response, avoiding redundant upstream API calls.
 *
 * No Redis dependency — keeps deployment simple.
 */

interface CacheEntry<T> {
  data: T;
  expiresAt: number;
}

export class ServerCache<T> {
  private cache = new Map<string, CacheEntry<T>>();
  private lastCleanup = Date.now();
  private readonly cleanupIntervalMs = 60_000; // Run cleanup at most every 60s

  /**
   * Retrieve a cached value. Returns null if the key is missing or expired.
   */
  get(key: string): T | null {
    this.maybeCleanup();

    const entry = this.cache.get(key);
    if (!entry) return null;

    if (Date.now() >= entry.expiresAt) {
      this.cache.delete(key);
      return null;
    }

    return entry.data;
  }

  /**
   * Store a value with a time-to-live in milliseconds.
   */
  set(key: string, data: T, ttlMs: number): void {
    this.cache.set(key, {
      data,
      expiresAt: Date.now() + ttlMs,
    });
  }

  /**
   * Immediately remove a cached entry.
   */
  invalidate(key: string): void {
    this.cache.delete(key);
  }

  /**
   * Periodic cleanup of expired entries to prevent unbounded memory growth.
   * Runs at most once per cleanupIntervalMs.
   */
  private maybeCleanup(): void {
    const now = Date.now();
    if (now - this.lastCleanup < this.cleanupIntervalMs) return;
    this.lastCleanup = now;

    for (const [key, entry] of this.cache) {
      if (now >= entry.expiresAt) {
        this.cache.delete(key);
      }
    }
  }
}

/** Shared cache for graduation feed data (TTL: 5 seconds). */
export const graduationCache = new ServerCache<any>();

/** Shared cache for quote responses (TTL: 3 seconds). */
export const quoteCache = new ServerCache<any>();
