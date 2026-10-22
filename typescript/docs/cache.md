# HTTP response cache

October 22, 2026. This page records what the Python package's hishel cache
actually does, then the TypeScript cache built to match it.

## Python's behavior, as found

Read from `mcp_data_core/cache.py` and `base_client.py` (mcp-data-core 0.14.0,
httpx2) and hishel 1.4.0, and confirmed by running `BaseAsyncClient` against a
local test server (hishel 1.2.1, which the typescript-port branch locks,
behaves the same on every point below).

**Wiring.** `BaseAsyncClient` defaults to `use_cache=True` and builds an
`AsyncCacheClient` over `RetryingAsyncSqliteStorage`, a hishel
`AsyncSqliteStorage` with WAL, `synchronous=NORMAL`, `busy_timeout=5000` and up
to five tenacity retries on `create_entry`, `get_entries` and the hourly batch
cleanup. The file is `~/.cache/patent_client_agents/<CACHE_NAME>.db` (or
`cache_path/<CACHE_NAME>.db`). No policy is passed, so hishel uses
`SpecificationPolicy()` with its default `CacheOptions(shared=True,
supported_methods=["GET", "HEAD"], allow_stale=False)`. EPO OPS passes
`SpecificationPolicy()` explicitly, which is the same thing. The cache sits
below httpx's redirect handling, auth flows and the client's retry loop, so it
sees each redirect hop with the final request headers, including
`Authorization`.

**Key.** `sha256(str(request.url))`: the full URL with its query string. Method,
body and headers are not in the key. Entries under one key are then filtered by
exact URL, method and the response's `Vary` headers.

**Storing.** A response is stored only if all of these hold (RFC 9111 §3 as a
shared cache): the method is GET or HEAD; the status is final and not 206 or
304; there is no `no-store`; there is no bare `private`; a request carrying
`Authorization` gets a response with `public`, `s-maxage` or `must-revalidate`;
and the response has `public`, `Expires`, `max-age`, `s-maxage`, or a
heuristically cacheable status (200, 203, 204, 206, 300, 301, 308, 404, 405,
410, 414, 501). POST is never stored. Error statuses are stored when they carry
explicit freshness (a 404 or a 500 with `max-age=60` was served from cache in
the probe). Hop-by-hop headers and fields named by `no-cache="…"` or
`private="…"` are dropped.

**Freshness.** `s-maxage`, then `max-age`, then `Expires − Date` (an invalid
`Expires` is already expired), then 10% of the time since `Last-Modified`
capped at one week, else none. Age is `now − Date`; the `Age` header and the
time the response was stored are ignored, so a response without a `Date`
header and with `max-age` never goes stale. A response without freshness, or
with bare `no-cache`, or a request with `Cache-Control: no-cache`, is
revalidated: hishel sends `If-None-Match` / `If-Modified-Since` from the stored
validators, freshens the stored headers on 304 and serves the stored body, or
replaces the entry on 200. A 200 with no cache headers at all is therefore
stored but refetched every time (the probe saw a second network hit, marked
revalidated). Stale responses are never served. Range requests skip the
lookup.

**TTL and forced caching.** `ttl_seconds` is never passed to the storage, so
it has no effect on freshness or expiry; it is only the default age for
`cache_clear_expired`. The fee scrapers' `DEFAULT_TTL_SECONDS` (7 days; ILPO 30
days) therefore change nothing at request time. EPO OPS's
`extensions={"force_cache": True}` is a hishel 0.x extension; hishel 1.x reads
only `hishel_ttl`, `hishel_refresh_ttl_on_access`, `hishel_spec_ignore` and
`hishel_body_key`, and the probe confirmed `force_cache` is ignored. No
connector sets `hishel_ttl` or a `FilterPolicy`.

**Google Patents** does not use hishel. It has its own SQLite file,
`google_patents_html.db`, storing only GET responses with status 200 for 30
days regardless of headers, keyed by exact URL; patent pages and PDFs go
through it and search does not.

**Management API.** `cache_enabled`, `cache_stats()`, `cache_clear()`,
`cache_clear_expired(max_age)` and `cache_invalidate(pattern)` exist on every
`BaseAsyncClient`, but `CacheManager` queries a table named `cache`, while
hishel 1.x writes `entries` and `streams`. Every call hits the swallowed
`OperationalError`: `entry_count` is always 0, and clear, clear-expired and
invalidate return 0 and delete nothing (the probe cleared, then got the same
cached body back). `hits` and `misses` are always 0 because nothing calls
`record_hit` or `record_miss`. `size_bytes` is the main file only, excluding
the WAL.

**What is stored.** hishel packs the whole request into each entry, so the
SQLite file holds request headers in clear text: the probe found an
`X-API-KEY` value and an `Authorization: Bearer` token in the stored data.
Credential query parameters (KIPRIS `ServiceKey`, for example) are stored as
part of the URL. There are no size limits; bodies are written in 128 KiB
chunks.

**Concurrency.** WAL plus busy timeout plus retries. There is no coalescing of
identical in-flight requests.

**Recording.** The cache sits above the network transport, so a cache hit never
reaches vcrpy; record mode silently records nothing when the cache already
holds the response.

## TypeScript design

### The policy engine

Caching rules come from [`http-cache-semantics`](https://github.com/kornelski/http-cache-semantics)
4.3.0 (pinned exactly, published October 4, 2026), Kornel Lesiński's RFC 9111
policy engine behind got, cacheable-request and make-fetch-happen. It has no
dependencies, is CommonJS that Bun, Node and Bun's browser bundler all load,
and decides storability, freshness, `Vary` matching and the conditional
headers for revalidation. It is constructed with `shared: true`, matching
hishel's default. We chose it over hand-written rules because those rules are
easy to get subtly wrong (the hishel probe above found two such bugs) and this
package is widely exercised. The package ships JSDoc rather than declarations,
so [`http-cache-semantics.d.ts`](../packages/client/src/cache/http-cache-semantics.d.ts)
types the parts we use. Each entry stores `policy.toObject()` beside the body,
and lookups rebuild it with `CachePolicy.fromObject()`.

Our own code is the thin layer around it, in
[`packages/client/src/cache/`](../packages/client/src/cache/): the key,
storage adapters, forced caching, size limits, statistics and the management
API.

### Where it sits

`GenericHttpTransport` is the only path any network client uses (PPUBS and
Trademark Search wrap their session handling in the `fetch` they hand it;
corpus bootstrap and the relay are not client requests). The cache runs inside
it, per redirect hop, after the request headers are final and before Ky's
retries. For a GET it looks up the URL; a fresh entry returns without touching
the network; a stale entry with validators adds `If-None-Match` /
`If-Modified-Since`, and a 304 refreshes the stored policy and returns the
stored body. A successful response is stored after it has been read within the
request's byte limit and decoded (invalid JSON is never stored). Per-request
`cache: false` skips the cache.

Provenance follows Python: `cache_hit` is true only for a response served
without contacting the source, and `retrieved_at` is the time the body was
first fetched, also after a 304. The network `Provenance.cache_hit` type is
now a boolean instead of the literal `false`.

### Key and what is stored

The key is `sha256(full URL)`, Python's key. Entries under a key are told apart
by the request header values named in the response's `Vary`.

Nothing that authenticates a caller is stored in clear:

- Request headers named `authorization`, `proxy-authorization`, `cookie`,
  `x-api-key`, `x-access-token` or containing `token`, `secret`, `api-key`,
  `password` or `session` are replaced by their SHA-256 digest before the
  policy sees them. The policy still knows a request was authenticated, and
  `Vary` on such a header still matches.
- Response headers `set-cookie` and those containing the same words are
  replaced by a placeholder (so the policy's rules about them still apply)
  and removed from the headers handed back on a hit.
- Credential query parameters (`api_key`, `key`, `token`, `access_token`,
  `refresh_token`, `ServiceKey`, `accessKey`, `tk`, `signature`, signed-URL
  parameters and similar) are redacted in the stored URL and in the URL the
  serialized policy carries. The key still covers the full URL, so two KIPRIS
  keys never share an entry, as in Python.

A test opens the SQLite file and its WAL and checks that a bearer token, an
API key, a query key, a cookie and a token response header appear nowhere.

Stored per entry: the redacted URL, the `Vary` signature (digests for
credential headers, raw values otherwise), the fetch time, the serialized
policy (sanitized request and response headers, status, response time) and
the decoded body bytes. `content-encoding` is dropped and `content-length` set
to the decoded size, because fetch has already decoded the body.

### Rules, compared with Python

Same as Python: GET only (POST never stored); `no-store`, bare `private`, and
`Authorization` without `public` / `s-maxage` / `must-revalidate` are not
stored; freshness from `s-maxage`, `max-age`, `Expires` or 10% of the
`Last-Modified` age; a response without freshness is stored but revalidated
every time; request `Cache-Control: no-cache` forces revalidation; stale
responses are never served; range requests skip the cache; no coalescing of
identical in-flight requests (a test asserts three concurrent identical GETs
reach the server three times).

Different, by the library or by choice:

| Python (hishel) | TypeScript | Why |
| --- | --- | --- |
| Age is `now − Date`; without `Date` a `max-age` response never expires | `Age` header plus time since the response arrived | RFC 9111 §4.2.3; fixes the stuck-forever case |
| `must-revalidate` responses served while fresh | Always revalidated | Library behavior |
| Heuristic is 10% of `now − Last-Modified`, capped at one week | 10% of `Date − Last-Modified`, uncapped | Library behavior |
| Shared-cache responses with `Set-Cookie` cached normally | Stored but revalidated unless `public` | Library behavior; safer |
| Request `max-age`, `min-fresh`, `max-stale`, `Pragma: no-cache` ignored | Honored | Library behavior |
| 4xx/5xx with explicit freshness stored and replayed (a cached 500 survives retries) | Only successful responses are stored | Ky raises errors before the body reaches the cache, and a pinned outage is worse than a refetch |
| 301/308 redirect hops stored | Not stored; each hop's final response is | The transport follows redirects itself, only to approved hosts |
| On 304 with several variants, may freshen a variant the request did not select | Only the selected variant is revalidated | Avoids serving the wrong variant |
| Credentials stored in clear | Digests and placeholders only | See above |
| No size limit | 64 MiB per entry by default (`maxCacheEntryBytes`); memory storage 128 MiB in total | Large PDFs and ZIPs still fit the transport's default 64 MiB response limit |
| Management API is a no-op (wrong table) | Works | |
| `hits` / `misses` always 0 | Counted per client | |

`ttlSeconds` (Python's `ttl_seconds`) keeps Python's effective meaning: it is
the default age for `cacheClearExpired()` and never affects freshness. The fee
clients default it to Python's `DEFAULT_TTL_SECONDS` (7 days; ILPO 30 days).
EPO OPS's `force_cache` is not ported, because hishel 1.x ignores it. Google
Patents uses forced caching, layered over the policy as Python's separate
cache is: every GET 200 is kept for 30 days regardless of headers, in
`google_patents_html.db`; search passes `cache: false`. One deliberate
difference: a request carrying `Cache-Control: no-cache` refetches even a
forced entry.

Cache names are Python's `CACHE_NAME`s: `uspto_odp` (applications, petitions,
PTAB, bulk data), `uspto_office_actions`, `uspto_tsdr`, `uspto_assignments`,
`uspto_trademark_assignments`, `epo_ops`, `cafc`, `copyright`, `wipo_lex`,
`kipo_kipris`, `canada_federal_court`, `china_spc_ip_court`,
`japan_ip_high_court`, `usitc_edis`, `usitc_hts`, `usitc_ids`,
`usitc_dataweb`, the 22 `<office>_fees` names and `google_patents_html`. Patent
Public Search and Trademark Search have no cache in Python and none here.

### Storage

| Storage | Runtimes | Location |
| --- | --- | --- |
| SQLite (`bun:sqlite`, `node:sqlite`) | Bun; Node 22.5+ | `<dir>/<cache name>.db`, dir defaulting to `~/.cache/patent_client_agents` |
| IndexedDB | Browsers and workers | Database `patent_client_agents`, store `http_cache`, one namespace per cache name |
| Memory | Everywhere | Per cache name in the process, sharing one least-recently-used budget |

The SQLite file is the same path Python uses, but our rows live in their own
table, `pca_http_cache`, so the file can hold hishel's `entries` and
`streams` tables too without either side touching the other's. The connection
uses Python's settings: WAL, `synchronous=NORMAL`, `busy_timeout=5000`, and up
to five attempts with jittered backoff from 0.1 s to 2 s when another process
holds the lock, like `RetryingAsyncSqliteStorage`. Writes run in one
`BEGIN IMMEDIATE` transaction. A test runs four processes writing 160 entries
into one file at once. One connection per file is shared within a process.
SQLite calls are synchronous, so a long lock wait blocks the event loop for up
to the busy timeout. Node prints an `ExperimentalWarning` the first time
`node:sqlite` loads. Where SQLite is unavailable (older Node, a directory that
cannot be created), the cache falls back to memory and prints a one-time
notice.

For browsers we chose IndexedDB over the Cache API: it is available outside
secure contexts and in all workers, stores our records (bytes plus the
serialized policy and redacted URL) directly, and supports the namespace and
URL scans the management API needs. The Cache API keys by request and would
have needed the metadata smuggled into headers. IndexedDB is opt-in
(`cacheStorage: "indexeddb"`); the browser default is memory, because the
browser's own HTTP cache already persists direct responses and an origin
should not accumulate office data on disk unless the page asks for it.

### Defaults and configuration

The cache is on by default for library consumers, as in Python: SQLite on Bun
and Node, memory in browsers. Options, all on every network client:

| Option | Python | Meaning |
| --- | --- | --- |
| `useCache` | `use_cache` | false turns the cache off |
| `cacheStorage` | | `"sqlite"`, `"memory"`, `"indexeddb"` or an `HttpCacheStorage` instance |
| `cachePath` | `cache_path` | Directory for SQLite files |
| `ttlSeconds` | `ttl_seconds` | Default age for `cacheClearExpired()` |
| `maxCacheEntryBytes` | | Largest body stored (default 64 MiB) |

Environment, read when a client is constructed (options win):
`PATENT_CLIENT_AGENTS_CACHE` = `off`, `on`, `memory`, `sqlite` or
`indexeddb`; `PATENT_CLIENT_AGENTS_CACHE_DIR`; and
`PATENT_CLIENT_AGENTS_CACHE_MEMORY_MB` (default 128) for the shared memory
budget.

The hosted app (`packages/hosted`) defaults to `memory`, set from its config
(`PATENT_CLIENT_AGENTS_CACHE`, one of `off`, `memory`, `sqlite`). Cloud Run's
filesystem is memory-backed and per instance, so a SQLite file would cost the
same memory with locking on top and still vanish with the instance; a bounded
in-process cache gives the same repeat-request savings. The hosted server
uses its own office credentials for every user, so entries hold public office
data, not per-user data.

### Management API

Network clients extend `CachedClient`, which finds the caches on the client's
transports:

```ts
const client = new ApplicationsClient();
client.cacheEnabled;                 // false when off or for an uncached connector
await client.cacheStats();           // { hits, misses, hitRate, entryCount, sizeBytes, sizeMb, databasePath, storage }
await client.cacheClear();           // entries removed
await client.cacheClearExpired(3600);// older than one hour; default ttlSeconds, else 24 hours
await client.cacheInvalidate(/applications\/14412875/); // regex over the redacted URL
```

As in Python, each call raises (`ConfigurationError`) when caching is off, and
clearing applies to the whole cache name, which clients sharing it share.
`sizeBytes` counts stored bodies and metadata rather than the file size.

### Tests and recording

Tests and recorders run with the cache off. `bunfig.toml` preloads
[`tests/no-cache.ts`](../tests/no-cache.ts), which sets
`PATENT_CLIENT_AGENTS_CACHE=off`, and every `scripts/record-*.ts` and
`live-facade.ts` imports it first. Tests about the cache opt in with
`useCache: true` and their own storage or temporary directory.
[`tests/http-cache.test.ts`](../tests/http-cache.test.ts) runs a local fake
upstream through `max-age`, plain 200s, ETag and `Last-Modified`
revalidation and heuristics, `no-store`, `private`, `Vary`, `Authorization`,
POST, request `no-cache`, binary bodies through SQLite, persistence across
client instances and connections, size limits, `ttlSeconds`, forced caching,
the management API, environment selection, the memory fallback, concurrent
writer processes, the absence of coalescing, and a check that a warm cache in
the default directory changes neither cassette recording nor replay (an
unrecorded request still fails). `smoke:node` checks the SQLite store under
Node; `smoke:browser` checks IndexedDB persistence across client instances
and the memory default in Chromium.
