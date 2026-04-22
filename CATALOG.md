# Patent & IP Data Connector Catalog

Canonical index of the patent and IP data sources shipped by `ip-tools`.

## Active connectors

| Source | Description | Auth | MCP Tools | Downloads | Rate Limit |
|---|---|---|---:|:---:|---|
| [Google Patents](src/ip_tools/catalog/google-patents.md) | Global patent search, claims, figures, PDFs, families | None | 8 | ✓ | Unpublished (scraped) |
| [USPTO ODP](src/ip_tools/catalog/uspto-odp.md) | Applications, file wrapper, PTAB trials/appeals/interferences, petitions, bulk data via Open Data Portal | `USPTO_ODP_API_KEY` | 26 | ✓ | 60 req/min |
| [USPTO Applications](src/ip_tools/catalog/uspto-applications.md) | Function-level wrapper over `ApplicationsClient` (search, get, documents, family, PTAB) | `USPTO_ODP_API_KEY` | — | — | (inherits ODP) |
| [USPTO Office Actions](src/ip_tools/catalog/uspto-office-actions.md) | OA rejection analytics, cited references, full-text OA retrieval, enriched citations | `USPTO_ODP_API_KEY` | 4 | — | 60 req/min |
| [USPTO Publications](src/ip_tools/catalog/uspto-publications.md) | Patent Public Search (PPUBS) full-text and document retrieval | None | 4 | ✓ | Unpublished |
| [USPTO Assignments](src/ip_tools/catalog/uspto-assignments.md) | Patent ownership transfers via Assignment Center | None | 7 | — | Unpublished |
| [USPTO Petitions](src/ip_tools/catalog/uspto-petitions.md) | Wrapper for ODP petition decisions | `USPTO_ODP_API_KEY` | — | — | (inherits ODP) |
| [USPTO Bulk Data](src/ip_tools/catalog/uspto-bulkdata.md) | Bulk data product catalog + download manifests | `USPTO_ODP_API_KEY` | — | — | (inherits ODP) |
| [EPO OPS](src/ip_tools/catalog/epo-ops.md) | European patents — biblio, fulltext, families, legal events | `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET` | 12 | ✓ | 4 GB/week free tier |
| [CPC](src/ip_tools/catalog/cpc.md) | Cooperative Patent Classification lookup / search / IPC mapping (via EPO OPS) | `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET` | 3 | — | (inherits EPO OPS) |
| [MPEP](src/ip_tools/catalog/mpep.md) | Manual of Patent Examining Procedure search and section lookup | None | 2 | — | Unpublished (scraped) |

**Wrapper modules** — `uspto_applications`, `uspto_petitions`, and
`uspto_bulkdata` expose module-level functions that route through the same
underlying `UsptoOdpClient`. Their MCP tools are counted under
[uspto-odp](src/ip_tools/catalog/uspto-odp.md).

## Inactive / deprecated

| Source | Status | Notes |
|---|---|---|
| [JPO](src/ip_tools/catalog/jpo.md) | Disabled | Module present; requires `JPO_API_USERNAME` + `JPO_API_PASSWORD` which are not broadly available. All clients skip at runtime if credentials are absent. |
| [patentsview](archive/patentsview/) | Deprecated | USPTO retired the PatentsView API (search.patentsview.org no longer resolves); module kept in `archive/` for reference only. |

## By auth type

**No credentials required:** Google Patents, USPTO Publications, USPTO Assignments, MPEP.

**Free API key:** USPTO ODP (and wrappers — Applications, Office Actions, Petitions, Bulk Data) via `USPTO_ODP_API_KEY`; EPO OPS and CPC via `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET`.

**Credentialed / disabled:** JPO via `JPO_API_USERNAME` + `JPO_API_PASSWORD`.
