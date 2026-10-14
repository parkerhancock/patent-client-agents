# Refactor analysis: scrapers, court/docket connectors, top-level modules, tests/, scripts/

Read-only. Repo left clean (`git status` empty). Baseline: the 784 tests in this slice pass
(`uv run pytest tests/google_patents tests/cafc tests/canada_federal_court tests/china_spc_ip_court
tests/copyright tests/japan_ip_high_court tests/prh_fi tests/prv_se tests/usitc tests/uspto_publications
tests/upc_decisions tests/wipo_lex tests/test_unified_*.py tests/test_corpus_bootstrap.py`, 9.9 s).

## Packages covered

Source (src/patent_client_agents/): google_patents (3,492 lines), uspto_publications / PPUBS (1,558),
usitc (1,108), prh_fi (1,065), prv_se (1,009), cafc (626), upc_decisions (608), wipo_lex (558),
canada_federal_court (536), china_spc_ip_court (479), copyright (342), japan_ip_high_court (322),
top-level `__init__.py`, `unified.py` (568), `corpus_bootstrap.py` (467), `skill_install.py` (108),
`catalog/` (30 markdown files, no Python). Plus `tests/` structure (root conftest, per-package
conftests, cassettes, fixtures, repeated test shapes) and `scripts/` (12 files, 4,108 lines).

Not covered (other agents): corpus connectors, mcp/, the live API clients, fees/. Where a primitive
I propose also applies there, I say so and keep the line estimate for my slice separate.

## Headline findings

Verbatim duplication in this slice is small (symilar flags mostly `__all__` lists repeated between
`__init__.py` and `api.py`, and the prh_fi/prv_se date parser). The value is structural, and three
of the items below are real bugs found while measuring, not just tidiness:

1. **Google Patents PDF cache corrupts bytes on every cache hit (confirmed).**
   `google_patents/cache.py:86-99,145-161` stores `response.text` and rebuilds a response with no
   headers. `GooglePatentsClient.download_patent_pdf` (`client.py:1301-1325`) uses that cache
   (`use_cache=True` default), then checks `content-type` for "pdf". Repro script
   (`scratchpad/refactor/pdfcache_check.py`, PatentCache in a temp dir + MockTransport):
   first call `ctype=application/pdf bytes_equal=True`; second call `ctype=None bytes_equal=False`.
   So every repeat download within the 30-day TTL raises `ValueError("... received unknown")`, which
   `unified.download_patent_pdf` treats as "not found" and silently falls through to PPUBS/EPO.
2. **`ttl_seconds` does not make mcp-data-core cache anything (confirmed).** `CacheManager` never
   passes `ttl_seconds` into hishel (`AsyncSqliteStorage(default_ttl=...)` exists but is unused,
   `mcp_data_core/cache.py:120-128`), and hishel 1.2.1's spec policy does not cache responses that
   lack freshness headers. Repro (`scratchpad/refactor/ttl_check2.py`, real `AsyncCacheTransport`
   over MockTransport): no cache headers + `ttl_seconds=600` -> 2 upstream calls; `max-age=600` ->
   1 call. So `ttl_seconds=600/900/21_600` in china_spc_ip_court/client.py:280,
   canada_federal_court/client.py:109, japan_ip_high_court/client.py:202 are no-ops for request
   caching, and google_patents built its own cache because of this gap.
3. **usitc resource getters are broken.** `usitc/resources.py:13-14` reads
   `resources.files("law_tools.usitc.docs")`; `law_tools` is not a dependency.
   `uv run python -c "from patent_client_agents.usitc import get_edis_resource; get_edis_resource()"`
   -> `ModuleNotFoundError: No module named 'law_tools'`. The docs are present locally at
   `usitc/docs/*.md`. Exported from `usitc/__init__.py:5,28-34,67-74` and `usitc/api.py:42-50,80-87`.

Also: `google_patents/client.py:962` awaits `_rate_limit()` (4 s minimum spacing) *before* the
cache lookup, so cache hits are throttled too; and `unified.get_patent_claims` decides "US" with
`startswith("US")` (`unified.py:189`) while `get_patent_claims_clean` uses `_is_us_number`
(`unified.py:305-308`), so a bare `10301023` skips ODP in the default path but not the clean path.

---

## Proposed primitives

Line estimates are from real counts (wc/sed ranges cited). "Saves" means net lines removed after
adding the primitive.

### P1. HTML-to-Markdown: drop markitdown, convert with markdownify (lazy) or lxml

- **Owns:** `html_to_markdown(html) -> str | None` used for Google Patents description HTML,
  plus the existing `_preprocess_patent_html` para-number fixup.
- **Current users:** `google_patents/client.py:16` (`from markitdown import MarkItDown`, eager),
  `:108-121` (`_html_to_markdown` builds a new `MarkItDown()` per patent), `:981`. No other
  markitdown user in src, scripts, or tests. `mcp/tools/patents.py:25` imports
  `GooglePatentsClient` at module top, so markitdown loads at server start.
- **Measured cost:** `import markitdown` = +52.6 MB RSS, 1.06 s (pulls magika -> onnxruntime +
  numpy, bs4, markdownify, requests). `import markdownify` alone = +22.2 MB, 0.31 s.
  `import patent_client_agents.mcp.server` leaves `markitdown` and `onnxruntime` in `sys.modules`.
  Each `MarkItDown()` constructs `magika.Magika()` (loads an ONNX model): 34 ms first, ~5 ms after,
  per patent fetch, for a converter that only ever sees `.html`.
- **Options:** (a) `markdownify.markdownify(html, heading_style="ATX")` imported inside the function:
  the same engine markitdown's HtmlConverter wraps (`markitdown/converters/_markdownify.py`
  subclasses `markdownify.MarkdownConverter` with ATX headings and link tweaks), so output should be
  near-identical; start cost 0, first-use cost 22 MB. (b) A ~40-line lxml converter (p, h1-h6, ul/ol,
  table, sub/sup, br) since lxml is already loaded; zero new deps, but output will differ more.
  (c) Keep markitdown but import lazily and reuse one instance; fixes start cost only.
  Recommend (a).
- **Dependency change:** remove `markitdown[pdf]>=0.1.3` (`pyproject.toml:32`). The `[pdf]` extra
  (pdfminer-six, pdfplumber) is unused: every PDF read in src uses `pypdf`. Add `markdownify`
  explicitly if (a).
- **Lines:** about net 0 in code (−3 import/instance lines, +2 lazy import). The win is ~50 MB and
  ~1 s off server start, and onnxruntime/numpy/pdfminer out of the install.
- **Stays source-specific:** the para-num preprocessing regexes.
- **Risks:** `description_markdown` formatting drift (link style, table rendering, escaping).
- **Coverage:** none. No test touches `_html_to_markdown` or `description_markdown`. Add a golden
  test from a recorded description HTML before swapping.

### P2. Force-TTL caching in mcp-data-core, then delete google_patents/cache.py

- **Owns:** a `ttl_seconds` that actually caches (hishel `FilterPolicy`/custom `CachePolicy` that
  treats 200 responses as fresh for N seconds, plus `AsyncSqliteStorage(default_ttl=...)`), stored
  as bytes with headers.
- **Current users:** `google_patents/cache.py` (207 lines: `PatentCache`, `CachingAsyncClient`,
  `build_cached_http_client` shadowing the core function of the same name);
  `google_patents/client.py:72-79,962-966,1208-1209,1316`; the three no-op `ttl_seconds` callers
  above. `GooglePatentsClient` (`client.py:1083-1104`) is not a `BaseAsyncClient` and opens a new
  httpx client per call.
- **Lines:** delete cache.py 207, `_build_http_client` 8; add ~25 in mcp-data-core. Moving the
  `_rate_limit()` call after the cache check needs the cache lookup to happen first, which the core
  transport does naturally if the throttle lives in a request hook. Saves ~190 src lines;
  `tests/google_patents/test_cache.py` (259) shrinks to a ~40-line core test: ~−220 test lines.
- **Minimal alternative if mcp-data-core cannot change now:** store `response.content` (BLOB) and
  `content-type` in `PatentCache`, ~+10 lines; fixes the PDF bug only.
- **Stays source-specific:** Google's 4 s spacing and 90 s 503 cooldown.
- **Risks:** cache DB filename changes (`google_patents_html.db` -> new), so first run is cold;
  forced caching in core must stay opt-in per client or it will start caching connectors that
  currently refetch every time (that may be what the ttl callers intended, but confirm).
- **Coverage:** test_cache.py covers PatentCache mechanics only; nothing covers binary bodies or
  header preservation. Add both.

### P3. Delete the deprecated `client=` paths in api.py (or replace with one helper)

- **Owns:** nothing if deleted; otherwise `borrow_client(client, factory)` async context manager
  that yields the passed client or a fresh owned one.
- **Current users in my slice:** `google_patents/api.py:15-18,194-200,239-241,267-269,324-326,
  413-415`; `usitc/api.py:18-21,111-145` (four identical `_warn_*_deprecated` functions) and nine
  branches; `uspto_publications/api.py:18,76-82` and five branches. Counted by script
  (`scratchpad/refactor/depcount.py`): google 32, usitc 80, PPUBS 49 = **161 lines**, plus ~15
  lines of "Legacy" module docstrings.
- **Repo-wide (other slices):** same pattern in epc 26, uspto_applications 69, epo_ops 119, cpc 45,
  mpep 26, uspto_petitions 25, uspto_bulkdata 18, ukipo_mopp/epo_up_guidelines/epo_case_law/
  epo_guidelines/epo_pct_guidelines 26 each = ~620 total, ~690 with docstrings. Version is 0.30.0;
  the warning says "removed in v1.0".
- **Consumers:** no in-repo src caller passes `client=`. law-tools (`tools/law-tools/src`) imports
  classes only. Tests use it as a fake-client seam: `tests/google_patents/test_api.py:83,91,97,112`,
  `tests/usitc/test_api.py:47,64,99,109,131,142`. Those need `monkeypatch.setattr(api,
  "GooglePatentsClient", Fake)` instead.
- **Saves:** 161 src (my slice), ~690 repo-wide.
- **Risks:** external callers (PyPI users) on the deprecated path break; it is a breaking change
  either at 1.0 or now with a changelog entry.
- **Coverage:** the test_api files above, after rewrite.

### P4. Google Patents: replace 15 hand-written dict-to-model builders

- **Owns:** `_rows(Model, rows, key) -> list[Model]` = `[Model.model_validate(r) for r in rows if
  r.get(key)]`, with lenient field validators where the builders currently do `isinstance` checks.
- **Current users:** `google_patents/client.py:246-521` (276 lines: `_build_citations`,
  `_build_citations_simple`, `_build_family_members`, `_build_country_filings`,
  `_build_priority_applications`, `_build_legal_events`, `_build_non_patent_literature`,
  `_build_concepts`, `_build_landscapes`, `_build_definitions`, `_build_child_applications`,
  `_build_detailed_npl`, `_build_chemical_data`, `_build_external_links`), consumed at
  `client.py:1055-1078`. The parser stage (`parsers/metadata.py`) already returns dicts keyed by the
  model field names.
- **Saves:** ~240 src lines (keep ~35: the helper, `country_filings` int coercion, the
  `examiner_cited` bool path). `tests/google_patents/test_builders.py` (390 lines, 35 tests) could
  drop to a parametrized ~150.
- **Stays source-specific:** the 50-field `PatentData` assembly.
- **Risks:** builders silently drop non-str values; `model_validate` would raise. Use
  `BeforeValidator` coercers or `extra="ignore"` + `str | None` with a to-None coercer.
- **Coverage:** test_builders.py (35 tests) and test_models.py (319 lines) protect it.

### P5. unified.py cascade steps

- **Owns:** `_pdf_from_ppubs(n)`, `_pdf_from_epo(n)`, `_claims_from_odp(n)`, and one
  `_first_success(steps, label)` runner that collects `tried` and raises the `NotFoundError`.
- **Current users:** PPUBS step duplicated at `unified.py:467-484` and `530-547`; EPO step at
  `486-502` and `549-565`; ODP step at `188-204` and `243-259`; filename imports repeated in both
  PDF functions (`430-438`, `521-526`).
- **Saves:** ~55 lines. Also fixes the `startswith("US")` vs `_is_us_number` inconsistency by
  using one predicate.
- **Second, riskier consolidation:** `_ppubs_claim_texts` + `_CLAIM_REF_RE` (`unified.py:301-357`)
  re-parse `claims_text` that `uspto_publications/transformers.py:250-262` already parses with
  `ClaimsParser` (`uspto_publications/utils.py:44-100`) from `claimsHtml`. Two parsers, two
  algorithms, same field. unified's handles reissue `.Iadd.` and unnumbered design claims;
  ClaimsParser handles ranges like `2-5.`. Pick one (~45 lines).
- **Risks:** low for the step extraction; the claim-parser merge changes claim boundaries.
- **Coverage:** `tests/test_unified_pdf_cascade.py` (4 tests), `tests/test_unified_clean_sources.py`
  (12 tests incl. reissue/design claim splitting). Add a bare-number test for the non-clean path.

### P6. Shared lenient model types for JSON connectors

- **Owns:** `IsoDate = Annotated[date | None, BeforeValidator(parse_iso_date)]` and
  `PassthroughModel(BaseModel)` with `model_config = ConfigDict(populate_by_name=True,
  extra="allow")`.
- **Current users:** identical `_parse_iso_date` at `prh_fi/models.py:30-45` and
  `prv_se/models.py:24-39` (symilar hit); 11 `@field_validator(..., mode="before")` blocks that only
  call it (prh_fi 5, prv_se 6); `model_config = _BASE_CONFIG` on 16 prh_fi and 15 prv_se classes;
  `model_config = {"populate_by_name": True}` on 5 canada_federal_court classes.
  Repo-wide: 156 `model_config =` lines; same `_BASE_CONFIG` idiom in tipo_opdata (24), euipo_* (17),
  ip_australia_* (11), ilpo_tm, inpi_br_bulk; inpi_pi and kipo_kipris have their own date coercers.
- **Saves:** ~16 (dup parser) + ~50 (validators) + ~40 (config lines incl. blank) = ~105 in my
  slice; ~200 more repo-wide.
- **Risks:** low; inpi_pi's parser also accepts `YYYYMMDD` and sentinels, so a shared parser should
  take formats as an argument rather than merge semantics.
- **Coverage:** tests/prh_fi/test_models.py, tests/prv_se/test_models.py.

### P7. Small BaseAsyncClient fixes in mcp-data-core that remove per-connector workarounds

- **(a) Absolute URL passthrough** in `_build_url` (`base_client.py:228-230`). Overrides doing
  exactly that: `prh_fi/client.py:363-366`, `prv_se/client.py:158-161`, plus
  `uspto_odp/clients/base.py:222`, `epo_ops/client.py:242` (other slices). It also lets
  `cafc/client.py:237-241` and `upc_decisions/client.py:361-363` go through `self._request` instead
  of raw `self._client.get`, which today bypasses retry and (cafc) raises bare
  `httpx.HTTPStatusError` instead of the typed hierarchy. Saves ~10 lines here, ~20 repo-wide.
- **(b) Injected-client headers.** `base_client.py:147-150` uses `setdefault`, which never overrides
  httpx's default `User-Agent`/`Accept`. china_spc (`client.py:282-283`) and japan
  (`client.py:204-205`) patch with `client.headers.update(...)`; canada_federal_court
  (`client.py:108-110`) does not, so its tests send different headers than production. Use update
  for caller-supplied keys. Saves 4 lines; removes a test/prod divergence.
- **(c) `fetch_document(url, *, expect="pdf", context, output_path=None) -> bytes`**: GET absolute
  URL, typed errors, `%PDF` magic or content-type check, optional write. Users: cafc
  `download_pdf` (`cafc/client.py:216-248`), upc_decisions `download_pdf` (`:351-363`), google
  `download_patent_pdf` (`:1301-1325`). Saves ~25 lines.
- **Risks:** (a) and (b) touch every connector through the base class; run the full suite.
- **Coverage:** cafc test_exact_document.py, upc test_parser.py (download not tested),
  google test_api.py via fake, test_unified_pdf_cascade.py.

### P8. One desktop-browser header constant

- **Owns:** `DESKTOP_CHROME_UA` and `browser_headers(*, accept, language, referer)`.
- **Current users (four different Chrome versions):** google `cache.py:183-188` (Chrome/127),
  cafc `client.py:31-37` (136.0.0.0), canada `client.py:30-37` (136.0), china `client.py:29-37`
  (136.0), PPUBS `client.py:28-39` (114). upc_decisions has its own `DEFAULT_USER_AGENT` (`:42`).
  Note mcp-data-core deliberately defaults to the httpx UA because Akamai sites reject a browser UA
  with httpx's TLS fingerprint (`cache.py` comment), so this constant is opt-in only.
- **Saves:** ~15 lines; one place to bump the version.
- **Risks:** changing a UA string can flip a WAF decision; keep each site's current value until
  verified live.
- **Coverage:** china/japan/canada test_client.py assert headers.

### P9. Package doc resources

- **Owns:** `read_package_doc(package: str, name: str) -> str`.
- **Current users:** 28 `resources.py` modules (988 lines total) each wrapping
  `resources.files(pkg.docs).joinpath(x).read_text()`. Mine: usitc (30, broken, see finding 3),
  uspto_publications (24), wipo_lex (15). No MCP tool calls these getters; they are library API
  plus a few tests (`tests/dpma_statutes/test_api.py:63` etc.).
- **Saves:** ~20 here, ~150 repo-wide.
- **Risks:** none beyond the usitc fix.
- **Coverage:** usage-resource tests exist only for corpus packages; add one for usitc.

### P10. Patent-number parsing (one parser, per-source formatters)

- **Owns:** `parse_publication_number(s) -> (country, serial, kind)` plus `.google()`, `.ppubs()`,
  `.is_us`.
- **Current users:** `google_patents/client.py:910-929` (`_normalize_patent_number`: US prefix,
  pgpub zero-pad, 2-digit WO year), `uspto_publications/utils.py:113-149`
  (`normalize_publication_number`: strip country/kind, docdb pgpub expand), `unified.py:297-308`
  (`_is_us_number`) and `:189` (`startswith("US")`); outside my slice
  `mcp/tools/patents.py:63` (`_country_from_publication_number`), `mcp/tools/epo_ops.py:275`,
  `uspto_odp/client.py:145` and `uspto_odp/clients/base.py:228` (application numbers).
- **Saves:** ~40 lines here. The value is one definition of "is this a US number".
- **Risks:** high; each source's quirks are encoded in these. Google's normalizer has no test.
- **Coverage:** tests/uspto_publications/test_utils.py (33 tests). Add a table test for Google's.

### P11. Optional: interval throttle

`google_patents/client.py:36-69` (module-global lock/timestamps/cooldown) and
`inpi_pi/client.py:~160-245` (instance throttle with injectable clock) both implement min-interval
spacing. A `MinIntervalThrottle(interval, cooldown, clock)` in mcp-data-core would save ~20 lines.
Low priority; only two users.

---

## Test scaffolding

### T1. `mock_http` helper / fixture
`httpx.AsyncClient(transport=httpx.MockTransport(handler))` plus a `captured` list appears 142 times
in 34 files (e.g. `tests/china_spc_ip_court/test_client.py:13-24`,
`tests/canada_federal_court/test_client.py:69-80`, `tests/japan_ip_high_court/test_client.py:20-28`).
85 hand-rolled `Dummy*/Fake*/Stub*` classes, heaviest in usitc (9), epo_ops (8), uspto_tmsearch (6).
A root-conftest `mock_http(responses|handler) -> (client, captured)` saves ~2-3 lines per use:
**~250-300 lines**. Low risk.

### T2. One parametrized "no batch_* tools" contract test
`test_no_batch_tool_present` is copied into 20+ `test_mcp_envelope.py` files (e.g.
`tests/copyright/test_mcp_envelope.py:217-222`). Some check `dir(module)` for any `batch_` name, some
(cafc `:207-213`) only check three hard-coded names. One test iterating every
`patent_client_agents.mcp.tools.*` module is stronger and saves **~130 lines**.

### T3. JSON fixture loader
`tests/prh_fi/conftest.py` and `tests/prv_se/conftest.py` (45 lines each) are the same file with
different filenames. A root `json_fixture(name)` fixture or `load_fixture(__file__, name)` saves
**~75 lines**.

### T4. Corpus fixture factory (tests for other slices' connectors)
`dpma_statutes`, `ipo_in_statutes`, `legifrance_ip`, `tw_trade_secrets`, `ipo_in_mppp` conftests
(31/31/31/31/28 lines) differ only in module, filename, and env var. A
`make_corpus_fixtures(prefix, build_corpus, env_var)` factory that returns the two named fixtures
saves **~110 lines**. The hand-authored-row conftests (mpep, tmep, epo_*, ukipo_mopp,
inpi_br_statutes, 72-97 lines) can share only the env fixture (~6 lines each).

### T5. Corpus-status contract tests (largest test win; other slices' connectors)
18 `test_corpus_status.py` files, **1,811 lines**, same six-test shape (dict with two keys, version
fallback, synced_at normalized, missing corpus -> unknown, source_version preferred, bad date
tolerated). Expected values differ per corpus (e.g. mpep expects `"unknown"`, dpma expects
`snapshot-...`), so a shared contract module needs a per-corpus expectations row. Estimate
**~1,300 lines saved** (18 x ~100 -> ~150 shared + 18 x ~10 config). Coordinate with the corpus agent.

### Root conftest and cassettes
`tests/conftest.py` (461 lines) is mostly VCR setup and JPO/EUIPO token scrubbers; only 9 test files
use `vcr_cassette`/`pytest.mark.vcr` and the 88 cassettes (15 MB) are JPO/USPTO/EUIPO. Nothing in my
scraper packages uses cassettes; they use MockTransport. No change proposed beyond T1.

symilar over tests/ + scripts/ (`scratchpad/refactor/symilar_tests_scripts.txt`): 630 duplicate
lines of 58,677 (1.07%), concentrated in corpus status/build tests (T5).

---

## Dead or legacy code that can simply go

| Item | Location | Lines | Notes |
|---|---|---|---|
| Unused GooglePatentsClient methods | `google_patents/client.py:1126-1157` `get_patent_details`, `:1232-1253` `get_patent_claims`, `:1254-1266` `get_structured_claim_limitations`, `:1267-1275` `get_patent_pdf_url` | ~76 | No caller in src, tests, or law-tools/src. MCP re-implements `get_patent_details` (`mcp/tools/patents.py:114-118`). Public API, so changelog it. |
| Redundant alias + empty block | `client.py:1112-1113` `_get_patent_data` (same as `get_patent_data`; `unified.py:207` calls the private one), `client.py:19-20` empty `TYPE_CHECKING` | ~6 | |
| Duplicate `_clean_list` | `google_patents/api.py:203-214` vs `client.py:654-662` | ~10 | |
| Broken usitc resources | `usitc/resources.py` + exports | 30 + 16 | Fix path to `patent_client_agents.usitc.docs` or delete. |
| Deprecated `client=` paths | see P3 | 161 (690 repo-wide) | |
| Stale AGENTS.md lines | `AGENTS.md:117-118` describe `archive/` (patentsview) | 2 | `archive/` no longer exists. |
| Unused runtime deps | `pyproject.toml`: `markitdown[pdf]` (P1), `python-dateutil` and `pyyaml` (no src import; only scripts/tests -> dev group), `zstandard` (only used by mcp-data-core, which declares it), duplicate `tenacity>=8.4` line (`:28-29`) | — | |
| Unwired scripts | `scripts/lint_catalog.py` (passes "OK", not in CI), `verify_connector.py` (referenced from research/RUNBOOK only), `probe_wipo_publish.py`, `build_profiles_snapshot.py` (no references) | 910 | Not dead code; decide wire-into-CI or delete. `src/patent_client_agents/catalog/` (30 md files) is still being edited (2026-09-14) and is shipped, so keep. |

## Considered and rejected

- Generic lxml selector module: google_patents has 144 `.xpath(` calls and its own
  `_first_text/_first_attr` helpers; china_spc (13), upc (7), wipo_lex (4) are lean. Moving
  google's helpers saves ~20-30 lines. Not worth it.
- Shared whitespace collapse: ~2-line helpers in upc_decisions `:81`, PPUBS utils `:37`, china
  `:84` (different: removes all whitespace). 46 inline `re.sub(r"\s+", " ", ...)` repo-wide, mostly
  corpus builders. Trivial savings.
- Shared result models for courts: case/party/docket models in canada, china, japan, upc, cafc
  differ in substance; a common base would be cosmetic.
- `__init__.py` re-exporting `api.__all__`: symilar flags it in usitc, upc_decisions,
  canada_federal_court, wipo_lex, uspto_publications, prh_fi. `from .api import *` with `__all__`
  saves ~10 lines per package but obscures the public surface; optional.
- Session bootstrap primitive (lazy page visit for nonce/cookie/token, refresh on 401/403): PPUBS
  (`client.py:170-214`), cafc (`:98-101,254-276`), plus inpi_pi and uspto_tmsearch in other slices.
  Patterns differ enough that a shared helper saves ~40 lines at real risk. Defer.

## Totals

Source, my slice: P2 ~190, P3 161, P4 ~240, P5 ~55 (+45 optional), P6 ~105, P7 ~40, P8 ~15, P9 ~20,
P10 ~40, dead code ~110 => **~975 src lines** (about 8% of the 12,670-line slice), plus P1's
~50 MB / ~1 s server-start saving and dependency removal.
Tests: T1 ~275, T2 ~130, T3 ~75, T4 ~110, T5 ~1,300, plus ~220 (cache) and ~240 (builders)
=> **~2,350 test lines**, of which ~1,400 (T4/T5) are tests of other slices' corpus connectors.
Cross-slice extras if the shared primitives are applied everywhere: P3 ~530, P6 ~200, P9 ~130,
P7a ~10 => ~870 more src lines.

## Suggested order

1. Fix the three bugs (PDF cache bytes, usitc resource path, US-number predicate) with tests.
2. P1 (golden test first), P4, P5, dead-code deletions: self-contained, well covered.
3. P2 + P7 in mcp-data-core (needs a release of that package, then a dep bump here).
4. P3 at a deliberate breaking-change release.
5. T1-T5 alongside whichever package is being touched.
