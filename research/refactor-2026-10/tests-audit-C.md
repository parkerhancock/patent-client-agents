# Test audit C: document-collection corpora + top-level tests

Scope: 18 corpus dirs (ipos_statutes, ilpo_statutes, ipos_manuals, inpi_br_statutes, dpma_statutes, legifrance_ip, mpep, ipo_in_statutes, tw_trade_secrets, upc_statutes, ipo_in_mppp, tmep, ukipo_mopp, epo_guidelines, epc, epo_case_law, epo_up_guidelines, epo_pct_guidelines), the 13 top-level `tests/test_*.py`, `tests/conftest.py`, and per-dir conftests.
Counts are collected pytest items (`--collect-only`, parametrizations expanded): 805 in the dirs + 158 top-level = 963. "Lines" = lines of the test function bodies (decorators included), not fixtures/helpers. Row detail is in `tests_audit_C.csv`.

## Totals

| Verdict | Tests | Lines |
|---|---:|---:|
| KEEP | 458 | 2,667 |
| REWRITE | 424 | 4,459 |
| DELETE | 81 | 517 |
| **Total** | **963** | **7,643** |

Most REWRITE volume is not "bad test" but "per-package copy": ~350 of the 424 REWRITE items collapse into five parametrized contract tests (below).

## Per directory (tests / lines)

| Dir | KEEP | REWRITE | DELETE |
|---|---|---|---|
| dpma_statutes | 32 / 146 | 29 / 269 | 5 / 18 |
| epc | 11 / 31 | 22 / 161 | 2 / 11 |
| epo_case_law | 9 / 28 | 16 / 126 | 2 / 10 |
| epo_guidelines | 25 / 107 | 11 / 124 | 2 / 10 |
| epo_pct_guidelines | 5 / 10 | 10 / 133 | 2 / 12 |
| epo_up_guidelines | 5 / 12 | 16 / 138 | 2 / 11 |
| ilpo_statutes | 24 / 176 | 27 / 307 | 5 / 24 |
| inpi_br_statutes | 29 / 150 | 29 / 257 | 5 / 32 |
| ipo_in_mppp | 17 / 58 | 28 / 222 | 5 / 17 |
| ipo_in_statutes | 29 / 129 | 29 / 270 | 5 / 18 |
| ipos_manuals | 21 / 142 | 24 / 317 | 6 / 77 |
| ipos_statutes | 25 / 176 | 25 / 349 | 6 / 76 |
| legifrance_ip | 35 / 158 | 27 / 247 | 5 / 18 |
| mpep | 24 / 173 | 20 / 263 | 3 / 16 |
| tmep | 8 / 49 | 14 / 190 | 11 / 88 |
| tw_trade_secrets | 25 / 89 | 30 / 268 | 5 / 18 |
| ukipo_mopp | 20 / 112 | 12 / 138 | 2 / 11 |
| upc_statutes | 6 / 52 | 12 / 157 | 1 / 5 |
| top-level (13 files) | 108 / 869 | 43 / 523 | 7 / 45 |

## Duplicate-contract clusters (what one parametrized test would replace)

1. **get_corpus_status** — 18 `test_corpus_status.py` files, 104 tests, 1,811 file lines. Same four cases everywhere (shape, version source, UTC-midnight date, missing/malformed meta), seeded by raw `corpus.schema.DDL` + `INSERT INTO meta`. The 18 shape tests are DELETE; the rest become one test over a `CORPORA` table `(module, env_var, meta_seed, expected_version)`, roughly 80-120 lines. Note the implementations genuinely differ in version precedence (`source_version` vs `epc_year`/`guidelines_year`/`caselaw_year`/`lpi_year` vs `snapshot-<date>` fallback; MPEP also maps `current` to `unknown`, TMEP does not), so the table must encode a per-corpus version key, or the factory must standardize it first.
2. **MCP envelope** — 18 `test_mcp_envelope.py` files, 156 tests, ~1,630 function lines (≈2,950 file lines). Fourteen files run the real tool against a fixture corpus and repeat the same checks: lean keys, `full=True` keys, provenance `corpus_version`/`corpus_synced_at`, str+list `get_*`, order preserved, "Fetched N", empty list raises, limit bounds, `no_batch_tool_present`. One registry-parametrized contract (~150 lines plus a data table) replaces ~120 of them; ~25 corpus-specific cases (statute filter, Rule/Art citation forms, LPI suffix, English translation search, invalid citation) remain as table rows. The four mocked files (ipos_statutes, ilpo_statutes, ipos_manuals, upc_statutes, 30 tests) must be rewritten onto real fixture corpora anyway.
3. **Search/availability semantics on clients** — 36 tests across 18 dirs (blank query, pagination disjointness/has_more, `CorpusUnavailable` with install hint). Belongs to the shared search helper; one parametrized test.
4. **Seed-JSONL builds** — dpma_statutes, ipo_in_statutes, tw_trade_secrets, ipo_in_mppp, legifrance_ip: 54 tests / 418 lines of near-identical `test_build.py` (invalid JSON, missing key, non-object, comments, overwrite, source_version, CLI rc). One shared-build contract; raw `SELECT ... FROM sections` checks become client read-backs.
5. **API convenience + usage resource** — 69 tests; `get_client()` class-name checks (DELETE) and 10 copies of "usage resource names its tools" (one parametrized test). The rest are thin but legitimate KEEPs.

Related: the per-package `_translate_fts_query` string tests (ipos_statutes, ipos_manuals, ilpo_statutes, upc_statutes, legifrance_ip) should become one translator table once the shared translator lands.

## Worst offenders

- `ipos_statutes/test_build.py`, `ipos_manuals/test_build.py`: `test_fetcher_fetch_*` patches `default_retryer` to a single attempt and swaps private `_client` for a MagicMock. One is named "retries_then_succeeds" but tests no retry. Also: a blank-PDF `isinstance(str)` test, a frozen-dataclass test, and a KeyboardInterrupt test that patches the `asyncio` module.
- `ipos_statutes`, `ilpo_statutes`, `ipos_manuals`, `upc_statutes` `test_mcp_envelope.py`: patch `mcp.tools.<x>.search` / `_search_statutes` / the `*Client` class and assert on canned models. They pass with a broken client and break on any tool-module refactor.
- `ilpo_statutes/test_build.py`: patches the fetcher class, `extract_pdf_text`, and `build_corpus`; carries a dead `bad_fetch` helper that is immediately deleted.
- `inpi_br_statutes/test_build.py`: valuable PT/EN merge and fallback behavior, but driven by patching private `build._fetch`. `test_main_cli_smoke` only asserts `assert_awaited_once()`.
- `mpep/test_api.py`: DummyClient asserting call kwargs.
- `tmep/test_models.py`: 8 Pydantic field-echo tests (DELETE all).
- `tests/test_core.py` and `tests/test_cache.py` (99 tests): these test `mcp_data_core`, not this package, and partly duplicate `tools/mcp-data-core/tests/test_resilience.py`. They should move to mcp-data-core. Some read private `_raise_for_status`, `_owns_client`, `_hits`, `_storage`; `test_timeout_forwarded` asserts nothing.
- `test_unified_pdf_cascade.py` and `test_unified_clean_sources.py`: real regressions, but enforced by patching module-level client classes, plus several `assert_awaited_once_with` checks.
- Fixture coupling: conftests for epc, epo_guidelines, epo_case_law, epo_up_guidelines, epo_pct_guidelines, ukipo_mopp, and inpi_br_statutes, and the inline seeds in ipos_statutes, ilpo_statutes, ipos_manuals, and upc_statutes, all write raw SQL against `corpus.schema.DDL`. Any schema change in the generic layer breaks every one. Build fixtures through the public `write_corpus`/builder, as mpep, tmep, and the seed family already do.

## Gaps

1. **offset/limit paging.** 13 tools compute `page = offset // limit + 1`: dpma_statutes, epc, epo_case_law, epo_guidelines, epo_pct_guidelines, epo_up_guidelines, inpi_br_statutes, ipo_in_mppp, ipo_in_statutes, mpep, trademarks (tmep), tw_trade_secrets, ukipo_mopp. Only 4 tests pass `offset` at all, and all use `offset=0`. Nothing covers offset≠0, so the non-multiple flooring (offset=3, limit=2 re-serves item 2) is untested.
2. **Punctuation in FTS queries.** Nine translators pass raw tokens through in and/or modes: tmep, epc, epo_guidelines, epo_case_law, epo_pct_guidelines, epo_up_guidelines, ukipo_mopp, inpi_br_statutes, and legifrance_ip (always AND). None of them has a punctuation test. A direct FTS5 probe raises on `Art. 54`, `G-II`, `L.611-10 brevet`, `52(2)(a)`, `1207.01(a) confusion`, and `inventive-step`. These are the citation shapes users type for exactly these corpora. Only mpep has behavioral punctuation and embedded-quote tests; the quoting translators (ipos×2, ilpo, upc, tw, dpma, ipo_in×2) have string-level or weak tests. legifrance's `TestTranslateFtsQuery::test_joins_tokens_with_space` pins the unquoted behavior.
3. **No error mapping for bad queries or a missing corpus at the MCP layer.** No tool under `mcp/tools/` catches `CorpusUnavailable` or `sqlite3.OperationalError`, and no envelope test covers either path. Raw exceptions reach the caller. The corpus-unavailable tests exist only at the client level (one per package).
4. **Builds with no smoke test.** epc, epo_case_law, epo_up_guidelines, epo_pct_guidelines, and upc_statutes have no build test at all; their fixtures bypass the builder via raw SQL. tmep's `write_corpus` runs only as a conftest fixture, and its scraper and `build_corpus` are never exercised. epo_guidelines and ukipo_mopp test only slug/HTML helpers, never `write_corpus` or `build_corpus`. That makes 8 builds without an end-to-end smoke; mpep is only partially covered (`write_corpus` and `parse_chapter_html` yes, crawl via a monkeypatched `fetch`).
5. **Outline sort.** dpma, ipo_in_statutes, tw_trade_secrets, ipo_in_mppp, and inpi_br test `sort="outline"` by asserting hits exist; only ilpo checks the ordering.

## Suspect tests (pass while asserting something wrong or nothing)

- `mpep/test_corpus_status.py::test_version_string_is_source_version_from_meta` asserts `'unknown'`, contradicting its name. In `mpep/test_mcp_envelope.py`, the docstring says the fixture stamps `'current'` while the assertion is `'unknown'`.
- `tmep/test_corpus_status.py` and `tmep/test_mcp_envelope.py` pin `corpus_version == 'current'`, which MPEP deliberately rejects ("absent release evidence remains unknown"). TMEP provenance claims a version it cannot evidence, and the tests lock that in.
- `ipos_statutes/test_build.py::test_fetcher_fetch_retries_then_succeeds` covers no retry (retryer patched to one pass).
- `tw_trade_secrets/test_client.py::test_query_with_hyphen_quoted` asserts `isinstance(r.hits, list)`.
- `inpi_br_statutes/test_build.py::TestTitleFromBody::test_splits_on_first_period` admits "any non-empty string is fine". Titles for `Art. 6º ...` get cut at `Art.`.
- `ipos_statutes/test_corpus.py::test_get_by_citation_with_subsection`: the comment says the parser must resolve the statute, but it asserts only `None`, which also passes if parsing fails.
- `test_unified_clean_sources.py::test_claims_clean_never_imports_google` never guards Google; it only checks NotFoundError on empty EPO claims.
- `mpep`/`tmep` `test_search_or_syntax_widens` (`>=`) passes when both searches return zero hits.
- Outline-sort tests (gap 5).
- `test_validate_mcp_contracts.py` mutates module global `LEGACY_PROVENANCE_EXCEPTIONS` without restoring it. It's harmless today because the module is loaded per file, but it's order-sensitive.
- `test_build_coverage.py` / `test_build_source_catalog.py` pin magic counts (12 standalone, 120 records, 114 projected) and break on every catalog addition. They are REWRITE to invariant-only.

## Notes on conftest.py

`tests/conftest.py` is VCR and env-placeholder plumbing, with no corpus fixtures and nothing in scope to change. The per-dir conftests are where the coupling lives (see worst offenders). A shared `build_fixture_corpus(kind, rows)` helper would let the status, envelope, and search contracts share one fixture per corpus.
