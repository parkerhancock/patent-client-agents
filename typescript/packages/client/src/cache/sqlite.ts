import type { CacheRecord, HttpCacheStorage } from "./storage.js";

/** The synchronous subset shared by `bun:sqlite` and `node:sqlite`. */
export interface SqlStatement {
  run(...parameters: unknown[]): unknown;
  get(...parameters: unknown[]): unknown;
  all(...parameters: unknown[]): unknown[];
}
export interface SqlDatabase {
  exec(sql: string): void;
  prepare(sql: string): SqlStatement;
  close(): void;
}

/**
 * Its own table, so the file can sit beside Python's hishel tables
 * (`entries`, `streams`) in the same `<cache name>.db` without touching them.
 */
const TABLE = "pca_http_cache";
const SCHEMA = `
CREATE TABLE IF NOT EXISTS ${TABLE} (
  id TEXT PRIMARY KEY,
  cache_key TEXT NOT NULL,
  url TEXT NOT NULL,
  vary_signature TEXT NOT NULL,
  stored_at INTEGER NOT NULL,
  policy TEXT NOT NULL,
  body BLOB NOT NULL,
  size INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ${TABLE}_key ON ${TABLE}(cache_key);
CREATE INDEX IF NOT EXISTS ${TABLE}_stored ON ${TABLE}(stored_at);`;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const busy = (error: unknown) =>
  /\b(?:busy|locked)\b/i.test(
    error instanceof Error ? error.message : String(error),
  );

interface Row {
  id: string;
  cache_key: string;
  url: string;
  vary_signature: string;
  stored_at: number;
  policy: string;
  body: Uint8Array;
}

/**
 * SQLite storage with Python's settings: WAL, `synchronous=NORMAL`,
 * `busy_timeout=5000`, and up to five attempts with jittered exponential
 * backoff (0.1 s to 2 s) when another process still holds the lock.
 */
export class SqliteCacheStorage implements HttpCacheStorage {
  readonly kind = "sqlite";
  constructor(
    private readonly db: SqlDatabase,
    readonly location: string,
    private readonly attempts = 5,
  ) {}
  /** Apply pragmas and create the table; retried like every other operation. */
  async initialize() {
    await this.retry(() => {
      this.db.exec("PRAGMA busy_timeout=5000");
      this.db.exec("PRAGMA journal_mode=WAL");
      this.db.exec("PRAGMA synchronous=NORMAL");
      this.db.exec(SCHEMA);
    });
    return this;
  }
  private async retry<T>(operation: () => T): Promise<T> {
    for (let attempt = 1; ; attempt++) {
      try {
        return operation();
      } catch (error) {
        if (!busy(error) || attempt >= this.attempts) throw error;
        const base = Math.min(2000, 100 * 2 ** (attempt - 1));
        await sleep(base / 2 + Math.random() * (base / 2));
      }
    }
  }
  /** Run statements in one immediate transaction, rolling back on failure. */
  private write<T>(operation: () => T): Promise<T> {
    return this.retry(() => {
      this.db.exec("BEGIN IMMEDIATE");
      try {
        const result = operation();
        this.db.exec("COMMIT");
        return result;
      } catch (error) {
        try {
          this.db.exec("ROLLBACK");
        } catch {}
        throw error;
      }
    });
  }
  async get(key: string): Promise<CacheRecord[]> {
    const rows = await this.retry(
      () =>
        this.db
          .prepare(
            `SELECT id, cache_key, url, vary_signature, stored_at, policy, body FROM ${TABLE} WHERE cache_key = ? ORDER BY stored_at DESC`,
          )
          .all(key) as Row[],
    );
    const records: CacheRecord[] = [];
    for (const row of rows) {
      try {
        records.push({
          id: row.id,
          key: row.cache_key,
          url: row.url,
          varySignature: row.vary_signature,
          storedAt: Number(row.stored_at),
          policy: JSON.parse(row.policy) as Record<string, unknown>,
          body: new Uint8Array(row.body),
        });
      } catch {
        // A row another version cannot parse is skipped, never fatal.
      }
    }
    return records;
  }
  async put(record: CacheRecord, replaceIds: string[]) {
    const policy = JSON.stringify(record.policy);
    await this.write(() => {
      const remove = this.db.prepare(`DELETE FROM ${TABLE} WHERE id = ?`);
      for (const id of replaceIds) remove.run(id);
      this.db
        .prepare(
          `INSERT OR REPLACE INTO ${TABLE} (id, cache_key, url, vary_signature, stored_at, policy, body, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(
          record.id,
          record.key,
          record.url,
          record.varySignature,
          record.storedAt,
          policy,
          record.body,
          record.body.byteLength + policy.length,
        );
    });
  }
  async updatePolicy(
    id: string,
    policy: Record<string, unknown>,
    storedAt?: number,
  ) {
    const text = JSON.stringify(policy);
    await this.write(() =>
      storedAt === undefined
        ? this.db
            .prepare(`UPDATE ${TABLE} SET policy = ? WHERE id = ?`)
            .run(text, id)
        : this.db
            .prepare(
              `UPDATE ${TABLE} SET policy = ?, stored_at = ? WHERE id = ?`,
            )
            .run(text, storedAt, id),
    );
  }
  private count(where: string, ...parameters: unknown[]) {
    const row = this.db
      .prepare(`SELECT COUNT(*) AS n FROM ${TABLE} ${where}`)
      .get(...parameters) as { n: number } | null | undefined;
    return Number(row?.n ?? 0);
  }
  async clear() {
    return this.write(() => {
      const n = this.count("");
      this.db.exec(`DELETE FROM ${TABLE}`);
      return n;
    });
  }
  async clearOlderThan(cutoffMs: number) {
    return this.write(() => {
      const n = this.count("WHERE stored_at < ?", cutoffMs);
      this.db.prepare(`DELETE FROM ${TABLE} WHERE stored_at < ?`).run(cutoffMs);
      return n;
    });
  }
  async invalidate(matches: (url: string) => boolean) {
    return this.write(() => {
      const rows = this.db.prepare(`SELECT id, url FROM ${TABLE}`).all() as {
        id: string;
        url: string;
      }[];
      const remove = this.db.prepare(`DELETE FROM ${TABLE} WHERE id = ?`);
      let n = 0;
      for (const row of rows)
        if (matches(row.url)) {
          remove.run(row.id);
          n++;
        }
      return n;
    });
  }
  async stats() {
    return this.retry(() => {
      const row = this.db
        .prepare(
          `SELECT COUNT(*) AS n, COALESCE(SUM(size), 0) AS bytes FROM ${TABLE}`,
        )
        .get() as { n: number; bytes: number } | null | undefined;
      return { entries: Number(row?.n ?? 0), bytes: Number(row?.bytes ?? 0) };
    });
  }
  close() {
    this.db.close();
  }
}
