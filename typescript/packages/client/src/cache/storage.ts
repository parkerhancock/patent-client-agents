/** One stored response. Request credentials never appear in it; see docs/cache.md. */
export interface CacheRecord {
  id: string;
  /** SHA-256 of the full request URL, as in Python's hishel key. */
  key: string;
  /** The URL with credential query values redacted, for invalidation and display. */
  url: string;
  /** Request header values named by the response's Vary, as stored digests. */
  varySignature: string;
  /** Milliseconds since the epoch when the body was fetched. */
  storedAt: number;
  /** `CachePolicy.toObject()` from http-cache-semantics. */
  policy: Record<string, unknown>;
  body: Uint8Array;
}

/** Storage adapter behind one cache name (one Python `.db` file). */
export interface HttpCacheStorage {
  readonly kind: string;
  /** File path, database name or label shown in cache statistics. */
  readonly location: string;
  get(key: string): Promise<CacheRecord[]>;
  /** Insert `record`, removing `replaceIds` in the same step. */
  put(record: CacheRecord, replaceIds: string[]): Promise<void>;
  updatePolicy(
    id: string,
    policy: Record<string, unknown>,
    storedAt?: number,
  ): Promise<void>;
  clear(): Promise<number>;
  clearOlderThan(cutoffMs: number): Promise<number>;
  invalidate(matches: (url: string) => boolean): Promise<number>;
  stats(): Promise<{ entries: number; bytes: number }>;
}

/** Approximate stored size of a record: body plus serialized metadata. */
export function recordSize(record: CacheRecord): number {
  return (
    record.body.byteLength +
    JSON.stringify(record.policy).length +
    record.url.length +
    record.varySignature.length +
    128
  );
}

/** A least-recently-used byte budget shared by several memory storages. */
export class MemoryBudget {
  private readonly lru = new Map<
    CacheRecord,
    { owner: MemoryCacheStorage; bytes: number }
  >();
  private used = 0;
  constructor(readonly maxBytes: number) {}
  get usedBytes() {
    return this.used;
  }
  add(owner: MemoryCacheStorage, record: CacheRecord, bytes: number) {
    this.lru.set(record, { owner, bytes });
    this.used += bytes;
    for (const [oldest, entry] of this.lru) {
      if (this.used <= this.maxBytes) break;
      entry.owner.evict(oldest);
    }
  }
  touch(record: CacheRecord) {
    const entry = this.lru.get(record);
    if (!entry) return;
    this.lru.delete(record);
    this.lru.set(record, entry);
  }
  remove(record: CacheRecord) {
    const entry = this.lru.get(record);
    if (!entry) return;
    this.lru.delete(record);
    this.used -= entry.bytes;
  }
}

/** In-process storage for every runtime, bounded by a least-recently-used byte budget. */
export class MemoryCacheStorage implements HttpCacheStorage {
  readonly kind = "memory";
  readonly location: string;
  private readonly records = new Map<string, CacheRecord>();
  private readonly byKey = new Map<string, Set<string>>();
  private readonly budget: MemoryBudget;
  constructor(
    options: { name?: string; maxBytes?: number; budget?: MemoryBudget } = {},
  ) {
    this.location = `memory:${options.name ?? "cache"}`;
    this.budget =
      options.budget ?? new MemoryBudget(options.maxBytes ?? 128 * 1024 * 1024);
  }
  async get(key: string) {
    const records: CacheRecord[] = [];
    for (const id of this.byKey.get(key) ?? []) {
      const record = this.records.get(id);
      if (!record) continue;
      this.budget.touch(record);
      records.push(record);
    }
    return records;
  }
  async put(record: CacheRecord, replaceIds: string[]) {
    for (const id of replaceIds) this.remove(id);
    const bytes = recordSize(record);
    if (bytes > this.budget.maxBytes) return;
    this.records.set(record.id, record);
    const ids = this.byKey.get(record.key) ?? new Set();
    ids.add(record.id);
    this.byKey.set(record.key, ids);
    this.budget.add(this, record, bytes);
  }
  async updatePolicy(
    id: string,
    policy: Record<string, unknown>,
    storedAt?: number,
  ) {
    const record = this.records.get(id);
    if (!record) return;
    record.policy = policy;
    if (storedAt !== undefined) record.storedAt = storedAt;
  }
  /** Called by the budget when it needs room. */
  evict(record: CacheRecord) {
    this.remove(record.id);
  }
  private remove(id: string) {
    const record = this.records.get(id);
    if (!record) return false;
    this.records.delete(id);
    this.budget.remove(record);
    const ids = this.byKey.get(record.key);
    ids?.delete(id);
    if (ids && !ids.size) this.byKey.delete(record.key);
    return true;
  }
  private removeWhere(test: (record: CacheRecord) => boolean) {
    let removed = 0;
    for (const record of [...this.records.values()])
      if (test(record) && this.remove(record.id)) removed++;
    return removed;
  }
  async clear() {
    return this.removeWhere(() => true);
  }
  async clearOlderThan(cutoffMs: number) {
    return this.removeWhere((record) => record.storedAt < cutoffMs);
  }
  async invalidate(matches: (url: string) => boolean) {
    return this.removeWhere((record) => matches(record.url));
  }
  async stats() {
    let bytes = 0;
    for (const record of this.records.values()) bytes += recordSize(record);
    return { entries: this.records.size, bytes };
  }
}
