# Changelog

All notable changes to `patent-client-agents` are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.11.1] — 2026-05-13

### Fixed

- **`get_patent` MCP tool no longer stalls for ~4.5 min when Google Patents
  returns 503.** Wrapped the tool body in a 60s `asyncio.timeout`, mapping
  budget overruns to `RateLimitError` (`[retryable]`) and Google's
  "couldn't find this patent" page to `NotFoundError` (`[not-retryable]`).
- **`GooglePatentsClient.get_patent_data` stops swallowing exceptions and
  returning `None`.** Typed errors (`httpx.HTTPStatusError`,
  `FileNotFoundError`, transport errors) now propagate so callers and the
  FriendlyErrors middleware can distinguish "rate-limited" from
  "actually not found." Removes the dead `if patent is None` branches in
  `download_patent_pdf` and `google_patents.api.fetch`.

## [0.15.0] — 2026-05-14

### Added

- **EPO Guidelines for Examination connector**
  (``patent_client_agents.epo_guidelines``). The EPO equivalent of
  the USPTO's MPEP — covers Parts A-H + General Part of the
  Guidelines, the canonical EPO examination practice manual.
  - Source: ``www.epo.org/en/legal/guidelines-epc/<year>``. EPO
    publishes annually (March releases); 2024 edition snapshot
    is the current default (``GUIDELINES_VERSION=2024``).
  - Built via ``patent-client-agents-build-guidelines-corpus``
    into a SQLite/FTS5 database (~10-30 MB; size scales with
    the number of leaf sections). BFS crawl from the year's
    ``index.html`` over the ``<part>_<chapter>_<section>_<sub>``
    URL hierarchy.
  - ``GuidelinesClient.search(query, syntax=...)`` — FTS5 with
    adj-phrase / AND / OR syntaxes.
  - ``GuidelinesClient.get_section(section)`` — accepts canonical
    citations (``G-II, 3.1`` / ``G-II 3.1`` / ``G.II.3.1``) and URL
    slugs (``g_ii_3_1``).
  - MCP tools: ``search_epo_guidelines`` + ``get_epo_guidelines_section``
    on the new ``epo_guidelines_mcp`` sub-server (76 default tools,
    +1 from 0.14.0).
- ``patent-client-agents-build-guidelines-corpus`` CLI ships with
  the wheel for local rebuilds.

### Coming next

- **EPC convention** + **Case Law of the Boards of Appeal**
  — both researched in this session, deferred to a v0.16.0 ship to
  keep this release focused.

## [0.14.0] — 2026-05-14

### Added

- **UKIPO Manual of Patent Practice (MoPP) connector**
  (``patent_client_agents.ukipo_mopp``). UK examination practice for
  PA 1977 + SPCs, mirroring the existing MPEP/TMEP corpus pattern.
  Source: gov.uk's ``/guidance/manual-of-patent-practice-mopp``
  (192 pages, OGL v3.0, no auth). Built once via
  ``patent-client-agents-build-mopp-corpus`` into a ~9 MB
  SQLite/FTS5 database, then served offline. Quarterly refresh
  cadence mirrors UKIPO's own MoPP update schedule.
  - ``MoppClient.search(query, syntax=...)`` — FTS5 search with
    AND / OR / adj-phrase syntaxes.
  - ``MoppClient.get_section(section)`` — section lookup by PA 1977
    section number ("1", "14", "4A", "100") or by gov.uk slug
    ("section-14-the-application").
  - ``MoppClient.list_versions()`` — corpus snapshot metadata.
  - MCP tools: ``search_mopp`` + ``get_mopp_section`` on the
    new ``ukipo_mopp_mcp`` sub-server (75 default tools, +1).
- ``patent-client-agents-build-mopp-corpus`` CLI ships with the
  wheel for local rebuilds.

## [0.13.0] — 2026-05-14

### Added

- **EPO OPS Register service + Unitary Patent Package helper.** Wraps
  the EPO Register service's ``/rest-services/register/.../upp``
  sub-endpoint and surfaces the structured ``<reg:unitary-patent>``
  block.
  - New low-level method: ``EpoOpsClient.fetch_register(number, sub=...)``
    returning raw XML for any of the four register sub-endpoints
    (``biblio`` / ``events`` / ``procedural-steps`` / ``upp``).
  - New high-level helper:
    ``EpoOpsClient.get_unitary_patent_package(epo_number)`` returns a
    ``UnitaryPatentPackage`` with the registration status timeline
    (e.g. "Request for unitary effect filed" → "Unitary effect
    registered" with dates) or ``None`` when the EP wasn't elected
    for unitary effect.
  - New module-level convenience functions: ``fetch_register`` and
    ``get_unitary_patent_package`` mirroring the client methods.
  - New MCP tool: ``get_unitary_patent_package`` on
    ``international_mcp`` (74 default tools, +1 from 0.12.1).
- Answers "is patent X a Unitary Patent and when was it registered?"
  for any EP via existing EPO OPS credentials. No UPC enrollment
  needed.

### Known limitation

- **UPC opt-out status is *not* exposed by the EPO Register.** The
  v0.11.0 research notes anticipated opt-out info being available at
  the same endpoint, but empirical testing on 2026-05-14 confirmed
  it isn't — opt-out data lives in subsequent EP publications
  (B8/B9 kind codes, INID 920) which the Register's ``/upp`` doesn't
  expose, and in the UPC CMS Public API which requires separate
  enrollment (still in flight). Tracked in TODO.md.

## [0.12.1] — 2026-05-14

### Fixed

- **`upc_decisions.UpcDecisionsClient.search` returned 0 hits on
  the first page.** The client sent ``?page=0`` for the default
  request, but the UPC site's Drupal View renders its *empty*
  template when ``page=0`` is in the URL — only the no-param case
  fetches the actual first listing page. Omit ``page`` when
  ``page=0``; keep sending it for ``page>=1``. The parser, response
  shape, and pager-discovery logic were already correct; this was a
  one-line URL-parameter bug.
- Repro: pre-0.12.1 `await UpcDecisionsClient().search()` →
  ``hits=0, total_pages=1``. Post-0.12.1 → ``hits=49, total_pages=38``.

### Known limitation

- **The hosted demo at `mcp.patentclient.com` cannot fetch the UPC
  decisions listing.** ``unifiedpatentcourt.org``'s Cloudflare config
  blocks Google Cloud Run egress IPs (verified 2026-05-14 — both
  ``httpx`` and ``curl_cffi`` with Chrome TLS impersonation returned
  HTTP 403 from Cloud Run; same client succeeds from a residential
  IP). Users who need the decisions feed should run the stdio MCP
  locally (``patent-client-agents-mcp``). The UPC *statutes* corpus
  (UPCA, Rules of Procedure, Fees) works on the demo — those PDFs
  are pre-baked into the container image.

## [0.12.0] — 2026-05-14

### Added

- **US Copyright Office connector** (`patent_client_agents.copyright`).
  Read-only search over the Copyright Public Records System
  (`publicrecords.copyright.gov`) — registrations (post‑1978 + digitized
  card catalog) and recorded documents (transfers, assignments,
  licenses). `CopyrightClient` exposes `search`, `search_by_title`,
  `search_by_name`, `get_record`. Public API, no auth. Requires HTTP/2 —
  the new `BaseAsyncClient.HTTP2` class attribute handles it
  automatically. MCP tools: `search_copyright`, `get_copyright_record`.
- **Federal Circuit (CAFC) connector** (`patent_client_agents.cafc`).
  Wraps the court's WordPress DataTables API at `cafc.uscourts.gov`,
  classifies each opinion as patent-related via a keyword `PatentClassifier`
  (strong indicators, statute references, technical terms — with
  false-positive filters for "patient care" / "patent leather"), and
  serves opinion PDFs over `pca://cafc/opinions/{appeal_number}`.
  `CAFCClient` exposes `search`, `search_patent_opinions`, `recent`,
  `download_pdf`. No auth — the client scrapes the WordPress nonce on
  session init. MCP tools: `search_cafc_opinions`,
  `search_cafc_patent_opinions`, `download_cafc_pdf`.
- **USITC connector** (`patent_client_agents.usitc`). Four sub-clients
  in one module: `EdisClient` (Section 337 patent enforcement
  investigations, dockets, and attachments — needs `USITC_EDIS_TOKEN`),
  `DataWebClient` (US import/export trade statistics — needs
  `USITC_DATAWEB_TOKEN`), `HtsClient` (Harmonized Tariff Schedule —
  public), `IdsClient` (Intellectual-property investigation index —
  public). MCP tools: `search_usitc_investigations`,
  `search_usitc_documents`, `list_usitc_attachments`,
  `download_usitc_attachment`, `download_usitc_investigation_documents`,
  `search_hts_tariffs`, `run_dataweb_report`, `list_ids_investigations`.
  EDIS attachments are addressable as
  `pca://usitc/documents/{doc_id}/attachments/{att_id}`.
- **USPTO Trademark Search (TESS) connector**
  (`patent_client_agents.uspto_tmsearch`). Wraps the TESS Elasticsearch
  backend behind AWS WAF at `tmsearch.uspto.gov`. `TmsearchClient`
  exposes `search`, `search_wordmark`, `search_owner`,
  `search_goods_services`, `get_by_serial`, `get_by_registration`,
  `search_all` (auto-paginating). Requires the new `[tmsearch]` optional
  extra (`curl_cffi` + `playwright`) for in-process WAF-token minting,
  OR a bring-your-own token via `PCA_WAF_TOKEN_JSON` / `PCA_WAF_TOKEN_PATH`.
  MCP tools: `search_trademarks`, `get_trademark` (now on PCA's
  `trademarks_mcp` alongside TSDR / TMEP / trademark assignments).
- **`http2` parameter on `BaseAsyncClient`**. Sub-classes can opt in via
  the `HTTP2: bool = True` class attribute (used by `CopyrightClient`)
  or pass `http2=True` per-instance. Wired through
  `build_cached_http_client` to httpx. h2 is already in PCA's
  dependencies for this purpose.
- **Catalog + skill docs** for copyright, cafc, usitc, uspto_tmsearch:
  three surfaces each (`docs/api/<name>.md`,
  `src/patent_client_agents/catalog/sources/<name>.md`,
  `src/patent_client_agents/skills/ip_research/references/<name>.md`).
  `mkdocs.yml` nav and the `ip_research` skill's routing table are
  updated.
- **UPC decisions-and-orders connector**
  (`patent_client_agents.upc_decisions`). Parses the Drupal listing at
  `unifiedpatentcourt.org/.../decisions-and-orders` into typed rows —
  canonical case IDs (`UPC_CFI_<n>/<yyyy>`, `UPC_CoA_<n>/<yyyy>`,
  `ACT_<n>/<yyyy>` — hyphenated variants normalized), court, type of
  action, parties, and direct PDF/A URLs. Per-decision detail pages
  sit behind Cloudflare's interactive challenge, but every needed
  field is already in the listing row and the PDF binaries are
  unchallenged, so the harvester reads only the listing.
  `UpcDecisionsClient` exposes `search`, `get_decision` (by case ID),
  `list_divisions`, `list_languages`, `download_pdf`. Public, no
  auth. MCP tools: `search_upc_decisions`, `get_upc_decision`,
  `list_upc_divisions`, `list_upc_languages`.
- **UPC statutes corpus**
  (`patent_client_agents.upc_statutes`). SQLite/FTS5 corpus over the
  Unified Patent Court Agreement (including Statute Annex I), the
  consolidated Rules of Procedure, and the consolidated Table of
  Court Fees and Recoverable Costs — each mirrored in English,
  French, and German. Mirrors the `mpep` / `tmep` shape: the wheel
  ships the builder
  (`patent-client-agents-build-upc-statutes-corpus`), runtime reads
  from `~/.cache/patent_client_agents/upc_statutes.db` (override via
  `UPC_STATUTES_CORPUS_PATH`). MCP tools: `search_upc_statutes`,
  `get_upc_section`, `list_upc_instruments`. Per-Article / per-Rule
  retrieval is on the v0.13.0 roadmap; v0.12.0 supports full-instrument
  fetch plus FTS5 search (`Article 33`, `opt-out`).

### Changed

- **Public MCP server is now deploy-agnostic.**
  `patent_client_agents.mcp.server` no longer hard-codes the hosted URL
  (`_HOSTED_BASE_URL = "https://mcp.patentclient.com"` removed) or
  passes a Firestore-backed OAuth `client_storage`. The stdio entry
  point uses `make_auth()` with env-only URL resolution. Deployments
  that need persistent OAuth/DCR state build their own server in a
  separate deploy package (see `patent-mcp-deploy`).
- **WAF token env vars renamed.** `PCA_WAF_TOKEN_JSON` /
  `PCA_WAF_TOKEN_PATH` are the canonical names; the legacy
  `LAW_TOOLS_WAF_TOKEN_JSON` / `WAF_TOKEN_PATH` are honored as
  fallbacks for one release. Default cache path moves from
  `~/.law-tools/waf_token.json` to
  `~/.cache/patent_client_agents/waf_token.json`; the legacy path is
  still read as a fallback when neither env nor an explicit path is
  supplied.

### Removed

- `make_firestore_client_storage` removed from
  `law_tools_core.mcp.auth` (and from the `law_tools_core.mcp`
  re-exports). The helper was deploy-only — `patent-mcp-deploy`
  constructs its own `FirestoreStore` directly, and the BB-internal
  `law-tools` server now has the helper inlined locally
  (`law_tools.mcp.firestore_storage`). The public PCA wheel has zero
  GCP dependencies.

### Migrated from `law-tools`

The CAFC, USITC, USPTO Trademark Search, and Copyright connectors
previously lived in the BB-internal `law-tools` package. They are now
part of the public `patent-client-agents` wheel. `law_tools.{cafc,
usitc, uspto_tmsearch, copyright}` remain as re-export shims for one
release so existing internal callers don't break.

## [0.10.0] — 2026-05-13

### Added

- **EUIPO Trademark Search connector** (`patent_client_agents.euipo_trademarks`).
  Async OAuth2 client_credentials wrapper over EUIPO's REST API; covers all
  ~2.3M EU trademarks (EUTMs + international registrations designating the
  EU, since 1996). Methods: `search` (RSQL filter — `applicationDate>=2024-01-01
  and (markFeature==FIGURATIVE and niceClasses=all=(25,26))`), `get_trademark`
  (full record with prosecution history + multilingual goods-and-services),
  plus media bytes for image, image thumbnail, sound, video, and 3D model.
  Environment toggle via `EUIPO_ENV` (`production`/`sandbox`) flips both the
  API host and the OIDC token endpoint; production uses
  `https://api.euipo.europa.eu/trademark-search` +
  `https://euipo.europa.eu/cas-server-webapp/oidc/accessToken`. Every
  request carries both `Authorization: Bearer ...` and `X-IBM-Client-Id`
  headers (the spec's two security schemes are AND-combined, not OR). Page
  size must be 10..100 — the spec's `size=3` examples will return HTTP 400.
- **EUIPO Design Search connector** (`patent_client_agents.euipo_designs`).
  Same OAuth2 app/credentials as trademarks. Covers all ~1.5M Registered
  Community Designs since April 2003. Methods: `search`, `get_design`, plus
  per-view image / thumbnail / 3D model bytes. Design numbers are
  `NNNNNNNNN-NNNN` (e.g. `099037115-0001`); multi-design applications
  produce one entry per indexed design.
- **EUIPO MCP tools** (env-gated on `EUIPO_CLIENT_ID` + `EUIPO_CLIENT_SECRET`):
  `search_euipo_trademarks`, `get_euipo_trademark`, `search_euipo_designs`,
  `get_euipo_design`. Mount on `ip_mcp` alongside the existing surface;
  absent from `tool/list` when credentials aren't set, matching the
  JPO / CanLII pattern. Media downloads (image / sound / video / 3D model)
  are library-only in v1.
- **Catalog + skill docs** for EUIPO: `CATALOG.md` row,
  `src/patent_client_agents/catalog/sources/euipo.md`,
  `src/patent_client_agents/catalog/intents/README.md` Search + Lookup
  entries, `src/patent_client_agents/skills/ip_research/references/euipo.md`,
  `docs/api/euipo.md`, and the mkdocs nav entry.
- **OpenAPI specs** captured from the authenticated EUIPO dev portal to
  `research/openapi/`: trademark-search v1.0.0 (production) and v1.1.0
  (sandbox — operation signatures identical), design-search v1.0.0, plus
  bonus specs for document-repository, persons, goods-and-services, and
  product-indications (deferred for future connectors).
- **Sandbox response fixtures** captured into `tests/fixtures/euipo/`:
  `tm_list_size10.json`, `tm_apple_size10.json`, `design_list_size10.json`.
  27 new unit tests cover model parsing (lean search items + full detail
  records), client construction (environment toggle, env-var precedence,
  custom auth handler, missing-credential errors, page-size validation),
  and the `is_live` / `is_registered` / multilingual `terms_in(...)`
  helpers.

### Changed

- **`tests/conftest.py`** gained EUIPO support: placeholder `EUIPO_CLIENT_ID`
  / `EUIPO_CLIENT_SECRET` env vars (so client construction works in unit
  tests), a `--run-live-euipo` opt-in flag + `EUIPO_LIVE_TESTS` env var, a
  `require_live_euipo` fixture, OAuth token-endpoint scrubbers for the
  cas-server-webapp (prod) and auth-sandbox (sandbox) hosts, the
  `x-ibm-client-id` filter on `filter_headers`, and the EUIPO token paths
  on the `oauth_safe_body` VCR matcher. JPO and EUIPO scrubbers compose
  via two new helpers (`_chain_request_scrubbers`,
  `_chain_response_scrubbers`).

### Open

- **EUIPO production access** requires identity-document review at
  `docs.apiplatform@euipo.europa.eu` (passport copy + proof of address for
  natural persons; company register excerpt for legal persons). Sandbox is
  auto-approved on subscription but carries a frozen historical snapshot
  plus synthetic test rows (newest trademarks are literally labelled *"EUTM
  Generated by QC Automated Script"*) — fine for shape testing and CI, not
  for "is this mark live today" questions. Library code is base-URL-
  agnostic; flipping `EUIPO_ENV=production` is the only change once prod
  is approved.
- **Bulk data** (EUIPO Open Data Platform — separate registration, XML
  dumps) and **3-legged `authorizationCode` OAuth flow** are deferred. The
  smoke test confirmed `clientCredentials` + scope `uid` returns the full
  register (the spec's "partial read access under certain conditions"
  warning on the Designs scope was empirically misleading — 1.5M results),
  so the simpler flow covers the read-only library's needs.

## [0.9.2] — 2026-05-13

### Changed

- **MPEP module switched from live USPTO HTTP to a local SQLite/FTS5
  corpus.** USPTO's eMPEP `/search` endpoint has been intermittently
  broken since 2026-05-13 — confirmed via probes with the library UA,
  full Chrome UA + Referer, persisted session cookies, and HTTP/2 —
  while `/content` remained healthy. New
  `patent_client_agents.mpep.corpus.{schema,db,build}` module ships
  with the wheel as a build artifact, not data: a single CLI
  (`patent-client-agents-build-mpep-corpus --output <PATH>`) BFS-crawls
  `/content` from one seed href, parses chapter HTML into
  per-section rows, and writes a SQLite+FTS5 snapshot
  (~3,000 sections across all 29 chapters, ~50MB, ~4-minute scrape).
  `MpepClient` preserves the public surface exactly — `search`,
  `get_section`, `resolve_section_href`, `list_versions` — but now
  reads from the corpus. Runtime locates the file via
  `MPEP_CORPUS_PATH` env var → `~/.cache/patent_client_agents/mpep.db`
  → `CorpusUnavailable` with the build command in the message. No
  silent fallback to live HTTP.
- **TMEP module switched to the same corpus pattern.** Sister script
  `patent-client-agents-build-tmep-corpus --output <PATH>` produces
  ~1,750 sections across all 19 TMEP chapters in ~16MB / ~2 minutes.
  Runtime resolves via `TMEP_CORPUS_PATH` → `~/.cache/patent_client_agents/tmep.db`
  → `CorpusUnavailable`. Same public surface preserved.
- **JPO retry loop consolidated onto `law_tools_core.resilience.default_retryer`.**
  The bespoke `AsyncRetrying(...)` block in `JpoClient._raw_request`
  now delegates backoff and the retry-filter (RateLimitError,
  TransportError, retryable HTTPStatusError) to the shared helper.
  Rate-limit acquire, token refresh on 401/403, and the
  429→`RateLimitError` mapping stay inline because they encode
  JPO-specific protocol details. Side benefit: the prior filter
  retried on every Exception including plain `ApiError` for 4xx/5xx,
  which never recovered — dropping `tests/jpo/` runtime from 9.01s to
  3.93s.

### Fixed

- **TSDR `get_status` returned all-null fields.** USPTO switched
  `casestatus/sn{serial}/info` to JSON-by-default; the ST96 XML parser
  threw `ParseError`, a bare `except` swallowed it, and every caller
  got a `TrademarkStatus` with only `serialNumber` populated. Replaced
  `_parse_status_xml` in `uspto_tsdr/client.py` with
  `_parse_status_json` mapping the new
  `trademarks[0].{status,parties,gsList,prosecutionHistory}` shape
  onto the existing model. Silent except removed; parse errors
  propagate. `_parse_documents_xml` unchanged (TSDR documents endpoint
  still returns XML).
- **TSDR `test_get_status` was asserting only on `serial_number`** —
  exactly what passed when every other field was None. Strengthened
  to cover `mark_text`, `filing_date`, `status_date`,
  `abandonment_date`, `mark_type`, owners, prosecution events, and
  goods/services counts so the all-null regression can't recur.
  Stale `test_get_last_update` cassette refreshed by copying the JSON
  body from the matching `test_get_status` cassette (same URL).

### Added

- `CorpusUnavailable` re-exported from `patent_client_agents.mpep`
  and `patent_client_agents.tmep` package roots so callers don't need
  to know about the `.corpus` submodule.
- `tmep/docs/usage.md` + `tmep/resources.py` ship a `resource://tmep/usage`
  static doc reachable via `get_usage_resource()`, matching the MPEP
  pattern.
- New `live_tsdr` / `live_mpep` / `live_tmep` pytest markers
  registered in `pyproject.toml`; the matching `live_mpep` / `live_tmep`
  markers also registered in the law-tools repo to silence
  `PytestUnknownMarkWarning` across both suites.

### Documentation

- Threaded the corpus story through every user-facing reference:
  `mpep/docs/usage.md` (full rewrite — agents see this when they pull
  `resource://mpep/usage`), `catalog/sources/{mpep,tmep}.md` (replaced
  the obsolete eMPEP/eTMEP endpoint tables with a "Backend:
  SQLite/FTS5 corpus" section), `docs/api/{mpep,tmep}.md` (new
  "First-time setup" + "Cloud deploys" sections),
  `skills/ip_research/references/{mpep,tmep}.md` (Backend section so
  the agent knows the corpus must exist), `docs/installation.md`
  (replaced the misleading "MPEP/TMEP still work without keys" line
  with a "MPEP / TMEP corpus setup" subsection), and the README rows
  for MPEP/TMEP now flag the one-time build step.

### Tests

- `tests/mpep/` rewritten: new `conftest.py` builds a five-section
  fixture corpus per session via `write_corpus`; `test_client.py`
  exercises 14 cases against it (lookups, search syntax variants,
  pagination, version, missing-corpus error). Removed dead
  `test_transformers.py`, `test_mpep_transformers.py`,
  `test_utils.py`.
- `tests/tmep/` matched: new `conftest.py` fixture corpus,
  `test_client.py` with 13 parallel cases. Removed dead
  `test_transformers.py`.
- Cross-repo fix in `tools/law-tools/tests/test_section_lookup.py`:
  it imported the deleted `patent_client_agents.mpep.transformers` —
  removed the obsolete `TestMpepTocParsing` class (covered now by
  `tests/mpep/test_client.py` in patent-client-agents), redirected
  `TestTmepLiveSectionLookup` from the legacy `law_tools.tmep`
  (broken against USPTO `/search`) to the corpus-backed
  `patent_client_agents.tmep`. Bundled with the FedReserve cassette
  refresh in the law-tools repo (`a986b10`).
- Removed dead `mpep/{transformers,utils}.py` and
  `tmep/{transformers,utils}.py` modules; the new corpus path
  doesn't need the old HTTP-response parsers.

### Wheel / CLI

- New console scripts in `[project.scripts]`:
  `patent-client-agents-build-mpep-corpus` and
  `patent-client-agents-build-tmep-corpus`. The wheel ships the
  builders; corpus data is materialized separately and located via
  env var or `~/.cache`. Refresh story: rerun the builder.

## [0.9.1] — 2026-05-13

### Added

- **Persistent OAuth client storage via Firestore.** New
  `make_firestore_client_storage()` helper in `law_tools_core.mcp.auth`
  reads `LAW_TOOLS_CORE_OAUTH_FIRESTORE_{PROJECT,COLLECTION}` from
  the environment and returns a `py-key-value-aio` `FirestoreStore`;
  wiring it through `make_auth(client_storage=...)` keeps Dynamic
  Client Registration entries alive across Cloud Run redeploys instead
  of dying with the ephemeral container filesystem. Patent-client-agents
  MCP server registers the store when those env vars are set; falls
  back to in-memory storage otherwise.

## [0.9.0] — 2026-05-13

### Added

- **CanLII connector** (`patent_client_agents.canlii`). Async client for the
  CanLII REST API covering Canadian courts, tribunals, statutes, and
  regulations. The IP-relevant slice includes the Federal Court / Federal
  Court of Appeal / Supreme Court of Canada (patent and trademark
  infringement / validity), the Trade-marks Opposition Board, the
  Commissioner of Patents — Patent Appeal Board, plus the Patent Act,
  Trademarks Act, Industrial Design Act, and Copyright Act with
  point-in-time entry-into-force / repeal markers. Nine library methods
  (`list_case_databases`, `browse_cases`, `get_case`, `get_cited_cases`,
  `get_citing_cases`, `get_cited_legislations`, `list_legislation_databases`,
  `browse_legislation`, `get_legislation`) and nine MCP tools. Auth via
  `CANLII_API_KEY` (free key by request through the CanLII feedback form);
  MCP tools env-gate on the key in the same pattern as JPO.
- **WIPO Lex connector** (`patent_client_agents.wipo_lex`). Async client
  for the WIPO Lex public web surface — global IP statute database
  curated by WIPO across ~200 jurisdictions in six UN languages. v0.9
  scope is the **legislation collection** (search + per-entry detail with
  PDF/DOC attachment links); treaties and judgments share the same URL
  shape and are planned follow-ups. Two library methods
  (`search_legislation`, `get_legislation`) and two MCP tools. No auth
  required; client identifies via a descriptive User-Agent and caches
  aggressively. Parser keys on OpenGraph + `<meta name>` tags (stable
  across page redesigns) plus extension-substring file-link detection;
  parser-stability notes ship in `docs/usage.md`.
- **`OAuth2ClientCredentialsAuth`** in `law_tools_core` — generic
  `httpx.Auth` for RFC 6749 §4.4 client_credentials grant. Token cache
  with 30-second safety margin, refresh-on-401 retry, HTTP Basic or
  in-body credentials, optional scope + extra token params. Ships ready
  for the upcoming EUIPO, IP Australia, and PISTE (Légifrance + Judilibre)
  integrations. Eleven unit tests via `httpx.MockTransport`.

### Changed

- README "Coverage" table now lists CanLII and WIPO Lex; MCP tool counts
  bumped to 51 default / 60 with CanLII / 63 with JPO / 72 with both.
- MCP server `instructions` string mentions CanLII and WIPO Lex.
- `CATALOG.md` adds rows for both new sources and per-source pages at
  `src/patent_client_agents/catalog/sources/{canlii,wipo-lex}.md`.

## [0.8.2] — 2026-05-13

### Documentation

- Surfaced the **dual-transport download** feature shipped in v0.8.1
  through README, `docs/mcp-stdio.md`, and the packaged JPO skill
  reference. Every download tool's return now carries both a
  `pca://...` MCP resource URI and an HMAC-signed `download_url`;
  six resource templates are advertised via
  `resources/templates/list`. Resource-aware clients (Claude CoWork)
  fetch through `resources/read`; URL-comfortable clients keep using
  `download_url`. v0.8.1 shipped the code but the release notes
  undersold the surface.
- Corrected README claims that JPO MCP tools "are not available."
  Twelve JPO MCP tools + the `pca://jpo/documents/...` resource
  template register on the local stdio server and Claude Code plugin
  when `JPO_API_USERNAME` and `JPO_API_PASSWORD` are set in the
  server's env. The hosted demo at `mcp.patentclient.com` does not
  carry JPO credentials (deployment choice).

### Fixed

- `__version__` in `src/patent_client_agents/__init__.py` had drifted
  again — it stayed at `0.8.0` while `pyproject.toml` advanced to
  `0.8.1`. Both now read `0.8.2`.

## [0.8.1] — 2026-05-12

### Added

- **Downloads now ride two transports.** Every download tool's return
  pairs a `pca://...` MCP resource URI with the existing HMAC-signed
  `download_url`. Resource-aware clients (Claude CoWork, any client
  that follows MCP `ResourceLink` content blocks) fetch bytes through
  `resources/read` over the same MCP session the tool call rode in on,
  so no outbound HTTP allowlist is required. Clients without that
  affordance keep using `download_url` unchanged. Six resource
  templates are advertised via `resources/templates/list`:
  `pca://patents/{publication_number}`,
  `pca://publications/{publication_number}`,
  `pca://epo/patents/{publication_number}`,
  `pca://uspto/applications/{application_number}/documents/{document_identifier}`,
  `pca://ptab/documents/{document_identifier}`, and
  `pca://jpo/documents/{ip_type}/{application_number}/{doc_kind}` (last one is
  registered only when `JPO_API_USERNAME` + `JPO_API_PASSWORD` are
  set). Bulk tools decompose into one `ResourceLink` per successfully
  fetched item alongside the zip URL — large-archive callers can pull
  per-doc through MCP and avoid JSON-RPC message caps. Invariant:
  cache key === MCP URI path === HTTP `/downloads` path; one fetch
  serves both transports.
- `law_tools_core.mcp.server_factory.build_server()` now accepts optional
  `icons` and `website_url` kwargs, forwarded to FastMCP and surfaced in
  the MCP `initialize` response's `serverInfo.icons` / `serverInfo.websiteUrl`
  (MCP spec 2025-11-25). Hosted UIs like Claude.ai's connector card / CoWork
  use these to render the server card; without them the card falls back to
  a generic placeholder. Defaults stay `None`, so existing stdio / library
  callers are unaffected.

## [0.8.0] — 2026-05-12

### Added

- **Trademark tooling — Phase 1.** Three new modules, ported from
  `law-tools`, bring trademark prosecution data alongside the existing
  patent surface:
  - `patent_client_agents.tmep` — Trademark Manual of Examining
    Procedure (search + section lookup). No auth.
  - `patent_client_agents.uspto_tsdr` — Trademark Status & Document
    Retrieval. Requires `USPTO_TSDR_API_KEY` (request via the USPTO
    API Key Manager at `account.uspto.gov/api-manager/` with a free
    MyUSPTO account).
  - `patent_client_agents.uspto_trademark_assignments` — USPTO
    Assignment Center trademark recordations. No auth.
- **Seven new MCP tools** mounted on `ip_mcp` via the new
  `trademarks_mcp` sub-server: `search_tmep`, `get_tmep_section`,
  `get_trademark_status`, `get_trademark_documents`,
  `batch_trademark_status`, `get_trademark_last_update`, and
  `search_trademark_assignments`.

### Security

- `tests/conftest.py` now also redacts the `uspto-api-key` request
  header (used by TSDR; not a match for the existing `x-api-key`
  filter). The 4 TSDR cassettes shipped with this release were
  recorded under the upstream `law-tools` filter set and have the
  API key already scrubbed; this guards future re-records in this
  repo from leaking the key.
- Scrubbed F5 BIG-IP session-affinity `Set-Cookie` values from
  the 4 TSDR cassettes. These are server-side load-balancer cookies
  (not credentials), but no reason to keep them on disk.

### Fixed

- `__version__` in `src/patent_client_agents/__init__.py` had
  drifted to `0.5.1` while `pyproject.toml` advanced to 0.7.0.
  Both now read `0.8.0`.

### Skipped from the law-tools port

- `uspto_tmsearch` (TESS) — depends on Playwright + a periodic
  AWS WAF token refresh job. Deferred to Phase 2; tracked
  separately.

## [0.7.0] — 2026-05-07

### Added

- **Env-gated MCP tool registration** via
  `law_tools_core.mcp.conditional_tool` and the parallel
  `register_source_if_configured` helper. Tools registered with
  `@conditional_tool(mcp, requires_env=[...])` only appear in
  `tool/list` when every named env var is set and non-empty;
  otherwise the function is still callable from Python but no
  MCP-side registration happens. Decorator-time gate (no per-call
  overhead); restart the process to pick up env changes.
- All 12 JPO MCP tools (`get_jpo_progress`, `get_jpo_progress_simple`,
  `get_jpo_priority_info`, `get_jpo_registration_info`,
  `get_jpo_number_reference`, `get_jpo_jplatpat_url`,
  `get_jpo_applicant_by_code`, `get_jpo_applicant_by_name`,
  `get_jpo_documents`, `get_jpo_patent_divisional_info`,
  `get_jpo_patent_cited_documents`,
  `get_jpo_pct_national_phase_number`) now auto-register only when
  both `JPO_API_USERNAME` and `JPO_API_PASSWORD` are set. The
  `jpo/documents` download fetcher uses
  `register_source_if_configured` for the same env gate (defense
  in depth).
- The hosted public deploy at `mcp.patentclient.com` intentionally
  does NOT carry these keys per JPO TOS; private deploys flip JPO
  on by mounting the secrets in their own Cloud Run env.

### Changed

- This is a behavior change for any deployment that previously
  saw `get_jpo_*` tools advertised without JPO credentials in
  the env. The tools were already non-functional in that case
  (every call failed at OAuth2 password-grant time); now they
  no longer appear in `tool/list`.

## [0.6.6] — 2026-05-05

### Fixed

- **Default cache HTTP client no longer impersonates Chrome.**
  `build_cached_http_client` was injecting a Chrome 127 `User-Agent`
  and `Accept-Language: en-US,en;q=0.9` for every `BaseAsyncClient`
  subclass. Combined with httpx's Python TLS fingerprint, that
  triggered Akamai (and similar) bot-management WAFs to 403 hard on
  USITC EDIS, federalregister.gov, and consumerfinance.gov. The
  default UA is now httpx's native `python-httpx/<ver>` string, which
  those WAFs allow as a known programmatic consumer. Callers that
  need a specific UA (e.g. SEC EDGAR's email-contact mandate) still
  override via `headers=`. Two regression tests guard against the
  Chrome UA sneaking back in.

## [0.6.5] — 2026-05-04

### Added

- `make_auth(client_storage=...)` accepts an `AsyncKeyValue` and
  threads it through to FastMCP's `GoogleProvider`. Hosted MCP
  deployments need this — FastMCP's default `FileTreeStore` is
  per-container and silently breaks Dynamic Client Registration when
  containers cycle or scale horizontally.

### Changed

- `epo_ops.fetch_fulltext` now raises a clean `ValueError` for the
  "no full-text indexed" case instead of bubbling EPO's raw 404 with
  its opaque log-path hint.

## [0.6.4] — 2026-05-04

### Fixed

- `make_auth` static verifier now claims full-URL Google scopes,
  matching what the Google Identity API actually issues.

## [0.6.3] — 2026-05-04

### Fixed

- `make_auth` static verifier now claims Google scopes on the
  `MultiAuth` path (previously only set on the single-provider path).

## [0.6.2] — 2026-05-04

### Added

- `make_auth` accepts env-driven issuer / redirect URLs so hosted
  deployments can configure them without code changes.

## [0.6.1] — 2026-04-30

### Added

- `LAW_TOOLS_CORE_LOG_TO_STDOUT` attaches a `StreamHandler(sys.stdout)`
  to the tool-call logger. Right for Cloud Run / container
  deployments where the filesystem is ephemeral and stdout is
  captured by Cloud Logging. Existing `LAW_TOOLS_CORE_LOG_DIR` file
  sink still works; either, both, or neither can be set.

## [0.6.0] — 2026-04-30

### Changed (breaking)

- **`uspto_assignments`: consolidated search surface onto
  `/search/patent`.** Replaces `search_by_assignee`, `search_by_assignor`,
  `search_by_patent`, `search_by_application`, `search_by_reel_frame`,
  `search`, `search_all`, and `get_application_assignments` with a
  single `search()` method that returns `SearchResults`. Callers must
  migrate to the new method.

### Added

- **`google_patents`: estimated expiration date.** When Google Patents
  returns an empty `expiration_date`, the client now estimates it as
  `priority_date + 20 years` and exposes a new `expiration_estimated:
  bool` field on the result so callers can distinguish authoritative
  vs estimated values.

[0.6.6]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.6
[0.6.5]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.5
[0.6.4]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.4
[0.6.3]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.3
[0.6.2]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.2
[0.6.1]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.1
[0.6.0]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.0
