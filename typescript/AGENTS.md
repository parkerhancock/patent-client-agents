# TypeScript port

Read `README.md`, `docs/stack.md`, and `docs/port-status.md` before changing this
subproject. Root repository instructions and connector standards still apply.

Before porting another connector, read `docs/connector-patterns.md` for reference
implementations, unrepresented styles and the MPEP corpus prerequisites.
For corpus work, also read `docs/mpep.md`: runtime reads verified standalone
snapshots; maintenance builds preserve source retrieval times across rebuilds.

Use Bun 1.4.3 and the committed lockfile. Run `bun install --frozen-lockfile`,
`bun run check`, and `bun run build`. Use `bun test <file>` or `bun run test:watch`
for the inner loop; tests execute TypeScript source without rebuilding first.
Run `bun run format` for deterministic Biome fixes.

Keep `packages/client` independent of MCP. Put shared HTTP behavior in its Ky
transport. `packages/mcp` contains only protocol/transport configuration, tool
schemas and presentation, portfolio handling, and authorization.

Do not read or print `.env` credentials. Bun loads the ignored local `.env`
automatically. Never include raw Ky request objects or credential-bearing
causes in public errors. HTTP mode must require external identity verification;
test the actual listener because FastMCP's `fetch()` does not enforce configured
authentication itself.

Tests replay Cassetter recordings with `recordMode: "none"`. Missing or changed
requests must fail. Never permit live fallback in ordinary tests or CI. Refresh
with the explicit `bun run record:odp` command, inspect fixture diffs, verify
secret filtering, then run `gitleaks protect --staged --redact` before committing.
Real ODP fixtures and synthetic edge-case tests serve different purposes.

Track coverage honestly in `docs/port-status.md`. Current main OpenAPI is an
external-reference index, not a complete schema bundle. Archive current official
sources with URL/date/SHA-256 receipts; do not overwrite the historical Python
snapshot or equate the portal release with a specification's `info.version`.

Prefer Rust/WASM for future measured CPU bottlenecks. Do not add a Rust crate,
backend abstraction, or native binding before profiling justifies it. Preserve
the TypeScript API and reuse behavioral fixtures across implementations.
