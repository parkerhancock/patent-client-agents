# Patent & IP Data Connector Catalog

Two-layer documentation for `patent-client-agents`:

- **[src/patent_client_agents/catalog/sources/](src/patent_client_agents/catalog/sources/)** — per-backend Python client reference (one file per upstream service).
- **[src/patent_client_agents/catalog/intents/](src/patent_client_agents/catalog/intents/)** — MCP tool reference, grouped by what you want to do. Cross-source fused tools are documented here.

The separate **[worldwide source catalog](catalog/README.md)** inventories
litigation sources whether or not they have a connector. Its current JP/CN/KR
pilot includes manual, restricted, blocked, and commercial sources as well as
the connected sources listed below.

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
| [CanLII](src/patent_client_agents/catalog/sources/canlii.md) | Canadian case law + statutes + citator (FC / FCA / SCC + TMOB + PAB + Patent Act + Trademarks Act with point-in-time queries) | `CANLII_API_KEY` | Not published; keys revocable on high-volume use |
| [WIPO Lex](src/patent_client_agents/catalog/sources/wipo-lex.md) | Global IP statute + treaty + judgment database curated by WIPO (~50k docs across ~200 jurisdictions). Sprint-1 scope: legislation collection (search + detail) | None | Not published; polite-scrape posture, aggressive caching |
| [EUIPO](src/patent_client_agents/catalog/sources/euipo.md) | EU Trade Marks (~2.3M, since 1996) + Registered Community Designs (~1.5M, since 2003). RSQL search, full prosecution records, multilingual goods-and-services / product indications. Sandbox vs production toggle. | `EUIPO_CLIENT_ID` + `EUIPO_CLIENT_SECRET` (OAuth2 client_credentials) | 25,000 calls/day per app (Default Plan) |
| [USPTO Trademark Search (TESS)](src/patent_client_agents/catalog/sources/uspto-tmsearch.md) | Live USPTO trademark register — search by wordmark, owner, goods/services, serial / registration number. TESS Elasticsearch backend behind AWS WAF | AWS WAF token (~4 day lifetime); install `[tmsearch]` extra (Playwright + curl_cffi) or BYO via `PCA_WAF_TOKEN_JSON` / `PCA_WAF_TOKEN_PATH` | Not published; 403/202 triggers automatic token refresh |
| [Federal Circuit (CAFC)](src/patent_client_agents/catalog/sources/cafc.md) | Federal Circuit opinions with date / origin (PTO, DCT, ITC, CFC) filters, patent-case classifier, opinion PDF download | None (WordPress nonce auto-extracted on session init) | Not published |
| [USITC](src/patent_client_agents/catalog/sources/usitc.md) | EDIS Section 337 patent enforcement investigations + dockets + attachments; DataWeb trade stats; HTS tariff codes; IDS IP investigation index | `USITC_EDIS_TOKEN` for EDIS (JWT, ~2 wk); `USITC_DATAWEB_TOKEN` for DataWeb; HTS and IDS public | Not published |
| [US Copyright Office](src/patent_client_agents/catalog/sources/copyright.md) | Copyright Public Records System — registrations (post‑1978 + digitized card catalog) and recorded documents (transfers, assignments, licenses) | None | Not published; HTTP/2 required |

## MCP tools

The MCP surface is grouped by intent rather than by backend. Most tools
register by default; additional families are env-gated and appear only
when their credentials are present (JPO: 12 tools, CanLII: 9 tools,
EUIPO: 4 tools). See
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

**Free key on request:** CanLII via `CANLII_API_KEY` (issued through the CanLII feedback form). MCP tools are env-gated and absent on deploys without the key. ToS warns against high-volume scraping; cache-and-serve through the CoWork allowlist is an open question to escalate before any public exposure.
