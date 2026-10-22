import CachePolicy from "http-cache-semantics";
import {
  cacheFilePath,
  defaultCacheDirectory,
  openSqlite,
} from "#cache-sqlite";
import { env, sha256Hex } from "../runtime/env.js";
import { IndexedDbCacheStorage, indexedDbAvailable } from "./indexeddb.js";
import { SqliteCacheStorage } from "./sqlite.js";
import {
  type CacheRecord,
  type HttpCacheStorage,
  MemoryBudget,
  MemoryCacheStorage,
} from "./storage.js";

export type CacheStorageKind = "memory" | "sqlite" | "indexeddb";

/** Cache options every network client accepts, named after Python's `BaseAsyncClient` arguments. */
export interface CacheClientOptions {
  /**
   * Python's `use_cache`. Defaults to on, unless `PATENT_CLIENT_AGENTS_CACHE`
   * is `off`. Clients without a Python cache never cache.
   */
  useCache?: boolean;
  /**
   * Where entries live. Defaults to `PATENT_CLIENT_AGENTS_CACHE` when it names
   * a storage, else SQLite on Bun and Node and memory in browsers.
   */
  cacheStorage?: CacheStorageKind | HttpCacheStorage;
  /**
   * Directory for SQLite files (Python's `cache_path`). Defaults to
   * `PATENT_CLIENT_AGENTS_CACHE_DIR`, else `~/.cache/patent_client_agents`.
   */
  cachePath?: string;
  /**
   * Python's `ttl_seconds`: the default age for `cacheClearExpired()`. As in
   * Python it never changes freshness; HTTP headers decide that.
   */
  ttlSeconds?: number;
  /** Largest body stored, in bytes. Defaults to 64 MiB, the transport's default response limit. */
  maxCacheEntryBytes?: number;
}

/** Per-connector cache settings, mirroring Python's `CACHE_NAME` and its overrides. */
export interface CacheBinding {
  /** Python's `CACHE_NAME`; the SQLite file is `<name>.db`. */
  name: string;
  /**
   * Store every GET 200 for this many seconds regardless of headers, as
   * Python's Google Patents cache does. Undefined follows HTTP caching rules.
   */
  forceTtlSeconds?: number;
}

export const DEFAULT_MAX_ENTRY_BYTES = 64 * 1024 * 1024;
const DEFAULT_MEMORY_BYTES = 128 * 1024 * 1024;
const DAY_SECONDS = 24 * 3600;

const notices = new Set<string>();
function notice(message: string) {
  if (notices.has(message)) return;
  notices.add(message);
  console.warn(`patent-client-agents cache: ${message}`);
}

/** `PATENT_CLIENT_AGENTS_CACHE`: off, on, memory, sqlite or indexeddb. */
function cacheEnv(): { enabled?: boolean; kind?: CacheStorageKind } {
  const value = env("PATENT_CLIENT_AGENTS_CACHE")?.trim().toLowerCase();
  if (!value) return {};
  if (["off", "0", "false", "no", "none"].includes(value))
    return { enabled: false };
  if (["on", "1", "true", "yes"].includes(value)) return { enabled: true };
  if (value === "memory" || value === "sqlite" || value === "indexeddb")
    return { enabled: true, kind: value };
  notice(`ignoring unrecognized PATENT_CLIENT_AGENTS_CACHE=${value}.`);
  return {};
}

let sharedBudget: MemoryBudget | undefined;
function memoryBudget() {
  const mb = Number(env("PATENT_CLIENT_AGENTS_CACHE_MEMORY_MB"));
  sharedBudget ??= new MemoryBudget(
    Number.isFinite(mb) && mb > 0 ? mb * 1024 * 1024 : DEFAULT_MEMORY_BYTES,
  );
  return sharedBudget;
}

/** One storage per cache name and location per process, shared by every client. */
const registry = new Map<string, Promise<HttpCacheStorage>>();
function shared(
  id: string,
  create: () => Promise<HttpCacheStorage>,
): Promise<HttpCacheStorage> {
  let storage = registry.get(id);
  if (!storage) {
    storage = create();
    registry.set(id, storage);
  }
  return storage;
}
function memory(name: string) {
  return shared(
    `memory:${name}`,
    async () => new MemoryCacheStorage({ name, budget: memoryBudget() }),
  );
}

/** Resolve options, environment and runtime into a cache, or undefined when caching is off. */
export function createHttpCache(
  options: CacheClientOptions,
  binding: CacheBinding | undefined,
): HttpCache | undefined {
  if (!binding) return undefined;
  const fromEnv = cacheEnv();
  if (!(options.useCache ?? fromEnv.enabled ?? true)) return undefined;
  const requested = options.cacheStorage ?? fromEnv.kind;
  const name = binding.name;
  let open: () => Promise<HttpCacheStorage>;
  if (requested && typeof requested === "object") {
    open = async () => requested;
  } else {
    const directory =
      options.cachePath ??
      env("PATENT_CLIENT_AGENTS_CACHE_DIR") ??
      defaultCacheDirectory();
    const kind = requested ?? (directory ? "sqlite" : "memory");
    if (kind === "indexeddb")
      open = indexedDbAvailable()
        ? () =>
            shared(
              `indexeddb:${name}`,
              async () => new IndexedDbCacheStorage(name),
            )
        : () => {
            notice("IndexedDB is unavailable here; caching in memory.");
            return memory(name);
          };
    else if (kind === "sqlite" && directory) {
      const path = cacheFilePath(directory, name);
      open = () =>
        shared(`sqlite:${path}`, async () => {
          try {
            const db = await openSqlite(path);
            if (db) return await new SqliteCacheStorage(db, path).initialize();
            notice(
              "SQLite is unavailable in this runtime (Node 22.5 or later has node:sqlite); caching in memory.",
            );
          } catch {
            notice(`could not open ${path}; caching in memory.`);
          }
          return new MemoryCacheStorage({ name, budget: memoryBudget() });
        });
    } else {
      if (kind === "sqlite")
        notice("SQLite file storage is unavailable here; caching in memory.");
      open = () => memory(name);
    }
  }
  return new HttpCache(name, open, {
    ...(binding.forceTtlSeconds === undefined
      ? {}
      : { forceTtlMs: binding.forceTtlSeconds * 1000 }),
    ...(options.ttlSeconds === undefined
      ? {}
      : { ttlSeconds: options.ttlSeconds }),
    maxEntryBytes: options.maxCacheEntryBytes ?? DEFAULT_MAX_ENTRY_BYTES,
  });
}

/** Request headers that identify a caller. Stored and compared only as digests. */
const CREDENTIAL_HEADER =
  /^(?:authorization|proxy-authorization|cookie|x-api-key|x-access-token|.*(?:token|secret|api[-_]?key|password|session).*)$/i;
/** Response headers that may carry a credential. Kept as a placeholder so the policy still sees them. */
const SECRET_RESPONSE_HEADER =
  /^(?:set-cookie2?|.*(?:token|secret|api[-_]?key|password|session).*)$/i;
const REDACTED = "[redacted]";
/** Query parameters whose values are credentials: Python's list plus the transport's. */
const CREDENTIAL_PARAMETER =
  /^(?:api[-_]?key|key|token|access_token|refresh_token|authorization|signature|expires|key-pair-id|x-amz-.+|servicekey|accesskey|tk|client_secret|password)$/i;

export function redactUrl(url: URL): string {
  const copy = new URL(url);
  for (const key of [...copy.searchParams.keys()])
    if (CREDENTIAL_PARAMETER.test(key)) copy.searchParams.set(key, "REDACTED");
  return copy.href;
}
async function policyRequest(
  url: URL,
  headers: Headers,
): Promise<CachePolicy.Request> {
  const record: Record<string, string> = {};
  for (const [name, value] of headers)
    record[name] = CREDENTIAL_HEADER.test(name)
      ? `sha256:${await sha256Hex(new TextEncoder().encode(value))}`
      : value;
  // The policy serializes its URL, so it sees the redacted form; the key covers the full URL.
  return { url: redactUrl(url), method: "GET", headers: record };
}
/** Response headers for the policy: secrets redacted, decoded-body framing. */
function policyResponse(
  status: number,
  headers: Headers,
  bodyLength?: number,
): CachePolicy.Response {
  const record: Record<string, string> = {};
  for (const [name, value] of headers)
    record[name] = SECRET_RESPONSE_HEADER.test(name) ? REDACTED : value;
  if (bodyLength !== undefined) {
    // fetch already decoded the body, so the stored framing must describe the decoded bytes.
    delete record["content-encoding"];
    record["content-length"] = String(bodyLength);
  }
  return { status, headers: record };
}
function clientHeaders(record: Record<string, string>): Headers {
  const headers = new Headers();
  for (const [name, value] of Object.entries(record))
    if (value !== REDACTED) headers.set(name, value);
  return headers;
}
function varyNames(response: CachePolicy.Response) {
  return (response.headers.vary ?? "")
    .split(",")
    .map((name) => name.trim().toLowerCase())
    .filter(Boolean)
    .sort();
}
function signature(names: string[], request: CachePolicy.Request) {
  return JSON.stringify(
    names.map((name) => [name, request.headers[name] ?? null]),
  );
}
function storedVaryNames(record: CacheRecord): string[] {
  try {
    return (JSON.parse(record.varySignature) as [string, unknown][]).map(
      ([name]) => name,
    );
  } catch {
    return [];
  }
}
function newId() {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) =>
    b.toString(16).padStart(2, "0"),
  ).join("");
}

export interface CacheHit {
  status: number;
  headers: Headers;
  body: Uint8Array;
  storedAt: number;
  /** True when served without contacting the origin. */
  fresh: boolean;
}
/** The state of one GET between lookup and response. */
export interface CacheLookup {
  key: string;
  request: CachePolicy.Request;
  candidates: CacheRecord[];
  hit?: CacheHit;
  revalidate?: { record: CacheRecord; policy: CachePolicy };
  /** Validators to add to the outgoing request. */
  conditional: Record<string, string>;
}

export interface HttpCacheStats {
  hits: number;
  misses: number;
  entries: number;
  bytes: number;
  storage: string;
  location: string;
}

/**
 * RFC 9111 caching for one connector, using http-cache-semantics as a shared
 * cache (Python's hishel `shared=True`) for storability, freshness, Vary and
 * revalidation. This class adds the key, storage, forced caching, size limits
 * and statistics. Storage failures never fail a request.
 */
export class HttpCache {
  hits = 0;
  misses = 0;
  private storagePromise: Promise<HttpCacheStorage> | undefined;
  constructor(
    readonly name: string,
    private readonly open: () => Promise<HttpCacheStorage>,
    readonly settings: {
      forceTtlMs?: number;
      ttlSeconds?: number;
      maxEntryBytes: number;
    },
  ) {}
  storage(): Promise<HttpCacheStorage> {
    this.storagePromise ??= this.open();
    return this.storagePromise;
  }
  /** Find a usable or revalidatable entry for a GET. Undefined means bypass the cache. */
  async lookup(url: URL, headers: Headers): Promise<CacheLookup | undefined> {
    // Python skips the cache for range requests; so does this cache.
    if (headers.has("range")) return undefined;
    try {
      const request = await policyRequest(url, headers);
      const key = await sha256Hex(new TextEncoder().encode(url.href));
      const records = await (await this.storage()).get(key);
      const candidates = records
        .filter(
          (record) =>
            record.varySignature ===
            signature(storedVaryNames(record), request),
        )
        .sort((a, b) => b.storedAt - a.storedAt);
      const lookup: CacheLookup = { key, request, candidates, conditional: {} };
      const noCache = /no-cache/i.test(headers.get("cache-control") ?? "");
      for (const record of candidates) {
        const policy = CachePolicy.fromObject(record.policy);
        if (this.settings.forceTtlMs !== undefined) {
          if (
            noCache ||
            Date.now() - record.storedAt >= this.settings.forceTtlMs
          )
            continue;
          lookup.hit = this.hit(record, policy.responseHeaders(), true);
          return lookup;
        }
        const evaluation = policy.evaluateRequest(request);
        // Stale-while-revalidate still revalidates first: Python never serves stale.
        if (evaluation.response && !evaluation.revalidation) {
          lookup.hit = this.hit(record, evaluation.response.headers, true);
          return lookup;
        }
      }
      const newest = candidates[0];
      if (newest && this.settings.forceTtlMs === undefined) {
        const policy = CachePolicy.fromObject(newest.policy);
        const validators = policy.revalidationHeaders(request);
        for (const name of ["if-none-match", "if-modified-since"]) {
          const value = validators[name];
          if (value && !headers.has(name)) lookup.conditional[name] = value;
        }
        if (Object.keys(lookup.conditional).length)
          lookup.revalidate = { record: newest, policy };
      }
      return lookup;
    } catch {
      return undefined;
    }
  }
  private hit(
    record: CacheRecord,
    headers: Record<string, string>,
    fresh: boolean,
  ): CacheHit {
    this.hits++;
    const policy = CachePolicy.fromObject(record.policy);
    return {
      status: policy.status(),
      headers: clientHeaders(headers),
      body: record.body.slice(),
      storedAt: record.storedAt,
      fresh,
    };
  }
  /** A 304 answered a conditional request: refresh the stored headers and reuse the body. */
  async notModified(
    lookup: CacheLookup,
    headers: Headers,
  ): Promise<CacheHit | undefined> {
    const target = lookup.revalidate;
    if (!target) return undefined;
    try {
      const { policy } = target.policy.revalidatedPolicy(
        lookup.request,
        policyResponse(304, headers),
      );
      await (await this.storage()).updatePolicy(
        target.record.id,
        policy.toObject(),
      );
      return this.hit(target.record, policy.responseHeaders(), false);
    } catch {
      return undefined;
    }
  }
  /** Store a successful GET response when the policy (or forced caching) allows it. */
  async store(
    lookup: CacheLookup,
    url: URL,
    status: number,
    headers: Headers,
    body: Uint8Array,
    fetchedAt = Date.now(),
  ): Promise<boolean> {
    this.misses++;
    try {
      if (body.byteLength > this.settings.maxEntryBytes) return false;
      const response = policyResponse(status, headers, body.byteLength);
      const policy = new CachePolicy(lookup.request, response, {
        shared: true,
      });
      const storable =
        this.settings.forceTtlMs !== undefined
          ? status === 200
          : policy.storable();
      if (!storable) return false;
      const varySignature = signature(varyNames(response), lookup.request);
      const record: CacheRecord = {
        id: newId(),
        key: lookup.key,
        url: redactUrl(url),
        varySignature,
        storedAt: fetchedAt,
        policy: policy.toObject(),
        body: body.slice(),
      };
      await (await this.storage()).put(
        record,
        lookup.candidates
          .filter((old) => old.varySignature === varySignature)
          .map((old) => old.id),
      );
      return true;
    } catch {
      return false;
    }
  }
  async stats(): Promise<HttpCacheStats> {
    const storage = await this.storage();
    const { entries, bytes } = await storage.stats();
    return {
      hits: this.hits,
      misses: this.misses,
      entries,
      bytes,
      storage: storage.kind,
      location: storage.location,
    };
  }
  async clear() {
    return (await this.storage()).clear();
  }
  async clearExpired(maxAgeSeconds?: number) {
    const age = maxAgeSeconds ?? this.settings.ttlSeconds ?? DAY_SECONDS;
    return (await this.storage()).clearOlderThan(Date.now() - age * 1000);
  }
  async invalidate(pattern: string | RegExp) {
    const regex =
      typeof pattern === "string"
        ? new RegExp(pattern)
        : new RegExp(pattern.source, pattern.flags.replace(/[gy]/g, ""));
    return (await this.storage()).invalidate((url) => regex.test(url));
  }
}
