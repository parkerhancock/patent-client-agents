import { ConfigurationError, GenericHttpTransport } from "../transport.js";
import type { HttpCache } from "./http-cache.js";

/** Python's `CacheStats`, with its `hit_rate` and `size_mb` properties as fields. */
export interface CacheStats {
  hits: number;
  misses: number;
  /** Percentage, 0-100. */
  hitRate: number;
  entryCount: number;
  /** Stored bodies plus metadata (Python reported the main database file size). */
  sizeBytes: number;
  sizeMb: number;
  /** SQLite file path, or a `memory:` / `indexeddb:` label. */
  databasePath: string;
  storage: string;
}

/**
 * Python's cache management API (`cache_enabled`, `cache_stats`,
 * `cache_clear`, `cache_clear_expired`, `cache_invalidate`) for clients whose
 * transports carry a cache. Clearing affects the whole cache name, shared by
 * every client using it, as clearing Python's `<name>.db` does.
 */
export abstract class CachedClient {
  /** Caches of this client's transports, found among its own properties. */
  private caches(): HttpCache[] {
    const caches = new Set<HttpCache>();
    for (const value of Object.values(this))
      if (value instanceof GenericHttpTransport && value.httpCache)
        caches.add(value.httpCache);
    return [...caches];
  }
  private required(): HttpCache[] {
    const caches = this.caches();
    if (!caches.length)
      throw new ConfigurationError("Caching is disabled for this client.");
    return caches;
  }
  /** Distinct storages, so a cache name shared by two transports is counted once. */
  private async storages() {
    const seen = new Map<unknown, HttpCache>();
    for (const cache of this.required()) seen.set(await cache.storage(), cache);
    return [...seen.values()];
  }
  get cacheEnabled(): boolean {
    return this.caches().length > 0;
  }
  async cacheStats(): Promise<CacheStats> {
    const caches = this.required();
    let hits = 0;
    let misses = 0;
    for (const cache of caches) {
      hits += cache.hits;
      misses += cache.misses;
    }
    let entryCount = 0;
    let sizeBytes = 0;
    const locations: string[] = [];
    const kinds = new Set<string>();
    for (const cache of await this.storages()) {
      const stats = await cache.stats();
      entryCount += stats.entries;
      sizeBytes += stats.bytes;
      locations.push(stats.location);
      kinds.add(stats.storage);
    }
    return {
      hits,
      misses,
      hitRate: hits + misses ? (hits / (hits + misses)) * 100 : 0,
      entryCount,
      sizeBytes,
      sizeMb: sizeBytes / (1024 * 1024),
      databasePath: locations.join(", "),
      storage: [...kinds].join(", "),
    };
  }
  /** Remove every entry; returns the number removed. */
  async cacheClear(): Promise<number> {
    let removed = 0;
    for (const cache of await this.storages()) removed += await cache.clear();
    return removed;
  }
  /**
   * Remove entries fetched more than `maxAgeSeconds` ago. Defaults to the
   * client's `ttlSeconds`, else 24 hours, as in Python.
   */
  async cacheClearExpired(maxAgeSeconds?: number): Promise<number> {
    let removed = 0;
    for (const cache of await this.storages())
      removed += await cache.clearExpired(maxAgeSeconds);
    return removed;
  }
  /** Remove entries whose URL (credentials redacted) matches a regular expression. */
  async cacheInvalidate(pattern: string | RegExp): Promise<number> {
    let removed = 0;
    for (const cache of await this.storages())
      removed += await cache.invalidate(pattern);
    return removed;
  }
}
