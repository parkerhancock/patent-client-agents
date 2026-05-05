# Patent & IP Data Connector Catalog

Two-layer documentation for `patent-client-agents`:

- **[src/patent_client_agents/catalog/sources/](src/patent_client_agents/catalog/sources/)** — per-backend Python client reference (one file per upstream service).
- **[src/patent_client_agents/catalog/intents/](src/patent_client_agents/catalog/intents/)** — MCP tool reference, grouped by what you want to do. Cross-source fused tools are documented here.

## Active sources

| Source | Description | Auth | Rate Limit |
|---|---|---|---|
| [Google Patents](src/patent_client_agents/catalog/sources/google-patents.md) | Global patent search, claims, figures, PDFs, families | None | Unpublished (scraped) |
| [USPTO ODP](src/patent_client_agents/catalog/sources/uspto-odp.md) | Applications, file wrapper, PTAB trials/appeals/interferences, petitions, bulk data via Open Data Portal | `USPTO_ODP_API_KEY` | 60 req/min |
| [USPTO Applications](src/patent_client_agents/catalog/sources/uspto-applications.md) | Function-level wrapper over `ApplicationsClient` (search, get, documents, family, PTAB) | `USPTO_ODP_API_KEY` | (inherits ODP) |
| [USPTO Office Actions](src/patent_client_agents/catalog/sources/uspto-office-actions.md) | OA rejection analytics, cited references, full-text OA retrieval, enriched citations | `USPTO_ODP_API_KEY` | 60 req/min |
| [USPTO Publications](src/patent_client_agents/catalog/sources/uspto-publications.md) | Patent Public Search (PPUBS) full-text and document retrieval | None | Unpublished |
| [USPTO Assignments](src/patent_client_agents/catalog/sources/uspto-assignments.md) | Patent ownership transfers via Assignment Center | None | Unpublished |
| [USPTO Petitions](src/patent_client_agents/catalog/sources/uspto-petitions.md) | Wrapper for ODP petition decisions | `USPTO_ODP_API_KEY` | (inherits ODP) |
| [USPTO Bulk Data](src/patent_client_agents/catalog/sources/uspto-bulkdata.md) | Bulk data product catalog + download manifests | `USPTO_ODP_API_KEY` | (inherits ODP) |
| [EPO OPS](src/patent_client_agents/catalog/sources/epo-ops.md) | European patents — biblio, fulltext, families, legal events | `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET` | 4 GB/week free tier |
| [CPC](src/patent_client_agents/catalog/sources/cpc.md) | Cooperative Patent Classification lookup / search / IPC mapping (via EPO OPS) | `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET` | (inherits EPO OPS) |
| [MPEP](src/patent_client_agents/catalog/sources/mpep.md) | Manual of Patent Examining Procedure search and section lookup | None | Unpublished (scraped) |

## MCP tools

The MCP surface (~40 tools) is grouped by intent rather than by backend —
see [intents/README.md](src/patent_client_agents/catalog/intents/README.md)
for the master table. Cross-source fused tools have dedicated pages:

- [`get_patent_claims`](src/patent_client_agents/catalog/intents/claims.md) — ODP → Google cascade, canonical nested-limitation shape.
- [`download_patent_pdf`](src/patent_client_agents/catalog/intents/downloads.md) — Google → PPUBS → EPO cascade.
- [`search_patent_assignments`](src/patent_client_agents/catalog/intents/assignments.md) — parameter fusion (6 → 1).
- [`search_office_actions`](src/patent_client_agents/catalog/intents/office-actions.md) — result-type discriminator (4 → 1).
- [`search_ptab`, `get_ptab`, `list_ptab_children`](src/patent_client_agents/catalog/intents/ptab.md) — tribunal-type discriminators (15 → 4).

## Inactive / deprecated

| Source | Status | Notes |
|---|---|---|
| [JPO](src/patent_client_agents/catalog/sources/jpo.md) | Library only | JPO MCP tools are not available. The Python library still exposes `JpoClient` and the `jpo` submodule for users with their own `JPO_API_USERNAME` + `JPO_API_PASSWORD`. The MCP tool wrappers in `src/patent_client_agents/mcp/tools/international.py` are commented out, so the hosted demo at `mcp.patentclient.com`, the stdio MCP server, and the Claude Code plugin all omit JPO tools. |
| [patentsview](archive/patentsview/) | Deprecated | USPTO retired the PatentsView API (search.patentsview.org no longer resolves); module kept in `archive/` for reference only. |

## By auth type

**No credentials required:** Google Patents, USPTO Publications, USPTO Assignments, MPEP.

**Free API key:** USPTO ODP (and wrappers — Applications, Office Actions, Petitions, Bulk Data) via `USPTO_ODP_API_KEY`; EPO OPS and CPC via `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET`.

**Credentialed / disabled:** JPO via `JPO_API_USERNAME` + `JPO_API_PASSWORD`.
