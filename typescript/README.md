# Patent Client Agents: TypeScript

A Bun workspace containing an independent patent research library and a thin
MCP server. This is an incremental port; the Python package continues to be
maintained separately.

The first slice implements USPTO ODP application search, application retrieval,
and prosecution-document listing. It does not yet implement all ODP 5.0 APIs.
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
The results include access-time provenance. There is no runtime HTTP cache in
this first slice. Unknown response fields are retained rather than discarded.

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
bun run --cwd packages/mcp start
```

The tools are `search_applications`, `get_application`, and `list_file_history`.
They declare input/output schemas and read-only annotations, return the existing
summary/items/provenance envelope, and support opaque pagination cursors.
`get_application` accepts one number or a portfolio of up to 20 numbers.

HTTP mode requires identity configuration and the `odp:read` scope. Put HTTPS
in front of the loopback HTTP listener for remote deployments. No identity
provider, login UI, discovery integration, or hosted deployment is created here.
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

# Verify available upstream recordings offline.
bun run replay:odp
```

Configure the key in the ignored local `.env` or through your existing secret
manager. Recordings are public application records, not private Patent
Center data. Review cassette diffs and run the repository's secret scan before
committing refreshed recordings. Successful live recordings require an active
ODP key; synthetic contract tests and an anonymous API-error recording are
identified separately and do not establish successful live feature coverage.

On October 20, 2026, application search, full application retrieval, and document
listing (including associated metadata) were recorded successfully for the
official sample application 14412875. Search and retrieval each returned one
application; the document response contained 184 documents. All three recordings
replayed offline, and the MCP tools returned their data through the real client.
These fixtures are required by the default test suite; deleting one fails tests.

See [stack decisions](docs/stack.md) for the Rust/WASM boundary and security limits.
