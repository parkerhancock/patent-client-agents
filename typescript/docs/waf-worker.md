# Trademark Search WAF refresh

The optional `@patent-client-agents/waf-worker` package runs Playwright under
Bun, acquires the official site's `aws-waf-token`, closes Chromium, and publishes
the session privately. The client and MCP runtime do not depend on Playwright.
The browser-free `@patent-client-agents/waf-session` package owns validation,
storage, and fresh-session delivery.

## Local file delivery

From `typescript/`, install the pinned dependencies and matching Chromium:

```sh
bun install --frozen-lockfile
bun run waf:install-browser
install -d -m 700 "$HOME/.local/state/patent-client-agents"
export PCA_WAF_TOKEN_FILE="$HOME/.local/state/patent-client-agents/uspto-waf.json"
bun run waf:refresh
```

Start the MCP server with the same `PCA_WAF_TOKEN_FILE` and its normal transport
and authentication settings. Subsequent worker runs replace the file atomically
with mode `0600`. The parent directory must already exist. File storage requires
POSIX permission semantics on macOS/Linux; native Windows is rejected.

The server polls on requests with a 30-second cache. On WAF rejection it reloads
immediately and retries the search once if a different session is available.
An unchanged rejected cookie fails cleanly. The provider is authoritative over
any old `PCA_WAF_TOKEN_JSON` environment snapshot; a warm process sees rotation
without restarting. Conflicting file/Google settings are rejected.

## Google Secret Manager delivery

Set this on both the worker and MCP service, without setting the file variable:

```sh
export PCA_WAF_SECRET_RESOURCE="projects/PROJECT_ID/secrets/SECRET_ID"
```

The secret must already exist. The worker adds a version; the server accesses
`versions/latest` using native Fetch and the workload identity metadata endpoint.
There is no Google SDK, `gcloud` process, interactive login, or service-account
key file in the runtime path. The worker identity needs
`roles/secretmanager.secretVersionAdder` on this secret; the server identity
needs `roles/secretmanager.secretAccessor`. Keep those identities separate.

Reads and writes have deadlines, body limits, fixed Google origins, redirect
refusal, and CRC32C integrity checking. Old versions without a returned checksum
remain readable. Errors omit response bodies, bearer tokens, cookies, and causes.
The provider coalesces concurrent reads, validates expiry and User-Agent, and
refuses to treat the same rejected session as a successful refresh.

Canonical in-process timestamps use epoch seconds. Published `acquired` values
use ISO timestamps to preserve compatibility with the existing Python refresh
job and its cache ordering; readers accept either representation. Old Python
payloads without `userAgent` use the same established User-Agent constant.

## Worker execution and deployment

`bun run waf:refresh` is one bounded job, not a scheduler. The CLI also accepts
`--output-file PATH` or `--secret-resource RESOURCE`. It emits only success,
expiry/acquisition times, or a fixed failure code. Cookie values never appear in
its output. Browser protocol debugging is rejected, and the Chromium child
receives a minimal OS environment rather than office or cloud credentials.
No traces, HARs, screenshots, or persistent browser profile are saved.

The default refresh budget is 60 seconds across acquisition and publication,
plus bounded browser cleanup. Cancellation/deadline checks prevent publication
from starting after cancellation. A remote write already in flight can have an
unknown outcome if the caller times out; do not blindly retry it.

Build the separate worker image from this workspace:

```sh
docker build -f packages/waf-worker/Dockerfile -t pca-waf-worker .
```

The image installs the pinned browser with Bun and runs as the unprivileged
`bun` user. The build context excludes environment files, dependencies, fixtures,
and Git data. The image is intended for a scheduled job with workload identity,
not for inclusion in the MCP service image. Set a schedule appropriate to the
actual cookie expiry and observed WAF acceptance; a rejected session does not
trigger browser acquisition inside a research request.

This change does not create or update a production job, schedule, secret, IAM
policy, or deployment. The existing Python job remains in place until a separate
cutover.

## Validation

Ordinary tests use fake browsers and fake Google responses; they never acquire
live credentials. Tests cover worker cleanup/cancellation, protected file
rotation, warm default-MCP delivery, concurrent refresh, unchanged rejected
sessions, deadline behavior, integrity checks, and sanitized failures.
A dependency-boundary test prevents the client, MCP, or delivery package from
acquiring browser runtime dependencies.

Relevant primary documentation: [Playwright Library](https://playwright.dev/docs/library),
[Secret Manager access](https://cloud.google.com/secret-manager/docs/access-secret-version),
[Secret Manager integrity](https://cloud.google.com/secret-manager/docs/data-integrity).

For an explicit live smoke test, run `bun run verify:waf --live`. It acquires a
fresh session, verifies `0600` file delivery through the default MCP client
despite a synthetic stale environment snapshot, performs one public search,
and removes its private temporary file. It reports only verification stage
and cleanup status. It never changes a production secret.

To verify the built worker image itself, mount only the verification script:

```sh
docker run --rm --init --shm-size=1g \
  --mount "type=bind,source=$(pwd)/scripts/verify-waf-container.ts,target=/app/scripts/verify-waf-container.ts,readonly" \
  --entrypoint bun pca-waf-worker:local \
  --no-env-file scripts/verify-waf-container.ts --live
```

This checks Linux non-root execution, actual Chromium acquisition, `0600` file
publication, provider delivery and one native-client search. The temporary
credential stays inside the container and is removed; only verification stage
and cleanup status are printed. It does not mount host credentials or exercise
MCP inside the worker image. The separate host smoke test above verifies default
MCP wiring. Ordinary tests do not run either live command.

On October 20, 2026, both `linux/arm64` and `linux/amd64` images built and passed
this live verification under OrbStack Docker 29.4.0. The AMD64 run used local
emulation; it does not establish hosted Cloud Run or workload-identity behavior.
The recorded local image IDs were `aca14a765583` (ARM64, `pca-waf-worker:local`)
and `6bcf91560ee3` (AMD64, `pca-waf-worker:amd64`). Build AMD64 explicitly with
`docker build --platform linux/amd64 -f packages/waf-worker/Dockerfile -t pca-waf-worker:amd64 .`
and add `--platform linux/amd64` to the verification command when testing that
tag on ARM64. No image was pushed and no production configuration changed.
The AMD64 image's default CLI also successfully published to a private file
inside an automatically removed container. Without a destination, the default
CLI returned only `INVALID_CONFIGURATION` and exited with status 1 as expected.
