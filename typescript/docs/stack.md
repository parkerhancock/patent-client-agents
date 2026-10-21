# TypeScript stack decisions

Agreed October 20, 2026. Optimize for a fast Bun development loop and a usable
library with a small MCP adapter. These are architectural choices, not a claim
of an independent security audit or complete production readiness.

| Concern | Choice | Contract |
| --- | --- | --- |
| Runtime and package manager | Bun 1.4.3, workspaces, text lockfile, for development and the MCP server | The client library also runs in Node and browsers; `bun run check` smoke-tests both ([runtimes](runtimes.md)) |
| Language | TypeScript 5.9.3, strict ESM | Incremental compiler checks and emitted declarations |
| Runtime schemas | Zod 4 | Infer types from validated schemas; retain unmodeled upstream fields |
| HTTP | Ky 2 over native Fetch | Central retry, cancellation, deadline, error and credential behavior |
| MCP | Prefect FastMCP TypeScript 1.7.3 | Framework stays outside the client package |
| Remote identity | External OAuth/OIDC provider, JWT/JWKS verification | Require expected issuer, audience, expiration and explicit read scopes |
| Tests | `bun test`, watch mode | Source execution; scoped tests during iteration |
| HTTP recordings | Cassetter 0.11.0 | Replay only by default; explicit recording, secret filtering |
| Offline outline corpora | Official SQLite WebAssembly build (FTS5) plus libzstd WebAssembly, in every runtime | Whole-file Zstd, file and decoded SHA-256 pins, bounded in-memory read-only snapshots and explicit source freshness |
| File-history archives | fflate 0.8.3 | ZIP assembly in the MCP package; bounded document bytes and manifest hashes |
| PDF page merging | pdf-lib 1.17.1 | EPO OPS full-document PDFs in the client package; pure JavaScript, last published 2021, page count bounded |
| Formatting and lint | Biome | Deterministic checks, no parallel formatting conventions |
| Future CPU work | Rust compiled to WebAssembly | Optional measured extraction, no native addon required by the client |

## Package responsibilities

`packages/client` owns authentication to upstream offices, HTTP requests, response
validation, normalization, provenance, and typed errors. It imports no MCP
framework. `packages/mcp` depends on the client and adds tool schemas, concise
summaries, portfolio handling, cursors, authorization, and transport startup.
The two packages are private while their API settles; nothing is published.

MPEP is the first offline corpus reference. The client library runs in Bun,
Node and browsers ([runtimes](runtimes.md)); there is no Python subprocess. Maintenance reuses
the existing Python builder outside requests. See [MPEP setup](mpep.md) for
standalone artifact preparation, bounded memory use and source-time provenance.
Use the shared [corpus pattern](corpus-pattern.md) for whole-file Zstandard
packaging and independent distributed-file/decoded-database pins.

Connector behavior follows [CONNECTOR_STANDARDS.md](../../CONNECTOR_STANDARDS.md).
The Python-only scaffolding requirement is implemented in this port with one
shared Ky transport. The TypeScript source review and operation inventory are
separate from the Python source catalog; existing coverage metadata must not
claim the TypeScript implementation is complete.

## HTTP and credentials

Ky retains standard Request/Response/AbortSignal semantics and avoids a second
network implementation. Only retry known read operations; a POST search is
read-only even though arbitrary POSTs are not. Respect Retry-After and impose a
total deadline. Do not stack retries in the MCP layer. Redirects require an
exact connector-approved HTTPS hostname and never inherit cross-origin office
credentials or cookies. Provenance identifies the original API resource and
removes credential query parameters. Responses are read with a 64 MiB default
limit before full buffering; callers can explicitly configure that bound.
HTTP errors expose safe status/code information rather than request objects
containing credentials. HTTPS is required except for local test endpoints.

Upstream credentials and MCP caller tokens serve different purposes. Never
forward an MCP bearer token as an office credential. There is no shared-service
key or public-demo authorization implicit in this port.

Prefect documents Node as its server runtime. Bun compatibility is therefore
established by our actual protocol and HTTP auth tests, not inferred from Node
compatibility. Its built-in OAuth authorization server is an interim legacy
implementation; production identity stays external. Tests use the authenticated
HTTP listener, not `server.fetch()`, which accepts caller-supplied identity.
Public deployment, HTTPS termination, provider metadata and client login remain
separate work. See [Prefect auth guidance](https://fastmcp-ts.docs.prefect.io/servers/auth/oauth).

## Cassette discipline

Cassetter's native Fetch interception was verified under Bun 1.4.3 with Ky 2.2.0.
The selected older release satisfies the seven-day dependency-age policy. It
is a small pre-1.0 project; pin it and retain an executable compatibility test.
Its compiled Rust addon is a test dependency, not a runtime client dependency.
That existing addon does not change the project's preference for WASM for our
own future processing modules.

Default matching includes method, URI, and JSON request body. Keep secrets out
of both recordings and diagnostic output; API keys, authorization, cookies,
query credentials and token/password fields need filtering. A missing cassette
never authorizes a live request. Record and refresh are deliberate commands.
Do not auto-refresh expired fixtures in ordinary tests or CI. Periodic live
contract checks are still needed to detect upstream changes.

## Rust and WebAssembly

Keep parsing and bulk transformation functions separate from HTTP and MCP.
If profiling identifies meaningful CPU work, build a Rust library for
`wasm32-unknown-unknown` with `wasm-bindgen`, using ESM bindings and declarations.
Load its bytes explicitly under Bun rather than depending on browser fetching
or Node-specific WASI loaders. Prefer a pure compute module; TypeScript retains
networking, storage and credentials. See [binding deployment](https://wasm-bindgen.github.io/wasm-bindgen/reference/deployment.html).

Use the same fixtures and behavioral tests for the TypeScript and WASM paths.
Pass whole documents or batches, initialize once, and measure copies and startup
as part of end-to-end performance. Large synchronous WASM work still blocks the
event loop: run it in a worker when responsiveness requires it. Rust dependencies
must support the WASM target, and browser threads/filesystem behavior needs its
own adapters. No Rust crate, speculative backend interface, or performance claim
is introduced before a measured bottleneck warrants it.

## Document retrieval outside model context

The REST download interface runs on the same Bun/FastMCP listener. Library
methods retrieve upstream bytes without knowing about MCP or download URLs.
MCP adapters store a temporary artifact and return its filename, MIME type,
size, provenance, expiry and URL. Stdio returns a local file path. Document
bytes and upstream API keys never appear in these MCP metadata responses.

MCP-issued, single-use download links are the default HTTP workflow while
credential injection across agent hosts stabilizes. Set `MCP_PUBLIC_BASE_URL`
to the externally reachable base URL. `MCP_DOWNLOAD_MODE=signed` issues a
short-lived signature for one artifact; the default lifetime is 15 minutes.
The first GET consumes the link atomically before reading its file, so concurrent
requests cannot redeem it twice. HEAD does not consume it. Range requests are
rejected without consuming it. A failed or interrupted GET still consumes the
link; call the MCP download tool again to obtain a fresh artifact and link.

Authenticated REST remains available concurrently. Remove `expires` and
`signature` from the issued URL to use `GET /downloads?id=<id>` with an OAuth
bearer token. This requires `documents:read`, verified issuer, audience and
expiry, and the same issuer/subject that created the artifact. Authenticated
retrieval does not consume the one-time link and remains available after link
redemption until artifact expiry. `MCP_DOWNLOAD_MODE=authenticated` selects bare
URLs in tool responses instead of signed links.

A trusted host downloader would obtain and attach the OAuth token, save bytes
outside model context, and return a file handle. That integration is not
implemented here. Ordinary URL-fetch tools do not gain this ability merely
because MCP login succeeded. MCP and REST may share an explicitly configured
resource audience; `createServer.downloadAuth` can select a separate REST
verifier. Upstream USPTO credentials remain server-side.

Signed URLs are bearer capabilities. Avoid logging their query strings, use
HTTPS, and keep lifetimes short. Neither mode puts OAuth access tokens or USPTO
keys in URLs. Do not forward MCP tokens upstream.

The implementation uses per-process temporary files, a bounded 256 MiB cache,
a 15-minute lifetime, idle expiry cleanup and random artifact identifiers.
Graceful shutdown removes owned artifacts; an abrupt process crash can leave
temporary files for the operating system to clean. Restart invalidates
links; re-call the download tool to obtain a fresh artifact. Deployment across
multiple replicas requires shared artifact storage or request affinity before
it is supported. Native MCP resources are supplementary and do not guarantee
that a client saves bytes outside model context.

## Trademark Search session acquisition

The optional `waf-worker` package acquires sessions with Playwright 1.64.0 under
Bun. The client and MCP runtime remain browser-free. The `waf-session` package
provides protected atomic files and Secret Manager workload-identity storage,
plus polling, coalesced reloads, deadlines and unchanged-session rejection.
MCP configures it through `PCA_WAF_TOKEN_FILE` or `PCA_WAF_SECRET_RESOURCE`.

A configured provider is authoritative over static environment JSON. Warm
processes see rotation on the next poll; a WAF rejection forces a fresh read and
at most one search retry. Browser acquisition runs separately from requests.
The existing Python worker can supply sessions during transition; new writes
preserve its timestamp contract. No production cutover is included.

See [worker setup and delivery](waf-worker.md) for configuration, permissions,
container build, validation and the remaining deployment boundary.
