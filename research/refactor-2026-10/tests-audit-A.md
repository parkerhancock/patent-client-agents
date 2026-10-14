# Test audit A: fees, jpo, uspto_odp, google_patents, epo_ops

Scope: 51 files, 17,550 lines, 1,447 collected tests (1,420 test functions). Per-test verdicts are in `tests_audit_A.csv` (one row per test function; `n_tests` counts parametrized cases; `lines` is the test function body only, so the 10,921 "test lines" below exclude roughly 6,600 lines of fixtures, fake payloads, helpers and imports, which follow the fate of the tests that use them).

Replay run on 2026-10-14 (`uv run pytest tests/{fees,jpo,uspto_odp,google_patents,epo_ops}`): 1,423 passed, 24 skipped. All 24 skips are the PTAB cassette tests (see "suspect tests" below).

Rubric applied: KEEP = public function/client/tool through its real interface with realistic input, or a pure input->output function that is a natural seam (per-office fee parsers, number normalizers, XML/HTML parsers on realistic markup). REWRITE = real behavior but bound to internals (private methods/attributes, `patch.object` on private methods, AsyncMock'd client with `assert_awaited_once_with`, monkeypatched fetch methods, per-tool copies of shape checks). DELETE = constructor/declared-field/enum restatement, pass-through to a dummy, absence-of-removed-name guards, duplicates.

## Totals by directory

| dir | KEEP tests / lines | REWRITE tests / lines | DELETE tests / lines | total tests |
|---|---|---|---|---|
| fees | 567 / 3,001 | 75 / 876 | 14 / 72 | 656 |
| jpo | 95 / 854 | 56 / 673 | 71 / 399 | 222 |
| uspto_odp | 97 / 603 | 86 / 1,204 | 30 / 149 | 213 |
| google_patents | 39 / 368 | 125 / 837 | 77 / 411 | 241 |
| epo_ops | 35 / 539 | 53 / 756 | 27 / 179 | 115 |
| **all** | **833 / 5,365** | **395 / 4,346** | **219 / 1,210** | **1,447** |

Reading the numbers: fees looks healthy because most of its 656 tests are small pure-parser cases against per-office parsing logic plus builders run on recorded source files, which the shared-primitive refactor will not touch. The other four directories are where the implementation-bound tests live: outside fees, only 266 of 791 tests are KEEP.

## Worst offenders

1. `jpo/test_models.py` (63 tests, 643 lines): 57 DELETE. Twenty-four tests assert enum literal values (`StatusCode.SUCCESS.value == "100"`), nine re-test `ApiResult` construction and status properties already covered by the client's MockTransport no-data/error tests, and the rest construct a Pydantic model and read back the fields they passed. Two real-payload tests are the only coverage of nested `rightPersonInformation`/priority rows and should move into the client MockTransport handler.
2. `google_patents/test_models.py` + `test_api_utils.py` (68 tests): 40 DELETE are constructor/default tests and `isinstance(get_client(), GooglePatentsClient)`. Keep only `_resolve_expiration_date` (7).
3. `google_patents/test_builders.py` (35 tests, all REWRITE): every test feeds hand-built intermediate dicts into 13 private `_build_*` functions. That parser-to-builder handoff is internal, and there is no recorded Google Patents page anywhere in the suite, so these are standing in for the fixture test that should exist.
4. `jpo/test_mcp_dispatch.py` (25 tests, 23 REWRITE): replaces `JpoClient` with an AsyncMock and asserts `assert_awaited_once_with` on the routed method. A real `JpoClient` over the MockTransport handler already in `test_client.py` would prove the same routing by output.
5. `uspto_odp/test_mcp_envelope.py` + `test_ptab_envelope.py` (47 tests, 37 REWRITE): `patch("...tools.uspto.UsptoOdpClient")` with hand-built fakes. The application fakes use nested `applicationMetaData`, a shape the default client path never emits (it flattens), so the summary assertions exercise a fallback branch. The shape gap is the same one that let the "(no title)" production summary bug ship (fixed in f85f5b9).
6. `uspto_odp/test_applications.py` (34 tests, 21 REWRITE): `patch.object` on `_search_with_payload`, `_get_with_404_handling`, `_request`, `_fetch_single_application_record`, plus `call_args` query inspection. No test in scope sends a real HTTP request through `ApplicationsClient`.
7. `uspto_odp/test_client.py` (12 tests, 0 KEEP): duplicates `test_base.py` init/normalization tests, asserts private sub-client attributes, and one context-manager test asserts nothing.
8. `epo_ops/test_api.py` (7 of 8 DELETE) and `epo_ops/test_parsing.py` (16 of 23 DELETE): dummy-client pass-throughs and private XML utilities, NS constants and exception constructors.
9. `jpo/test_env_gating.py` (7 REWRITE): `importlib.reload` plus rebinding the module global `jpo_mcp` plus the private `downloads._SOURCES` dict. The env-gating behavior is important, but `conditional_tool` moves to mcp-data-core in the refactor, so these will break first.
10. Fees e2e scrape tests (26 tests across 10 office files): monkeypatch `XFeesClient.fetch_html/fetch_pdf`, which is exactly the fetch layer being extracted. These are the only tests of schedule metadata (currency, source_url, statutory_basis, effective_date), so they are REWRITE (serve the same fixture bytes through MockTransport), not DELETE.

## Duplicate-contract clusters

**MCP envelope and dispatch files.** These seven files total about 2,765 lines: `jpo/test_mcp_envelope.py`, `jpo/test_mcp_dispatch.py`, `uspto_odp/test_mcp_envelope.py`, `uspto_odp/test_ptab_envelope.py`, `google_patents/test_mcp_envelope.py`, `epo_ops/test_mcp_envelope.py` and `epo_ops/test_unitary_patent_envelope.py`, plus the MCP-view block of `epo_ops/test_structured_records.py`. Together they hold about 47 `isinstance(result, ListEnvelope|ResponseEnvelope|Provenance)` assertions, about 57 `provenance.source_name/source_url` assertions and 11 docstring checks. Each file builds its own client-patching helper (`_patch_client_from_env`, `mock_client` fixture, `patch("...UsptoOdpClient")`, `patch.object(patents_module, "GooglePatentsClient")`).

`scripts/validate_mcp_contracts.py` already checks output schemas statically. A runtime contract test would need three parts:
- a table of tool to recorded upstream fixture;
- one parametrized test that invokes every tool and asserts the envelope type, the core provenance fields, the source_url host, a non-empty summary, and input order preserved for list-accepting tools;
- one docstring lint (Related tools line, acronym expansion, sibling list).

That would replace the shape half of about 100 tests. What remains is about 40 to 50 behavior-specific tests: PTAB pagination and coverage `ParseError`, lean projections, CQL jurisdiction recipes, cursor-to-Range, file-history format selection, the flattened-metadata summary regression, and the JPO empty-item semantics. Rough size change: about 2,800 lines become about 250 lines of contract test plus fixture table and about 900 lines of focused behavior tests. Net reduction is about 1,600 lines.

**Fees registry wiring.** There are 11 copies of "`get_scraper(OFFICE, right) is module.scrape_x`", one per office file plus `test_epo_unitary`. One parametrized test over the expected routing table would replace them all, combined with `test_every_office_code_is_aliased`, which today reads the private `registry._DISPATCH`.

**Fees money parsers.** About 116 tests across about 15 per-locale parsers: `_parse_money` (USPTO, CIPO, HK), `_parse_eu_money`, `_parse_euipo_money`, `_parse_amount` (DPMA, PRH), `_parse_nt`, `_parse_br_amount`, `_parse_es_amount`, `_parse_sek_amounts`, `_parse_tr_amount`, `_parse_yen`, `_parse_sgd_amounts` and `_extract_amounts`. They are verdict KEEP because they are real behavior. If the refactor consolidates them into a shared locale-aware amount parser, these cases become one parametrized table of (locale, input, expected).

**Fees dispatch patching.** Nine tests in `fees/test_client.py` and `fees/test_envelope_compliance.py` use `patch.dict(registry._DISPATCH, ...)`. One public injection hook, or a recorded USPTO fee page, would serve them all.

## Gaps (important behavior with no behavioral test)

**Fees.** Only 10 of 25 offices have a recorded source fixture: HKIPD, ILPO, IMPI, IPOS, JPO, KIPO, OEPM, PRH, PRV and TURKPATENT.
- No source-byte test at all for USPTO (only helper parsers plus the freshness receipt), EPO, EUIPO, CNIPA, CIPO, DPMA, TIPO, INPI-BR, UKIPO trademarks, KIPO patents or JPO patents (one per-claim test only).
- IP India and the three WIPO routes (PCT, Madrid, Hague) have zero tests anywhere in the repo.
- INPI-FR has only one constant check. IP Australia is covered only through a monkeypatched fetch.
- OEPM has no end-to-end `scrape_oepm_*` test, and its builder tests pass the `accept_buckets` set themselves, so a wrong bucket set in the scraper would go unnoticed.
- The nightly `fees-snapshot.yml` is live monitoring, not regression coverage.

**USPTO ODP.**
- The PTAB client suite never runs in CI (see below), so PTAB clients have no executing replay coverage.
- `ApplicationsClient` has no MockTransport or cassette test. `search`/`get_application`/`get_documents`/`download_document`, the 404 to NotFound mapping and search pagination are only exercised with private methods patched out.

**Google Patents.**
- No recorded patent page or xhr/query JSON fixture.
- The public `extract_metadata` (status, dates, expiration, inventors, assignee, events) has no test.
- `get_patent_data`, `search_patents` and `download_patent_pdf` are never run against realistic bytes.

**EPO OPS.**
- No cassettes. Legal events, number conversion, PDF download, CPC, and fulltext description beyond a handwritten snippet have no realistic-bytes test.
- Request construction (paths, Range header, CQL `q`) is only checked through mocked `_request` and `assert_awaited_with`.
- The 403 quota-header path is untested in practice (see below).

**JPO.**
- No test proves `RateLimiter` ever blocks; the existing tests only count private `_timestamps`.
- No retry/backoff test on 5xx or 303.

**Cache-hit paths.**
- The fees freshness receipt is tested with fake hishel `extensions` on an AsyncMock'd `_request`, not a real hishel cache.
- ODP, EPO and JPO hishel cache behavior has no test in this scope (it may live in `tests/test_cache.py`, which is outside my scope).
- Google's bespoke SQLite cache is tested, but if the refactor swaps it for the mcp-data-core cache, its "non-200 not cached" and "hit avoids network" expectations need to move with it.

## Suspect tests (passing while asserting something wrong or nothing)

1. **`epo_ops/test_client.py::TestForbiddenErrorBuilder::test_builds_error_with_all_headers` enshrines a live bug.** The test comment admits the quota headers are never extracted. I confirmed it in `src/patent_client_agents/epo_ops/client.py:255`: `_build_forbidden_error` copies `response.headers.items()` (lowercased by httpx) into a plain dict and then looks up `"X-Rejection-Reason"` and the other mixed-case keys, so they always miss. Users never see the reason or the hourly/weekly usage on a 403. The test only asserts `"EPO OPS returned 403"` and `headers is not None`.
2. **The PTAB cassette tests are skipped in CI.** All 24 tests in `uspto_odp/test_ptab.py` that take the `api_key` fixture skip unless a real `USPTO_ODP_API_KEY` is in the environment, even in replay mode. `ci.yml` sets no such variable, and the cassettes exist on disk. When they do run, the assertions are `result.count >= 0` and `if result.count > 0:` guards, so an empty parse passes. The three `TestPtabModels` tests assert `hasattr()` on declared Pydantic fields, which is always true.
3. **`fees/test_oepm.py::TestParseEsAmount::test_bare_integer_returns_none`** asserts `== Decimal("100")`. The name and the comment say it should return None.
4. **USPTO envelope fakes don't match production.** The `_make_application` fakes in `uspto_odp/test_mcp_envelope.py` return nested `applicationMetaData`. The tool's summary falls back to the nested block, so these tests pass on a shape production never produces by default.
5. **`jpo/test_live.py` has five weak assertions**: `test_get_mailed_documents`, `test_get_cited_documents`, `test_cross_reference_by_publication`, `test_divisional_info` and `test_pct_lookup_no_data` assert "X is None or isinstance(X, ...)" or sit behind `if` guards. With a fixed cassette, each should assert the recorded value.
6. **`fees/test_epo_unitary.py::test_schedule_is_distinct...`** compares scraped amounts to the module constant they were built from, which is a tautology. Only the separate golden-table test checks real numbers.
7. **`fees/test_kipo.py::test_live_fetch_has_total_deadline`** patches `KIPO_REQUEST_DEADLINE_SECONDS` with `raising=False`. If the constant is renamed, the patch silently does nothing and the test's meaning changes.
8. **`fees/test_client.py::test_every_office_code_is_aliased`** silently skips every `WIPO-*` office, so alias coverage for those routes is unverified.
9. **`uspto_odp`'s `_normalize_download_bag` is imported from two modules** (`clients.ptab_trials` and `clients.base`) by different tests. That suggests a duplicated symbol the refactor should collapse; the tests will need one import path.

## Suggested order for the refactor

1. Before extracting anything, convert the REWRITE tests that guard behavior otherwise untested: the fees e2e scrapes via MockTransport, the PTAB replay key fix, the EPO 403 test (expect it to fail until the bug is fixed), and `test_get_application_summary_reads_client_flattened_metadata` through the real client.
2. Delete the 219 DELETE tests; that removes about 1,200 test-body lines plus their fixtures.
3. Replace the envelope/dispatch shape checks with one registry contract test and one docstring lint.
4. Add the missing fixtures: a Google Patents page plus xhr JSON, OPS XML for legal/number/PDF, and source pages for the 15 untested fee offices.
