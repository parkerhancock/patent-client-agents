/**
 * Storage seams for hosted state. OAuth records, rate-limit buckets and usage
 * records each sit behind a small interface with an in-memory implementation
 * (tests, single-process local runs) and a Firestore one (Cloud Run).
 */

/** OAuth record kinds; each maps to its own `ts-mcp-oauth-*` collection. */
export type OAuthKind =
  | "clients"
  | "transactions"
  | "codes"
  | "grants"
  | "refresh_tokens";

export interface OAuthStore {
  get<T>(kind: OAuthKind, id: string): Promise<T | undefined>;
  /** Create or replace. Records with a TTL read as absent once expired. */
  put<T>(
    kind: OAuthKind,
    id: string,
    value: T,
    ttlSeconds?: number,
  ): Promise<void>;
  /** Read and delete atomically: of concurrent callers, at most one gets the record. */
  take<T>(kind: OAuthKind, id: string): Promise<T | undefined>;
  delete(kind: OAuthKind, id: string): Promise<void>;
}

export interface Bucket {
  tokens: number;
  last_refill: Date;
  capacity: number;
  window_seconds: number;
}
export interface BucketState {
  minute?: Bucket;
  day?: Bucket;
}

export interface RateLimitStore {
  read(actor: string): Promise<BucketState | undefined>;
  /** Atomic read-modify-write of one actor's buckets. */
  update(
    actor: string,
    change: (current: BucketState | undefined) => BucketState,
  ): Promise<void>;
}

/** One record per tool call. `actor_id` replaces the Python record's plaintext email. */
export interface UsageRecord {
  actor_id: string;
  tool: string;
  ts: Date;
  duration_ms: number;
  ok: boolean;
  error: string | null;
}

export interface UsageSink {
  record(entry: UsageRecord): Promise<void>;
}

export type Clock = () => number;

interface Entry {
  value: unknown;
  expiresAt?: number;
}

export class MemoryOAuthStore implements OAuthStore {
  private readonly records = new Map<string, Entry>();
  constructor(private readonly now: Clock = Date.now) {}

  private live(key: string): Entry | undefined {
    const entry = this.records.get(key);
    if (entry?.expiresAt !== undefined && entry.expiresAt <= this.now()) {
      this.records.delete(key);
      return undefined;
    }
    return entry;
  }

  async get<T>(kind: OAuthKind, id: string) {
    return structuredClone(this.live(`${kind}/${id}`)?.value) as T | undefined;
  }

  async put<T>(kind: OAuthKind, id: string, value: T, ttlSeconds?: number) {
    this.records.set(`${kind}/${id}`, {
      value: structuredClone(value),
      ...(ttlSeconds !== undefined
        ? { expiresAt: this.now() + ttlSeconds * 1000 }
        : {}),
    });
  }

  async take<T>(kind: OAuthKind, id: string) {
    const key = `${kind}/${id}`;
    const entry = this.live(key);
    this.records.delete(key);
    return entry?.value as T | undefined;
  }

  async delete(kind: OAuthKind, id: string) {
    this.records.delete(`${kind}/${id}`);
  }

  /** Test helper: number of live records of one kind. */
  count(kind: OAuthKind): number {
    return [...this.records.keys()].filter(
      (key) => key.startsWith(`${kind}/`) && this.live(key),
    ).length;
  }
}

export class MemoryRateLimitStore implements RateLimitStore {
  readonly buckets = new Map<string, BucketState>();
  async read(actor: string) {
    return structuredClone(this.buckets.get(actor));
  }
  async update(
    actor: string,
    change: (current: BucketState | undefined) => BucketState,
  ) {
    this.buckets.set(actor, change(structuredClone(this.buckets.get(actor))));
  }
}

export class MemoryUsageSink implements UsageSink {
  readonly records: UsageRecord[] = [];
  async record(entry: UsageRecord) {
    this.records.push(entry);
  }
}
