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
| [USPTO TSDR](src/patent_client_agents/catalog/sources/uspto-tsdr.md) | Trademark Status & Document Retrieval — status, prosecution documents, mark images, batch lookups | `USPTO_TSDR_API_KEY` | 60 req/min peak (4 for PDF/ZIP); 2× off-peak |
| [USPTO Trademark Assignments](src/patent_client_agents/catalog/sources/uspto-trademark-assignments.md) | Trademark ownership transfers via Assignment Center | None | Unpublished |
| [EPO OPS](src/patent_client_agents/catalog/sources/epo-ops.md) | European patents — biblio, fulltext, families, legal events | `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET` | 4 GB/week free tier |
| [CPC](src/patent_client_agents/catalog/sources/cpc.md) | Cooperative Patent Classification lookup / search / IPC mapping (via EPO OPS) | `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET` | (inherits EPO OPS) |
| [JPO](src/patent_client_agents/catalog/sources/jpo.md) | Japan Patent Office — patent / design / trademark progress, registration, priorities, applicant lookup, document bundles, J-PlatPat permalinks. 12 MCP tools dispatched by `ip_type`; document parser handles XML (patents) and HTM (design/trademark). MCP tools auto-register only when `JPO_API_USERNAME` AND `JPO_API_PASSWORD` are both set; intentionally absent on the hosted public server `mcp.patentclient.com` per JPO TOS. | `JPO_API_USERNAME` + `JPO_API_PASSWORD` (OAuth2 password grant) | 10 req/min + per-endpoint daily caps |
| [MPEP](src/patent_client_agents/catalog/sources/mpep.md) | Manual of Patent Examining Procedure search and section lookup | None | Unpublished (scraped) |
| [TMEP](src/patent_client_agents/catalog/sources/tmep.md) | Trademark Manual of Examining Procedure search and section lookup | None | Unpublished (scraped) |

## MCP tools

The MCP surface — 49 tools by default, 61 when JPO credentials are in the
environment — is grouped by intent rather than by backend. See
[intents/README.md](src/patent_client_agents/catalog/intents/README.md)
for the master table. Cross-source fused tools have dedicated pages:

- [`get_patent_claims`](src/patent_client_agents/catalog/intents/claims.md) — ODP → Google cascade, canonical nested-limitation shape.
- [`download_patent_pdf`](src/patent_client_agents/catalog/intents/downloads.md) — Google → PPUBS → EPO cascade.
- [`search_patent_assignments`](src/patent_client_agents/catalog/intents/assignments.md) — parameter fusion (6 → 1).
- [`search_office_actions`](src/patent_client_agents/catalog/intents/office-actions.md) — result-type discriminator (4 → 1).
- [`search_ptab`, `get_ptab`, `list_ptab_children`](src/patent_client_agents/catalog/intents/ptab.md) — tribunal-type discriminators (15 → 4).

## Inactive / deprecated

| Source | Status | Notes |
|---|---|---|
| [patentsview](archive/patentsview/) | Deprecated | USPTO retired the PatentsView API (search.patentsview.org no longer resolves); module kept in `archive/` for reference only. |

## By auth type

**No credentials required:** Google Patents, USPTO Publications, USPTO Assignments, USPTO Trademark Assignments, MPEP, TMEP.

**Free API key:** USPTO ODP (and wrappers — Applications, Office Actions, Petitions, Bulk Data) via `USPTO_ODP_API_KEY`; USPTO TSDR via `USPTO_TSDR_API_KEY`; EPO OPS and CPC via `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET`.

**Credentialed (registration required):** JPO via `JPO_API_USERNAME` + `JPO_API_PASSWORD` (OAuth2 password grant; corporate registration recommended for higher daily quotas). JPO MCP tools are env-gated — they only register when both vars are set, so the public `mcp.patentclient.com` deploy doesn't advertise them at all. Private deploys flip the surface on by mounting both secrets in their own Cloud Run env.
