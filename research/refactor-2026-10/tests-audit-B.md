# Test audit B (all six batches merged: 38 directories)

## Totals (tests, lines) by verdict and per directory
```
rows 441
mismatch []
{'REWRITE': [574, 7438], 'DELETE': [179, 1273], 'KEEP': [635, 5670]}
cafc {'KEEP': [35, 142], 'REWRITE': [27, 265]}
canada_federal_court {'KEEP': [10, 123], 'REWRITE': [5, 99]}
canlii {'KEEP': [17, 170], 'REWRITE': [27, 435], 'DELETE': [4, 35]}
china_spc_ip_court {'KEEP': [10, 85], 'REWRITE': [3, 58]}
copyright {'KEEP': [9, 85], 'REWRITE': [12, 157]}
cpc {'DELETE': [14, 43], 'REWRITE': [15, 214]}
dpma_register {'DELETE': [6, 38], 'KEEP': [12, 99], 'REWRITE': [9, 177]}
euipo_designs {'REWRITE': [8, 108], 'KEEP': [6, 67], 'DELETE': [2, 17]}
euipo_trademarks {'REWRITE': [11, 142], 'KEEP': [10, 96], 'DELETE': [2, 15]}
ilpo_tm {'DELETE': [1, 4], 'KEEP': [3, 70], 'REWRITE': [5, 85]}
inpi_br_bulk {'DELETE': [2, 6], 'KEEP': [3, 65], 'REWRITE': [5, 91]}
inpi_pi {'REWRITE': [35, 321], 'DELETE': [14, 83], 'KEEP': [98, 828]}
ip_australia_bulk {'DELETE': [1, 4], 'KEEP': [3, 65], 'REWRITE': [5, 101]}
ip_australia_designs {'REWRITE': [7, 103], 'KEEP': [5, 106]}
ip_australia_patents {'KEEP': [6, 109], 'REWRITE': [7, 122]}
ip_australia_trademarks {'REWRITE': [7, 107], 'KEEP': [5, 108]}
ipi_swissreg {'DELETE': [8, 56], 'REWRITE': [21, 326], 'KEEP': [2, 30]}
iponz_new_zealand {'DELETE': [7, 56], 'REWRITE': [23, 246], 'KEEP': [6, 50]}
japan_ip_high_court {'REWRITE': [8, 110], 'KEEP': [3, 28]}
kipo_kipris {'REWRITE': [34, 386], 'KEEP': [51, 524], 'DELETE': [25, 119]}
oepm_spain {'DELETE': [3, 31], 'KEEP': [12, 131], 'REWRITE': [5, 87]}
patent_client_agents {'KEEP': [6, 76], 'REWRITE': [21, 321]}
prh_fi {'KEEP': [26, 151], 'REWRITE': [20, 261], 'DELETE': [1, 5]}
prv_se {'REWRITE': [10, 123], 'KEEP': [37, 356]}
thai_dip {'DELETE': [9, 81], 'REWRITE': [30, 239], 'KEEP': [6, 42]}
tipo_opdata {'DELETE': [23, 113], 'REWRITE': [31, 295], 'KEEP': [44, 569]}
upc_decisions {'KEEP': [10, 58], 'REWRITE': [8, 132]}
usitc {'REWRITE': [45, 622], 'DELETE': [21, 104], 'KEEP': [46, 373]}
uspto_applications {'DELETE': [4, 54]}
uspto_assignments {'DELETE': [3, 52], 'KEEP': [14, 150], 'REWRITE': [9, 111]}
uspto_bulkdata {'DELETE': [2, 40]}
uspto_office_actions {'REWRITE': [16, 416], 'KEEP': [3, 59], 'DELETE': [3, 30]}
uspto_petitions {'DELETE': [4, 57], 'REWRITE': [5, 84]}
uspto_publications {'REWRITE': [63, 604], 'DELETE': [3, 34], 'KEEP': [98, 426]}
uspto_tmsearch {'KEEP': [26, 254], 'REWRITE': [17, 245], 'DELETE': [6, 54]}
uspto_trademark_assignments {'DELETE': [7, 93], 'REWRITE': [8, 104], 'KEEP': [2, 18]}
uspto_tsdr {'KEEP': [6, 68], 'REWRITE': [4, 23], 'DELETE': [3, 33]}
wipo_lex {'KEEP': [5, 89], 'DELETE': [1, 16], 'REWRITE': [8, 118]}
```

## Batch A notes
# Batch A notes: tests/inpi_pi, tests/usitc

259 collected tests, 73 CSV rows. KEEP 144 tests / 1201 lines, REWRITE 80 / 943, DELETE 35 / 187.
Counts per file match collect_by_file.txt (checked by build_A.py).

Absolute-URL check: neither connector passes an absolute URL to `_request`/`get`.
INPI overrides `_request` and builds `f"{self.base_url}{path}"` from relative paths
(client.py:346); session.py builds its own URLs from `base_url.rstrip('/')`. USITC
clients all pass relative paths. No `_build_url` bug here.

## tests/inpi_pi

Worst offenders
- `test_api.py` (5 tests): monkeypatches `api_mod.InpiPiClient` with a hand-rolled fake and checks kwargs pass-through. This tests the wrapper layer that one_shot() replaces.
- `test_mcp_envelope.py` (17 tests): every tool test monkeypatches the module-level `InpiPiClient` to return `_FakeRow` objects, not the real `InpiTrademarkRow`/`InpiDesignRow`. So `model_dump(by_alias=True)` on real models (dates come back as `date` objects) is never exercised. The fixture also does an `importlib.reload` per test.
- `test_env_gating.py` (6 tests): reload-based, with a teardown that doesn't restore anything (see SUSPECT).
- `test_models.py`: 8 of 29 tests only restate Pydantic config (defaults, extra=ignore, populate_by_name, passthrough).
- `test_resources.py`: tests a stub string and a constant.

DUPLICATE-CONTRACT
- `test_mcp_envelope.py::test_search_trademarks_envelope_shape` and `test_search_designs_envelope_shape` (2 tests, ~27 lines) check isinstance ListEnvelope/Provenance plus source_name. A registry-wide parametrized contract test would cover them. Keep the INPI-specific attribution string ("licence INPI") and provenance path as table data.
- The lean/full projection tests (5 tests, ~52 lines) follow the same shape for every connector. One parametrized `(tool, full)` test per connector would do, ideally fed by real models.

GAPS
- `_build_solr_query` always emits `MarkCurrentStatusCode:` for `status`, including from `search_designs` (client.py:149-150). Its own docstring says designs use `DesignCurrentStatusCode`. No test calls `search_designs(status=...)`. This is probably a live bug.
- The proactive refresh path (`_ensure_session` -> `is_expired` -> `_refresh_or_relogin`) has no test at client level. Neither does "refresh fails -> fresh XSRF + login". `test_session.py`'s docstring lists "refresh fails -> caller falls back" as covered, but no test does it.
- 401 retry (`test_401_retries_with_fresh_session`) asserts only attempt count >= 2, with the bearer check disabled. It never shows a second login happened or that the retry carried the new token.
- No test checks the request shape of search: the exact `q`, `offset`, `limit`, and full path. The happy path asserts only `"q" in params`.
- Throttle across calls: the MCP tools build a new `InpiPiClient` per call (mcp/tools/inpi_pi.py:174,232,294,346). The 10 req/min throttle and the session are therefore per call, and every tool call costs 2 extra auth requests. No test pins down the intended behavior (PLAN item 8).
- XML parse errors surface as raw `ET.ParseError` from `get_trademark`/`get_design` (not mapped to ApiError). The current tests treat that as correct.
- A 404 on a notice is surfaced as generic `ApiError`, not NotFound. Untested.

SUSPECT
- `tests/inpi_pi/test_env_gating.py:47-51`: `fresh_state(monkeypatch)` depends on monkeypatch, so its teardown runs before monkeypatch restores env. The "restore" reload happens under the test's env (e.g. both vars unset), and the module is left with no tools registered. The comment claims it restores conftest state.
- `tests/inpi_pi/test_client.py:761-764` `test_search_envelope_dict_alone_yields_no_rows`: the name and docstring say "{'unknown': [...]} -> empty", but it only asserts the `docs` key case. That duplicates `test_numfound_envelope`.
- `tests/inpi_pi/test_client.py:676-694` (429, 5xx): each takes ~4-5 s because `default_retryer` really sleeps between retries of RateLimitError/5xx. They pass but slow the suite and don't assert the retry count.
- `tests/inpi_pi/test_client.py:715` has an unused `monkeypatch` param. Harmless.

## tests/usitc

Worst offenders
- `test_date_filtering.py::TestSearchUsitcDocumentsDateFiltering` (5 tests, ~120 lines): every test copies the filter loop into the test body and asserts on that copy. `search_usitc_documents` is never called. These are worthless as written. REWRITE them to drive the tool.
- `test_api.py` (9 tests): all go through the deprecated `client=` path with DummyClient, which emits a DeprecationWarning. The non-deprecated `async with Client()` branch of every helper is untested.
- `test_mcp_envelope.py`: `unittest.mock.patch` on the module `EdisClient`/`HtsClient`/`DataWebClient` with AsyncMock. The `get_usitc_investigation` tests use a positional `side_effect` that ignores the argument (see SUSPECT).
- `test_utils.py` and `test_transformers.py` test dead code: `coerce_bool`, `_bool`, and the `*_BASE_URL`/`IDS_URL` constants are unused in src.
- `test_env_gating.py`: reload-based, pokes private `downloads._SOURCES`, and has the same teardown-order problem as INPI.

DUPLICATE-CONTRACT
- `test_mcp_envelope.py`: the envelope/provenance assertions in 5 tool tests (~120 lines total; only part of each is contract). Also `test_docstring_ends_with_related_tools[5]`, `test_run_dataweb_report_first_sentence_passes_elevator_test`, and `test_no_batch_tool_present`. That's 7 collected items (~27 lines) that registry-wide docstring/naming contract tests would replace. The batch test only checks three hard-coded names.

GAPS
- `EdisClient.download_attachment` stores the raw `Content-Disposition` header as `filename` (usitc/client.py:146-153). That gives e.g. `attachment; filename=test.pdf`. `_fetch_usitc_attachment` returns it as the filename, and `download_usitc_attachment` derives the extension with `PurePosixPath(...).suffix`, which yields `pdf"` for a quoted filename. `test_download_attachment` doesn't assert the filename, so this goes unnoticed.
- No test for `download_usitc_attachment`, `download_usitc_investigation_documents` (item_ids fast path, the 25-attachment cap, parallel page walk stopping at the first empty page, type/date filters), `search_usitc_documents` (either branch), `list_ids_investigations` (filters, offset/limit, participant exclusion), or `_fetch_usitc_attachment` path parsing.
- No test that `Authorization: Bearer` is sent when `USITC_EDIS_TOKEN`/`USITC_DATAWEB_TOKEN` is set, or omitted when unset.
- `DataWebClient.get_all_countries` and `get_global_vars` have no tests and no callers.
- `run_dataweb_report` never checks the request body `build_dataweb_query` produces, because DataWebClient is patched.
- `usitc/resources.py` reads `law_tools.usitc.docs`, a package that doesn't exist here (PLAN item 10). No test calls `get_*_resource`, so the import error stays hidden.
- Env-name mismatch: `utils.IDS_URL` reads `USITC_IDS_URL`, but `IdsClient` reads `USITC_IDS_BASE_URL`. The tested constant is not what the client uses.
- No test covers error mapping (4xx/5xx -> ApiError, Akamai 403/503 HTML) for any USITC client.

SUSPECT
- `tests/usitc/test_date_filtering.py:40-177`: the five date-filter tests re-implement the filtering inline, so they pass no matter what the tool does. They're also marked `@pytest.mark.asyncio` but contain no awaits.
- `tests/usitc/test_mcp_envelope.py:164-190`: `AsyncMock(side_effect=[...])` returns canned rows by call order and ignores `investigation_number`. If the tool fetched the wrong number, or the same one three times, the tests would still pass. The "preserves order" assertion only checks the mock's own order.
- `tests/usitc/test_client.py:190-223`: URL assertions are suffix-only (`endswith("/investigation/337-1234")`). This is correct today because the paths are relative, but it would not catch a dropped `/data` base segment or a doubled base URL. Assert the full path.
- `tests/usitc/test_env_gating.py:57-72`: `fresh_state` is torn down before monkeypatch undo (both are function fixtures and fresh_state was requested after it). The reload labelled "under the conftest's env" actually runs under the test's env, e.g. with the token deleted, which leaves `_EDIS_ENABLED=False` in the reloaded module.
- `tests/usitc/test_client.py:315-334`: sets `client._token` directly after construction even though the env var is already set, so the env-driven auth path is never shown to work on its own.

## Batch B notes
# Batch B notes: kipo_kipris, tipo_opdata, canlii

256 collected tests across 11 files; per-file sums match collect_by_file.txt.
Totals: KEEP 112 tests / 1263 lines, REWRITE 92 / 1116, DELETE 52 / 267.
CSV: parts/B.csv (53 rows). Generator: parts/gen_B.py, node ids: parts/B_nodeids.txt.

No connector in this batch passes an absolute URL into BaseAsyncClient._request/_build_url.
TIPO and CanLII call `_request_json` with relative paths. KIPO bypasses `_request` entirely
(see below), building `f"{self.base_url}/{service}/{operation}"` and calling `self._client.get`
directly, so `_build_url` is not involved.

## tests/kipo_kipris

- Worst offenders
  - `test_mcp_envelope.py`: every tool test runs under a fixture that `importlib.reload`s the tool
    module after rebinding `kipo_kipris_mcp`. It then monkeypatches `kipo_kipris.api.search_*` or the
    `KiprisClient` symbol to return canned dicts. Nothing touches the transport or the XML fixtures.
  - `test_api.py` (9 tests): AsyncMock delegation checks on api.py. The MCP search tools do call
    api.py through `__import__`, so this is the only coverage of that hop. Marked REWRITE, not DELETE.
  - `test_models.py`: 38 tests for 3 flat row models. Date validation is tested three ways: 14
    TestParseKiprisDate tests, 6 parametrized model-level tests, and 3 more copies in test_client.py.
    `_empty_str_to_none` is tested both directly and through the models. Pydantic-config tests
    (all-Optional, extra=ignore, populate_by_name) are DELETE.
- DUPLICATE-CONTRACT: 15 tool tests in `test_mcp_envelope.py` (about 230 lines) assert
  ListEnvelope/Provenance shape plus content. The shape part belongs in the registry-wide
  contract test. About 4 KIPO content tests stay: lean/full projection, more_available math,
  list fan-out, right_type mapping.
- GAPS
  - KIPO `_get` re-implements retry and error mapping instead of using `BaseAsyncClient._request`.
    5xx raises plain `ApiError`, not `ServerError`; 401/403/404 are not typed. No test covers
    401/403/404 or verifies retry count.
  - Request URL host is never asserted. All client tests check the substring `f"/{SERVICE}/{op}"`
    in `str(req.url)`.
  - `get_kipo_trademark`/`get_kipo_design` say "application or registration number" but only send
    `applicationNumber`. Untested.
  - `paginate()` has no production caller; its 3 tests cover library-only surface.
- SUSPECT
  - `test_mcp_envelope.py:179,261,328,343,388,404,479` and `:437-442`: these assert the
    provenance URL by substring or `endswith`. Provenance is built from the hard-coded
    `BASE_URL = "http://kipo-api.kipi.or.kr/..."` (mcp/tools/kipo_kipris.py:83). That is the
    cleartext endpoint the client refuses to call, not the operator HTTPS URL actually used. The
    tests pass while the advertised source URL is the disabled http endpoint.
  - `test_client.py:551-576`: the two error tests each sleep about 4 s in real tenacity backoff
    (measured 4.07 s and 4.54 s). They don't assert attempt count.
  - `test_mcp_envelope.py:111`: the fixture sets only `KIPO_KIPRIS_API_KEY`. Tool registration
    still works only because root conftest sets `KIPO_KIPRIS_BASE_URL`. The tests call the
    functions directly, so registration is never exercised here.

## tests/tipo_opdata

- Worst offenders
  - `test_api.py` (17 delegation tests plus 2 resource tests): pure mock-vs-mock, and
    `tipo_opdata/api.py` is not used by the MCP tools at all. DELETE.
  - `test_mcp_envelope.py` "smoke for coverage" block (9 tests, lines 314-386): each mocks a
    client method and asserts a provenance substring. Provenance comes from a hard-coded
    `_TIPO_BASE` in the tool module, so the tests can't detect a tool calling the wrong client
    method or endpoint.
- DUPLICATE-CONTRACT: 18 tool tests in `test_mcp_envelope.py` (about 250 lines). The 9 smoke
    tests plus the envelope parts of 9 content tests fold into the registry-wide contract test.
    TIPO content to keep: lean drops `xml-detail-url` and null Latin names recursively,
    applclass label, events-tool `event_type` tagging.
- GAPS
  - No error-mapping test at all: 4xx, 5xx, 429, or a non-OK `status` in the envelope.
  - 14 of 16 per-endpoint client tests never inspect the request. Their handler returns the
    same JSON for any URL, so a wrong endpoint path would pass. The 2 that do check use
    `url.path.endswith(...)`.
  - `search_tipo_patents.more_available` is `len(items) == top`; `total-count` from the envelope
    is discarded by the client. Untested at the edge.
  - MCP fetch tools call client methods with default `top=MAX_TOP` (6000). api.py uses top=100.
    Neither is tested.
- SUSPECT
  - `test_client.py:805-834` (live cassette smokes): assert only `isinstance(rows, list)`. They
    pass on `[]` or a parse regression even though the cassettes hold 2 real rows each.
  - `test_client.py:366`: the endpoint assert is inside the MockTransport handler. It works
    (AssertionError is not retryable, so it propagates), but it is a suffix-only check.
  - `test_mcp_envelope.py:305-306`: the trademark-events order check asserts only
    `appl_order[0] == "T1"`.

## tests/canlii

- Worst offenders
  - `test_client.py` TestModuleLevelApi (9 tests): its own docstring says it is "just execute the
    factory + dispatch path" coverage of api.py. It is still the only coverage of
    `get_citing_cases`/`get_cited_legislations` request parsing, hence REWRITE (move to client level).
  - `test_mcp_envelope.py`: all tool tests `patch(...CanLIIClient)` with `_FakeModel` objects.
    That includes the 4 IP-case fan-out/filter tests, which hold the most valuable CanLII logic.
- DUPLICATE-CONTRACT: 13 tool tests in `test_mcp_envelope.py` (about 300 lines) assert
    `isinstance(ListEnvelope)` and `provenance.source_name == "CanLII (...)"` plus content. The
    shape goes to the registry contract test. About 5 content tests stay: lean key sets,
    full-mode nested case_id, more_available, list order.
- GAPS
  - No env-gating test for CanLII tools (`requires_env=CANLII_API_KEY`), unlike KIPO and TIPO.
  - No HTTP error-mapping test (404/401/429/5xx). Only the 200-with-TOO_LONG path is tested.
  - `CANLII_BASE_URL` is read once at import into the class attribute `DEFAULT_BASE_URL`. Later
    env changes are ignored. Untested and arguably a bug.
  - Pagination (`offset`) and `more_available` are only tested against mocked objects.
- SUSPECT
  - `test_mcp_envelope.py:168`: `assert "2 courts" in result.summary or "2 " in result.summary`
    is near-vacuous.
  - `test_client.py:136`: `url.path.endswith("/caseBrowse/en/")` is a suffix check. Other
    client tests use exact `/v1/...` paths, which is the right pattern. get_case/get_legislation
    tests never check the URL.
  - `test_mcp_envelope.py:524`: `assert kwargs["language"] == "fr"` runs inside a mocked
    side_effect. Fine as written, but it relies on the patch target staying `CanLIIClient`.

## Cross-cutting

- Env-gating via `importlib.reload` (KIPO 5 tests, TIPO 3) should become one registry-wide
  parametrized test using a public server builder.
- The KIPO, TIPO, and CanLII tool modules each have their own list coercion (`_coerce_list`,
  inline empty/cap checks), `_dump`, and provenance helpers. Their tests duplicate across
  connectors and go away once the shared helper exists.
- Date parsers (`_parse_kipris_date`, `_parse_tipo_date`) have 22 single-assert functions
  between them. Each could be one parametrized table.

## Batch C notes
# Batch C audit notes

Scope: tests/uspto_publications, tests/uspto_tmsearch, tests/patent_client_agents/mcp, tests/prv_se.
287 collected tests (280 pass, 7 skipped live_tmsearch). CSV: parts/C.csv (59 rows). Builder: parts/build_C.py (re-runnable; asserts per-file counts and one-row-per-test coverage).

Totals: KEEP 167 tests / 1112 lines; REWRITE 111 / 1293; DELETE 9 / 88.

Absolute-URL check: none of the connectors in scope pass an absolute URL through an unpatched `BaseAsyncClient._build_url`. PPUBS (raw httpx) and TESS (curl_cffi) don't use BaseAsyncClient. `PrvClient` passes absolute URLs but overrides `_build_url` to pass them through (and `DEFAULT_BASE_URL=""`). `_ptab_download_pdf` (mcp/tools/uspto.py:1264) strips the URI down to its path, so the host gets dropped instead (see GAPS). No test in scope checks only a URL suffix. The PRV routing tests check host prefix and path. The PPUBS provenance check `source_url.endswith("/api/patents/highlight")` (uspto_publications/test_mcp_envelope.py:277) is a suffix check on provenance, not on a request.

## tests/uspto_publications

- Worst offenders
  - test_client_reliability.py (11 of 29 tests REWRITE). Every retry, 403-refresh and concurrency test calls private `_request` or `_request.__wrapped__`, swaps `_refresh_session_once` for an AsyncMock, and reads or writes `_case_id`. These are the most valuable invariants in the directory (one session refresh shared by concurrent 403s, the caseId rewritten in the retried body), but any client restructure breaks them. Replace them with an httpx.MockTransport PPUBS fake that drives `search_biblio` and `get_document`. Two of them also sleep about 1s each on the real `with_retry` backoff.
  - test_api.py: all 3 tests go through the deprecated `client=` kwarg. `test_search_delegates` asserts that a fake returning `"ok"` gets returned.
  - test_mcp_envelope.py patches the `PublicSearchClient` class symbol in the tool module and feeds hand-built pydantic fakes. The family-pagination logic (ParseError on inconsistent counts, cursor by family offset) is real and should survive behind a transport-level fake.
  - test_transformers.py: 28 micro-tests cover trivial private helpers (`_coerce_int`, `_normalize_str`, `_ensure_list`, `take_first`, `_split`). One parametrized messy-input test through `convert_biblio` or `convert_document_payload` can replace them.
- DUPLICATE-CONTRACT: 3 tests / 41 lines here: `test_search_full_true_returns_upstream_shape` plus the envelope half of the two single-get tests. The isinstance(ListEnvelope)/Provenance lines inside the 4 search tests also belong to the registry-wide contract test.
- GAPS
  - `resolve_document_by_publication_number` (client.py:420) has no test. It normalizes the number, queries `.pn.`, picks the matching doc, falls back to the first doc, and raises on no hits. It is only ever replaced by fakes.
  - PDF path has no test: `_request_save`, `_poll_print_job` (print-process polling and its 300s timeout -> PublicSearchError), `_download_pdf_bytes` streaming, `download_pdf_base64`, the `resolve_and_download_pdf` wrapper, and the `pca://publications/{n}` fetcher `_fetch_publication_pdf` in mcp/tools/publications.py.
  - The `resolve_publication_number` MCP tool has no test.
  - `get_document` has no test of the highlight request (params, guid in path).
  - No test feeds a full recorded PPUBS search or highlight JSON through the converters. All transformer inputs are hand-built dicts.
- SUSPECT
  - test_utils.py:22-41 (3 tests named "converts br to newlines"). They assert only that `"Line one"` and `"Line two"` are both in the result. They would still pass if `<br>` were dropped with no newline. Assert `== "Line one\n\nLine two"`.
  - test_mcp_envelope.py:280 `test_get_list_fans_out_to_one_call_per_input` duplicates the order test. It checks only mock call args.

## tests/uspto_tmsearch

- Worst offenders
  - test_mcp_envelope.py `_FakeTrademark` (lines 33-41) uses camelCase field names (`serialNumber`, `ownerName`, `filingDate`, `statusCode`). The real `TrademarkSearchResult` dumps snake_case (`serial_number`, `owner_name`, `filed_date`, `status_live`), because `_dump` calls `model_dump()` without `by_alias`. I verified this against the real model. `_stub_trademark(_dump(real))` returns `serial_number=None, registration_number=None, owner_name=None, filing_date=None, status_*=None`; only `wordmark` survives. `_summarize_trademark` prints "(no serial)" and "(no owner)". This is a production bug in the lean `search_trademarks` and `get_trademark` output that the tests hide (see SUSPECT).
  - test_client.py: 7 of 9 tests are live-only and skipped by default. The 2 offline tests call private `_init_session` and `_post` and monkeypatch `client._session.post`.
- DUPLICATE-CONTRACT: 5 TSDR pass-through tests / 65 lines (`get_trademark_status` x2, `get_trademark_documents`, `get_trademark_last_update` x2) only check the envelope, provenance and list order over a patched `TsdrClient`.
- GAPS
  - Nothing offline covers `TmsearchClient`. Untested: `_search` parsing (`hits.totalValue`, the `serialNumber` fallback from `hit.id`, the `size` cap at 500), query construction in `search()` (should/must clauses, live/dead status, ValueError on no criteria), `search_all` pagination (`max_results` truncation, short-page stop, 10000 cap), and the 403 -> token refresh -> retry success path. Only the "refresh impossible" branch is tested.
  - Token manager: no test of the legacy `~/.law-tools` fallback, `PCA_WAF_TOKEN_PATH` resolution, or corrupt JSON in the cache.
  - The `search_trademarks` `paginate_all` and `search_by` branches (owner uses `search_owner`, goods_services is rejected with `paginate_all`) are untested.
- SUSPECT
  - test_mcp_envelope.py:116-126 and 139-140 (lean and full search), 162-163 (summary contains serial), 190 (`r["serialNumber"]` order check). These pass only because of the wrongly shaped camelCase fake. With real `TrademarkSearchResult` objects they fail, which exposes the bug above.
  - test_client.py:61-63 `test_get_by_serial` and 82-83 `test_pagination` put their assertions inside `if`, so they pass vacuously when the API returns nothing. They are live-only.
  - test_client.py:90 `test_raises_without_token_or_playwright` does not clear `PCA_WAF_TOKEN_JSON` or `PCA_WAF_TOKEN_PATH`, so it fails if a developer has a valid token in the env. test_token_manager.py's autouse fixture clears the PCA_* vars but not the legacy `LAW_TOOLS_WAF_TOKEN_JSON` and `WAF_TOKEN_PATH`.
  - test_token_manager.py:118 `test_env_var_wins_when_set` passes only because sorting is stable when both payloads lack `acquired`. It does not show that env takes precedence.
  - The `live_tmsearch` marker is registered in tests/conftest.py, not in pyproject markers. Fine, but the 7 live tests have no cassette (curl_cffi bypasses VCR).

## tests/patent_client_agents/mcp

- Worst offenders
  - test_download_ptab_bulk.py (11 tests) and test_download_file_history.py (10 tests). The assertions are strong outcome checks (filters, caps, zip member names and bytes, partial failure, cache reuse), but both monkeypatch the `UsptoOdpClient` symbol in mcp/tools/uspto.py with hand-built fakes (SimpleNamespace bags for PTAB). The PTAB file also replaces the private `_ptab_download_pdf`. These are the tests the client-factory refactor will break first. Keep the assertions and move the seam to an httpx transport serving recorded ODP JSON.
  - `test_uses_separate_cache_prefix` asserts through private `downloads._cache_get`.
  - Three files snapshot and restore the private `downloads._SOURCES` dict. mcp-data-core should expose a public registry reset or fixture.
- DUPLICATE-CONTRACT: none.
- GAPS
  - `_ptab_download_pdf` (tools/uspto.py:1264) is always stubbed. It keeps only `urlparse(uri).path` and calls `PtabTrialsClient.download_document_pdf(path)` against `base_url=https://api.uspto.gov`. If ODP ever returns a `fileDownloadURI` on another host, the host is silently swapped, and no test would notice. A transport-level test should assert the outgoing URL equals the `fileDownloadURI`.
  - The `download_file_history` real fetcher for `uspto/applications/{app}/documents/{id}` is always replaced via `register_source`.
- SUSPECT: none found. test_lazy_package `test_tool_submodule_import_does_not_construct_complete_surface` took about 22s locally (subprocess import of mcp.tools.cpc). It is worth checking import cost.

## tests/prv_se

- Worst offenders
  - test_mcp_envelope.py repeats the same 10-line MockTransport `_factory` and `monkeypatch.setattr("...mcp.tools.prv_se.PrvClient", ...)` in 7 tests, while the `_mock_client` helper at line 35 is never used. The fake sits at the right boundary (real PrvClient plus MockTransport plus recorded fixtures), but the class-symbol patch will break under the factory refactor. Make it one shared fixture.
  - test_client.py has 6 unit tests of private body builders (`_build_simple_search_body`, `_build_advanced_search_body`). The same properties are visible in the captured request body of the public routing tests.
- DUPLICATE-CONTRACT: 2 tests / 46 lines (`search_prv_trademarks` and `search_prv_designs` envelope tests). The isinstance and provenance lines in the other 5 KEEP tests (122 lines) also belong to the contract test.
- GAPS
  - No test covers HTTP error mapping (4xx/5xx -> ApiError) or the documented HTTP 500 on an empty SPC body.
  - `get_patents` (sequential portfolio fetch) and the api.py module helpers are untested.
  - `more_available` / `total_pages` pagination in the tools is untested.
  - The routing tests are the only guard for absolute-URL handling. If the refactor fixes `BaseAsyncClient._build_url` to pass absolute URLs through and deletes PrvClient's override, keep these.
- SUSPECT
  - The live smoke tests (test_client.py:208-303) assert only `total_hits > 0` and `len <= 2`. A warm hishel cache at `~/.cache/patent_client_agents/prv_se.db` can satisfy them without touching the cassette.
  - test_mcp_envelope.py:258 `test_search_prv_spcs_rejects_empty_filters` locks in a bare ValueError from the client rather than the tool-level ValidationError other tools raise.
  - test_models.py:100 `test_registry_entry_date_alias` covers a Pydantic alias on a synthetic dict. Better to assert `entry_date` on the real fixture.

## Batch D notes
# Batch D audit notes

Scope: tests/uspto_office_actions, prh_fi, cafc, ipi_swissreg, copyright, thai_dip, iponz_new_zealand.
264 collected tests (all pass in replay). KEEP 87 tests / 559 lines, REWRITE 149 / 1910, DELETE 28 / 228.

Cross-cutting: no connector in this batch hands an absolute URL to `BaseAsyncClient._request` without protection. PRH (`prh_fi/client.py:363`) and USPTO ODP base (`uspto_odp/clients/base.py:221`) each carry their own copy of an absolute-URL passthrough `_build_url` override. Thai DIP, IPONZ, IPI and CAFC `download_pdf` sidestep the problem by calling `self._client.post/get` directly with absolute URLs, which also skips the shared retry and error mapping. When `_build_url` moves into mcp-data-core it should accept absolute URLs natively, and the two overrides can go.

Most REWRITEs in the newer connectors (IPI, Thai, IPONZ, PRH) only need a new injection seam. The assertions run through `httpx.MockTransport` and are strong; they simply inject it through the `client=` kwarg that is being removed. A single shared transport fixture (for example, patching `build_cached_http_client`, or a `transport=` hook on BaseAsyncClient) fixes all of them mechanically.

## uspto_office_actions
- Worst: `test_client.py`. It patches `httpx.AsyncClient.request` with `MagicMock(spec=Response)` and checks endpoints only by substring (`"/oa_rejections/v2/records" in call_args[0][1]`, lines 73, 179, 222, 278). A doubled or broken base URL would still pass.
- SUSPECT `test_client.py:309-319` `test_sends_api_key`: the docstring says it verifies the X-API-KEY header, but the only assertion is `mock_request.call_args is not None`.
- SUSPECT `test_mcp_envelope.py:258` `test_get_office_action_bounded_concurrency_fanout`: it never observes concurrency or the semaphore, only MagicMock call counts.
- `test_citation_monitoring.py` covers real workflow logic but swaps `OfficeActionClient` for a MagicMock and asserts `await_args`.
- GAPS: `get_office_action` raising NotFoundError for one missing id; invalid `result_type` raising ValidationError; Lucene escaping in `_escape_lucene`; `check_citation_hits` `more_available` when `num_found > len(results)`; HTTP error mapping for ODP OA endpoints.

## prh_fi
- Mostly healthy. Body-builder, model and fixture-parse tests are KEEP, and the 7 cassette smoke tests are KEEP.
- The routing tests assert host prefix plus exact path. They are the only guard on PRH's multi-host absolute-URL `_build_url` override. Keep the assertions when swapping the seam.
- SUSPECT `test_mcp_envelope.py:173-182` `test_search_prh_well_known_envelope`: the comment says the "TMR endpoint reaches the /tmr path", but the check is against the static provenance URL. The MockTransport handler serves the TMR fixture for any URL, so a tool calling the trademark endpoint would still pass.
- SUSPECT, mild: the cassette smoke tests construct `PrhClient()` with the default hishel cache (~/.cache), so a warm cache can answer without the cassette ever being hit.
- `test_default_user_agent_identifies_project` checks a constant. Nothing verifies that the UA header is actually sent.
- GAPS: HTTP error mapping (404 on get_patent, 5xx); `get_patents` sequential fetch; the `api.py` wrapper is untested (fine, since it is being replaced).

## cafc
- The classifier tests (15) are clean pure-function KEEPs and could become one parametrized table.
- Worst: `test_pagination.py` stubs the private `_fetch_page` (30 of 38 tests) and calls the private `_build_form_data`. The behavior it covers (offset, short pages, contradictory counts) is valuable, so drive it through a transport fake that serves the nonce HTML page plus the DataTables POST JSON.
- GAPS: WordPress nonce extraction (`_init_session`, both regex orders and the failure path) has no test; `download_pdf` HTTP behavior is untested and uses raw `self._client.get` + `raise_for_status`, so it gets no retry or typed errors; `_parse_row` HTML case-name extraction and `pdf_url` building are untested; the `register_source("cafc/opinions")` fetcher is untested.

## ipi_swissreg
- `test_client.py` is the best auth coverage in the batch: token form, one token reused across calls, 401 then re-auth, token 429 with Retry-After, no secret leak. These are seam-only REWRITEs and are the key regression tests for moving auth/token into mcp-data-core.
- DELETE `test_api.py` (8 tests): api.py pass-through delegation via mocked client.
- GAPS: the token-expiry `refresh_token` grant path (`_fetch_token(refresh=True)`, 30 s skew in `_token`) is never exercised; token endpoint 5xx; `_post_xml` 429 on the data endpoint; the HTTPS check is skipped whenever `client=` is injected (`client.py` `if client is None and ...`).

## copyright
- The client outcome tests are KEEP. Their seam is a class-level patch of `httpx.AsyncClient.request`, which is acceptable but should become MockTransport.
- SUSPECT `test_client.py:228-238` `test_api_error_raises`: `pytest.raises((CopyrightError, ServerError))`. `CopyrightError` is never raised anywhere (dead class), and the comment calling it an alias is wrong.
- Source inconsistency the tests miss: `search_copyright` returns `more_available=True` with `next_cursor=None` (`mcp/tools/copyright.py`, about line 150). `test_search_copyright_more_available_when_total_exceeds_page` asserts only the flag.
- GAPS: HTTP/2 requirement; `get_record` only scans the top 5 keyword hits for an exact id (an unverified failure path).

## thai_dip
- SUSPECT, and a real bug, at `test_client.py:93-107` `test_fetch_uses_exact_identifier_search`: the test never inspects the request body. `get_trademark` uses `_TRADEMARK_FIELDS["application_number"] = ("req_no", True)`, so it sends `{"req_no": "%<n>%"}` and returns `rows[0]` without checking it. A probe (scratchpad/thai_probe.py) confirmed `get_trademark("25000001")` returns application `2500000019`.
- Weak: `test_all_patent_datasets`. `right_type` is copied from the argument and every patent endpoint serves the same fixture, so design-to-PRODUCTPATENT routing is not proven.
- `ThaiDipClient._post` re-implements status-to-exception mapping instead of using `_request`, which is duplicated code for the collapse. `total` is `len(rows)`, not an upstream total.
- DELETE `test_api.py` (9). Env-gating uses reload, so REWRITE.

## iponz_new_zealand
- SUSPECT `test_client.py:54-68`: the name says "exact paths" but it only asserts `startswith(PRODUCTION_BASE_URL)`. The inconsistent detail paths (`/patent/{n}`, `/trademarks/{n}`, `/design/{n}`) are never pinned. `test_date_range_operations` checks only `url.path.endswith(...)`.
- `_get_xml` re-implements error mapping (bespoke 401/403/404/429). DELETE `test_api.py` (7).
- GAPS: URL-quoting of design numbers (`quote(..., safe="")`); IPONZ_ENV env-var selection (only the kwarg is tested).

## DUPLICATE-CONTRACT clusters (fold into one registry-wide parametrized contract test)
- The envelope/provenance/isinstance/more_available/no-batch checks across `uspto_office_actions/test_mcp_envelope.py` (9 tests, 180 lines), `cafc/test_mcp_envelope.py` (7, 162), `copyright/test_mcp_envelope.py` (8, 120), `prh_fi/test_mcp_envelope.py` (11 of 12, 142), `ipi_swissreg/test_mcp_envelope.py` (8 param, 135), `thai_dip/test_mcp_envelope.py` (9 param, 129) and `iponz_new_zealand/test_mcp_envelope.py` (7 param, 97). That is about 59 tests and 965 lines. A registry-wide contract test (ListEnvelope type, Provenance source_name/url non-empty, more_available implies next_cursor or an explicit no-cursor reason, lean excludes `raw`, full includes it, no `batch_*` tool names) would replace the shape half. The connector-specific lean-key and summary asserts stay as small per-connector content tests on transport fakes.
- The `test_no_batch_tool_present` copies (OA, CAFC, copyright) plus `test_search_and_get_both_importable` collapse to one registry assertion.
- The api.py delegation tests (IPI 8, Thai 9, IPONZ 7: 24 tests, 193 lines) become one generic factory test.
- The env-gating reload tests (IPI 2, Thai 2, IPONZ 2) become one parametrized registry check over (connector, required env vars).

## Batch E notes
# Batch E notes

Scope: euipo_trademarks, euipo_designs, dpma_register, uspto_assignments, wipo_lex,
upc_decisions, cpc, canada_federal_court, oepm_spain. 25 files, 188 collected tests (all pass
offline, 15s). Totals: KEEP 79 tests / 813 lines, REWRITE 78 / 1188, DELETE 31 / 212.
Builder script and node ids: scratchpad/refactor/E_work/.

## Absolute-URL / _build_url check (batch-wide)

No connector in this batch passes an absolute URL to `_request`/`_request_json`/`get`.
Three connectors bypass BaseAsyncClient and call the raw httpx client with absolute URLs,
which also skips retry/cache/`_raise_for_status`:

- `dpma_register/client.py:218-219` `_get_xml` builds `f"{self.base_url}/{service}/..."` and calls `self._client.get(url)`.
- `oepm_spain/client.py:310-311` `self._client.post(self.base_url, ...)`.
- `upc_decisions/client.py:355-366` `download_pdf` calls `self._client.get(pdf_url)` (absolute).

Refactor hazard: if the refactor routes these through `_request` without changing the
argument, `_build_url` will produce `base_url + absolute_url`. Only OEPM has a test that
would catch it (`oepm_spain/test_client.py:51` asserts `str(request.url) == BASE_URL`).
DPMA's only URL check is suffix-only (below); UPC `download_pdf` has no test at all.

Suffix-only URL assertions:
- `tests/dpma_register/test_client.py:48` `raw_path.endswith(b"/search/AKZ%3D10%202023")`; does not verify host or the `DPMAregisterPatService` segment.
- `tests/canada_federal_court/test_client.py:91,116,127` `url.path.endswith(...)`; paths are relative today so correct, but host is never asserted.
- `tests/euipo_trademarks/test_mcp_envelope.py:192`, `tests/euipo_designs/test_mcp_envelope.py:185`, `tests/wipo_lex/test_mcp_envelope.py:176` provenance `endswith` (provenance only, not requests).

## euipo_trademarks / euipo_designs

- **No behavioral test of any EUIPO request path.** Nothing drives `EuipoTrademarksClient.search/get_trademark/get_image*/get_sound/get_video/get_model` or `EuipoDesignsClient.search/get_design/get_view*/get_model` through HTTP. No cassettes exist (`tests/cassettes` has none for euipo) despite conftest having EUIPO token scrubbers and `--run-live-euipo`.
- **OAuth token fetch and refresh are untested for EUIPO.** The generic `OAuth2ClientCredentialsAuth` is covered in `../mcp-data-core/tests/test_oauth2.py` (first fetch, cached reuse, expiry refresh, 401 refresh+retry, error mapping), but EUIPO's composition (token URL per environment, `credentials_in_body=True`, `scope=uid`, Bearer plus `X-IBM-Client-Id` on the actual API request) is only checked via constructor attributes and the private `_client.headers`.
- Worst offenders: `test_client.py` in both dirs (environment/base_url/`_client_id`/`_client.headers` attribute checks). The MCP envelope tests patch the Client class with `_FakeModel` objects, so tool -> client -> HTTP is never connected.
- Suggested replacement: one MockTransport handler that answers the token POST and `/trademarks` (`/designs`) using the existing `tests/fixtures/euipo/*.json`; assert token request body, Authorization + X-IBM headers, host per environment, a forced 401 -> one refresh, then reuse the same harness through the MCP tools.
- Minor source observation: `mcp/tools/euipo.py:38` hardcodes the production host in provenance, so sandbox calls report a prod `source_url`.

## dpma_register

- `test_api.py` (6 parametrized): pure delegation through monkeypatched `api.DpmaRegisterClient`. DELETE.
- `test_client.py` is good: MockTransport injection via the constructor `client=` (transport boundary, not the deprecated api-level `client=`). Note the source skips the HTTPS check and reassigns `client.auth` when `client=` is passed, so if the refactor drops constructor `client=`, move these to a transport fixture.
- `test_mcp_envelope.py` patches `tools.api.*` (the wrapper layer being replaced) and counts mock awaits.
- `test_env_gating.py` uses `importlib.reload`; REWRITE to a registry check.
- GAPS: no non-429 HTTP error test (e.g. 401/500 -> ApiError); `limit` truncation (`ACCOUNT_RESULT_CAP`) at client level untested; query-length validation (1..2000) untested.

## uspto_assignments

- Cassette tests (`TestSearchLive`) are the strongest in the batch: KEEP.
- SUSPECT `tests/uspto_assignments/test_client.py:213`: `assert filtered.total <= unfiltered.total` passes even if `executed_between` is ignored. The cassette shows 2762 vs 7593, so a strict `<` works. The cassette also holds 2 stale v2 interactions (`/api/v2/...`) that are never replayed.
- SUSPECT `tests/uspto_assignments/test_mcp_envelope.py:69-70`: asserts provenance `assignment-api.uspto.gov` + `/PatentAssignmentSearch/`, but the client actually calls `https://assignmentcenter.uspto.gov/ipas/search/api/v3/public/search/patent` (`mcp/tools/patent_assignments.py:31`). The test locks in a stale provenance URL.
- `test_invalid_axis_rejected` asserts a raw `KeyError` leaking from `_SEARCH_AXIS_TO_API`.
- GAPS: `details()` NotFoundError path (no recordation) untested; conveyance + offset interaction (offset applied after client-side filter) untested; the 10k page-stop loop guard is untested except via the truncated cassette.

## wipo_lex

- `test_client.py` is solid MockTransport + inline HTML. It never asserts the request path/host (`/wipolex/en/legislation/results`, `/details/{id}`); add that.
- `TestModuleLevelApi` monkeypatches `api.WipoLexClient`; search variant duplicates the client test (DELETE), bare-id coercion is real (REWRITE onto whatever replaces api.py).
- `test_mcp_envelope.py` patches the client class with fake pydantic models; summary content is worth keeping via transport.
- GAPS: HTTP error mapping (404 on details, 5xx) untested; `start_date`/`end_date` -> `sDate`/`eDate` params untested.

## upc_decisions

- `test_parser.py`: all KEEP (pure, public `parse_decisions_page`).
- GAPS (no test drives the client over HTTP at all): `search()` page-0 Drupal quirk (must omit `page` param), filter param mapping (`division_1`, `proceedings_lang`), `get_decision` page walk, `list_divisions` dedupe across division_1..4, `list_languages`, `download_pdf` (absolute-URL raw `_client.get`, relative-URL ValueError).
- `test_mcp_envelope.py` patches api-layer `search_decisions`/`list_divisions`/`list_languages`, so the tool -> client wiring is never exercised and the real `<select>` parsing has zero coverage.

## cpc

- Worst offender in the batch: `tests/cpc/test_api.py`. 13 tests are `hasattr`/constant-string checks (DELETE). 5 inject `DummyClient` via the deprecated api-level `client=` kwarg (DeprecationWarning on every run) and only assert delegation.
- GAP: no test anywhere in the repo exercises `EpoOpsClient.retrieve_cpc/search_cpc/map_classification/fetch_cpc_media/fetch_cpci_biblio` over HTTP (grep of tests/ outside tests/cpc finds none; no cpc cassettes). Request paths are relative (`/rest-services/classification/cpc/...`) so `_build_url` is fine.
- `test_mcp_envelope.py` patches `client_from_env` and api-layer `map_classification`; the latter disappears with the api.py factory refactor.

## canada_federal_court

- `test_client.py` and `test_models.py` are good (MockTransport, pure `assess_docket_status`). KEEP.
- `test_mcp_envelope.py` (5) patches the Client class; the status-inference integration and failure fallback are worth keeping via transport.
- GAPS: unexpected response shape -> ValueError (`client.py:115`) untested; HTTP error mapping untested; RelatedListInfo results never asserted (the fan-out test only counts 4 paths).

## oepm_spain

- `test_client.py` is the model for the batch: full URL equality, SOAP body inspection, error mapping incl. Retry-After. KEEP.
- `test_api.py` delegation-only (DELETE); env gating via reload (REWRITE); MCP fan-out asserts mock `await_count` (REWRITE).

## DUPLICATE-CONTRACT clusters (one registry-wide parametrized contract test would replace)

- Envelope/provenance/lean-vs-full shape: euipo_trademarks mcp (5 of 6), euipo_designs mcp (5 of 6), dpma mcp (7 of 9), uspto_assignments mcp (3 of 8), wipo_lex mcp (5 of 7), upc mcp (6 of 9), cpc mcp (6 of 8), canada mcp (5), oepm mcp (3). About 45 tests / ~900 lines carry envelope/full=True shape checks. The connector-specific summary/projection assertions in them should move to transport-driven tool tests; the shape portion folds into one contract test.
- List-accepting `get_*` order preservation + empty-list ValidationError: euipo_trademarks, euipo_designs, wipo_lex, upc (4 order tests, ~61 lines; 3 empty-list tests).
- Docstring "Related tools:"/first-sentence rules: uspto_assignments (1), cpc (2), plus wipo_lex `test_no_batch_tool_present` (1). Fold into one registry lint.
- Env-gating via `importlib.reload`: dpma_register (2), oepm_spain (2). Same pattern, one parametrized registry test.
- api.py delegation tests (monkeypatch Client, assert pass-through): dpma `test_api.py` (6), oepm `test_api.py` (3), wipo_lex `TestModuleLevelApi` (2), cpc `TestCpcApiMethods` (5). All become obsolete with the api.py factory.

## Batch F notes
# Batch F audit notes

Scope: 13 dirs, 27 files, 134 collected tests (all pass in replay mode, 18 s). F.csv: 80 rows.
Totals: KEEP 46 tests / 722 lines; REWRITE 64 / 988; DELETE 24 / 291.

## Confirmed bug: CKAN `download_resource` builds a broken URL (all three connectors)

`BaseAsyncClient._build_url` (mcp-data-core base_client.py:228-230) always returns `f"{self.base_url}{path}"`.
All three CKAN clients pass the absolute resource URL straight into `_request`:

- src/patent_client_agents/ip_australia_bulk/client.py:90-94
- src/patent_client_agents/ilpo_tm/client.py:86-90
- src/patent_client_agents/inpi_br_bulk/client.py:99-103 (INPI resources live on revistas.inpi.gov.br, a different host, so even a "strip base_url" fix would not be enough)

Reproduced with MockTransport (scratchpad/refactor/parts/F_urlcheck.py). The requested URLs were:
`https://data.gov.auhttps//data.gov.au/data/dataset/x/...`, `https://data.gov.ilhttps//data.gov.il/...`, `https://dados.gov.brhttps//dados.gov.br/...`.
The three `test_download_resource_streams_bytes` tests (ip_australia_bulk/test_client.py:118, ilpo_tm/test_client.py:120, inpi_br_bulk/test_client.py:126) assert only `str(url).endswith(filename)`, so they pass anyway. They are marked SUSPECT/REWRITE: assert exact URL equality, which will fail until the bug is fixed.
Mitigation: no src code calls `download_resource`. The MCP `download_*` tools only return the CKAN URL, so users are not hit today. The method is effectively dead public API.

## ip_australia_patents / _trademarks / _designs

- GAP (OAuth): no test anywhere fetches an IP Australia token. Every client test injects `client=httpx.AsyncClient(MockTransport)`, and BaseAsyncClient only attaches `auth` when it builds its own client (base_client.py:133-150), so the injected client carries no OAuth handler. The only OAuth check is `test_constructor_wires_oauth_against_production_host`, which reads private `client._client.auth._token_url`. Generic OAuth2ClientCredentialsAuth flows (cache, expiry refresh, 401 retry, credentials_in_body) are covered in mcp-data-core/tests/test_oauth2.py. What is never tested is the AU wiring: the token URL per environment, form-body credentials, and Bearer on API calls. The refactor needs an injection seam that keeps `auth`, e.g. pass `transport=` rather than `client=`.
- GAP: detail 404 -> NotFoundError and 401/403 -> AuthenticationError are not exercised for AU.
- GAP (minor): MCP tool provenance hard-codes the production host (`_IPA_BASE` in mcp/tools/ip_australia_{patents,trademarks,designs}.py), even when IPAUSTRALIA_ENV=sandbox.
- DUPLICATE: the three test_client.py files are line-for-line clones (7 tests each, about 165 lines). So are the three test_mcp_envelope.py files (5-6 tests each). One parametrized AU suite would replace 38 tests (about 700 lines) with roughly 10 parametrized tests.
- The client search/detail tests are good behavioral tests (body shaping, parsed models). They are KEEP but should assert full URLs, not `endswith`.

## ip_australia_bulk / ilpo_tm / inpi_br_bulk (CKAN trio)

- DUPLICATE-CONTRACT: these are identical CKAN clients (package_show, success=False -> ApiError, download_resource) with identical tool shapes. That is 27 tests and about 590 lines across 6 files. One CKAN suite parametrized over (client, tool module, fixture) would cover it with about 7 tests. The source code also collapses naturally into one CKAN base.
- Worst offenders: `test_default_base_url_*` (constructor constant plus private `_client.auth`) and inpi_br_bulk `test_default_dataset_id_is_rpi` (asserts a constant against its own literal). Both are DELETE.
- Envelope tests patch the client class with `_FakeModel` (model_dump ignores by_alias). The resource projection and NotFound logic are real, so these are REWRITE to transport-level fixtures.

## uspto_trademark_assignments

- SUSPECT: test_mcp_envelope.py:61 asserts provenance contains `assignment-api.uspto.gov`. The client actually queries `assignmentcenter.uspto.gov` (client DEFAULT_BASE_URL; tool constant at mcp/tools/trademarks.py:642). The test locks in a provenance URL that probably points at the retired host.
- Weak: live tests test_client.py:121-140 (by_assignor/serial/registration) assert only `isinstance(list)`, but the cassettes hold 1, 3 and 3 rows. `test_search_combined` sends one criterion and replays the same 278 KB response as `by_assignee`, so it is a DELETE duplicate.
- Request-shape tests patch private `_request` and assert `assert_awaited_once_with` (REWRITE to MockTransport).
- GAP: the error branch (non-dict `successResponse` -> ApiError, client `_search`) is untested.
- test_models.py (5 tests) is all Pydantic field acceptance: DELETE.

## japan_ip_high_court

- Parser and client tests inject input by patching `client.xlrd.open_workbook` / `client.parse_case_workbook`, which ties them to xlrd internals. REWRITE to a tiny committed .xls fixture. The parsing logic (era years, Excel dates, identifier typing) is valuable.
- The envelope tests patch the client class but assert real tool filtering and normalization. REWRITE the input path and keep the assertions.

## china_spc_ip_court

- In the best shape in this batch: MockTransport plus representative HTML; the parsers are pure.
- GAP: the `get_hearing_notice` positive full-official-URL branch (client.py:301-305, strips base_url) is untested, and `test_exact_notice_fetch` never asserts the request path.
- `test_module_import_does_not_require_tz_database` uses importlib.reload. It is KEEP as a cheap #86 regression test but brittle.

## uspto_petitions / uspto_applications / uspto_bulkdata

- Worst offenders: all 9 `test_api.py` tests. Each passes a hand-written DummyClient through the deprecated `client=` kwarg, asserts forwarded kwargs inside the dummy, and emits DeprecationWarning. No src module imports these api.py wrappers. DELETE (146 lines). Check that tests/uspto_odp covers the underlying UsptoOdpClient methods.
- petitions envelope: `test_get_petition_parameter_renamed` inspects the signature (DELETE). `test_docstrings_carry_related_tools_lines` is DUPLICATE-CONTRACT, as is tm-assignments `test_docstring_carries_related_tools_line`. Together they are 2 tests and 13 lines that belong in one registry-wide §5.6 test, alongside about 10 similar tests in other dirs (usitc, jpo, epo_ops, cpc, uspto_assignments, ...).

## uspto_tsdr

- SUSPECT/weak: test_client.py:62. `get_last_update` asserts only `serial_number`, which the method copies from its argument (client.py:174-178), so the derived `last_update_date` is never checked. test_client.py:69 `get_documents` asserts only `isinstance(list)`. `_parse_documents_xml` swallows ParseError and returns [] (client.py:485), even though the cassette parses to 16 documents.
- `_format_case_id` is tested privately via `__new__` (REWRITE through the request path).
- The `is_live`/`is_registered` model tests are KEEP. Document/Owner/GoodsServices model tests are DELETE.

## DUPLICATE-CONTRACT summary (batch F)

The §5.9 ListEnvelope/Provenance isinstance checks and source_name assertions repeat in 9 envelope files (AU x4, ilpo, inpi_br, tm-assign, petitions, plus the Japan/China type checks). One registry-wide parametrized contract test owns envelope type, provenance presence, `Related tools:` docstrings, list-accept order, and empty-list ValidationError. That removes the shape portion of about 40 tests (about 700 lines). Only the connector-specific projection and summary assertions need to remain, at the transport level.
