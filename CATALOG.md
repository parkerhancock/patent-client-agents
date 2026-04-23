# Patent & IP Data Connector Catalog

Canonical index of the patent and IP data sources shipped by `patent-client-agents`.

## Active connectors

| Source | Description | Auth | MCP Tools | Downloads | Rate Limit |
|---|---|---|---:|:---:|---|
| [Google Patents](src/patent_client_agents/catalog/google-patents.md) | Global patent search, claims, figures, PDFs, families | None | 8 | ✓ | Unpublished (scraped) |
| [USPTO ODP](src/patent_client_agents/catalog/uspto-odp.md) | Applications, file wrapper, PTAB trials/appeals/interferences, petitions, bulk data via Open Data Portal | `USPTO_ODP_API_KEY` | 26 | ✓ | 60 req/min |
| [USPTO Applications](src/patent_client_agents/catalog/uspto-applications.md) | Function-level wrapper over `ApplicationsClient` (search, get, documents, family, PTAB) | `USPTO_ODP_API_KEY` | — | — | (inherits ODP) |
| [USPTO Office Actions](src/patent_client_agents/catalog/uspto-office-actions.md) | OA rejection analytics, cited references, full-text OA retrieval, enriched citations | `USPTO_ODP_API_KEY` | 4 | — | 60 req/min |
| [USPTO Publications](src/patent_client_agents/catalog/uspto-publications.md) | Patent Public Search (PPUBS) full-text and document retrieval | None | 4 | ✓ | Unpublished |
| [USPTO Assignments](src/patent_client_agents/catalog/uspto-assignments.md) | Patent ownership transfers via Assignment Center | None | 7 | — | Unpublished |
| [USPTO Petitions](src/patent_client_agents/catalog/uspto-petitions.md) | Wrapper for ODP petition decisions | `USPTO_ODP_API_KEY` | — | — | (inherits ODP) |
| [USPTO Bulk Data](src/patent_client_agents/catalog/uspto-bulkdata.md) | Bulk data product catalog + download manifests | `USPTO_ODP_API_KEY` | — | — | (inherits ODP) |
| [EPO OPS](src/patent_client_agents/catalog/epo-ops.md) | European patents — biblio, fulltext, families, legal events | `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET` | 12 | ✓ | 4 GB/week free tier |
| [CPC](src/patent_client_agents/catalog/cpc.md) | Cooperative Patent Classification lookup / search / IPC mapping (via EPO OPS) | `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET` | 3 | — | (inherits EPO OPS) |
| [MPEP](src/patent_client_agents/catalog/mpep.md) | Manual of Patent Examining Procedure search and section lookup | None | 2 | — | Unpublished (scraped) |

**Wrapper modules** — `uspto_applications`, `uspto_petitions`, and
`uspto_bulkdata` expose module-level functions that route through the same
underlying `UsptoOdpClient`. Their MCP tools are counted under
[uspto-odp](src/patent_client_agents/catalog/uspto-odp.md).

## Inactive / deprecated

| Source | Status | Notes |
|---|---|---|
| [JPO](src/patent_client_agents/catalog/jpo.md) | Disabled | Module present; requires `JPO_API_USERNAME` + `JPO_API_PASSWORD` which are not broadly available. All clients skip at runtime if credentials are absent. |
| [patentsview](archive/patentsview/) | Deprecated | USPTO retired the PatentsView API (search.patentsview.org no longer resolves); module kept in `archive/` for reference only. |

## By auth type

**No credentials required:** Google Patents, USPTO Publications, USPTO Assignments, MPEP.

**Free API key:** USPTO ODP (and wrappers — Applications, Office Actions, Petitions, Bulk Data) via `USPTO_ODP_API_KEY`; EPO OPS and CPC via `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET`.

**Credentialed / disabled:** JPO via `JPO_API_USERNAME` + `JPO_API_PASSWORD`.
