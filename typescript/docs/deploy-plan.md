# Curated shadow deploy plan

October 22, 2026. Plan only; nothing in this document has been run.

The goal is to run the TypeScript curated facade (`toolset: "curated"`) on Cloud
Run next to the Python demo at `mcp.patentclient.com`, vet it with real
traffic from a known client, and only then decide on cutover. Each phase below
ends at a stop: the next one starts only after Parker approves it, and every
step that writes to GCP is shown (Terraform plan, exact `gcloud` command,
or diff) before it runs.

## Where things stand

The Python demo is more than the MCP server. The deploy wrapper
(`patent-client-agents-deploy/src/patent_mcp_deploy/`, about 1,400 lines)
adds:

| Wrapper piece | Python today | TypeScript today |
| --- | --- | --- |
| OAuth | FastMCP `GoogleProvider` (DCR proxy to Google), client state in Firestore | `cli.ts` takes only a JWKS verifier; fastmcp-ts accepts a custom OAuth provider, but its own providers keep registrations in memory |
| Terms gate | Middleware diverts `/authorize` to `/consent` until a versioned cookie is set | None |
| Rate limits | Firestore token buckets per pseudonymous user, per minute and per day | None (fastmcp-ts ships an in-memory `RateLimitingMiddleware`) |
| Usage log | Firestore `usage/` record per tool call | None |
| Downloads | `blob_store.py` supports GCS objects with V4 signed URLs (IAM `signBlob`), but the deploy Terraform sets no `LAW_TOOLS_CORE_GCS_BUCKET`; links go through the HMAC `/downloads` route behind `downloads.patentclient.com` | Done locally: `GcsBlobStore` with V4 signed URLs through `signBlob`, enabled by `DOWNLOAD_BUCKET` ([downloads.md](downloads.md)); without it, HMAC-signed URLs served by the process |
| Web pages | Landing page, `/static` icons, `robots.txt`, favicon, `/-/health`, browser redirect on `GET /mcp`, security headers | None |
| Hidden tools | `search_trademarks`, `search_upc_decisions` hidden on the demo | Facade has no visibility filter; UPC decisions is already unported |
| Corpora | Bootstrap pulls zstd blobs from `gs://patentclient-mcp-corpora/manifest.json` at start; UPC baked in | Reads prepared DELETE-mode `.zst` files; all twelve, EPO included, are packaged locally with a bootstrap and publish script ([corpus bootstrap](corpus-bootstrap.md)), none published yet |

Credentials: the EDIS and DataWeb tokens in Secret Manager expired (May 27 and
September 27), no KIPRIS Plus key exists, and the WAF token secret is refreshed
by the Python Playwright job, whose JSON the TypeScript client can read.

## Decisions to make before Phase 0

1. **Shadow shape.** Recommended: a separate Cloud Run service
   (`patent-mcp-ts`) with no domain mapping. It cannot take prod traffic by
   accident and keeps its OAuth state apart. The alternative, a zero-traffic
   tagged revision on `patent-mcp-demo`, reuses the existing promote flow but
   shares the issuer URL and Firestore OAuth collections with a server that
   writes them in a different format.
2. **Where the hosted app lives.** Recommended: a new workspace package,
   `typescript/packages/hosted`, built into an image from this repository,
   with the deploy repository holding only Terraform and Cloud Build config.
   The TypeScript packages aren't published, so keeping the app in the
   workspace avoids a publishing step. The alternative is a TypeScript app in
   the deploy repository that pins this repository by commit.
3. **OAuth storage.** fastmcp-ts's built-in `oauthProvider()` and
   `oauthProxy()` keep all state in memory, but its auth config accepts any
   MCP SDK `OAuthServerProvider`. Recommended: write a Google proxy provider
   in the hosted package with Firestore-backed clients, codes and tokens under
   separate collections (`ts-mcp-*`).

## Phase 0: hosted app, local only

No GCP writes.

1. Build `packages/hosted`: the curated server plus Google OAuth with
   Firestore storage, the terms gate, Firestore rate limits and usage log,
   GCS signed-URL downloads (done in `packages/mcp`: pass a `GcsBlobStore`
   as `downloads.blobStore`; see [downloads.md](downloads.md), which also
   lists the bucket, lifecycle rule and IAM Phase 1 needs), the web pages
   and headers, serverInfo icons, and
   a hidden-tool list (`search_trademarks` until hosted WAF refresh is shown
   to work).
   Status (October 22): built, see [hosted](hosted.md). `DOWNLOAD_BUCKET`
   switches downloads to the GCS store, and `CORPORA_MANIFEST_URI` runs the
   corpus bootstrap before the server binds.
2. Corpora: prepare the five EPO corpora as `.zst` and write a TypeScript
   bootstrap that reads a separate manifest
   (`gs://patentclient-mcp-corpora/ts/manifest.json`), checks sha256 and
   fails the container on mismatch, as Python does. The total is small enough
   that baking them into the image is the fallback.
   **Done locally (October 22):** all twelve corpora the curated server reads
   are packaged under `.data/` (37,442,379 bytes compressed), the bootstrap is
   `@patent-client-agents/client/corpus-bootstrap`, and
   `scripts/publish-corpora.ts` has been run only as a dry run. See
   [corpus bootstrap](corpus-bootstrap.md). The upload is Phase 1, step 1.
3. Dockerfile on `oven/bun`, run with the Node and Bun smoke tests.
   Status (October 22): `Dockerfile.hosted` builds a 267 MB image that
   passes the eight public smoke checks locally; Node and browser smoke
   scripts pass.
4. Tests against the Firestore emulator and a fake GCS; an end-to-end local
   run with Claude Code against the container, using auth bypass.
   Status (October 22): storage tests pass against the Firestore emulator
   and a fake Firestore server, and the OAuth flow is tested end to end
   against a fake Google. The container served tools/list and live tool
   calls over HTTP with auth bypass; a Claude Code session against it and
   fake-GCS tests are not done.

Stop: review the diff and a local demo.

## Phase 1: shadow service, no prod impact

Every write shown first.

1. Upload the TypeScript corpus artifacts under the new `ts/` prefix and
   write its manifest. The Python manifest is not touched.
2. Terraform in the deploy repository: an Artifact Registry image path, a
   runtime service account, IAM on the secrets, the corpus bucket, Firestore
   and `signBlob`, and the `patent-mcp-ts` service (min 0, max 1, same egress
   network). `terraform plan` output is reviewed before `apply`.
3. Build and push the image with a dedicated `cloudbuild-ts.yaml`, run by
   hand (deploy repository GitHub automation is disabled).
4. Deploy. The service URL is the only way in.

Stop: confirm the service is up and the health and OAuth metadata endpoints
answer.

## Phase 2: vetting

1. Run the deploy repository's hosted smoke checks and
   `bun run verify:facade-live` against the shadow URL.
2. Compare the 30 facade tools side by side with Python prod on the same
   inputs, and record differences that are bugs and differences that are
   intended fixes.
3. Parker connects the shadow URL in Claude.ai as a custom connector and uses
   it for a few days. Watch Cloud Logging, errors, memory and cost.

Stop: decide on cutover.

## Phase 3: cutover

1. Move `mcp.patentclient.com` to `patent-mcp-ts` (the mapping mechanism is
   confirmed then). Existing Claude.ai connections hold Python-format DCR
   registrations, so users reconnect once.
2. Keep `patent-mcp-demo` running at min 0 as the rollback target; rollback
   is pointing the domain back.
3. Re-enable the daily smoke test against the new service.

## Phase 4: retire Python

After a quiet period, remove the Python service, its WAF job (once a
TypeScript refresh path is proven) and the Python corpus manifest.
