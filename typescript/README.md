# Patent Client Agents: TypeScript

A Bun workspace containing an independent patent research library and a thin
MCP server. This is an incremental port; the Python package continues to be
maintained separately.

The USPTO API port covers the 70 inventoried public Python domain methods,
current ODP Office Actions and Petition Decisions, and all 25 archived TSDR
routes. Live verification varies by family; see [port status](docs/port-status.md).
See the [source review](docs/odp-research.md) and [stack decisions](docs/stack.md).

## Development

Use Bun 1.4.3. The older Bun installed on a machine is not the project's tested
runtime; check `bun --version` before installing dependencies.

```sh
cd typescript
bun install --frozen-lockfile
bun run check
bun run test:watch
bun run build
```

`check` runs Biome, incremental TypeScript checking, and offline tests. Tests run
source TypeScript without a preceding build. Type checking also emits the
library's ESM JavaScript and declarations for package consumption. Dependency
versions and the Bun version are pinned; installs have a seven-day minimum
release age. No lifecycle scripts are explicitly trusted by this workspace.

## Library

```ts
import { ApplicationsClient } from "@patent-client-agents/client";

// Reads USPTO_ODP_API_KEY from the environment, or accept apiKey explicitly.
const applications = new ApplicationsClient();
const results = await applications.search({
  query: "applicationMetaData.inventionTitle:semiconductor",
  limit: 10,
});
const application = await applications.get("14/412,875");
const history = await applications.getDocuments("14412875", {
  documentCodes: ["CTNF"],
  includeAssociated: false,
});
```

Search defaults to a lean projection. `full: true` requests the full upstream
record; explicit `fields` overrides that choice. Application metadata is
flattened by default; `normalize: false` preserves the upstream search shape.
The results include access-time provenance. There is no runtime HTTP response cache. Unknown response fields are retained rather than discarded.

Clients accept an `AbortSignal` per operation. Requests have a bounded total
time budget and retry transient failures, including read-only search POSTs.
Authentication errors are not retried. Search 404s return an empty result;
application and document retrieval 404s raise `OdpApiError`.

## MCP

```sh
# Local stdio: configure USPTO_ODP_API_KEY first.
bun run --cwd packages/mcp start

# Hosted HTTP: use your existing identity provider's values.
MCP_TRANSPORT=http MCP_HOST=127.0.0.1 MCP_PORT=3000 \
MCP_JWKS_URL=https://identity.example/.well-known/jwks.json \
MCP_ISSUER=https://identity.example/ MCP_AUDIENCE=patent-client-agents \
MCP_PUBLIC_BASE_URL=https://patents.example \
bun run --cwd packages/mcp start
```

Tools cover application search and data, file history and downloads, family and
claims retrieval, PTAB, petitions, bulk products, Office Actions, assignments,
Patent Public Search, and trademark search/status/documents. Input/output
schemas, read-only annotations, lean defaults and query-bound cursors keep the
MCP adapter small. TSDR tools are advertised when `USPTO_TSDR_API_KEY` is set or
a client is injected. Historical search guides and schemas remain available as
explicitly labeled MCP resources.

HTTP mode requires identity configuration. ODP tools require `odp:read`;
other USPTO families require `uspto:read`. Document REST retrieval requires
`documents:read` and the originating caller's issuer/subject. Put HTTPS in front
of the loopback listener. No hosted identity provider, login UI, or deployment
is configured by this project.

Document tools return filename, MIME type, size, expiry, provenance, and a
REST URL, with local file paths in stdio mode. Authenticated REST is the default;
a trusted host download tool must attach OAuth credentials outside the model
context and save response bytes to a file. Ordinary URL fetchers do not
automatically inherit MCP authentication. `MCP_DOWNLOAD_MODE=signed` explicitly
selects short-lived, document-specific signed links for hosts that cannot
attach credentials. These links are bearer capabilities, not single-use tokens.
See [document transport](docs/stack.md#document-retrieval-outside-model-context).

The CLI uses FastMCP's authenticated listener; its low-level `fetch()` entrypoint
does not itself enforce the configured authentication and must not be substituted
without explicit verification. The framework's public handler context does not
currently expose cancellation, so client cancellation support is not yet forwarded
from MCP calls.

## Recorded HTTP tests

Default tests replay committed recordings without credentials or live traffic.
Cassettes use Cassetter's replay-only mode with method, URI, and JSON-body
matching. New or changed requests must fail, not silently call the network.
Secret filtering runs before recordings are written.

```sh
# Explicitly record successful upstream interactions using your own key.
bun run record:odp

# More USPTO families and application datasets/downloads.
bun run record:uspto
bun run record:applications

# Verify recordings offline.
bun run replay:odp
bun run replay:uspto
bun run replay:applications
```

Configure the key in the ignored local `.env` or through your existing secret
manager. Recordings are public application records, not private Patent
Center data. Review cassette diffs and run the repository's secret scan before
committing refreshed recordings. Successful live recordings require an active
ODP key; synthetic contract tests and an anonymous API-error recording are
identified separately and do not establish successful live feature coverage.

Live recordings include application search/retrieval/history and seven dataset
views, status codes, PDF/XML/DOCX, 32 granted claims, seven PTAB/petition/bulk
searches, the new Office Actions search, a small bulk ZIP, and current Assignment
Center v3 responses. Native Bun Patent Public Search also retrieved an official
18-page PDF; its archived response fixture verifies all 26 claims. TSDR uses
separate credentials, and Trademark Search requires an externally provided WAF
session; fresh authenticated coverage of those two remains pending.

Bulk redirects can contain signed credentials in Location headers and response
bodies. Use the dedicated bounded recorder rather than the ordinary helper:
`bun run record:bulk-file --product=TRTDXFAG --file=asb261018.zip`.
Select a currently available file smaller than 1 MiB; updating the fixture's
product/name also requires updating its explicit replay assertion. The recorder
scrubs signed query values in requests, response locations and redirect bodies.

See [stack decisions](docs/stack.md) for the Rust/WASM boundary and security limits.
