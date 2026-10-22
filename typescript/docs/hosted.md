# Hosted curated server

October 22, 2026. Phase 0 of the [shadow deploy plan](deploy-plan.md):
`packages/hosted` serves the curated facade the way the Python public demo
(`mcp.patentclient.com`, `patent-client-agents-deploy`) does. It has run only
locally; nothing has been deployed and no cloud resources were written.

## Architecture

The package is a Bun HTTP server (`Bun.serve`) in front of the FastMCP
server from `packages/mcp`. Its router owns every route: the web pages, the
terms gate, the OAuth endpoints and `/mcp`. For `/mcp` it verifies the
bearer token itself and passes the verified identity to FastMCP's stateless
`server.fetch(request, { authInfo })`. Routes that `packages/mcp` registers
on the FastMCP server (today `/downloads`) are dispatched from the same
router.

It does not use FastMCP's own listener with its `oauth` option. That path
serves OAuth through Express and the SDK's legacy authorization-server
router, which the SDK marks deprecated, and it offers no place to put the
terms gate in front of `/authorize`, the browser redirect on `GET /mcp`, or
security headers. The Google provider is therefore a plain class with
fetch-style handlers rather than an `OAuthServerProvider`.

| Module | Role |
| --- | --- |
| `src/main.ts` | Entrypoint: config, corpus bootstrap, `Bun.serve`, graceful stop |
| `src/app.ts` | Router, `/mcp` authentication, security headers, MCP server setup |
| `src/oauth/google-proxy.ts` | OAuth 2.1 server for MCP clients, proxying sign-in to Google |
| `src/oauth/redirects.ts` | Redirect URI allowlist (ported from `mcp_data_core`) |
| `src/consent.ts` | Terms gate, `/consent`, `/consent/accept` |
| `src/rate-limit.ts` | Byte buckets and their FastMCP middleware |
| `src/usage.ts` | Stdout events and the usage-log middleware |
| `src/storage.ts` | Storage interfaces and in-memory implementations |
| `src/firestore.ts` | Firestore REST client and Firestore implementations |
| `src/google-auth.ts` | Google credentials for Firestore (metadata server or ADC) |
| `src/pages.ts`, `assets/` | The Python templates and static files, copied verbatim |
| `src/corpora.ts` | Corpus bootstrap seam |

`packages/mcp` gained three generic `createServer` options for this:
`hiddenTools` (registers the named tools disabled, so `tools/list` omits
them and `tools/call` refuses them), `serverInfo` (icons, website URL,
title) and `instructions`. FastMCP builds a new SDK `Server` per request
and passes it only a name and version, so `serverInfo` and `instructions`
are applied to each one as it is made; that relies on FastMCP and SDK
internals and throws at startup if their shape changes.

### OAuth

The flow follows the Python `GoogleProvider` (FastMCP's `OAuthProxy`):

1. The MCP client registers at `/register` (dynamic client registration).
   Every client is public (`token_endpoint_auth_method: none`), and each
   redirect URI must match the allowlist Python uses: claude.ai,
   `*.anthropic.com`, Claude Desktop's `claude://` callback, ChatGPT, and
   loopback addresses on any port.
2. `/authorize` checks the client, redirect URI, PKCE S256 challenge, scope
   and optional `resource`, stores a transaction, and redirects to Google
   with its own PKCE pair, `access_type=offline` and `prompt=consent`. A
   cookie scoped to `/auth/callback` binds the transaction to that browser.
3. Google redirects to `/auth/callback`. The server checks the binding
   cookie, exchanges the code with Google, reads the identity from Google's
   ID token (issuer, audience and expiry are checked; the signature is not,
   since the token came directly from Google over TLS) and requires a
   verified email. It then redirects to the client with a one-time code.
4. `/token` redeems the code (five-minute, single use, PKCE-checked, bound
   to the client and redirect URI) for an access token and, when Google
   issued a refresh token, a refresh token.
5. `/token` with `grant_type=refresh_token` refreshes Google's token first,
   then issues a new access token and a new refresh token. The old refresh
   token stops working. Google `invalid_grant` ends the grant; a Google
   outage returns 503 and gives the refresh token back.
6. `/revoke` (RFC 7009) accepts either token and ends the whole grant.

Access tokens are HS256 JWTs (`typ: at+jwt`) signed with a key derived from
`SESSION_SECRET`, with issuer `ISSUER_URL`, audience `<PUBLIC_URL>/mcp`,
the Google subject, the client id, scopes, and the grant id. Their lifetime
is the shorter of an hour and Google's `expires_in`. Verification checks
the signature, issuer, audience, expiry (30 seconds of clock tolerance)
and that the grant still exists in storage, so revocation takes effect on
the next request. Refresh tokens are random strings stored only as SHA-256
hashes, and a grant ends 30 days after sign-in, as in Python. Google's
tokens are stored encrypted with AES-256-GCM under another key derived from
`SESSION_SECRET`, bound to the record they sit in. Tokens are never logged.

### Storage

Three small interfaces in `src/storage.ts`, each with an in-memory and a
Firestore implementation:

| Interface | Firestore collections |
| --- | --- |
| `OAuthStore` (`get`, `put` with TTL, atomic `take`, `delete`) | `ts-mcp-oauth-clients`, `-transactions`, `-codes`, `-grants`, `-refresh-tokens` |
| `RateLimitStore` (read, atomic read-modify-write) | `ts-mcp-rate-limits` |
| `UsageSink` (append) | `ts-mcp-usage` |

The Firestore implementation calls the REST API (v1) with `fetch` instead of
a Google SDK. Atomic `take` and rate-limit updates use commit preconditions
on the document's update time, retried on conflict. OAuth records are
stored as `{ value, expires_at }`; reads treat expired records as absent,
and a Firestore TTL policy on `expires_at` for the `ts-mcp-oauth-*`
collections (a Phase 1 Terraform item) would delete them. Credentials come
from the Cloud Run metadata server, or locally from
`GOOGLE_APPLICATION_CREDENTIALS` or gcloud's application default
credentials file (service account keys and `gcloud auth
application-default login` both work). `FIRESTORE_EMULATOR_HOST` points it
at the emulator.

### Rate limits and usage log

Both are FastMCP `onCallTool` middleware, with usage outermost so rejected
calls are logged. The limits are Python's: two byte buckets per user,
`MB_PER_MINUTE` refilled over a minute and `MB_PER_DAY` over a day, each
call checked before it runs and debited afterwards with the larger of its
JSON result size and `MIN_CHARGE_BYTES`. Admins (`ADMIN_EMAILS`) get the
admin limits. A rejection is a tool error reading `[retryable] Rate limit
exceeded on <bucket> bucket. Retry in ~Ns.` Unauthenticated calls (auth
bypass) skip both buckets and the usage collection.

Users are identified by a pseudonymous actor id: the first 32 hex
characters of HMAC-SHA256(`ACTOR_HASH_KEY`, lowercased email), the same
function Python uses for `actor_id`, so the ids match across the two
services when they share the key. Each tool call writes one usage record
with Python's fields minus `email`: `actor_id`, `tool`, `ts`,
`duration_ms`, `ok`, `error`. Stdout carries `tool_call` events
(`actor_id`, `tool`, `duration_ms`, `ok`, `error`, an argument preview)
and `rate_limited` events (`actor_id`, `bucket`, `retry_after_seconds`),
also without email.

## Routes

| Route | Behavior |
| --- | --- |
| `GET /` | Landing page (`home.html`) |
| `GET /terms`, `GET /privacy` | Policy pages |
| `GET /consent` | Terms form; `next` is echoed only if it is a same-origin path |
| `POST /consent/accept` | Requires `agree=on`; sets `pca_terms_accepted=<TERMS_VERSION>` for a year and 303s to `next` |
| `GET /static/icon.png`, `icon.svg`, `wordmark.png` | Fixed file list |
| `GET /favicon.ico` | `icon.png` bytes (no redirect, as in Python) |
| `GET /robots.txt` | Disallows the OAuth surface and `/mcp` |
| `GET /-/health` | `{"status":"ok"}` |
| `GET /mcp` | 302 to `/` for browser navigations (`Accept` has `text/html`, not `text/event-stream`); otherwise 405 with `Allow: POST, DELETE` |
| `POST`, `DELETE /mcp` | MCP over streamable HTTP, stateless; 401 with `WWW-Authenticate: Bearer ... resource_metadata="..."` without a valid token |
| `GET /.well-known/oauth-authorization-server[/mcp]` | Authorization server metadata |
| `GET /.well-known/oauth-protected-resource[/mcp]` | Protected resource metadata |
| `POST /register`, `/token`, `/revoke` | OAuth endpoints, with CORS for browser clients |
| `GET /authorize` | Terms gate, then the OAuth authorization request |
| `GET /auth/callback` | Google's redirect target |
| `/downloads` | Served from `packages/mcp` (signed, per-process artifacts) |

Every response gets `X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy`, HSTS when `PUBLIC_URL` is HTTPS, and on HTML Python's
Content-Security-Policy (whose `form-action` allows accounts.google.com for
the consent redirect chain). HEAD works wherever GET does. Unknown paths
return `{"error":"Not Found"}`; unhandled errors return a 500 JSON body
without details.

## Environment variables

Names follow the Python deploy wrapper where one exists. Empty values count
as unset.

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8080` | Listen port (Cloud Run sets it) |
| `HOST` | `127.0.0.1` (`0.0.0.0` in the image) | Listen address |
| `PUBLIC_URL` | `http://localhost:8080` | Public origin; base of every advertised URL. HTTPS unless loopback |
| `ISSUER_URL` | `PUBLIC_URL` | OAuth issuer identifier |
| `DOWNLOAD_BASE_URL` | `PUBLIC_URL` | Origin for download links |
| `AUTH_BYPASS` | `false` | Local only: no OAuth, `/mcp` open. Refused when `K_SERVICE` is set (Cloud Run) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | required with OAuth | Google OAuth web client. `LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID`/`_SECRET` also accepted. Its redirect URI must include `<PUBLIC_URL>/auth/callback` |
| `SESSION_SECRET` | required with OAuth, 32+ characters | Derives the access-token signing key and the key sealing Google tokens. Rotating it signs everyone out |
| `ACTOR_HASH_KEY` | required with OAuth, 16+ characters | HMAC key for actor ids |
| `TERMS_VERSION` | `2026-04-23` | Terms cookie value; bump to make everyone re-accept |
| `STATE_BACKEND` | `firestore` (`memory` with bypass) | `memory` keeps OAuth, limits and usage in the process |
| `GCP_PROJECT` | from credentials or metadata | Firestore project (`GOOGLE_CLOUD_PROJECT` also accepted) |
| `FIRESTORE_DATABASE` | `(default)` | Firestore database id |
| `FIRESTORE_EMULATOR_HOST` | unset | `host:port` of the Firestore emulator |
| `GOOGLE_APPLICATION_CREDENTIALS` | unset | Local credentials file for Firestore |
| `ADMIN_EMAILS` | empty | Comma-separated emails on the admin limits |
| `MB_PER_MINUTE`, `MB_PER_DAY` | `20`, `100` | Per-user byte buckets |
| `ADMIN_MB_PER_MINUTE`, `ADMIN_MB_PER_DAY` | `200`, `2048` | Admin buckets |
| `MIN_CHARGE_BYTES` | `1024` | Minimum debit per call |
| `HIDDEN_TOOLS` | `search_trademarks` | Comma-separated tools to hide; empty hides none |
| `CORPORA_MANIFEST_URI` | unset | When set, `bootstrapCorpora` runs before the server binds |
| `CORPORA_CACHE_DIR` | `/app/corpora` | Bootstrap target directory |
| `DOWNLOAD_BUCKET`, `DOWNLOAD_TTL_SECONDS`, `DOWNLOAD_PREFIX`, `DOWNLOAD_SIGNER_EMAIL` | unset, `86400`, `downloads`, unset | GCS signed-URL downloads; see [downloads](downloads.md) |

The connectors read their own credentials from the environment, as they do
outside the hosted app; startup logs which families are configured, never
the values:

| Variable | Used by |
| --- | --- |
| `USPTO_ODP_API_KEY` | USPTO Open Data Portal tools |
| `USPTO_TSDR_API_KEY` | `get_trademark` |
| `EPO_OPS_API_KEY`, `EPO_OPS_API_SECRET` (or `EPO_API_KEY`, `EPO_API_SECRET`) | EPO OPS |
| `KIPO_KIPRIS_API_KEY`, `KIPO_KIPRIS_BASE_URL` | KIPRIS (no key exists yet) |
| `USITC_EDIS_TOKEN` or `USITC_EDIS_TOKEN_FILE` | USITC EDIS. Python deliberately does not mount it on the demo; leave it unset to keep the ITC tools off |
| `USITC_DATAWEB_TOKEN` or `USITC_DATAWEB_TOKEN_FILE` | USITC DataWeb |
| `PCA_WAF_TOKEN_JSON`, `PCA_WAF_TOKEN_FILE` or `PCA_WAF_SECRET_RESOURCE` | Trademark Search session (the tool is hidden by default) |
| `<BOOK>_CORPUS_PATH`, `<BOOK>_CORPUS_SHA256`, `<BOOK>_CORPUS_FILE_SHA256` | Corpus artifacts; `<BOOK>` is `MPEP`, `TMEP`, `MOPP`, `EPC`, `CASELAW`, `GUIDELINES`, `PCT_GUIDELINES`, `UP_GUIDELINES`, `UPC_STATUTES`, `DPMA_STATUTES`, `IPO_IN_STATUTES` or `IPO_IN_MPPP`. Unset paths fall back to `~/.cache/patent_client_agents/` |

## Differences from Python

These are deliberate unless marked otherwise.

- **Token format and checks.** Python checks every request with two calls
  to Google (tokeninfo and userinfo). Here a request costs one grant read
  from Firestore and no Google call; Google is consulted at sign-in and on
  each refresh, which is when a user's revocation at Google takes effect
  (within an hour at most).
- **Refresh tokens rotate** on every use; Python reuses one refresh token.
- **Verified email required.** Python's demo text says any verified Google
  account; Python does not enforce it. This does.
- **Browser binding at the callback.** Python skips its consent-binding
  cookie when consent is external; this binds each sign-in to the browser
  that started it.
- **Consent form** refuses cross-site posts when the browser sends an
  `Origin` header. Python has no check.
- **Metadata.** The issuer has no trailing slash (Python advertises
  `https://mcp.patentclient.com/`), the server advertises
  `token_endpoint_auth_methods_supported: ["none"]` (Python advertises
  `client_secret_post`/`basic` but registers every client as public), and
  it adds a revocation endpoint. Client ID metadata documents (CIMD) are
  not supported, so clients use dynamic registration.
- **Registration** rejects redirect URIs outside the allowlist at
  `/register`; Python accepts them there and fails at `/authorize`.
- **No email in logs or usage records.** Python stores the plaintext email
  in `usage/` and logs it to stdout; this stores and logs only `actor_id`.
  Rate-limit buckets are keyed by the actor id instead of Python's
  unkeyed SHA-256 email prefix, in one document per user holding both
  buckets.
- **Error results count as failures.** The usage log marks a tool call
  `ok: false` when the tool returns an error result as well as when it
  throws; Python only saw exceptions.
- **Auth bypass** is refused on Cloud Run, and in bypass mode the server
  rejects requests whose `Host` is not local or the public host (DNS
  rebinding).
- **Page copy is Python's, unchanged.** The landing page still says "One
  hundred seven typed MCP tools"; the curated server lists 28. Updating
  the copy is a product decision left for review.

## Corpora and downloads

- **Corpora.** When `CORPORA_MANIFEST_URI` is set, `main.ts` runs
  `prepareCorpora` before binding. It calls the shared bootstrap in
  `@patent-client-agents/client/corpus-bootstrap` (see
  [corpus bootstrap](corpus-bootstrap.md)), which downloads and verifies every
  artifact into `CORPORA_CACHE_DIR` and throws on any mismatch, then copies
  the returned `<BOOK>_CORPUS_PATH` and sha256 pin variables into the process
  environment before the readers are built. Without the variable, the readers
  use whatever corpus paths the environment already sets.
- **Downloads.** `downloadOptions(config)` in `src/app.ts` builds the
  `downloads` option. With `DOWNLOAD_BUCKET` set it adds a `GcsBlobStore`, so
  download tools return V4 signed `storage.googleapis.com` URLs (see
  [downloads](downloads.md) for the bucket, lifecycle rule and IAM).
  Otherwise downloads use HMAC-signed links on `DOWNLOAD_BASE_URL`, served
  from per-process storage.

## Running locally

```bash
cd typescript
AUTH_BYPASS=true bun run start:hosted          # http://127.0.0.1:8080, no auth
```

With real Google sign-in, in one process and without Firestore:

```bash
PUBLIC_URL=http://localhost:8080 GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... \
SESSION_SECRET="$(openssl rand -hex 32)" ACTOR_HASH_KEY="$(openssl rand -hex 16)" \
STATE_BACKEND=memory bun run start:hosted
```

The Google client must list `http://localhost:8080/auth/callback`. Against
the Firestore emulator, start `gcloud emulators firestore start
--host-port=127.0.0.1:8681` and set `STATE_BACKEND=firestore`,
`FIRESTORE_EMULATOR_HOST=127.0.0.1:8681` and any `GCP_PROJECT`.

The image:

```bash
docker build -f Dockerfile.hosted -t patent-mcp-ts .
docker run --rm -p 127.0.0.1:8080:8080 -e AUTH_BYPASS=true \
  -e PUBLIC_URL=http://localhost:8080 patent-mcp-ts
```

It runs as the `bun` user on `oven/bun:1.4.3-slim` pinned by digest,
honors `PORT`, and has a Docker `HEALTHCHECK` on `/-/health`. Bun runs the
TypeScript sources; there is no build step.

## Tests

`tests/hosted-*.test.ts` run offline:

- `hosted-oauth`: the flow end to end over real listeners against a fake
  Google, including PKCE, single-use codes, binding cookies, unverified
  email, refresh rotation, expiry, revocation and Google failures. With
  `FIRESTORE_EMULATOR_HOST` set, OAuth state lives in the emulator.
- `hosted-storage`: one contract for the in-memory stores, Firestore REST
  against a fake Firestore server, and the emulator when
  `FIRESTORE_EMULATOR_HOST` is set (`describe.if`).
- `hosted-middleware`: bucket arithmetic (ported from the Python tests),
  the limiter, both middlewares, and a rate-limited call through FastMCP.
- `hosted-routes`: every route, the eight smoke-test checks, the terms
  gate, serverInfo, hidden tools and bypass mode.
- `hosted-config`: configuration validation, credential sources, the
  corpus seam and `hiddenTools` on the full toolset.

On October 22 the emulator runs (Java 21, `cloud-firestore-emulator`
installed) passed, and the built image passed the deploy repository's eight
public smoke checks with OAuth configured (checks 6 to 8 do not apply under
auth bypass). Under bypass the image listed 28 tools and served live
`search_cafc_patent_opinions` and `get_fees` calls.
