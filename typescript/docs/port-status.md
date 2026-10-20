# USPTO API port status

October 20, 2026. The independent Bun/TypeScript library covers all 70 inventoried
public Python domain methods across 12 USPTO network clients, plus current
ODP 5.0 additions and every route in the archived TSDR definition. This is
implementation coverage; verification below distinguishes live responses from
synthetic contracts. The Python package remains separate.

| Capability | Library and MCP | Verification |
| --- | --- | --- |
| Applications: search/get, metadata, adjustment, assignments, attorneys, continuity, foreign priority, transactions, status codes | Implemented; normalized and raw views | Real ODP cassettes for all listed datasets; synthetic pagination, filters and malformed responses |
| Document listing and associated metadata | Implemented; lean paginated file history | Live official sample has 184 documents |
| PDF/XML/DOCX, claims, family graph, identifier resolution and search exports | Implemented; REST artifacts for downloads | Real PDF/XML/DOCX and 32 granted claims; family traversal, export and edge cases synthetic |
| PTAB trials, decisions, documents, appeals and interferences | Implemented; consolidated tools, JSON/CSV/PDF retrieval | Five live search recordings; detailed retrieval/download contracts synthetic |
| Petition Decisions, including current outcome/status/text fields | Implemented | Live search recording; detail/download contracts synthetic |
| Bulk product catalog, details and file downloads | Implemented | Live catalog and 1,635-byte ZIP via approved data.uspto.gov redirect; larger files subject to explicit size limits |
| New Office Actions search, retrieval, exports and text download | All six official operations implemented | Live search recording; remaining operations synthetic |
| Four legacy Office Action analytics datasets | All eight current records/field operations implemented | Archived current specifications and synthetic request/response contracts |
| Patent and trademark assignments | Implemented | Three current Assignment Center v3 recordings, including 99 NIKE trademark matches |
| Patent Public Search | Search, document, publication resolution, PDF/base64 implemented | Native Bun live search/document/PDF success: 18 pages, 1,214,076 bytes; archived document verifies all 26 parsed claims |
| Trademark Search | Implemented with supplied WAF session and refresh callback | Synthetic contracts; no fresh authenticated live verification |
| TSDR | Python normalization plus all 25 archived official routes; separate API key | Complete route-contract tests and historical responses; no fresh authenticated live verification |
| Search guides, field/status catalogs, schemas and Swagger resources | Eleven labeled MCP resources and pure library helpers | Resource enumeration, content and authorization tests; historical source labels preserved |
| REST document retrieval | OAuth default; optional signed-link compatibility; stdio files | Actual listener verifies expiry, issuer, audience, scope, ownership; signature, capacity, MIME and cleanup tests |

The [feature inventory](uspto-feature-inventory.md) maps every Python method to
its TypeScript counterpart. It excludes legal manuals, fees and CPC connectors
under other namespaces, and excludes aliases/facade wrappers from the domain
count. Library naming and normalization follow TypeScript conventions; this is
not a drop-in replacement for Python imports. MCP uses consolidated intent-based
tools rather than one tool per REST route.

## Remaining verification and deployment limits

All eight portal Swagger entry definitions are archived with hashes. Seven
companion files referenced by the main ODP index remain unavailable, so the
schema-bundle completeness flag stays false. Live data and contract tests
support the implemented routes; the incomplete bundle is not treated as proof
of complete upstream schema coverage. See [source review](odp-research.md).

TSDR needs USPTO_TSDR_API_KEY. Trademark Search needs an externally supplied
current WAF token with its matching User-Agent, or a trusted refresh callback.
The port does not automate browser challenge acquisition or claim that native
Fetch duplicates Python curl_cffi's TLS behavior. PPUBS native Bun behavior was
verified for the recorded sample, not guaranteed for every future WAF policy.

Fresh live calls for every detail, export, legacy analytics and TSDR operation
remain unverified. Default tests never silently fall back to live traffic.
Missing required cassettes fail. Recorders are deliberate and bounded; signed
redirect credentials must be scrubbed from locations and response bodies as
well as request URIs. Preserve successful recordings when refreshing a subset,
and respect upstream 429 responses.

Remote identity-provider login/discovery and hosted HTTPS are not deployed.
Authenticated REST needs a trusted host downloader that attaches OAuth tokens
outside model context. Plain URL fetchers require explicit signed-link mode.
MCP scope is odp:read for ODP, uspto:read for other USPTO families, and
REST documents:read for artifacts. REST ownership uses the originating issuer
and subject. A separately configured REST audience must preserve that identity.

The per-process artifact cache is bounded, expires idle artifacts and removes
owned files on graceful shutdown. Abrupt crashes may leave temporary files.
Multiple replicas need shared storage or request affinity. Responses default to
a 64 MiB buffering limit; this implementation does not stream multi-gigabyte
bulk dumps. Native streaming can be added when that workflow is needed.
Library cancellation works; MCP cancellation propagation awaits a supported
FastMCP context signal. Rust/WASM extraction remains a profiling-driven path.
