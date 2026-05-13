# Changelog

All notable changes to `patent-client-agents` are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
