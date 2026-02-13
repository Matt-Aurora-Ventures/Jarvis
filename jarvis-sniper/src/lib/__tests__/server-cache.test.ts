import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { ServerCache, graduationCache, quoteCache } from '../server-cache';

describe('ServerCache', () => {
  let cache: ServerCache<string>;

  beforeEach(() => {
    cache = new ServerCache<string>();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('get', () => {
    it('returns null for missing keys', () => {
      expect(cache.get('nonexistent')).toBeNull();
    });

    it('returns cached data within TTL', () => {
      cache.set('key1', 'value1', 5000);
      expect(cache.get('key1')).toBe('value1');
    });

    it('returns null for expired entries', () => {
      cache.set('key1', 'value1', 1000);
      vi.advanceTimersByTime(1001);
      expect(cache.get('key1')).toBeNull();
    });

    it('returns data right at the TTL boundary', () => {
      cache.set('key1', 'value1', 5000);
      vi.advanceTimersByTime(4999);
      expect(cache.get('key1')).toBe('value1');
    });
  });

  describe('set', () => {
    it('stores and retrieves complex objects', () => {
      const objCache = new ServerCache<{ items: number[] }>();
      const data = { items: [1, 2, 3] };
      objCache.set('data', data, 10000);
      expect(objCache.get('data')).toEqual({ items: [1, 2, 3] });
    });

    it('overwrites existing entries', () => {
      cache.set('key1', 'old', 5000);
      cache.set('key1', 'new', 5000);
      expect(cache.get('key1')).toBe('new');
    });

    it('resets TTL on overwrite', () => {
      cache.set('key1', 'v1', 2000);
      vi.advanceTimersByTime(1500);
      cache.set('key1', 'v2', 2000);
      vi.advanceTimersByTime(1500);
      // Original TTL would have expired, but overwrite resets it
      expect(cache.get('key1')).toBe('v2');
    });
  });

  describe('invalidate', () => {
    it('removes an existing entry', () => {
      cache.set('key1', 'value1', 5000);
      cache.invalidate('key1');
      expect(cache.get('key1')).toBeNull();
    });

    it('is a no-op for missing keys', () => {
      // Should not throw
      cache.invalidate('nonexistent');
      expect(cache.get('nonexistent')).toBeNull();
    });
  });

  describe('cleanup', () => {
    it('removes expired entries when cleanup triggers', () => {
      // Set many entries that will expire
      for (let i = 0; i < 5; i++) {
        cache.set(`key${i}`, `value${i}`, 1000);
      }
      // Add one that won't expire
      cache.set('keeper', 'alive', 60000);

      vi.advanceTimersByTime(1500);

      // Trigger cleanup via a get on a valid key
      expect(cache.get('keeper')).toBe('alive');
      // Expired entries should return null
      expect(cache.get('key0')).toBeNull();
    });
  });

  describe('exported singletons', () => {
    it('graduationCache is a ServerCache instance', () => {
      expect(graduationCache).toBeInstanceOf(ServerCache);
    });

    it('quoteCache is a ServerCache instance', () => {
      expect(quoteCache).toBeInstanceOf(ServerCache);
    });

    it('singletons are different instances', () => {
      expect(graduationCache).not.toBe(quoteCache);
    });
  });
});
