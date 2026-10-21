# Connector implementation patterns

October 20, 2026. The USPTO API port establishes the network patterns below.
It does not yet demonstrate every connector style in Python. Use this guide
with [connector standards](../../CONNECTOR_STANDARDS.md), [stack decisions](stack.md)
and [verified port status](port-status.md) before copying an implementation.

Authentication, response format, workflow and freshness are separate concerns.
A connector can combine existing patterns. Establish one verified reference
for an unfamiliar style before copying it across offices; avoid a speculative
connector framework or every possible combination first.

## Established TypeScript references

The links identify working implementations and behavioral tests. Real sample
coverage is recorded in the [operation evidence map](uspto-operation-coverage.md).

| Style | Implementation | Proof and reuse boundary |
| --- | --- | --- |
| API-key JSON REST, search, pagination and exports | [Applications](../packages/client/src/applications.ts), [Office Actions](../packages/client/src/office-actions.ts), [transport](../packages/client/src/transport.ts) | [Application](../tests/applications-complete.test.ts) and [transport](../tests/transport.test.ts) tests, real ODP recordings. Reuse HTTP behavior; keep office payloads and normalization source-specific. |
| Public JSON/form API | [Assignments](../packages/client/src/assignments.ts), [trademark assignments](../packages/client/src/trademark-assignments.ts) | [Register tests](../tests/register-gaps.test.ts) and real assignment recordings. Keyless sources use the same transport. |
| XML parsing | [Application XML](../packages/client/src/application-xml.ts), [TSDR](../packages/client/src/tsdr.ts) | [TSDR replays](../tests/tsdr-live-recordings.test.ts) and application tests. Preserve namespaces, identifiers and source-derived document IDs. XML alone does not establish SOAP. |
| Read-only SQLite/FTS corpus with compressed content | [MPEP](../packages/client/src/mpep.ts), [outline lifecycle](../packages/client/src/corpus/outline.ts), [MCP adapter](../packages/mcp/src/mpep.ts) | [Reader tests](../tests/mpep-client.test.ts), [actual MCP tests](../tests/mpep-mcp.test.ts), fresh/legacy artifact verification. [Setup and limits](mpep.md) distinguish maintenance acquisition, pinned bytes, release identity and later guidance. |
| Several outline books behind one reader | [EPO legal corpora](../packages/client/src/epo-legal.ts), [MCP adapter](../packages/mcp/src/epo-legal.ts), [corpus cursors](../packages/mcp/src/corpus-paging.ts) | [Reader tests](../tests/epo-legal-client.test.ts), [actual MCP and scope tests](../tests/epo-legal-mcp.test.ts), [verification](epo-legal.md). One shared reader plus a configuration object per book; citation grammars and position metadata stay book-specific. |
| Session bootstrap, cookies and rotating headers | [Patent Public Search](../packages/client/src/publications.ts) | [Search-portal tests](../tests/publications-trademark-search.test.ts). Coalesce bootstrap and isolate credentials to approved origins. This is source-specific session handling, not upstream OAuth2. |
| Asynchronous document generation/polling | [Patent Public Search PDF workflow](../packages/client/src/publications.ts) | Same search-portal tests and recorded native PDF success. Bound polling, honor cancellation and validate final bytes. |
| Browser-minted temporary session | [Worker](../packages/waf-worker/src/index.ts), [provider](../packages/waf-session/src/provider.ts), [Trademark Search](../packages/client/src/trademark-search.ts) | [Worker](../tests/waf-worker.test.ts), [delivery](../tests/waf-session.test.ts), [MCP wiring](../tests/waf-integration.test.ts) and [dependency boundary](../tests/waf-boundaries.test.ts) tests. [Image verification](waf-worker.md) covers ARM64/AMD64. Browser acquisition stays separate. |
| Binary files, redirects and assembled archives | [Bulk data](../packages/client/src/bulkdata.ts), [PTAB](../packages/client/src/ptab.ts), [artifact storage](../packages/mcp/src/downloads.ts) | [Downloads](../tests/downloads.test.ts), [lifecycle](../tests/downloads-lifecycle.test.ts), [deadlines](../tests/transport-deadlines.test.ts) and [recorded files](../tests/record-feature-replay.test.ts). Bounded buffering is established; giant-dump streaming and shared replica storage are not. |
| Guides/specifications as static resources | [Library resources](../packages/client/src/uspto-resources.ts), [MCP resources](../packages/mcp/src/resources.ts) | [Resource](../tests/resources.test.ts) and [source archive](../tests/sources.test.ts) tests. Preserve source/version labels and hashes. Embedded strings are not a searchable legal corpus. |
| Thin MCP adapter with parallel REST retrieval | [Envelopes](../packages/mcp/src/shared.ts), [server](../packages/mcp/src/index.ts), [register tools](../packages/mcp/src/registers.ts) | [Actual MCP listener](../tests/mcp.test.ts), download and [option-forwarding](../tests/tsdr-mcp-options.test.ts) tests. MCP caller identity remains separate from office credentials. |
| Upstream OAuth2 client-credentials token | [EPO OPS](../packages/client/src/epo-ops.ts), [MCP tools](../packages/mcp/src/epo.ts), [details](epo-ops.md) | [Token lifecycle](../tests/epo-ops-client.test.ts), [real OPS replays](../tests/epo-ops-recordings.test.ts) and [MCP scope](../tests/epo-ops-mcp.test.ts) tests. Local-clock expiry, single-flight refresh, one retry on token rejection, scrubbed token/client-id/IP recordings. IP Australia OAuth should reuse the pattern, not the class. |

## Styles that still need a reference

These are proposed slices, not implemented TypeScript capabilities or selected
dependencies. Python supplies behavior and fixtures, not proof of TypeScript
runtime compatibility.

| Missing style | Python candidate | First-slice proof |
| --- | --- | --- |
| HTML DOM extraction from whole pages | [Google Patents](../../src/patent_client_agents/google_patents/client.py) | Archived page fixtures, deliberate parser selection, selectors/structured metadata and explicit changed-page failures. Claims HTML-to-text is narrower. |
| Live fee schedules | [Fees](../../src/patent_client_agents/fees/client.py) | Effective date distinct from retrieval time, currency, fee codes and entity tiers. Unknown effective dates stay explicit. This is a category contract even when parsing/transport is reused. |
| SOAP service | [Spain OEPM](../../src/patent_client_agents/oepm_spain/client.py) | WSDL-derived envelopes, namespaces, escaping, body-credential scrubbing, faults and not-found behavior. Python coverage is a BYOK beta, not live TypeScript proof. |
| Account login with CSRF/session refresh | [INPI France](../../src/patent_client_agents/inpi_pi/client.py) | Source-specific bootstrap/login, CSRF, expiry/relogin and safe credential isolation. WAF delivery does not establish this flow. |

An outline corpus and a statute corpus share lifecycle concerns but can have
different row/query schemas. Prove each new schema with fixtures when porting
it. A bulk-download catalog likewise does not prove an ingestion/indexing
pipeline. We have not yet done one of every style needed for the wider port.

## Package and request boundaries

`packages/client` owns importable office authentication, HTTP, parsing,
validation, normalization and provenance. Library users must not need FastMCP,
a browser, a Python process or MCP artifact URLs. Add an optional package when
a dependency needs isolation, as the worker does; avoid a package per endpoint.

`packages/mcp` owns tool schemas, authorization, presentation, cursors and
artifact delivery. Reuse existing helpers. New offices get upstream-focused
modules; do not append EPO/JPO tools to the USPTO register/search modules.
Consolidate tools by user intent while preserving library operations.

Copy the closest reference and make targeted changes:

1. Use shared Ky HTTP behavior, with source-specific origins, headers and
   read-only request semantics. Do not stack retry loops. Honor total deadlines,
   caller cancellation, Retry-After and response-size bounds.
2. Keep office credentials server-side. Allow redirects only to exact approved
   HTTPS hosts and remove cross-origin credentials. Treat browser cookies,
   signed upstream redirects and document links as credentials.
3. Validate success envelopes and preserve unknown upstream fields. Normalized
   values win collisions. Malformed data must not become empty searches or
   phantom records; not-found behavior is operation-specific.
4. Keep searches lean, with explicit full/field selection where useful. Accept
   bounded identifier lists, bind cursors to queries and test that every MCP
   option reaches its intended library operation.
5. Return document metadata plus a REST URL or stdio path, rather than bytes in
   model context. Single-use links remain the default; authenticated REST is
   also available. Preserve ownership, expiry, capacity and cleanup rules.

The browser worker is a reference for dependency isolation, private storage and
warm-process delivery. Google workload identity remains mock-tested; production
worker cutover is deferred. Artifact metadata intentionally differs from the
Python `details` envelope; the port is not a drop-in Python wire replacement.

## Provenance must match the source category

Current network library provenance carries source URL/name, retrieval time,
`cache_hit: false` and optional proceeding status. MCP adds private package
version `0.1.0`. There is no runtime HTTP response cache. Cassettes are test
recordings; the WAF cache holds credentials, not office data.

MPEP adds a separate `CorpusProvenance` type without weakening the network
contract: `cache_hit: true`, nullable source retrieval/sync time, current access
time and installed corpus version. MCP preserves those fields. Its status
resource exposes release, build, cutoff and interim-update metadata without a
network call. Follow this example for standards §§3–4; do not describe a local
read as a fresh upstream fetch. Fee effective-date provenance remains to be
implemented. Keep package-version identity consistent as packages evolve.

Retain canonical identity from `catalog/sources/`. The generated Python coverage
manifest does not prove TypeScript support. Track TypeScript method/route and
verification evidence separately until the catalog represents both runtimes.
For a new jurisdiction, follow the research runbook and substitution check
before building duplicate coverage.

## MPEP establishes the first corpus pattern

The [Python MPEP client](../../src/patent_client_agents/mpep/client.py) serves
SQLite/FTS5 snapshots through `search`, `get_section`, `resolve_section_href` and
`list_versions`. Python MCP exposes `search_mpep` and `get_mpep_section`.
The TypeScript client now ports those operations and adds a corpus-status
helper, the same two intent-based MCP tools and a protected status resource.

On October 20, a read-only check of the existing local Python installation
successfully searched the corpus and retrieved section 2106. The installed
snapshot is dated May 21, 2026 and lacks verified release identity. The legacy
`source_version: current` is reported as `unknown` by the client; it does not
prove current USPTO guidance. Other checkouts/deployments may lack the artifact.

The installed legacy schema-2 artifact stores HTML as zstd-compressed blobs
with a compression dictionary. The port uses Bun's native decoder, supports
plain/dictionary-compressed cells and keeps the legacy release unknown. Its
new shared outline lifecycle establishes these practices. The
[compressed corpus pattern](corpus-pattern.md) specifies whole-file Zstandard
distribution, separate file/decoded pins, bounded in-memory loading and unchanged
source freshness metadata:

1. Inventory [Python schemas](../../src/patent_client_agents/mpep/corpus/schema.py)
   and actual artifacts. Explicitly support a schema or reject it helpfully.
   Detect compression from table/row data, not a schema-version assumption.
2. Keep acquisition/building outside requests. Reuse a checksummed artifact
   where compatible; keep Python subprocesses out of the TypeScript runtime.
   Any artifact conversion must preserve provenance and be explicit.
3. Implement read-only search/retrieval, missing/corrupt/unsupported-artifact
   errors, source links, section hashes and installed-version metadata.
   `current` selects an installed snapshot without claiming the latest release.
4. Add corpus-status provenance and thin search/fetch MCP tools. Test library
   and actual MCP behavior with small real-schema fixtures, including compressed
   HTML and incomplete metadata. Ordinary tests must remain offline.

The fresh MPEP build checks the official TOC and pinned release before publishing
a standalone artifact. Runtime reads the exact verified bytes in memory and
rejects WAL headers; [explicit preparation](mpep.md) preserves legacy content
without silently patching headers or upgrading metadata. Corpus fixtures prove
the compressed schema, and a real local check verifies default MCP/artifact use.

EPO OPS now establishes upstream OAuth2; HTML/fees and SOAP follow when
their connectors enter the port. MPEP does not establish every statute
schema or ingestion format, and no new decoder dependency was required.

## Verification and iteration

Use `bun test <affected-file>` during iteration. Real recordings prove observed
upstream shapes; synthetic fixtures prove edge cases. Preserve and label both.
[Cassette helpers](../tests/cassettes.ts) replay method, URI and JSON-body
matches; missing/mismatched requests fail. OAuth/body-auth connectors require
additional source-specific filters.

Record only through explicit live commands. Inspect fixture diffs and scrub
headers, cookies, query credentials, token bodies, signed locations and redirect
bodies. Never record browser session storage. Respect recorded rate limits and
retain successful captures when retrying a subset. Corpus tests query fixed
local artifacts without triggering builds or downloads.

Test library behavior and the actual MCP adapter, including option forwarding,
pagination, malformed/not-found distinctions and artifacts. HTTP auth tests use
FastMCP's authenticated listener; low-level `fetch()` is not equivalent. MCP
cancellation propagation remains pending a supported framework context signal.

Finish code changes with frozen install, `bun run check`, `bun run build`, diff
review and staged secret scanning. Update evidence with the implementation.
Keep implemented, offline-verified, live-verified, image-verified and deployed
states distinct. Preserve the [Rust/WASM boundary](stack.md#rust-and-webassembly)
for future measured CPU work.

## EPO legal corpora reuse the outline pattern

The five epo.org/en/legal books share MPEP's outline schema, so they reuse
`OutlineCorpus` (now with a per-book unavailable-artifact label), the shared FTS
quoting and timestamp helpers, and MCP cursor binding. Each book declares only
its citation grammar, slug-derived position, path label and URL suffix. Their
edition labels are recorded crawl-path years, reported as unverified rather
than unknown. See [EPO legal corpora](epo-legal.md) for limits and evidence.
