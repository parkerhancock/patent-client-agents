import { Database } from "bun:sqlite";
import {
  afterAll,
  afterEach,
  beforeAll,
  expect,
  setSystemTime,
  spyOn,
  test,
} from "bun:test";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  type CacheBinding,
  type CacheClientOptions,
  CachedClient,
  EpoFeesClient,
  GenericHttpTransport,
  MemoryCacheStorage,
  type SqlDatabase,
  SqliteCacheStorage,
} from "@patent-client-agents/client";
import { useCassette } from "cassetter";

const day = 24 * 3600 * 1000;
const hits = new Map<string, number>();
const seen = new Map<string, Headers>();
const binary = crypto.getRandomValues(new Uint8Array(65536));
const large = new Uint8Array(3 * 1024 * 1024).map((_, i) => (i * 31) % 251);
const upstream = Bun.serve({
  hostname: "127.0.0.1",
  port: 0,
  fetch(request) {
    const url = new URL(request.url);
    const label = `${request.method} ${url.pathname}${url.search}`;
    const n = (hits.get(label) ?? 0) + 1;
    hits.set(label, n);
    seen.set(label, request.headers);
    // Echo the request without credential query values, which must not be stored.
    const body = `${label.replace(/ServiceKey=[^&]*/, "ServiceKey=x")} #${n}`;
    const date = new Date().toUTCString();
    const reply = (
      headers: Record<string, string>,
      status = 200,
      text = body,
    ) =>
      new Response(status === 304 ? null : text, {
        status,
        headers: { date, "content-type": "text/plain", ...headers },
      });
    switch (url.pathname) {
      case "/max-age":
        return reply({ "cache-control": "max-age=60" });
      case "/plain":
        return reply({});
      case "/no-store":
        return reply({ "cache-control": "no-store, max-age=60" });
      case "/private":
        return reply({ "cache-control": "private, max-age=60" });
      case "/public":
        return reply({ "cache-control": "public, max-age=60" });
      case "/etag":
        return request.headers.get("if-none-match") === '"v1"'
          ? reply({ etag: '"v1"', "cache-control": "no-cache" }, 304)
          : reply({ etag: '"v1"', "cache-control": "no-cache" });
      case "/last-modified":
        return reply({
          "last-modified": new Date(Date.now() - 100 * day).toUTCString(),
        });
      case "/vary":
        return reply(
          { "cache-control": "max-age=60", vary: "Accept" },
          200,
          `${body} ${request.headers.get("accept")}`,
        );
      case "/cookie":
        return reply({
          "cache-control": "public, max-age=60",
          "set-cookie": "session=cookie-secret",
          "x-access-token": "response-token-secret",
        });
      case "/binary":
        return new Response(binary, {
          headers: {
            date,
            "cache-control": "max-age=60",
            "content-type": "application/pdf",
          },
        });
      case "/large":
        return new Response(large, {
          headers: { date, "cache-control": "max-age=60" },
        });
      case "/json":
        return Response.json(
          { n },
          { headers: { date, "cache-control": "max-age=60" } },
        );
      default:
        return reply({}, 404);
    }
  },
});
const base = `http://127.0.0.1:${upstream.port}`;
const count = (label: string) => hits.get(label) ?? 0;

class Probe extends CachedClient {
  readonly http: GenericHttpTransport;
  constructor(
    options: CacheClientOptions & { fetch?: typeof fetch } = {},
    cache: CacheBinding = { name: "probe" },
  ) {
    super();
    this.http = new GenericHttpTransport({
      retryLimit: 0,
      ...options,
      baseUrl: base,
      sourceName: "Probe",
      headers: { accept: "text/plain" },
      cache,
    });
  }
  text(path: string, headers?: HeadersInit) {
    return this.http.text("GET", path, headers ? { headers } : {});
  }
}
/** A cache-enabled probe with its own memory storage, so tests never share entries. */
const probe = (options: CacheClientOptions = {}, cache?: CacheBinding) =>
  new Probe(
    { useCache: true, cacheStorage: new MemoryCacheStorage(), ...options },
    cache,
  );
let unique = 0;
const path = (p: string) => `${p}?t=${++unique}`;

let directory: string;
beforeAll(async () => {
  directory = await mkdtemp(join(tmpdir(), "pca-cache-"));
});
afterEach(() => setSystemTime());
afterAll(() => upstream.stop(true));

test("tests run with the cache off unless they opt in", async () => {
  expect(process.env.PATENT_CLIENT_AGENTS_CACHE).toBe("off");
  const client = new Probe();
  expect(client.cacheEnabled).toBe(false);
  await expect(client.cacheStats()).rejects.toThrow(/disabled/);
  const p = path("/max-age");
  await client.text(p);
  await client.text(p);
  expect(count(`GET ${p}`)).toBe(2);
  expect(new EpoFeesClient().cacheEnabled).toBe(false);
});

test("max-age responses are served from the cache with their original retrieval time", async () => {
  const client = probe();
  const p = path("/max-age");
  const first = await client.text(p);
  const second = await client.text(p);
  expect(second.data).toBe(first.data);
  expect(count(`GET ${p}`)).toBe(1);
  expect(first.provenance.cache_hit).toBe(false);
  expect(second.provenance.cache_hit).toBe(true);
  expect(second.provenance.retrieved_at).toBe(first.provenance.retrieved_at);
  expect(second.headers.get("age")).not.toBeNull();
  const stats = await client.cacheStats();
  expect(stats).toMatchObject({ hits: 1, misses: 1, entryCount: 1 });
  expect(stats.hitRate).toBe(50);
});

test("a response without freshness is refetched; validators produce a 304 that reuses the body", async () => {
  const client = probe();
  const plain = path("/plain");
  await client.text(plain);
  await client.text(plain);
  expect(count(`GET ${plain}`)).toBe(2);

  const etag = path("/etag");
  const first = await client.text(etag);
  const second = await client.text(etag);
  expect(count(`GET ${etag}`)).toBe(2);
  expect(seen.get(`GET ${etag}`)?.get("if-none-match")).toBe('"v1"');
  expect(second.data).toBe(first.data);
  expect(second.status).toBe(200);
  // Revalidated, so not a pure cache hit, but the bytes date from the first fetch.
  expect(second.provenance.cache_hit).toBe(false);
  expect(second.provenance.retrieved_at).toBe(first.provenance.retrieved_at);
});

test("Last-Modified gives heuristic freshness (10% of its age)", async () => {
  const client = probe();
  const p = path("/last-modified");
  await client.text(p);
  await client.text(p);
  expect(count(`GET ${p}`)).toBe(1);
  setSystemTime(new Date(Date.now() + 11 * day));
  await client.text(p);
  expect(count(`GET ${p}`)).toBe(2);
});

test("no-store, private and POST are never stored", async () => {
  const client = probe();
  for (const p of [path("/no-store"), path("/private")]) {
    await client.text(p);
    await client.text(p);
    expect(count(`GET ${p}`)).toBe(2);
  }
  const p = path("/max-age");
  await client.http.text("POST", p, { body: { a: 1 } });
  await client.http.text("POST", p, { body: { a: 1 } });
  expect(count(`POST ${p}`)).toBe(2);
  expect((await client.cacheStats()).entryCount).toBe(0);
});

test("request Cache-Control: no-cache revalidates a fresh entry", async () => {
  const client = probe();
  const p = path("/max-age");
  await client.text(p);
  const refreshed = await client.text(p, { "cache-control": "no-cache" });
  expect(count(`GET ${p}`)).toBe(2);
  expect(refreshed.provenance.cache_hit).toBe(false);
});

test("Vary keeps one entry per selecting header value", async () => {
  const client = probe();
  const p = path("/vary");
  const json = await client.text(p, { accept: "application/json" });
  const xml = await client.text(p, { accept: "application/xml" });
  expect(xml.data).not.toBe(json.data);
  expect((await client.text(p, { accept: "application/json" })).data).toBe(
    json.data,
  );
  expect((await client.text(p, { accept: "application/xml" })).data).toBe(
    xml.data,
  );
  expect(count(`GET ${p}`)).toBe(2);
  expect((await client.cacheStats()).entryCount).toBe(2);
});

test("Authorization requests are stored only with public, and no credential reaches storage", async () => {
  const directoryPath = await mkdtemp(join(tmpdir(), "pca-secret-"));
  const client = new Probe({
    useCache: true,
    cacheStorage: "sqlite",
    cachePath: directoryPath,
  });
  const secret = {
    authorization: "Bearer bearer-secret",
    "x-api-key": "key-secret",
  };
  const maxAge = path("/max-age");
  await client.text(maxAge, secret);
  await client.text(maxAge, secret);
  expect(count(`GET ${maxAge}`)).toBe(2);
  const pub = path("/public");
  await client.text(pub, secret);
  await client.text(pub, secret);
  expect(count(`GET ${pub}`)).toBe(1);
  const cookie = path("/cookie");
  await client.text(cookie, { "x-api-key": "key-secret" });
  const cached = await client.text(cookie, { "x-api-key": "key-secret" });
  expect(cached.provenance.cache_hit).toBe(true);
  expect(cached.headers.get("set-cookie")).toBeNull();
  // Credential query values are redacted in the stored URL; the key is a digest of the full URL.
  const keyed = `/max-age?ServiceKey=query-secret&t=${++unique}`;
  await client.http.text("GET", keyed, {
    headers: { "x-api-key": "key-secret" },
  });
  await client.http.text("GET", keyed, {
    headers: { "x-api-key": "key-secret" },
  });
  expect(count(`GET ${keyed}`)).toBe(1);
  expect(await client.cacheInvalidate(/ServiceKey=REDACTED/)).toBe(1);
  const file = await readFile(join(directoryPath, "probe.db"));
  const wal = await readFile(join(directoryPath, "probe.db-wal")).catch(
    () => new Uint8Array(),
  );
  for (const bytes of [file, wal]) {
    const text = new TextDecoder("latin1").decode(bytes);
    for (const needle of [
      "bearer-secret",
      "key-secret",
      "query-secret",
      "cookie-secret",
      "response-token-secret",
    ])
      expect({ needle, found: text.includes(needle) }).toEqual({
        needle,
        found: false,
      });
  }
});

test("binary bodies round-trip through SQLite and persist across client instances", async () => {
  const cachePath = await mkdtemp(join(tmpdir(), "pca-binary-"));
  const options = {
    useCache: true,
    cacheStorage: "sqlite",
    cachePath,
  } as const;
  const p = path("/binary");
  const first = await new Probe(options).http.bytes("GET", p);
  const second = new Probe(options);
  const again = await second.http.bytes("GET", p);
  expect(count(`GET ${p}`)).toBe(1);
  expect(again.data).toEqual(binary);
  expect(first.data).toEqual(binary);
  expect(again.headers.get("content-type")).toBe("application/pdf");
  expect((await second.cacheStats()).databasePath).toBe(
    join(cachePath, "probe.db"),
  );
  // A separate connection, as another process would open it, sees the entry.
  const db = new Database(join(cachePath, "probe.db"));
  const storage = await new SqliteCacheStorage(
    db as unknown as SqlDatabase,
    "other",
  ).initialize();
  expect((await storage.stats()).entries).toBe(1);
  db.close();
  // JSON decoding of a cached body.
  const json = path("/json");
  const a = await second.http.json("GET", json);
  const b = await second.http.json("GET", json);
  expect(b.data).toEqual(a.data);
});

test("entries above the size limit are not stored, and a hit still honors the request limit", async () => {
  const client = probe({ maxCacheEntryBytes: 1024 * 1024 });
  const p = path("/large");
  await client.http.bytes("GET", p);
  await client.http.bytes("GET", p);
  expect(count(`GET ${p}`)).toBe(2);
  const roomy = probe();
  const q = path("/large");
  await roomy.http.bytes("GET", q);
  await expect(roomy.http.bytes("GET", q, { maxBytes: 1024 })).rejects.toThrow(
    /size limit/,
  );
});

test("ttlSeconds sets cacheClearExpired's default, never freshness; fee clients default to 7 days", async () => {
  const client = probe({ ttlSeconds: 1 });
  const p = path("/max-age");
  await client.text(p);
  await Bun.sleep(1100);
  await client.text(p);
  expect(count(`GET ${p}`)).toBe(1);
  expect(await client.cacheClearExpired()).toBe(1);

  const storage = new MemoryCacheStorage();
  const fees = new EpoFeesClient({
    useCache: true,
    cacheStorage: storage,
    fetch: (async () =>
      Response.json([], {
        headers: { "cache-control": "max-age=600" },
      })) as unknown as typeof fetch,
  });
  await fees.getEpcSchedule().catch(() => undefined);
  expect((await fees.cacheStats()).entryCount).toBe(1);
  setSystemTime(new Date(Date.now() + 6 * day));
  expect(await fees.cacheClearExpired()).toBe(0);
  setSystemTime(new Date(Date.now() + 8 * day));
  expect(await fees.cacheClearExpired()).toBe(1);
});

test("forced caching (Python's Google Patents cache) stores GET 200 for its TTL regardless of headers", async () => {
  const client = probe({}, { name: "forced", forceTtlSeconds: 30 * 24 * 3600 });
  const p = path("/no-store");
  await client.text(p);
  const second = await client.text(p);
  expect(count(`GET ${p}`)).toBe(1);
  expect(second.provenance.cache_hit).toBe(true);
  setSystemTime(new Date(Date.now() + 31 * day));
  await client.text(p);
  expect(count(`GET ${p}`)).toBe(2);
  // Per-request opt-out, as Google Patents search uses.
  const q = path("/max-age");
  await client.http.text("GET", q, { cache: false });
  await client.http.text("GET", q, { cache: false });
  expect(count(`GET ${q}`)).toBe(2);
  expect(await client.cacheInvalidate("/no-store")).toBe(1);
});

test("management API: invalidate by pattern, clear, and disabled clients", async () => {
  const client = probe();
  const a = path("/max-age");
  const b = path("/public");
  await client.text(a);
  await client.text(b);
  expect(await client.cacheInvalidate(/\/public/)).toBe(1);
  expect((await client.cacheStats()).entryCount).toBe(1);
  expect(await client.cacheClear()).toBe(1);
  expect((await client.cacheStats()).entryCount).toBe(0);
  const off = new Probe({ useCache: false });
  expect(off.cacheEnabled).toBe(false);
  await expect(off.cacheClear()).rejects.toThrow(/disabled/);
});

test("environment variables select storage and directory; unavailable storage falls back to memory once", async () => {
  const saved = { ...process.env };
  const warn = spyOn(console, "warn").mockImplementation(() => {});
  try {
    process.env.PATENT_CLIENT_AGENTS_CACHE = "sqlite";
    process.env.PATENT_CLIENT_AGENTS_CACHE_DIR = directory;
    const fromEnv = new Probe({}, { name: "env_probe" });
    expect((await fromEnv.cacheStats()).databasePath).toBe(
      join(directory, "env_probe.db"),
    );
    process.env.PATENT_CLIENT_AGENTS_CACHE = "memory";
    expect((await new Probe().cacheStats()).storage).toBe("memory");
    process.env.PATENT_CLIENT_AGENTS_CACHE = "indexeddb";
    const fallback = new Probe({}, { name: "idb_probe" });
    expect((await fallback.cacheStats()).storage).toBe("memory");
    await new Probe({}, { name: "idb_probe_2" }).cacheStats();
    expect(
      warn.mock.calls.filter((call) => /IndexedDB/.test(String(call[0])))
        .length,
    ).toBe(1);
    // A cache directory that cannot be created falls back to memory.
    delete process.env.PATENT_CLIENT_AGENTS_CACHE;
    const broken = new Probe(
      { useCache: true, cachePath: "/dev/null/not-a-directory" },
      { name: "broken" },
    );
    expect((await broken.cacheStats()).storage).toBe("memory");
    const p = path("/max-age");
    await broken.text(p);
    await broken.text(p);
    expect(count(`GET ${p}`)).toBe(1);
  } finally {
    process.env = saved;
    process.env.PATENT_CLIENT_AGENTS_CACHE = "off";
    warn.mockRestore();
  }
});

test("concurrent writers in separate processes share one SQLite file", async () => {
  const file = join(directory, "concurrent.db");
  const script = join(directory, "writer.ts");
  await Bun.write(
    script,
    `import { Database } from "bun:sqlite";
import { SqliteCacheStorage } from ${JSON.stringify(join(import.meta.dir, "../packages/client/src/cache/sqlite.ts"))};
const storage = await new SqliteCacheStorage(new Database(${JSON.stringify(file)}, { create: true }), "w").initialize();
const body = new Uint8Array(4096).fill(Number(process.argv[2]));
for (let i = 0; i < 40; i++)
  await storage.put({ id: process.argv[2] + "-" + i, key: "k" + (i % 5), url: "https://x/" + i, varySignature: "[]", storedAt: Date.now(), policy: {}, body }, []);
`,
  );
  const children = [1, 2, 3, 4].map((n) =>
    Bun.spawn([process.execPath, script, String(n)], {
      stdout: "ignore",
      stderr: "pipe",
    }),
  );
  const codes = await Promise.all(children.map((child) => child.exited));
  expect(codes).toEqual([0, 0, 0, 0]);
  const db = new Database(file);
  const storage = await new SqliteCacheStorage(
    db as unknown as SqlDatabase,
    file,
  ).initialize();
  expect((await storage.stats()).entries).toBe(160);
  db.close();
}, 60_000);

test("concurrent identical requests are not coalesced (Python does not coalesce)", async () => {
  const client = probe();
  const p = path("/max-age");
  await Promise.all([client.text(p), client.text(p), client.text(p)]);
  expect(count(`GET ${p}`)).toBe(3);
});

test("a warm cache never bypasses cassette recording or replay", async () => {
  const cachePath = await mkdtemp(join(tmpdir(), "pca-cassette-"));
  const p = path("/max-age");
  // Warm a cache file at the location the default client would use.
  await new Probe({
    useCache: true,
    cacheStorage: "sqlite",
    cachePath,
  }).text(p);
  const saved = process.env.PATENT_CLIENT_AGENTS_CACHE_DIR;
  process.env.PATENT_CLIENT_AGENTS_CACHE_DIR = cachePath;
  try {
    const cassette = join(cachePath, "cache.yaml");
    await useCassette(cassette, { recordMode: "all" }, async () => {
      await new Probe().text(p);
    });
    expect(count(`GET ${p}`)).toBe(2);
    expect(await readFile(cassette, "utf8")).toContain(p);
    await useCassette(cassette, { recordMode: "none" }, async () => {
      const replayed = await new Probe().text(p);
      expect(replayed.data).toBe(`GET ${p} #2`);
      // An unrecorded request still fails; nothing falls back to the cache or the network.
      await expect(new Probe().text(path("/max-age"))).rejects.toThrow();
    });
    expect(count(`GET ${p}`)).toBe(2);
  } finally {
    if (saved === undefined) delete process.env.PATENT_CLIENT_AGENTS_CACHE_DIR;
    else process.env.PATENT_CLIENT_AGENTS_CACHE_DIR = saved;
  }
});
