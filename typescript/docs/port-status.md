# USPTO port status

Initial slice, October 20, 2026. The current portal release is ODP 5.0. The
portal release number is distinct from the individual OpenAPI version numbers.

| Capability | TypeScript library | MCP | Verification |
| --- | --- | --- | --- |
| Application POST search, projections, filters, sort and pagination | Implemented | `search_applications` | Live sample search and offline replay; filter edge cases synthetic |
| Application retrieval and metadata flattening | Implemented | `get_application` | Live sample retrieval, offline replay and MCP/library integration |
| Prosecution document listing and code filter | Implemented | `list_file_history` | Live listing of 184 documents, offline replay; code filter synthetic |
| Associated publication/grant document metadata | Implemented | Not a separate tool | Live response and offline replay |
| Assignments, adjustment, attorneys, continuity, transactions and status codes | Pending | Pending | Current main specification lists routes |
| Document/PDF/XML and search downloads | Pending | Pending | Existing Python implementations and upstream specifications are references |
| New ODP 5.0 Office Action Search | Pending | Pending | Fresh, complete official specification archived; six operations inventoried |
| ODP 5.0 Petition Decisions | Pending | Pending | Release notes and separate Swagger definition observed |
| PTAB trials, appeals, interferences and bulk data | Pending | Pending | Current main file delegates to external specifications |
| Legacy Office Action APIs and TSDR | Pending | Pending | Separate current Swagger definitions observed |
| PPUBS, Assignment Center and Trademark Search | Pending | Pending | Separate USPTO sources; transport/auth requirements differ from ODP |

Application 14412875 (the official Swagger example) was recorded from ODP and
replayed offline on October 20. Search and retrieval returned one application,
and document listing returned 184 documents. The default suite requires those
fixtures and also sends them through the actual client and MCP tools.

Next: retrieve the shared ODP schema bundle, finish high-value application facets/downloads,
then port the new Office Action Search and Petition Decisions contracts. PTAB,
bulk data, trademark and legacy analytical APIs follow as separate clients.
Do not treat an unimplemented route, a downloaded schema, or an old Python
cassette as successful live coverage of the TypeScript client.

The MCP boundary is exercised under Bun through in-process protocol calls and
the real HTTP listener with a local JWKS server. Tests cover missing tokens,
wrong issuer/audience, expired or missing expiration, and insufficient scope.
External identity-provider login/discovery and hosted HTTPS deployment remain
unconfigured and unverified. MCP cancellation propagation awaits a supported
framework context API; library cancellation works independently.
