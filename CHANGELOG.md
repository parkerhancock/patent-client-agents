# Changelog

All notable changes to `patent-client-agents` are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Added `check_citation_hits` for stateless monitoring of new examiner
  citations to watched patents, including an application-level §102 screening
  flag.
- **CanLII connector — Canadian IP layer expansion.** Extends the
  existing `patent_client_agents.canlii` package with two new
  IP-focused MCP tools and documents the full Canadian IP surface:
  - `search_canlii_ip_cases` (in `mcp/tools/canlii.py`) — searches the
    five canonical Canadian IP databases in one call: Trade-marks
    Opposition Board (`tmob-comc`), Patent Appeal Board (`cab-cab`),
    Federal Court (`fct`), Federal Court of Appeal (`fca`), Supreme
    Court of Canada (`csc-scc`). TMOB / PAB rows pass through (pure-IP
    tribunals); FC / FCA / SCC rows are post-filtered by IP-rights
    keywords ("patent", "trade-mark", "trademark", "copyright",
    "industrial design", EN + FR) matched against case titles. Each
    surviving hit carries a `rights` tag listing matched rights.
  - `list_canlii_ip_statutes` — returns the four canonical Canadian IP
    Acts as a ready-to-use catalog: Patent Act (R.S.C. 1985, c. P-4),
    Trademarks Act (c. T-13), Industrial Design Act (c. I-9), and
    Copyright Act (c. C-42), all under the federal-statutes database
    (`cas`). Two new entries vs. the prior coverage: Industrial Design
    Act and Copyright Act.
  - Module-level constants `CANLII_IP_TRIBUNALS`,
    `CANLII_IP_REVIEWING_COURTS`, `CANLII_IP_DATABASES`,
    `CANLII_IP_STATUTES` for downstream reuse.
  - `canlii/docs/usage.md` extended with the IP-databases / IP-statutes
    tables.
  - Envelope tests refactored to the plain `_FakeModel` pattern from
    the IP Australia reference so `ty` no longer trips on Pydantic
    `populate_by_name` aliases.
- **IPOS Singapore connector — first cut.** Adds Singapore coverage to
  the substantive-law catalog via two new `mcp_local` corpus packages.
  Public, no credentials required; corpora ship as a SQLite/FTS5
  snapshot built once and replayed at agent runtime:
  - `patent_client_agents.ipos_statutes` — `IposStatutesClient` over
    the four IPOS-administered Acts (Patents Act 1994, Trade Marks Act
    1998, Registered Designs Act 2000, Copyright Act 2021). Sourced
    from Singapore Statutes Online (`sso.agc.gov.sg`); built by the
    `patent-client-agents-build-ipos-statutes-corpus` console script
    (env override `IPOS_STATUTES_CORPUS_PATH`).
  - `patent_client_agents.ipos_manuals` — `IposManualsClient` over the
    three IPOS examination / work manuals (Patent Examination
    Guidelines, Trade Marks Work Manual, Industrial Designs Work
    Manual). Sourced from `ipos.gov.sg`; built by the
    `patent-client-agents-build-ipos-manuals-corpus` console script
    (env override `IPOS_MANUALS_CORPUS_PATH`).
  Citation parsers accept `"Section 13 Patents Act"`, `"s 27(1) Trade
  Marks Act"`, `"IPOS PEG 1.5.3"`, `"IPOS TM Work Manual 3.4"`, plus
  short forms (`PA1994`, `TMA1998`, `PEG 1.5.3`, etc).
- **MCP tools (6 new, all envelope-shaped per CONNECTOR_STANDARDS.md
  §5.9, all unconditional read-only):**
  - `search_ipos_statutes`, `get_ipos_section`, `list_ipos_statutes` —
    `mcp/tools/ipos.py` (the statutes surface).
  - `search_ipos_manuals`, `get_ipos_manual_section`,
    `list_ipos_manuals` — `mcp/tools/ipos.py` (the manuals surface).
- **Manifest entries** in `coverage/sources.yaml`: `SG/IPOS/Statutes`
  and `SG/IPOS/Manuals` (both `category: substantive_law`,
  `transport: mcp_local`, `last_verified: 2026-05-16`).
- **INPI Brazil connector — first cut.** Adds Brazilian coverage to
  both the registered-IP catalog (RPI weekly bulk) and the substantive-
  law shelf (LPI). Two packages ship in this PR:
  - `patent_client_agents.inpi_br_bulk` — `InpiBrBulkClient` for the
    *Revista da Propriedade Industrial* (RPI) weekly feed on
    `dados.gov.br` (no auth; Decreto 8.777/2016 open license). Catalog
    + download surface (Shape E); per-section RPI XML ingestion is
    deferred to a follow-up.
  - `patent_client_agents.inpi_br_statutes` — `InpiBrStatutesClient`
    for the LPI (Lei 9.279/1996), Brazil's unified IP statute. Each
    Article carries both authoritative Portuguese (Planalto) and
    English (WIPO Lex translation) text, indexed in SQLite/FTS5 so
    queries in either language hit the same rows. Citation forms
    handled: `Art. 6`, `Article 6`, `Artigo 6`, `Art. 195 LPI`,
    `Art. 195(XI) LPI`, slug `art195`, and full Planalto URLs.
- **MCP tools (4 new, all envelope-shaped per
  CONNECTOR_STANDARDS.md §5.9):**
  - `list_inpi_br_bulk_releases`, `download_inpi_br_bulk` —
    `mcp/tools/inpi_br_bulk.py` (Shape E — catalog + download URL).
  - `search_inpi_br_statutes`, `get_inpi_br_section` —
    `mcp/tools/inpi_br_statutes.py` (substantive-law category;
    Provenance carries `corpus_synced_at` + `corpus_version`).
- **Corpus builder.**
  `patent-client-agents-build-inpi-br-statutes-corpus` pulls the LPI
  PT consolidation from Planalto (and the optional WIPO Lex EN
  translation) and lands a SQLite/FTS5 snapshot at
  `~/.cache/patent_client_agents/inpi_br_statutes.db`. Locator env var
  is `INPI_BR_STATUTES_CORPUS_PATH`.
- **Manifest entries** in `coverage/sources.yaml`:
  - `BR/INPI/RPI` (`registered_ip`, `mcp_proxy`, `bulk_download`,
    `last_verified: 2026-05-16`).
  - `BR/LPI/Statute` (`substantive_law`, `mcp_local`,
    `mcp_passthrough`, `update_strategy: scheduled_recrawl`,
    `update_cadence: irregular`).

### Notes (INPI Brazil)

- The RPI surface ships intentionally minimal — `list_inpi_br_bulk_releases`
  + `download_inpi_br_bulk` only — per CONNECTOR_STANDARDS.md §7.2
  Shape E. Full per-section RPI XML ingestion (eight sections, INID
  + INPI-dispatch-code decoders, schema-versioned record models) is
  deferred to a follow-up so this PR ships independently.
- The `dados.gov.br` portal migrated to a SPA in 2024 and gates the new
  public-search API behind `Authorization`. The legacy CKAN
  `package_show` action remains the most stable read-path; if the
  portal retires that route, `InpiBrBulkClient.get_dataset` is the
  single swap point.
- Pre-2017 RPI is PDF-only (no XML); the catalog lists every issue
  from 2017-01-31 forward.
- The LPI sub-paragraph addressing (e.g. `Art. 195(XI)` resolving to
  the specific paragraph row) is rolled up to the parent Article in
  v1; sub-section addressing is a v2 follow-up.

### Fixed

- Filled omitted USPTO ODP application range-filter bounds so one-sided date
  filters no longer produce invalid requests.
- Corrected PTAB trial, appeal, and interference sort payloads and normalized
  trial download responses so downloaded proceedings, decisions, and documents
  are returned instead of empty result bags.

### Changed

- Refreshed bundled fee snapshots through 2026-07-21.
- Pinned GitHub Actions and uv versions, added Dependabot and Gitleaks
  automation, aligned the pre-commit Ruff version, and required release tags to
  point to commits contained in `main`.

## [0.24.0] — 2026-07-28

### Changed

- **USITC EDIS MCP tools are now env-gated on `USITC_EDIS_TOKEN`.** The six
  EDIS tools (`search_usitc_investigations`, `get_usitc_investigation`,
  `search_usitc_documents`, `list_usitc_attachments`,
  `download_usitc_attachment`, `download_usitc_investigation_documents`)
  register only when the token is set, matching the existing pattern for
  JPO, KIPO, CanLII, and INPI. The `usitc/documents` download-proxy
  fetcher is gated with `register_source_if_configured` for the same
  reason.

  This is a behavior change for consumers that relied on those tools being
  registered unconditionally: without the token they no longer appear in
  `tool/list`. The Python functions remain importable either way, so
  library and skill callers are unaffected.

  The gate is deliberately broader than the technical auth requirement —
  only `EdisClient.download_attachment` calls `require_auth()`, so EDIS
  search and metadata work unauthenticated. Gating the whole group lets a
  public deployment advertise a coherent surface instead of search tools
  whose results it cannot fetch.

  `search_hts_tariffs`, `list_ids_investigations`, and `run_dataweb_report`
  are unchanged: the first two need no auth, and DataWeb fails closed on
  its own `USITC_DATAWEB_TOKEN`.

## [0.23.0] — 2026-07-27

### Fixed

- Moved USPTO Assignment Center patent-assignment search to the v3 public
  endpoint after USPTO's July 24, 2026 update retired v2 (searches had been
  failing with upstream 403 errors). The request payload and response
  envelope are unchanged.

### Added

- `AssignmentCenterClient.details(reel_number, frame_number)` fetches the
  full recordation detail — including the affected properties, which the
  v3 search response no longer carries — returning the new
  `AssignmentDetail` model.
- New v3 response fields: `mail_date` and `recorded` on
  `AssignmentRecord`, and `acknowledgement_date` on `Assignor`.

### Changed

- Assignment-search `conveyance` filtering is now matched client-side
  (USPTO's v3 server dropped the filter and returns zero rows for it);
  for conveyance-filtered queries `total` reports the matched count.
- v3 caveat, documented on the client: `totalRows` for broad name queries
  is unreliable (the server caps its scan, observed at 10,000, and may
  silently omit older recordations for high-volume names); number-axis
  searches remain exact.

## [0.22.0] — 2026-06-05

### Added

- Added clean-source patent helpers that avoid Google Patents: PDF retrieval
  cascades from USPTO PPUBS to EPO OPS, and claim retrieval cascades from USPTO
  grant XML to EPO full text.
- Added an explicit clean-source figures response that directs callers to
  patent-PDF drawing sheets and reports that per-figure callout annotations are
  unavailable.

### Changed

- Updated package, plugin, and installation pins to 0.22.0.
- Made standalone CI independent of a private cross-repository checkout,
  updated workflow action runtimes, and added an atlas-image freshness gate.
- Refreshed bundled fee snapshots through 2026-06-05.

## [0.21.2] — 2026-05-22

### Added

- Added compatibility aliases for common MCP argument names across Google
  Patents, EPO OPS, USPTO PPUBS, and patent-family tools; MPEP section lookup
  now accepts numeric references.

### Fixed

- Corrected EPO document-identifier model population and PTAB request
  serialization to use the upstream camelCase payload fields.

## [0.21.1] — 2026-05-22

### Fixed

- Enforced category-specific provenance contracts across representative
  MCP tools so list, document, statute, fee, and metadata envelopes keep
  their source fields stable.
- Added fee-envelope compliance coverage for the bundled fee snapshots.
- Fixed `docs/mcp-stdio.md` MCP tool-count drift and added a script check
  so the documented stdio surface stays aligned with the generated server.

### Changed

- Updated release docs, plugin metadata, and roadmap state for the published
  PyPI package/plugin flow.

## [0.21.0] — 2026-05-21

### Changed

- **Shared scaffolding extracted to [`mcp-data-core`](https://github.com/parkerhancock/mcp-data-core).** The `law_tools_core` subpackage that previously shipped inside this wheel now lives in a standalone package on PyPI. `patent-client-agents` depends on `mcp-data-core>=0.1.0` and imports the primitives via `from mcp_data_core import ...`. Public API is identical apart from the import path; in-tree consumers should rewrite `law_tools_core` → `mcp_data_core` and `LawToolsCoreError` → `McpDataCoreError`.

### Removed

- **`src/law_tools_core/` no longer ships in the `patent-client-agents` wheel.** Install `mcp-data-core` directly for the shared HTTP client base, cache, retry, OAuth2, response envelopes, exception hierarchy, file logging, corpus utilities, and MCP server scaffolding.

### Added

- **Compressed outline corpora + GCS-driven bootstrap.** The eight
  outline-shaped corpora (`mpep`, `tmep`, `epc`, `epo_guidelines`,
  `epo_pct_guidelines`, `epo_up_guidelines`, `epo_case_law`,
  `ukipo_mopp`) now ship as zstd-compressed SQLite files — total
  footprint drops from ~228 MB to ~67 MB (-70%; per-corpus ratios
  range from 4× to 36×, with `epc` benefiting most from
  statute-template repetition). New `law_tools_core.corpus_compression`
  exposes `compress_text_column(conn, table, column)` (trains a 64 KB
  zstd dictionary on a row sample, compresses every row in-place,
  persists the dictionary in a sidecar `compression_dict` table) and
  `finalize_outline_corpus(conn)` (the canonical compress → FTS5
  `optimize` → `VACUUM` build-finalization sequence). Read-side
  decompression is transparent: `CorpusDBBase` gains a lazy
  `_decoders` cache and `_column_value()` helper; `OutlineCorpusDB.
  _row_to_section` reads through it, so consumers of `get_section()`
  see decompressed `html` with zero contract change. Backward-
  compatible: corpora without a `compression_dict` table still read
  as plain TEXT. FTS5 indexes the unindexed `text` column, so
  `search()` and native `snippet()` are unaffected.
- **`corpus_bootstrap` module + `patent-client-agents-bootstrap-corpora`
  CLI.** Manifest-driven materialization of the compressed corpora
  into the local cache. Reads a JSON manifest from `gs://bucket/path`
  (via `google-cloud-storage` with ADC / Workload Identity), `file://`
  paths, or bare local paths, then for each entry: verifies the
  cached file's SHA-256, downloads to a `.tmp` sibling and atomic-
  renames on a miss, otherwise skips. Idempotent — designed to run
  on every container start. Manifest `schema_version=1` shape:
  `{schema_version, updated_at, corpora: {name → {uri, sha256,
  size_bytes, local_filename, snapshot, built_at, section_count,
  source_version}}}`. Cloud Run cold-start projected at 2–3 s
  same-region (67 MB of compressed `.db` files); warm-start ~2 s
  for SHA verification only. Adds `google-cloud-storage>=2.18` as a
  runtime dep (lazy-imported in the GCS code path, so consumers
  using only `file://` or local paths pay no startup cost).

- **INPI France fee schedules (patent + trademark + design).** Adds
  three routes to the bundled `patent_client_agents.fees` connector:
  `FR/INPI/Fees/Patent` (49 FeeItems incl. annuity years 2-20 plus
  SPC annual at year=21), `FR/INPI/Fees/Trademark` (10 FeeItems on
  10-year cycle), and `FR/INPI/Fees/Design` (5 FeeItems on 5-year
  prorogation cycle). Source is the official "Tarifs des procédures
  applicables au 27 avril 2026.pdf" linked from
  `inpi.fr/ressources/propriete-intellectuelle/tarifs-procedures-et-prestations-de-linpi`
  and fetched via the inpi-block download endpoint (anonymously
  accessible; the legifrance/Cloudflare-protected statutory route
  turned out to be unnecessary). The "TARIFS RÉDUITS" column maps
  to `EntityTier.small` (natural persons, non-profit research/
  education orgs, companies <1000 employees with <25% non-qualifying
  capital). Brings the fees connector to 17 offices / 25 routes
  (13 of WIPO top-30 by 2023 patent filing volume).
  v1 GAPS: pypdf reliably captures annuity reduced rates for years
  2-7 only — years 8-20 reduced rates exist in the source but
  the second column drops out of extracted text. REGISTRES NATIONAUX
  admin fees, GIs, and semiconductor-topography fees are out of
  scope.
- **INPI Brazil fee schedules (patent + trademark).** Adds two
  routes to the bundled `patent_client_agents.fees` connector:
  `BR/INPI/Fees/Patent` (60 fee codes expanded to 272 FeeItems via
  per-year annuity bands × large/small tier siblings — invention
  20-yr term, utility model 15-yr term, certificate of addition
  20-yr term) and `BR/INPI/Fees/Trademark` (34 FeeItems including
  10-year renewal cycle). Source is the English-language
  Schedule of Fees PDFs at
  `gov.br/inpi/en/costs-and-payment/schedule-of-fees-{patents,trademarks}.pdf`
  — anonymously accessible (path discovered 2026-05-19; the pt-BR
  `tabelas-de-retribuicao` landing remains Plone role-restricted).
  The "discounted" column maps to `EntityTier.small` per Resolution
  251/2019 §I.5 (up-to-60% reduction for individuals,
  micro-enterprises, SMEs, cooperatives, ICTs, non-profits, public
  bodies). Brings the fees connector to 16 offices / 22 routes
  (12 of WIPO top-30 by 2023 patent filing volume).
- **PRH Finland v0.2 — trademark + design image downloads.** Two new
  MCP tools — `download_prh_trademark_image` and
  `download_prh_design_image` — fetch the binary image bytes exposed
  in dossier search rows and return the canonical `download_response`
  shape (signed `download_url` in hosted mode; local `file_path` in
  stdio mode; MCP `pca://` resource URI in both). TM variants cover
  `image` (GIF/JPEG), `thumbnail`, and `thumbnail/large` (JPEG);
  design variants cover `image`, `thumbnail`, and `thumbnail/medium`
  (JPEG). Cache key per CoWork allowlist invariant:
  `prh_fi/{right}/{variant}/{ident}` is also the MCP URI and the HTTP
  path. Adds 2 VCR cassettes.
- **PRV Sweden v0.2 — SPC search.** Adds `search_prv_spcs` MCP tool +
  `PrvClient.search_spcs()` for Swedish Supplementary Protection
  Certificates (patent-term extensions under EU Regulation 469/2009
  + 1610/96). Decoded the advanced-search request shape from the
  PRV React bundle: each filter wraps as
  `{value: ..., searchType: "CONTAINS"|"STARTS_WITH"|"EXACT"}` and
  the endpoint requires at least one filter (empty body returns
  HTTP 500). Filters exposed: `substance_product`, `applicants`,
  `application_number_spc`, `base_patent_number`,
  `marketing_authorization_number`, `announcement`. Adds one
  manifest row (`SE/PRV/SPCs`) and one VCR cassette. Resolves the
  v0.1 deferral on PRV SPC coverage.
- **TIPO Taiwan fee schedules (patent + trademark).** Adds two routes
  to the bundled `patent_client_agents.fees` connector: `TW/TIPO/Fees/Patent`
  (HTML table scrape of `/en/tipo2/326.html`, 34 source rows expanded
  to 83 FeeItems via per-year annuity bands × SME-tier siblings; SME
  applies to patentees who are natural persons / schools / SMEs for
  annuity years 1-3 and 4-6 across all three Taiwan patent types) and
  `TW/TIPO/Fees/Trademark` (curated catalog of 30 entries verified
  against the bilingual 2024-05-01 PDF; each entry's label and amount
  must co-occur within a 300-char window in normalized text or the
  scraper raises). Brings the fees connector to 15 offices / 20 routes.
  Also corrects URL drift: TIPO migrated the EN fee landing pages
  from `/en/cp-289-…` to `/en/tipo2/<id>.html`.
- **PRH Finland connector (v0.1).** `patent_client_agents.prh_fi` wraps
  three undocumented but unauthenticated PRH JSON APIs reverse-engineered
  from the React bundles: `patenttitietopalvelu.prh.fi/nis-api-gateway-pat/`
  (patent / UM / SPC / EP-FI corpus + per-record GET),
  `tavaramerkkitietopalvelu.prh.fi/nis-api-gateway/` (national trademarks
  + well-known TMR), and `mallioikeustietopalvelu.prh.fi/nis-api-gateway/`
  (designs). Ships 5 MCP tools — `search_prh_patents`, `get_prh_patent`
  (accepts `list[str]` per §5.4), `search_prh_trademarks`,
  `search_prh_well_known_trademarks`, `search_prh_designs`. The
  patent-search body has 30 fields with three list-valued inclusion
  filters (`dossierStatus` / `patentTypes` / `publicationTypes`);
  the client supplies full upstream-default vocabularies (~35 statuses,
  4 patent types, 38 publication kinds) so callers who only set
  applicant/title filters still get results. Lean projection drops
  the file-history pointer list, payment timeline, and raw events on
  the per-record GET; drops the thumbnail-URL triplet on dossier
  search rows. Adds 4 manifest rows
  (`FI/PRH/{Patents,Trademarks,WellKnownTrademarks,Designs}`). Server
  caps the response at 3,000 rows per query — narrow filters required
  for high-population applicants. No auth; courtesy User-Agent
  identifies the project + contact `avoindata@prh.fi`.
- **PRV Sweden connector (v0.1).** `patent_client_agents.prv_se` wraps
  three undocumented but unauthenticated PRV JSON APIs reverse-engineered
  from the `search.prv.se` React bundle: `patents-search-api.prv.se`
  (patent simple-search), `dv-search-api.prv.se` (trademark + design
  simple-search), and `api.prv.se` (per-record patent GET). Ships 4 MCP
  tools — `search_prv_patents`, `get_prv_patent` (`applicationType=NAT`
  default; accepts `list[str]` per §5.4), `search_prv_trademarks`,
  `search_prv_designs` — with lean projection dropping the ~32 KB
  base64-encoded first-drawing image on `get_prv_patent`. No auth
  required; courtesy User-Agent identifies the project + contact
  `data@prv.se`. Adds 3 manifest rows
  (`SE/PRV/{Patents,Trademarks,Designs}`). Deferred to v0.2: SPC search
  (HTTP 500 on probe), municipal arms register, advanced-search field
  decoding. Parallel bulk feeds on `data.prv.se` are CC0 1.0 / CC BY 4.0
  under Sweden's Open Data Act (SFS 2022:818).
- **TIPO Taiwan OpenData REST connector.** `patent_client_agents.tipo_opdata`
  wraps the 15-endpoint TIPO OpenData REST API
  (`https://cloud.tipo.gov.tw/S220/opdataapi/api/`) for biblio-only
  access to TW patents, utility models, designs, and trademarks.
  Env-gated on `TIPO_API_KEY` (single `tk` UUID issued by TIPO).
  Ships 14 MCP tools (search/get for patents + trademarks; combined
  `*_events` surfaces for alteration/change/divide). Adds 4 manifest
  rows to `coverage/sources.yaml`:
  `TW/TIPO/{Patents,UtilityModels,Designs,Trademarks}`. Pagination
  clamps `top` to the 6,000-row empirical cap; lean projection drops
  the FTPS `xml-detail-url` and null Latin/Japanese name fields per
  CONNECTOR_STANDARDS.md §5.5.
- `patent_client_agents.kipo_kipris`: KIPO Korea KIPRIS Plus connector
  (9 MCP tools, env-gated on `KIPO_KIPRIS_API_KEY`; 3 manifest rows
  `KR/KIPO/{Patents,Trademarks,Designs}`). BYOK per ToS §11 (no
  shared-key proxy permitted). v1 ships with synthesized XML
  fixtures; live cassettes pending serviceKey acquisition (KIPRIS
  Plus signup currently blocked behind Korean phone / i-PIN
  verification — see `research/specs/kr-kipo-connector-spec.md` §6
  for status).
- `patent_client_agents.inpi_pi`: INPI France TM + Design BYOK
  connector (4 MCP tools, env-gated on `INPI_USERNAME` +
  `INPI_PASSWORD`; 2 manifest rows FR/INPI/{Trademarks, Designs}).
  NO patent tools (EPO OPS covers FR patents via INPADOC). v1 ships
  with synthesized JSON + ST.66/ST.86 XML fixtures; live cassettes
  pending INPI Data account acquisition.
- **IPO India statutes + MPPP connector — first cut.** Brings the
  Indian IP statutes and the IPO India examination manual into the
  substantive-law catalog. Two packages ship in this PR, both
  `category: substantive_law`, `transport: mcp_local`:
  - `patent_client_agents.ipo_in_statutes` — bundles the four core
    Indian IP Acts (Patents Act 1970, Designs Act 2000, Trade Marks Act
    1999, Copyright Act 1957) plus the Patent Rules 2003 (with 2024
    amendments) into one SQLite/FTS5 corpus discriminated by
    `statute_name`. Citation parser accepts `Section 3(d) Patents Act`,
    `Section 25(2) Patents Act`, `Rule 71 Patent Rules`, and bare
    section numbers (`107A`); ambiguous bare numbers raise with a
    cross-statute disambiguation hint.
  - `patent_client_agents.ipo_in_mppp` — IPO India Manual of Patent
    Practice & Procedure v3.0 (2019), the IPO India counterpart to the
    USPTO MPEP and UKIPO MoPP. Citation form `MPPP Chapter 04.05.01`
    (plus the bare-number / `Chapter` / `Ch.` shorthand variants).
- **MCP tools (4 new, all envelope-shaped per CONNECTOR_STANDARDS.md
  §5.9):** `search_ipo_in_statutes`, `get_ipo_in_section` (in
  `mcp/tools/ipo_in_statutes.py`); `search_ipo_in_mppp`,
  `get_ipo_in_mppp_section` (in `mcp/tools/ipo_in_mppp.py`). All four
  surface `Provenance.corpus_synced_at` and `corpus_version` from each
  package's `get_corpus_status()` callable; `get_*` accepts
  `citation: str | list[str]` for portfolio workflows.
- **Build CLIs.** `patent-client-agents-build-ipo-in-statutes-corpus`
  and `patent-client-agents-build-ipo-in-mppp-corpus` ingest the
  bundled JSON-lines seeds at
  `src/patent_client_agents/ipo_in_statutes/data/seed.jsonl` and
  `src/patent_client_agents/ipo_in_mppp/data/seed.jsonl` respectively.
  The seed-driven approach (rather than scraping indiacode.nic.in /
  ipindia.gov.in at build time) keeps CI deterministic and side-steps
  the CAPTCHA-everywhere problem the IPO India research file flags.
- **Manifest entries.** `coverage/sources.yaml` adds
  `IN/IPO/Statutes` (`update_strategy: scheduled_recrawl`,
  `update_cadence: annual`) and `IN/IPO/MPPP` (`update_cadence:
  irregular`, `corpus_version: "v3.0 (2019)"`).
- **IP Australia connector — first cut.** Adds Australian coverage to
  the registered-IP catalog. Four packages ship in this PR, gated on
  the shared `IPAUSTRALIA_CLIENT_ID` / `IPAUSTRALIA_CLIENT_SECRET`
  credentials (`IPAUSTRALIA_ENV=sandbox|production`, default
  production):
  - `patent_client_agents.ip_australia_patents` —
    `IpAustraliaPatentsClient` (Australian Patent Search API, OAuth 2.0
    client_credentials).
  - `patent_client_agents.ip_australia_trademarks` —
    `IpAustraliaTrademarksClient` (Australian Trade Mark Search API,
    formerly ATMOSS).
  - `patent_client_agents.ip_australia_designs` —
    `IpAustraliaDesignsClient` (Australian Designs Search API).
  - `patent_client_agents.ip_australia_bulk` — `IpAustraliaBulkClient`
    for the IP RAPID weekly bulk snapshot on `data.gov.au` (no auth;
    CC-BY 4.0).
- **MCP tools (8 new, all envelope-shaped per
  CONNECTOR_STANDARDS.md §5.9):**
  - `search_ipa_patents`, `get_ipa_patent` —
    `mcp/tools/ip_australia_patents.py`.
  - `search_ipa_trademarks`, `get_ipa_trademark` —
    `mcp/tools/ip_australia_trademarks.py`.
  - `search_ipa_designs`, `get_ipa_design` —
    `mcp/tools/ip_australia_designs.py`.
  - `list_ipa_bulk_releases`, `download_ipa_bulk` —
    `mcp/tools/ip_australia_bulk.py` (Shape E — catalog + download
    URL; the OAuth-API search/get tools are env-gated, the bulk tools
    are not).
- **Shared scaffolding.**
  `patent_client_agents.ip_australia_common` consolidates the
  environment / host / token-URL / `OAuth2ClientCredentialsAuth`
  wiring so the three rights clients only declare their own API path
  prefix and `CACHE_NAME`.
- **Manifest entries** in `coverage/sources.yaml`:
  `AU/IPAustralia/Patents`, `AU/IPAustralia/Trademarks`,
  `AU/IPAustralia/Designs`, `AU/IPAustralia/Bulk` (all
  `category: registered_ip`, `transport: mcp_proxy`,
  `last_verified: 2026-05-16`).

### Notes

- The IP RAPID surface ships intentionally minimal — `list_ipa_bulk_releases`
  + `download_ipa_bulk` only — per the connector standards §7.2 Shape E
  rule for download tools. Full CSV ingestion of the ~40 IP RAPID
  tables (patents / trade marks / designs / PBR) is deferred to a
  follow-up.
- Endpoint shape for the **Australian Patent Search API** is inferred
  from the symmetric trade-mark / design surface. The public
  `descriptions.api.gov.au/ipaustralia/patent-search/` page returned
  404 at build time (2026-05-16); the live host responds and the
  research file is annotated. Shape may need adjustment after the
  live-credential verification step.
- IP RAPID licence corrected from CC-BY 2.5 AU (older research) to
  **CC-BY 4.0 International** based on the CKAN ``package_show`` metadata
  fetched 2026-05-16.

### DPMA Germany statutes connector (substantive law)

- `patent_client_agents.dpma_statutes` — bundles the six core German IP
  Acts (PatG, MarkenG, GebrMG, DesignG, UrhG, GeschGehG) into one
  SQLite/FTS5 corpus discriminated by `statute`. Citation parser
  accepts `§ 139 PatG`, `§ 14 MarkenG`, `Section 14 MarkenG`, and bare
  section numbers; long-form aliases (Patentgesetz, Markengesetz, …)
  resolve to canonical short names.
- **MCP tools** (envelope-shaped per §5.9): `search_dpma_statutes`,
  `get_dpma_section` (in `mcp/tools/dpma_statutes.py`). Both surface
  `Provenance.corpus_synced_at` / `corpus_version` from
  `dpma_statutes.get_corpus_status()`; `get_dpma_section` accepts
  `citation: str | list[str]` for portfolio workflows.
- **Build CLI.** `patent-client-agents-build-dpma-statutes-corpus`
  ingests the bundled JSON-lines seed at
  `src/patent_client_agents/dpma_statutes/data/seed.jsonl`.
- **Manifest entry** in `coverage/sources.yaml`: `DE/DPMA/Statutes`
  (`category: substantive_law`, `transport: mcp_local`,
  `update_strategy: scheduled_recrawl`, `update_cadence: annual`,
  `last_verified: 2026-05-16`).

### Légifrance IP statutes connector (substantive law)

- `patent_client_agents.legifrance_ip` — bundles the French
  intellectual-property statutes (Code de la propriété intellectuelle:
  patents L.611, trade marks L.711, designs L.511, copyright L.111)
  plus the Code de commerce L.151 trade-secret regime into one
  SQLite/FTS5 corpus discriminated by `statute`. Citation parser
  accepts `L. 611-10 CPI`, `Art. L. 611-10 CPI`, `L611-10 CPI`, and
  `L. 151-1 Code de commerce`; diacritics fold in search
  (`brevetabilite` matches `brevetabilité`).
- **MCP tools** (envelope-shaped per §5.9): `search_legifrance_ip`,
  `get_legifrance_section` (in `mcp/tools/legifrance_ip.py`). Both
  surface `Provenance.corpus_synced_at` / `corpus_version` from
  `legifrance_ip.get_corpus_status()`; `get_legifrance_section` accepts
  `citation: str | list[str]` for portfolio workflows.
- **Build CLI.** `patent-client-agents-build-legifrance-ip-corpus`
  ingests the bundled JSON-lines seed at
  `src/patent_client_agents/legifrance_ip/data/seed.jsonl`.
- **Manifest entry** in `coverage/sources.yaml`: `FR/Legifrance/IP`
  (`category: substantive_law`, `transport: mcp_local`,
  `update_strategy: scheduled_recrawl`, `update_cadence: annual`,
  `last_verified: 2026-05-16`).

### Taiwan Trade Secrets Act connector (substantive law)

- `patent_client_agents.tw_trade_secrets` — bundles the official English
  translation of the Taiwan Trade Secrets Act (營業秘密法), Articles 1,
  2, 3, 10, 11, 13, and 13-1, into one SQLite/FTS5 corpus. Single-statute
  schema (no `statute` discriminator). Citation parser accepts
  `Art. 2 Trade Secrets Act`, `Section 13 Trade Secrets Act`,
  `Art. 13-1`, and bare numeric forms (`13`, `13-1`). TIPO REST + bulk
  are deferred to a follow-up.
- **MCP tools** (envelope-shaped per §5.9): `search_tw_trade_secrets`,
  `get_tw_trade_secrets_section` (in `mcp/tools/tw_trade_secrets.py`).
  Both surface `Provenance.corpus_synced_at` / `corpus_version` from
  `tw_trade_secrets.get_corpus_status()`; `get_tw_trade_secrets_section`
  accepts `citation: str | list[str]` for portfolio workflows.
- **Build CLI.** `patent-client-agents-build-tw-trade-secrets-corpus`
  ingests the bundled JSON-lines seed at
  `src/patent_client_agents/tw_trade_secrets/data/seed.jsonl`.
- **Manifest entry** in `coverage/sources.yaml`: `TW/MOJ/TradeSecretsAct`
  (`category: substantive_law`, `transport: mcp_local`,
  `update_strategy: scheduled_recrawl`, `update_cadence: irregular`,
  `last_verified: 2026-05-16`).

## [0.19.0] — 2026-05-15

This release rolls up four bodies of work that landed on `main` without
being individually tagged (the in-progress version markers `0.16.0`,
`0.17.0`, and `0.18.0` were never published). It is therefore the first
release since `v0.15.0` and carries a large number of breaking changes
across the connector surface.

### Added

- **`CONNECTOR_STANDARDS.md`** — opinionated rules every connector must
  satisfy (coverage scope, architecture defaults, provenance, recency,
  MCP tool design §5.1-§5.13, closed-vocabulary manifest §6).
- **`MIGRATION_PLAYBOOK.md`** — working sweep plan for migrating the
  existing tool surface onto the standards, ordered for impact and
  blast radius (21 PRs queued; rows 1-2 done).
- **`coverage/sources.yaml`** — 31-entry closed-vocabulary manifest
  enforced by `scripts/build_coverage.py`. Top-30 patent offices by
  WIPO 2023 filing volume tracked for gap analysis.
- **`law_tools_core.envelope`** — `Provenance`, `ResponseEnvelope[T]`,
  `ListEnvelope[T]`, plus `make_provenance`, `encode_cursor`,
  `decode_cursor` helpers. Cursors are opaque base64(JSON); connectors
  decide the payload schema. The response shape is now uniform across
  the catalog (§5.9).

### Changed (breaking)

- **USPTO Applications surface migrated to `ListEnvelope`.**
  `search_applications`, `get_application`, and `list_file_history`
  now return `ListEnvelope[dict]` with `Provenance` metadata (UTC
  `retrieved_at`, `source_url`, `source_name`, `connector_version`)
  and a Markdown `summary`. The shape is `{summary, items, next_cursor,
  more_available, provenance}`.
- **`get_application` now accepts `list[str]`** per §5.4 — pass a list
  of application numbers for portfolio workflows. Single-string calls
  still work and still return a `ListEnvelope` (shape is stable).
  Internal bounded concurrency, order preservation.
- **Trademarks surface migrated to `ListEnvelope`** (row 2 of
  `MIGRATION_PLAYBOOK.md`):
  - `search_trademarks` now returns lean stubs by default (eight
    scalar fields); pass `full=True` for the upstream-shaped record.
  - `get_trademark` collapses the two-argument
    `(serial_number, registration_number)` pattern into one
    `serial_number` parameter that accepts either format (auto-detected
    by digit count: 8 → serial, 6-7 → registration). Accepts a list per
    §5.4.
  - `get_trademark_status` and `get_trademark_last_update` accept
    `str | list[str]` per §5.4.

### Removed

- **`batch_trademark_status` deleted.** It was a §5.4 violation (no
  `batch_*` tools). Use `get_trademark_status(serial_number=[...])`
  instead — the list-accepting form is now the supported pattern.

### Additional connector migrations (rows 3, 10, 19)

- **USPTO Publications (PPUBS) migrated to `ListEnvelope`**
  (row 3). `search_patent_publications` now returns lean stubs
  (eight scalar fields) by default with `full=True` opt-in;
  `get_patent_publication` accepts `publication_number: str | list[str]`
  per §5.4 with bounded-concurrency fan-out. `resolve_publication_number`
  in the same file now returns `ResponseEnvelope` (single-record shape;
  true 1:1 resolver).
- **EUIPO trademarks + designs migrated to `ListEnvelope`** (row 10).
  `search_euipo_trademarks`, `get_euipo_trademark`,
  `search_euipo_designs`, and `get_euipo_design` all conform; gets
  accept `application_number: str | list[str]` (trademarks) or
  `design_number: str | list[str]` (designs). Lean stubs of 8 / 7
  scalars respectively. Single `_euipo_provenance` helper covers both
  surfaces (shared host).
- **WIPO Lex migrated to `ListEnvelope`** (row 19).
  `search_wipo_lex_legislation` and `get_wipo_lex_legislation` conform;
  get accepts `legislation_id: str | list[str]`. Note:
  `LegislationSearchHit` upstream carries only three fields
  (`legislation_id`, `title`, `url`) — country / year / IP-category
  appear only on the detail-page fetch, documented in the search
  docstring's cross-reference rather than fabricated into the lean
  view.
- **CAFC search tools migrated to `ListEnvelope`** (row 14).
  `search_cafc_opinions` and `search_cafc_patent_opinions` return
  lean stubs (eight scalars including `is_patent_case`) by default
  with `full=True` opt-in. Shared `_stub_opinion()` helper. Provenance
  is `substantive_law` / `mcp_proxy` shape (no `corpus_synced_at` /
  `corpus_version`). `download_cafc_pdf` shape unchanged per playbook
  §2 Shape E; its docstring picks up a `Related tools:` line and the
  CAFC acronym expansion for §5.13 compliance.
- **Copyright migrated to `ListEnvelope`** (row 16). `search_copyright`
  now lean by default (eight scalar fields via a `_first()` list-flattener)
  with `full=True` opt-in. `get_copyright_record` accepts
  `public_records_id: str | list[str]` per §5.4. The parameter name
  is intentionally kept — the upstream's `public_records_id` is a
  distinct opaque ID (`voyager_12345`, `card_catalog_...`), not the
  user-facing registration number (`TX 1234567`). Docstrings now
  distinguish the two and point at `search_copyright` for
  registration-number lookups.
- **CPC tools migrated to envelope** (row 20). `lookup_cpc` and
  `map_cpc_classification` return `ResponseEnvelope[dict]` (single
  record); `search_cpc` returns `ListEnvelope[dict]` with a lean
  default. First sentences sharpened per §5.13 audit finding — the
  three tools' docstrings no longer "blur together." Tools live in
  `mcp/tools/international.py` alongside the EPO OPS surface (which
  CPC delegates to). `lookup_cpc` deliberately not list-accepting
  for now (per-symbol summaries are more quotable; can flip if
  portfolio resolution becomes a real workflow).
- **MPEP migrated to envelope + `get_corpus_status()` callable**
  (row 17). `search_mpep` returns `ListEnvelope[dict]` with a lean
  default; `get_mpep_section` accepts `section: str | list[str]`
  per §5.4. New module-level `patent_client_agents.mpep.get_corpus_status()`
  returns a `CorpusStatus` TypedDict with `corpus_synced_at` and
  `corpus_version`. The MCP tool calls it once per request to populate
  `Provenance.corpus_synced_at` / `Provenance.corpus_version`. The
  validator's MPEP-specific warning is now gone (8 corpora remain
  pending row 18). The callable's pattern (TypedDict + `_parse_snapshot_date`
  helper + try/except fallback to "unknown") is the template for the
  8 row-18 sub-PRs.
- **UPC migrated to envelope** (row 12). Seven tools: `search_upc_decisions`,
  `get_upc_decision` (list-accept on `case_id`), `search_upc_statutes`,
  `get_upc_section` (list-accept on `instrument`), and the three
  `list_upc_*` vocab enumerators (§5.8 acceptable extension).
  Decisions are `mcp_proxy` (no corpus fields); statutes are `mcp_local`
  with corpus fields hardcoded to "unknown — needs verification" until
  the `get_corpus_status()` rollout reaches `upc_statutes` (queued for
  row 18). §5.6 audit fix: `search_upc_statutes` ↔ `get_upc_section`
  now cross-reference.
### Batch 7 connector migrations (rows 5, 7, 8) — sweep complete (21/21)

- **Row 5: PTAB envelope + §5.4 list-accept + §5.13 acronym expansion.**
  `search_ptab`, `get_ptab`, and `list_ptab_children` migrated to
  `ListEnvelope[dict]` / `ResponseEnvelope[dict]`. The type-multiplex
  (`proceeding` / `trial_decision` / `trial_document` /
  `appeal_decision` / `interference_decision`) is preserved (§5.1
  soft-cap acceptable); a single `_stub_ptab_record(record, ptab_type)`
  helper branches per type. `list_ptab_children` collapses the
  previous nested-dict shape (`{decisions: ..., documents: ...}`)
  into a flat `ListEnvelope` where each item carries a `type` field —
  agents can sort/filter without knowing the nesting. Every PTAB
  tool's first sentence now spells out "Patent Trial and Appeal Board
  (PTAB)" on first use. Download tools (`download_ptab_*`) keep
  Shape E; docstrings picked up `Related tools:` lines.

- **Row 7: Petitions envelope + §5.8 parameter rename.**
  `search_petitions` returns `ListEnvelope[dict]` with a lean default
  (drops upstream `statuteBag` / `ruleBag` / `issueTypeBag`).
  `get_petition` accepts `petition_number: str | list[str]` per §5.4
  with bounded fan-out — **parameter renamed from `petition_id` per
  §5.8's "never `id`" rule.** Test pins the rename via `inspect.signature`.

- **Row 8: Patent + Trademark Assignments envelope + lean projections.**
  Spans three files:
  - `search_patent_assignments` in `patent_assignments.py` — lean
    projection (reel/frame, conveyance, first-party names, dates).
    Now propagates `result.truncated` into both `more_available` and
    the summary text ("USPTO capped at ~N; narrow to access more").
  - `search_trademark_assignments` in `trademarks.py` — lean
    projection. **Latent bug fix:** the previous code passed
    `start_row=` to `search_by_serial` / `search_by_registration` /
    `search_by_reel_frame` (would have raised `TypeError`); fixed to
    only pass to methods that accept it.
  - `get_patent_assignment` in `uspto.py` — `ListEnvelope[dict]` with
    `application_number: str | list[str]` per §5.4.
  - Provenance helpers: the two `search_*` tools hit
    `assignment-api.uspto.gov` (distinct from ODP) and each get their
    own source-specific helper (`_patent_assignment_provenance`,
    `_tm_assignment_provenance`). `get_patent_assignment` hits the
    ODP `/applications/{n}/assignment` endpoint and reuses
    `_odp_provenance`.

**The connector standards sweep is complete: all 21 playbook rows
migrated. ~99 MCP tools across 25 connectors now ship the
`ResponseEnvelope` / `ListEnvelope` contract with structured
`Provenance` metadata.**

### Batch 6 connector migrations (rows 4, 6, 9)

- **Row 4: Google Patents collapse + rename + envelope.** Three
  coordinated changes:
  - `search_google_patents` → `search_patents_global` (§5.7
    jurisdiction-neutral name; Google Patents indexes >100
    jurisdictions, not just one source's view).
  - `get_patent_details` **deleted**; `get_patent` gains a
    `view: "full" | "details"` parameter — same data, half the
    catalog surface (§5.1 catalog discipline).
  - `get_patent` accepts `patent_number: str | list[str]` per §5.4
    with bounded-concurrency fan-out; returns `ListEnvelope[dict]`
    even for a single string.
  - `search_patents_global` lean default of 9 scalars + `full=True`
    opt-in (§5.5). New helpers: `_google_patents_provenance`,
    `_summarize_patent`, `_details_view`, `_stub_search_hit`.
  - Catalog (`catalog/sources/google-patents.md`,
    `catalog/intents/README.md`) and docs (`docs/installation.md`)
    updated for the rename.
- **Row 6: Office Actions envelope + new `get_office_action`.**
  Closes the §5.2 orphan-search audit finding via a real upstream
  endpoint: `POST /api/v1/patent/oa/oa_actions/v1/records` with a
  Lucene `id:<documentIdentifier>` query (the `oa_actions` Solr
  dataset is the only office-action endpoint with full `body_text`
  + structured `sections`). `search_office_actions` now returns
  `ListEnvelope[dict]` with lean default (rejection_types included
  in the projection) + `full=True` opt-in. Cursor encoding:
  `{"start": N, "rows": M}`. `get_office_action` accepts
  `document_identifier: str | list[str]` per §5.4 with bounded
  fan-out. No client-layer changes needed.
- **Row 9: EPO OPS migration — largest remaining surface.**
  Seven tools migrated in `international.py`:
  - `search_epo`: `ListEnvelope[dict]` with lean default + `full=True`
    opt-in. EPO's `range_begin`/`range_end` pagination encoded as
    opaque `next_cursor` payload per playbook §3.
  - `get_epo_biblio`, `get_epo_family`, `get_epo_fulltext`,
    `get_epo_legal_events`: all accept `application_number: str | list[str]`
    per §5.4 with `_EPO_FANOUT_CONCURRENCY=5`.
  - `get_epo_cql_help`: `ResponseEnvelope[dict]`. §5.13 rewrite:
    "Show the search syntax (CQL — Common Query Language) accepted
    by `search_epo`."
  - `convert_epo_number`: `ResponseEnvelope[dict]`.
  - §5.6 cross-references: `search_epo` now names all 5 `get_epo_*`
    siblings + `convert_epo_number`; each `get_epo_*` references the
    others (closes the audit finding that the EPO get-family was
    not cross-referenced from `search_epo`).
  - Sibling tools in `international.py` (JPO, CPC,
    `get_epo_unitary_patent_status`) explicitly verified unmodified.

### Batch 5 connector migrations (rows 13, 15, 21)

- **Row 21: Unitary patent helper renamed and migrated.**
  `get_unitary_patent_package` → `get_epo_unitary_patent_status`
  (§5.7 jurisdiction prefix, §5.8 dropped "package" jargon, §5.13
  first sentence rewritten to lead with what an attorney actually
  wants). Returns `ResponseEnvelope[dict]` (Shape B — single-record
  EPO Register lookup). Library-level API
  (`epo_ops.get_unitary_patent_package`, client method,
  `UnitaryPatentPackage` model) intentionally unchanged — only the MCP
  tool surface renamed.

- **Row 13: USITC migrated + new `get_usitc_investigation` tool.**
  Closes the §5.2 orphan-search audit finding via a real EDIS
  endpoint (`/data/investigation/{N}`); no search fallback needed.
  `search_usitc_investigations`, `search_usitc_documents`,
  `search_hts_tariffs`, `list_usitc_attachments`,
  `list_ids_investigations` now all conform to the envelope.
  `run_dataweb_report` first sentence rewritten per §5.13:
  "Pull US import/export statistics from USITC DataWeb (the official
  trade-statistics interface)." All docstrings spell out USITC, EDIS,
  and DataWeb on first use. Download tools (`download_usitc_*`)
  retain their Shape E ResourceLink shape; docstrings updated for
  §5.6 cross-refs only.

- **Row 15: CanLII renamed and migrated.**
  `browse_canlii_cases` → `search_canlii_cases`,
  `browse_canlii_legislation` → `search_canlii_legislation` per the
  §5.8 verb table (the upstream behavior is filter-driven search, not
  vocabulary enumeration). `get_canlii_case` and
  `get_canlii_legislation` accept `str | list[str]` per §5.4 with
  bounded-concurrency fan-out. Citator tools
  (`get_canlii_cited_cases`, `get_canlii_citing_cases`,
  `get_canlii_cited_legislations`) gain §5.6 cross-refs to
  `get_canlii_case`. Vocabulary list_* enumerators retained per §5.8
  acceptable extension. Catalog and docs references updated for the
  rename.

- **Row 18 complete — all 8 substantive-law `mcp_local` corpora now
  expose `get_corpus_status()` AND ship envelope-conformant MCP tools.**
  Real `corpus_version` strings now flow through `Provenance.corpus_version`
  on every response:
  - **EPC**: `"2020"` (EPC 2020 edition)
  - **EPO Guidelines**: `"2024"` (March 2024 annual edition)
  - **EPO Case Law**: `"2022"` (10th edition Boards of Appeal "white book")
  - **PCT-EPO Guidelines**: `"2024"`
  - **EPO UP Guidelines**: `"2026"`
  - **UKIPO MoPP**: `"snapshot-2026-05-14"` (gov.uk doesn't publish a
    stable revision tag; falls back to dated snapshot)
  - **TMEP**: `"current"` (USPTO doesn't publish a stable revision label)
  - **UPC Statutes**: `"snapshot-YYYY-MM-DD"` (derived from
    `meta.snapshot_date` since the corpus schema doesn't carry a
    `source_version` field)

  `scripts/build_coverage.py` validator's check #3 is now a **hard
  error** (was a warning during rollout). Every category-2 mcp_local
  connector must expose `get_corpus_status()` or CI fails.

  Row-18b agent also fixed a pre-existing bug in `epo_pct_guidelines`
  and `epo_up_guidelines`: `default_corpus_path()` returned
  `~/.cache/patent_client_agents/guidelines.db` (the EPC corpus path)
  for both. Corrected to per-corpus filenames (`pct_guidelines.db`,
  `up_guidelines.db`).

- **JPO migrated to envelope** (row 11). All `get_jpo_*` and the
  `convert_*` family. Notable changes:
  - **`get_jpo_applicant_by_code` + `get_jpo_applicant_by_name`
    collapsed into single `get_jpo_applicant`** per §5.3 (auto-detect:
    9-digit numeric → code; anything else → exact-name match). Drops
    the JPO surface from 12 to 11 tools.
  - **§5.13 rewrites:** `get_jpo_jplatpat_url` first sentence now reads
    "Get the J-PlatPat (JPO public search portal) permalink for a JPO
    filing." `get_jpo_number_reference` now reads "Convert a JPO number
    between application, publication, and registration forms."
  - **§5.4 list-accept** on `get_jpo_progress`, `get_jpo_progress_simple`,
    `get_jpo_registration_info` with `_JPO_FANOUT_CONCURRENCY=5`.
  - **§5.6 cross-references** added between facet fetches and the
    parent `get_jpo_progress` (audit finding).
  - Catalog and `ip_research` skill references updated to name the
    collapsed applicant tool.

### Lean `search_applications` stub (originally planned as 0.18.0)

- **`search_applications` now returns a lean stub per hit by default.**
  Previously every hit carried the full ODP record (inventor bag,
  applicant bag, attorney of record, continuity, PTA history,
  prosecution events, etc.), which was megabytes per call and
  unworkable as agent context. The default projection is now sixteen
  scalar fields sufficient to identify and triage each application:
  ``applicationNumberText``, plus ``applicationMetaData.{inventionTitle,
  patentNumber, earliestPublicationNumber, filingDate, grantDate,
  applicationStatusCode, applicationStatusDescriptionText,
  applicationStatusDate, applicationTypeCategory, firstApplicantName,
  firstInventorName, examinerNameText, groupArtUnitNumber,
  docketNumber, cpcClassificationBag}``.

  Affects ``ApplicationsClient.search``, ``UsptoOdpClient.search_applications``,
  ``patent_client_agents.uspto_applications.api.search_applications``,
  and the ``search_applications`` MCP tool.

  **Migration:** pass ``full=True`` to restore the previous behavior, or
  pass an explicit ``fields=[...]`` projection (Python API only) for a
  custom shape. The stub list is exported as
  ``patent_client_agents.uspto_odp.clients.applications.STUB_APPLICATION_FIELDS``.

  When you only need one application's full record, prefer
  ``get_application(application_number)`` — that endpoint is unchanged.

### PCT-EPO + UP Guidelines connectors (originally planned as 0.17.0)

- **EPO PCT-EPO Guidelines connector**
  (``patent_client_agents.epo_pct_guidelines``). The Guidelines that
  apply when the EPO acts as ISA / IPEA / RO under the Patent
  Cooperation Treaty. Same URL shape as the EPC Guidelines
  (``a_i.html``, ``g_ii_3_1.html``); cloned scraper + citation parser.
  2024 edition: **756 leaf sections, ~9.7 MB**.
  - ``PctGuidelinesClient.search`` + ``.get_section`` with citation
    forms ``G-II, 3.1`` / ``g_ii_3_1`` / full URL.
  - MCP tools: ``search_epo_pct_guidelines`` + ``get_epo_pct_guidelines_section``.

- **EPO Unitary Patent (UP) Guidelines connector**
  (``patent_client_agents.epo_up_guidelines``). Guidelines for the
  Unitary Patent regime (opt-in, fees, renewals, UPP register).
  Different URL shape than EPC/PCT Guidelines — flat ``section_N_M_P``
  matching dotted ``N.M.P`` citation form. Pages don't have ``<main>``;
  custom extractor walks h1 → ``content-wrapper``. 2026 edition:
  **142 leaf sections, ~1.4 MB**.
  - ``UpGuidelinesClient.search`` + ``.get_section`` with citation
    forms ``1.2.1`` / ``Section 1.2.1`` / ``§ 1.2.1`` / ``section_1_2_1``.
  - MCP tools: ``search_epo_up_guidelines`` + ``get_epo_up_guidelines_section``.
- ``patent-client-agents-build-pct-guidelines-corpus`` and
  ``patent-client-agents-build-up-guidelines-corpus`` CLIs ship with
  the wheel.

#### EPO completeness

The PCT and UP additions bring the EPO static-corpus coverage to a
defensible "complete" set:

| Source | Module | Sections | Size |
|---|---|---|---|
| EPC Convention + Implementing Regulations | ``epc`` | 356 | 13 MB |
| EPO Guidelines for Examination (EPC) | ``epo_guidelines`` | 1,771 | 26 MB |
| EPO PCT-EPO Guidelines | ``epo_pct_guidelines`` (new) | 756 | 9.7 MB |
| EPO UP Guidelines | ``epo_up_guidelines`` (new) | 142 | 1.4 MB |
| Case Law of the Boards of Appeal ("white book") | ``epo_case_law`` | 2,631 | 111 MB |

**Still missing** for true completeness (queued for later releases):

- **RPBA** (Rules of Procedure of the Boards of Appeal) — single
  HTML page; could be added as a one-row corpus or split via internal
  anchors. Deferred.
- **Official Journal of the EPO (OJ EPO)** — 7,693 URLs in the legal
  sitemap; live monthly publication. Different update pattern than
  the static corpora; deferred to its own release.
- **Boards of Appeal raw decisions database** (G/T/D cases by number)
  — live search interface, not a static corpus.
- **National Law Relating to the EPC** — annual EPO publication
  tracking member-state implementations. URL needs investigation.

#### Tool count

- Default surface: 80 → **84** (4 new tools across PCT + UP Guidelines).

### EPC + EPO Case Law connectors (originally planned as 0.16.0)

- **European Patent Convention (EPC) connector** (``patent_client_agents.epc``).
  Corpus-backed access to the Convention Articles (180) and
  Implementing Regulations Rules (176) as published at
  ``www.epo.org/en/legal/epc/<year>``. Built via
  ``patent-client-agents-build-epc-corpus`` into a SQLite/FTS5 db
  (~13 MB). Accepts ``Article 54`` / ``Art. 54`` / ``a54`` and
  ``Rule 71`` / ``R. 71`` / ``r71`` citation forms plus URL slugs
  and full epo.org URLs.
  - ``EpcClient.search(query, syntax=...)`` and
    ``EpcClient.get_section(section)``.
  - MCP tools: ``search_epc`` + ``get_epc_section`` on
    ``epc_mcp``.
- **EPO Case Law of the Boards of Appeal connector**
  (``patent_client_agents.epo_case_law``). The canonical "white
  book" compilation of Boards-of-Appeal case law, referenced
  constantly in European patent prosecution and opposition.
  Source: ``www.epo.org/en/legal/case-law/<year>``. EPO publishes
  every 2-3 years (2019, 2022, ...).
  - Built via ``patent-client-agents-build-caselaw-corpus`` from
    the year's ``index.html`` (~2,600 ``clr_*`` URLs enumerated
    in one fetch). Direct fetch per URL — no BFS needed.
  - ``CaseLawClient.search`` and ``CaseLawClient.get_section``
    with ``I.A.1`` / ``I-A-1`` / ``I A 1`` citation forms plus
    ``clr_i_a_1`` URL slugs.
  - MCP tools: ``search_epo_case_law`` + ``get_epo_case_law_section``
    on ``epo_case_law_mcp``.
- ``patent-client-agents-build-epc-corpus`` and
  ``patent-client-agents-build-caselaw-corpus`` CLIs ship with the
  wheel.

#### Tool count

- Default surface: 76 → **80** (4 new tools across EPC + Case Law).

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

[Unreleased]: https://github.com/parkerhancock/patent-client-agents/compare/v0.22.0...HEAD
[0.22.0]: https://github.com/parkerhancock/patent-client-agents/compare/v0.21.2...v0.22.0
[0.21.2]: https://github.com/parkerhancock/patent-client-agents/compare/v0.21.1...v0.21.2
[0.21.1]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.21.1
[0.6.6]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.6
[0.6.5]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.5
[0.6.4]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.4
[0.6.3]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.3
[0.6.2]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.2
[0.6.1]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.1
[0.6.0]: https://github.com/parkerhancock/patent-client-agents/releases/tag/v0.6.0
