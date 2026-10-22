import {
  type CacheRecord,
  type HttpCacheStorage,
  recordSize,
} from "./storage.js";

const DATABASE = "patent_client_agents";
const STORE = "http_cache";

interface Stored extends CacheRecord {
  namespace: string;
  size: number;
}

const done = <T>(request: IDBRequest<T>) =>
  new Promise<T>((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
const committed = (transaction: IDBTransaction) =>
  new Promise<void>((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () => reject(transaction.error);
  });

let opened: Promise<IDBDatabase> | undefined;
function open(): Promise<IDBDatabase> {
  opened ??= new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => {
      const store = request.result.createObjectStore(STORE, { keyPath: "id" });
      store.createIndex("namespace_key", ["namespace", "key"]);
      store.createIndex("namespace", "namespace");
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  }).catch((error) => {
    opened = undefined;
    throw error;
  });
  return opened;
}

/** True where IndexedDB exists (browsers and workers). */
export function indexedDbAvailable(): boolean {
  return typeof indexedDB !== "undefined";
}

/**
 * Browser storage: one IndexedDB database, `patent_client_agents`, with one
 * object store holding every cache name as a namespace. Bodies are stored as
 * bytes; the origin's storage quota applies.
 */
export class IndexedDbCacheStorage implements HttpCacheStorage {
  readonly kind = "indexeddb";
  readonly location: string;
  constructor(private readonly namespace: string) {
    this.location = `indexeddb:${DATABASE}/${namespace}`;
  }
  private async store(mode: IDBTransactionMode) {
    const transaction = (await open()).transaction(STORE, mode);
    return { transaction, store: transaction.objectStore(STORE) };
  }
  async get(key: string): Promise<CacheRecord[]> {
    const { store } = await this.store("readonly");
    const rows = await done(
      store.index("namespace_key").getAll([this.namespace, key]),
    );
    return (rows as Stored[]).sort((a, b) => b.storedAt - a.storedAt);
  }
  async put(record: CacheRecord, replaceIds: string[]) {
    const { transaction, store } = await this.store("readwrite");
    for (const id of replaceIds) store.delete(id);
    store.put({
      ...record,
      namespace: this.namespace,
      size: recordSize(record),
    } satisfies Stored);
    await committed(transaction);
  }
  async updatePolicy(
    id: string,
    policy: Record<string, unknown>,
    storedAt?: number,
  ) {
    const { transaction, store } = await this.store("readwrite");
    const row = (await done(store.get(id))) as Stored | undefined;
    if (row)
      store.put({
        ...row,
        policy,
        ...(storedAt === undefined ? {} : { storedAt }),
      });
    await committed(transaction);
  }
  private async removeWhere(test: (row: Stored) => boolean) {
    const { transaction, store } = await this.store("readwrite");
    const rows = (await done(
      store.index("namespace").getAll(this.namespace),
    )) as Stored[];
    let removed = 0;
    for (const row of rows)
      if (test(row)) {
        store.delete(row.id);
        removed++;
      }
    await committed(transaction);
    return removed;
  }
  clear() {
    return this.removeWhere(() => true);
  }
  clearOlderThan(cutoffMs: number) {
    return this.removeWhere((row) => row.storedAt < cutoffMs);
  }
  invalidate(matches: (url: string) => boolean) {
    return this.removeWhere((row) => matches(row.url));
  }
  async stats() {
    const { store } = await this.store("readonly");
    const rows = (await done(
      store.index("namespace").getAll(this.namespace),
    )) as Stored[];
    return {
      entries: rows.length,
      bytes: rows.reduce((sum, row) => sum + row.size, 0),
    };
  }
}
