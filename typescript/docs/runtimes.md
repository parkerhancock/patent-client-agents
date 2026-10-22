# Runtimes and browsers

October 21, 2026. The client library runs in Bun, Node and browsers. The MCP
server is a server package and is developed on Bun; its compiled form also
starts and lists every tool under Node 24.

## What runs where

| | Bun | Node 24 | Browser |
| --- | --- | --- | --- |
| Corpora (MPEP, EPO legal books) | Yes, by path or bytes | Yes, by path or bytes | Yes, by bytes only |
| Network connectors | Yes | Yes | Where the office allows CORS, or through the relay |
| Patent Public Search, Trademark Search | Yes | Yes | No; use the MCP server |
| MCP server | Yes | Starts and serves tools (smoke-checked) | No |

Deno is untested.

## How the client stays portable

The client package uses web-standard APIs: `fetch`, Web Crypto, `TextEncoder`,
`btoa`. Runtime-specific code is confined to:

- **SQLite.** The official SQLite WebAssembly build (`@sqlite.org/sqlite-wasm`,
  FTS5 included) in every runtime, replacing `bun:sqlite`. Corpora are
  deserialized from verified bytes, read-only, as before.
- **Zstandard.** libzstd compiled to WebAssembly (`@bokuweb/zstd-wasm`), which
  supports the dictionary-compressed cells and verifies frame checksums. It
  decodes the 48.7 MB MPEP artifact in about 100-180 ms.
- **Gzip.** `fflate`, with a hard output bound.
- **Files.** `src/runtime/files.ts` reads artifact paths on server runtimes.
  The package's `#files` import condition swaps in `files.browser.ts` for
  browser builds, where paths fail with `CORPUS_UNAVAILABLE`.

Corpus clients take `source` (bytes, or a function returning bytes) instead of
`corpusPath`, which is how browsers supply artifacts:

```ts
const epc = new EpcClient({
  source: () => fetch("/corpora/epc.db.zst").then((r) => r.arrayBuffer()).then((b) => new Uint8Array(b)),
  expectedSha256: "…",
});
```

Pins work the same way in every runtime. A browser holds the decoded database
in memory, so a full corpus costs tens of megabytes of download and memory.

[A source scan](../tests/portability.test.ts) fails if `node:` or `bun:`
imports, or `Bun`, `process`, `Buffer` or `require`, appear in the client
package outside the server file adapter. The client's typecheck no longer
includes Bun's type definitions.

## WebAssembly binaries

Each library loads its `.wasm` file with `new URL(…, import.meta.url)`. Server
runtimes resolve that directly. A browser build must serve `sqlite3.wasm` and
`zstd.wasm`: bundlers that copy `new URL` assets do it automatically (not
verified here), and Bun's bundler does not. Otherwise serve the files and
call `configureWasm` before the first corpus use:

```ts
configureWasm({ sqlite: "/assets/sqlite3.wasm", zstd: "/assets/zstd.wasm" });
```

## The relay

Most office APIs send no CORS headers, and shared keys cannot ship to a
browser. With `createServer({ auth, relay: { origins } })` the MCP server
serves `/relay?url=…` ([source](../packages/mcp/src/relay.ts)):

- It requires a bearer token with the `relay:use` scope and refuses to start
  without server auth.
- Targets must be plain HTTPS URLs on an allowlist: `api.uspto.gov`,
  `data.uspto.gov`, `data-documents.uspto.gov`, `tsdrapi.uspto.gov`,
  `assignmentcenter.uspto.gov`, `ops.epo.org`, `fees.apps.epo.org`,
  `patents.google.com` and `patentimages.storage.googleapis.com`.
- It forwards only `accept`, `accept-language`, `content-type` and `x-ops-range`. Browser
  cookies, `Origin` and the relay token never reach the office.
- It injects the server's ODP and TSDR keys and the OPS client credentials for
  the token endpoint. A browser-held OPS bearer token travels as
  `X-Upstream-Authorization`.
- It follows up to five redirects within the allowlist itself and drops
  credentials when the host changes.
- It strips `Set-Cookie`, upstream CORS headers and the OPS caller-IP headers,
  bounds request bodies at 1 MiB and applies a 60-second budget.
- Every response, refusals included, carries CORS headers for configured
  origins. FastMCP answers the preflight, which also admits those origins to
  `/mcp`; that endpoint still requires its own token.

In the browser:

```ts
const fetch = createRelayFetch({ url: "https://mcp.example.com/relay", token: getToken });
const ops = new EpoOpsClient({ apiKey: RELAY_CREDENTIAL, apiSecret: RELAY_CREDENTIAL, fetch });
```

`RELAY_CREDENTIAL` is a placeholder the relay replaces. The relay hands the
browser short-lived OPS bearer tokens, so anyone holding a `relay:use` token
spends the server's office quotas; scope those tokens accordingly.

## Verification

`bun run check` now ends with two smoke tests:

- `smoke:node` runs the compiled client under Node: corpora by path and by
  bytes, dictionary-compressed cells, a whole-file Zstandard artifact, the fee
  parser and the OPS client.
- `smoke:browser` bundles [a harness](../tests/browser/harness.ts) and runs it
  in headless Chromium through Playwright: the same corpus checks from bytes,
  path refusal, and parsers, plus a cross-origin leg where a direct request to
  a CORS-less upstream is blocked and the same request through the relay
  succeeds.

[Relay tests](../tests/relay.test.ts) cover authentication, the allowlist,
credential injection and stripping, CORS, redirects, body limits and real
clients end to end. The real compressed MPEP artifact still verifies against
both pins. Nothing is deployed, and the relay has not been run against real
office endpoints.
