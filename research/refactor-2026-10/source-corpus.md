# Corpus (mcp_local) connector refactor analysis

Read-only analysis, 2026-10-14. Repo: `tools/patent-client-agents` (paths below are relative to
`src/patent_client_agents/` unless noted). Shared plumbing: `tools/mcp-data-core/src/mcp_data_core/`.

## 1. Inventory

18 packages ship or build a SQLite/FTS5 corpus. Every one has the same nine-file layout:
`__init__.py api.py client.py models.py resources.py corpus/{__init__,build,db,schema}.py`, plus
either `docs/usage.md` or `data/seed.jsonl`. MCP tools live in 16 modules under `mcp/tools/`
(TMEP's tools live inside `mcp/tools/trademarks.py`; `ipos.py` serves two corpora; `upc.py` and
`ilpo.py` also carry non-corpus tools).

Line counts (`wc -l`):

| pkg | init | api | client | models | res | build | db | schema | total .py |
|---|---|---|---|---|---|---|---|---|---|
| mpep | 124 | 198 | 259 | 35 | 15 | 526 | 54 | 72 | 1300 |
| tmep | 116 | 146 | 181 | 39 | 15 | 428 | 54 | 62 | 1058 |
| epc | 117 | 198 | 251 | 31 | 15 | 240 | 54 | 72 | 995 |
| epo_guidelines | 121 | 198 | 280 | 31 | 15 | 280 | 54 | 72 | 1068 |
| epo_pct_guidelines | 127 | 198 | 284 | 31 | 15 | 280 | 54 | 72 | 1078 |
| epo_up_guidelines | 127 | 198 | 257 | 31 | 15 | 244 | 54 | 72 | 1015 |
| epo_case_law | 121 | 198 | 237 | 31 | 15 | 236 | 54 | 72 | 981 |
| ukipo_mopp | 129 | 198 | 227 | 31 | 15 | 296 | 54 | 72 | 1039 |
| upc_statutes | 134 | 90 | 201 | 69 | 15 | 329 | 157 | 78 | 1090 |
| ipos_statutes | 134 | 117 | 297 | 88 | 15 | 402 | 231 | 86 | 1387 |
| ipos_manuals | 117 | 103 | 243 | 68 | 15 | 360 | 205 | 86 | 1214 |
| ilpo_statutes | 131 | 100 | 276 | 74 | 15 | 392 | 226 | 84 | 1316 |
| inpi_br_statutes | 119 | 98 | 267 | 56 | 15 | 287 | 223 | 81 | 1166 |
| ipo_in_statutes | 140 | 113 | 275 | 37 | 34 | 178 | 162 | 96 | 1053 |
| ipo_in_mppp | 136 | 66 | 180 | 36 | 24 | 166 | 127 | 68 | 820 |
| dpma_statutes | 131 | 114 | 270 | 52 | 29 | 165 | 156 | 102 | 1037 |
| legifrance_ip | 111 | 49 | 177 | 40 | 79 | 201 | 168 | 69 | 911 |
| tw_trade_secrets | 140 | 101 | 236 | 46 | 31 | 176 | 136 | 71 | 954 |

Package total: **19,482 lines**. MCP tool modules for these corpora: **4,607 lines** (mpep, epc,
epo_guidelines, epo_pct_guidelines, epo_up_guidelines, epo_case_law, ukipo_mopp, upc, ipos, ilpo,
inpi_br_statutes, ipo_in_statutes, ipo_in_mppp, dpma_statutes, legifrance_ip, tw_trade_secrets;
the TMEP section of trademarks.py is extra). Slice total is roughly **24,100 lines**.

They fall into three families:

- **A. Outline corpora (8):** mpep, tmep, epc, epo_guidelines, epo_pct_guidelines,
  epo_up_guidelines, epo_case_law, ukipo_mopp. Same `sections(href, section_number, title,
  breadcrumb, chapter, html, text)` schema, same DB class, HTML crawler builds.
- **B. Statute corpora, fetched (5):** upc_statutes (uses an `instruments` table, not `sections`),
  ipos_statutes, ipos_manuals, ilpo_statutes, inpi_br_statutes. PDF or HTML fetch → parse →
  write.
- **C. Statute corpora, seeded (5):** ipo_in_statutes, ipo_in_mppp, dpma_statutes, legifrance_ip,
  tw_trade_secrets. Build from a bundled `data/seed.jsonl`.

## 2. What is already shared, and who doesn't use it

`mcp_data_core/corpus_db.py` (451 lines) already provides:
- `CorpusDBBase`: path resolution (explicit → `ENV_VAR` → `~/.cache/...`), the install hint,
  `open()` with the `immutable=1` read-only URI and the `CorpusProvider` hook, lifecycle, `meta()`,
  `meta_get()`, and zstd column decode (`_column_value`).
- `OutlineCorpusDB`: `get_section`, `search` (snippet, BM25, or outline order), `count_for`.

`mcp_data_core/corpus_compression.py` provides `finalize_outline_corpus` (compress `html`, run FTS
optimize, VACUUM).

Adoption:
- Family A: all 8 `corpus/db.py` subclass `OutlineCorpusDB` (each file is 54 lines, about 50 of
  them docstring and import boilerplate; e.g. `mpep/corpus/db.py:39`). All 8 builds call
  `finalize_outline_corpus` (e.g. `epo_guidelines/corpus/build.py:221`).
- Family C plus upc_statutes (6) subclass `CorpusDBBase` and hand-write `search`/`get_section`
  (e.g. `dpma_statutes/corpus/db.py:48`, `upc_statutes/corpus/db.py:52`).
- **Four packages don't use the base at all:** `ipos_statutes/corpus/db.py`,
  `ipos_manuals/corpus/db.py`, `ilpo_statutes/corpus/db.py`, `inpi_br_statutes/corpus/db.py`. Each
  re-implements `CorpusUnavailable`, `_resolve_corpus_path`, `_INSTALL_HINT`, `open`, `close`,
  `__enter__`, `__exit__`, and `meta` (184 lines in total). The behavior has drifted:
  - They open with `file:...?mode=ro`, without `immutable=1` (`ipos_statutes/corpus/db.py:97`,
    `ipos_manuals:87`, `ilpo_statutes:93`, `inpi_br_statutes:96`). The base class comment at
    `corpus_db.py:267-273` says plain `mode=ro` fails on gcsfuse / Cloud Storage FUSE mounts.
  - They skip the `CorpusProvider.ensure()` hook, so a registered provider can never supply these
    four corpora.
  - Each defines its own `class CorpusUnavailable(RuntimeError)` (`ipos_statutes/corpus/db.py:22`
    and the others). It is not the `mcp_data_core` class, so `except
    mcp_data_core.corpus_db.CorpusUnavailable` will not catch it.
- Nothing shared exists above the DB layer. Every `__init__.get_corpus_status`, client, api, build
  `main`, and MCP module is hand-copied.

## 3. Proposed primitives

Estimates use the measured spans below. I extracted them with an AST script that sums the
`end_lineno - lineno + 1` of named top-level defs and methods. Docstrings are included because
they get removed along with the code.

### P1. `corpus_status_reader` (status and recency factory)

- **Owns:** the `CorpusStatus` TypedDict, `get_corpus_status()`, and `_parse_snapshot_date()`. The
  factory signature would be:
  `make_corpus_status(db_cls, *, version_keys=("source_version",), unknown_values=(), snapshot_fallback="snapshot-{date}" | None, synced_at_keys=("snapshot_date",))`.
  Each package keeps a module-level `get_corpus_status = make_corpus_status(CorpusDB, ...)`, which
  `scripts/build_coverage.py:411-433` requires (it imports the module and checks
  `callable(getattr(mod, "get_corpus_status"))`).
- **Used today:** all 18 `__init__.py` files (e.g. `mpep/__init__.py:47-124`,
  `epc/__init__.py:103`, `dpma_statutes/__init__.py:114`).
- **Lines:** the measured span (TypedDict + function + parser) is 1,304 lines over 18 files, about
  72 each. After: about 70 shared lines plus about 6 per package (108). **Saves about 1,125.**
- **Stays source-specific:** which meta key carries the version, and the fallback label.
- **Divergences to reconcile:**
  - Version key: `source_version` (mpep, tmep, ilpo, legifrance); `epc_year` (epc);
    `guidelines_year` (epo_guidelines); `source_version` then `guidelines_year`
    (epo_pct_guidelines); `source_version` then `up_guidelines_year` (epo_up_guidelines);
    `caselaw_year` (epo_case_law); `lpi_year` (inpi_br_statutes).
  - Snapshot fallback separator: `"snapshot-<date>"` (ukipo_mopp, ipo_in_statutes, ipo_in_mppp,
    dpma, tw) but `"snapshot <date>"` with a space (upc_statutes, ipos_statutes, ipos_manuals). No
    fallback at all (and therefore `"unknown"`) in the other 10.
  - upc_statutes ignores `source_version` entirely (`upc_statutes/__init__.py`, the
    `get_corpus_status` body).
  - Only mpep maps `"current"` to `"unknown"` and reads `synced_at` before `snapshot_date`, and only
    mpep's parser accepts full ISO datetimes (`mpep/__init__.py:97-117`). tmep's build writes
    `source_version="current"` (`tmep/corpus/build.py:331`), so TMEP reports `corpus_version="current"`,
    which mpep would report as `"unknown"`.
  - Log-message labels differ (cosmetic).
- **Tests:** 18 `tests/<pkg>/test_corpus_status.py` files assert the exact version strings, so they
  will catch any change in the separator or key order. Keep each package's current policy through
  config, then decide separately whether to normalize.

### P2. `fts_match_expression` (query translator)

- **Owns:** turning `(query, syntax)` into an FTS5 MATCH string, plus token quoting.
- **Used today:** 18 copies of `_translate_fts_query` and 8 of `_quote_if_needed` /
  `_BARE_TOKEN_RE` (e.g. `epc/client.py:56`, `dpma_statutes/client.py:97-119`,
  `mpep/client.py:32`, `legifrance_ip/client.py:37`).
- **Lines:** 299 measured. After: about 25 shared plus 18 imports. **Saves about 255.**
- **Stays source-specific:** the default syntax only. Families A and inpi_br default to `"adj"`;
  families B and C default to `"and"`.
- **Divergences (4 variants), one of which is a live bug:**
  1. The safe variant quotes non-`\w+` tokens (the 8 statute packages).
  2. mpep quotes every token.
  3. tmep, epc, the four epo_* packages, ukipo_mopp, and inpi_br_statutes pass `and`/`or` tokens
     unquoted.
  4. legifrance_ip has no `syntax` argument and always passes raw tokens.

  I checked variants 3 and 4 against sqlite: `54(2) EPC`, `art. 54`, and `L. 611-10` all raise
  `sqlite3.OperationalError: fts5: syntax error`. No package or MCP module catches
  `OperationalError` on the query path (grep finds it only in the four hand-rolled `open()`
  methods), so this surfaces as an unhandled tool error and breaks §5.12. Adopting the
  `_quote_if_needed` variant everywhere fixes it. It also changes results slightly for mpep (bare
  tokens become unquoted, which is equivalent for `\w+` tokens).
- **Tests:** `ipos_statutes/`, `ipos_manuals/`, `ilpo_statutes/`, and `upc_statutes/test_corpus.py`
  (about 8 references each) and `legifrance_ip/test_client.py` import the private helpers, so keep
  re-exports. No test covers punctuation under `and`/`or` in family A. Add one per family before
  switching.

### P3. Move the four hand-rolled DBs onto `CorpusDBBase`

- **Owns:** nothing new. This is adoption of the existing base.
- **Used today:** `ipos_statutes/corpus/db.py:20-115`, `ipos_manuals/corpus/db.py`,
  `ilpo_statutes/corpus/db.py`, `inpi_br_statutes/corpus/db.py`.
- **Lines:** 184 measured. After: 4 × about 6 lines of class vars. **Saves about 160.** About 36
  more come from changing the 18 module-level `default_corpus_path()` functions (53 lines) into
  `default_corpus_path = CorpusDB.default_path`. Four packages call it internally
  (`ipos_statutes/corpus/db.py:61` and the others).
- **Stays source-specific:** the row dataclasses and the query methods.
- **Risks:** this gains `immutable=1` and the provider hook, which is the intended fix. The
  exception identity changes: each package's `CorpusUnavailable` becomes the `mcp_data_core` one, so
  re-export it under the same name to keep imports working. The statute DBs read `row["text"]`
  directly rather than `self._column_value(...)`, so zstd compression silently doesn't apply to
  them. That's harmless today but becomes a trap once they are on the base.
- **Tests:** the four `test_corpus.py` files (56, 51, 56, and 49 tests across the packages). Add
  one test each that the opened connection URI includes `immutable=1`, or more simply that
  `isinstance(db, CorpusDBBase)`.

### P4. Declarative FTS search on `CorpusDBBase` (`fts_search`)

- **Owns:** a protected helper,
  `self._fts_search(table="sections", select=(...), snippet_col=N, filters={"statute": x, "language": y}, order_by=("statute","section"), limit, offset, snippet_chars)`.
  It builds the snippet/JOIN/MATCH/filter/ORDER/LIMIT SQL, applies the shared
  `token_count = max(8, min(snippet_chars // 5, 64))` (copied verbatim in 10 dbs, e.g.
  `dpma_statutes/corpus/db.py:112` and `upc_statutes/corpus/db.py:103`), and returns `sqlite3.Row`
  objects. Add `_count_for(...)` and `_rows_where(...)` for the "get by (statute, section)" and
  "find by number across statutes" lookups.
- **Used today:** the hand-written `search()` in the 10 family B and C dbs. The measured span is 538
  lines (`dpma_statutes/corpus/db.py:84-138`, `upc_statutes/corpus/db.py:84-138`,
  `legifrance_ip/corpus/db.py:76-135`, and so on).
- **Lines:** 538 → about 50 shared plus 10 × 12. **Saves about 370.**
- **Stays source-specific:** the column list, snippet column index, filter columns, outline order,
  and hit dataclass.
- **Divergences:** the snippet column index varies (1 in legifrance; 2 in ipos_statutes,
  ipos_manuals, ipo_in_mppp, tw, upc; 3 in dpma, ilpo, ipo_in_statutes, inpi_br). upc uses the
  `instruments`/`instruments_fts` tables. legifrance has no `sort` and uses a different tokenizer
  (`unicode61 remove_diacritics 2`, no porter), which matters only to the schema. Some return
  `rank` and some don't.
- **Tests:** the families B and C `test_corpus.py`/`test_client.py` suites (about 400 tests in
  total). `mcp-data-core/tests/test_corpus_db.py` has 23 tests; add helper tests there.

### P5. `CorpusClient` base (async lifecycle and pagination)

- **Owns:** `__init__(corpus_path=None)`, lazy `_open()`, `close`, `__aenter__`, `__aexit__`, and a
  `_page(fetch, page, per_page) -> (rows, has_more)` helper for the "fetch per_page+1, slice,
  has_more" idiom (18 copies, e.g. `epc/client.py:169-172`, `dpma_statutes/client.py` in `search`).
  Generic over the `DB` type (`DB_CLS` class var).
- **Used today:** all 18 `client.py` files.
- **Lines:** the lifecycle span is 374 lines. After: about 35 shared and about 3 per subclass.
  **Saves about 285.** The pagination idiom adds about 6 lines × 18. **Saves about 80 more,** so
  about 365 in total.
- **Stays source-specific:** citation parsing, result models, and the query surface.
- **Risks:** outline clients also carry `base_url` and `DEFAULT_*` env lookups at class-definition
  time (`epc/client.py:106-108`), so keep them as class vars. Tests construct clients with
  `corpus_path=`.
- **Tests:** the per-package `test_client.py` files.

### P6. Outline-family generic layer (client, models, api, schema)

This is the biggest win, because family A's eight packages are template copies. Measured diffs
against mpep: `corpus/db.py` 22–26 changed lines, `schema.py` 6, `resources.py` 6, `models.py` 14,
`api.py` 56 (tmep 156).

- **Owns:**
  - `OUTLINE_DDL` and `OUTLINE_SCHEMA_VERSION` in `mcp_data_core` (next to `OutlineCorpusDB`).
    Each `schema.py` becomes `DDL = OUTLINE_DDL` plus its `META_KEYS`. tmep's schema is identical
    except that it lacks `META_KEYS`.
  - `OutlineSearchHit`, `OutlineSearchResponse`, `OutlineSection`, and `OutlineVersion` pydantic
    bases. The package models become empty subclasses so the public names survive. mpep's
    `MpepSection` adds `source_url`, `content_sha256`, `section_revision`, and `corpus_metadata`
    (`mpep/models.py:26-29`).
  - `OutlineCorpusClient(CorpusClient)` with `search`, `get_section` (it tries a list of
    `candidate_hrefs(ref)` and then `section_number` lookups), `resolve_section_href`,
    `list_versions`, and `_hit_to_model`. Subclasses provide `citation_candidates()`,
    `normalize_href()`, `result_url(href, version)`, `VERSION_META_KEY`, and `VERSION_LABEL`.
  - `outline_api` helpers: shared `SearchInput`/`SectionInput` plus generic
    `search(params, client_cls)` and `get_section(...)`. Each `api.py` keeps typed one-line
    wrappers.
- **Used today:** `mpep/`, `tmep/`, `epc/`, `epo_guidelines/`, `epo_pct_guidelines/`,
  `epo_up_guidelines/`, `epo_case_law/`, `ukipo_mopp/`.
- **Lines:**
  - api: 1,532 → 8 × about 45 + about 130 shared. Saves about 1,040. To be conservative I count
    **about 900**.
  - schema: 566 → 8 × about 12 + about 55. Saves about **415**.
  - db (docstring/import shells): 432 → 8 × about 12. Saves about **335**.
  - models: 260 → 8 × about 10 + about 35. Saves about **145**.
  - client: about 590 (outline `search` ≈ 8 × 29, plus 359 for `_hit_to_model`, `list_versions`,
    and `resolve_section_href`) → about 90 shared + 8 × 10. Saves about **420**.
  - **Subtotal: about 2,200.** This is the softest estimate here. The api wrappers might stay
    longer if you want explicit signatures for docs.
- **Stays source-specific:** citation regexes (`epc/client.py:34-53`), href normalization, the
  result-URL template, the version meta key, and in mpep the release-metadata fields.
- **Divergences:** the eight `_hit_to_model` copies differ only in model class and URL builder. The
  `get_section` resolution chains differ: epc tries the citation slug, then the section number,
  then the href (`epc/client.py:186-219`), and mpep has its own section-number resolution.
  `SearchInput` carries MPEP-only no-op parameters (`include_index`, `include_notes`,
  `include_form_paragraphs`), which every client `del`s (`epc/client.py:163-164`).
  `epc/api.py:61-69` still documents MPEP examples (`"2106"`, `"d0e122292.html"`), a copy-paste
  artifact. Only mpep's `_translate_fts_query` quotes tokens (see P2).
- **Tests:** the 8 conftests build fixture corpora from each package's `corpus.schema.DDL` (36 test
  files import `...corpus.schema import DDL`), so keep `DDL` exported. Also covered by
  `test_client.py`, `test_mcp_envelope.py`, `test_corpus_status.py`, and mpep's
  `test_source_identity.py` and `test_api.py`.

### P7. Build scaffolding (`corpus_build` module)

- **Owns:**
  - `atomic_output(path)`: a context manager that writes to `.tmp` and renames.
  - `init_corpus(conn, ddl, meta: dict)`: `executescript` plus `INSERT OR REPLACE INTO meta`.
  - `fetch_text(client, url)`: the `default_retryer` GET. There are 7 byte-identical copies:
    epc, epo_guidelines, epo_pct_guidelines, epo_up_guidelines, epo_case_law, ukipo_mopp,
    inpi_br_statutes (e.g. `epo_guidelines/corpus/build.py:92`).
  - `normalize_whitespace` (9 copies, 3 variants).
  - `load_jsonl_seed(path, required_keys)` (5 copies; they differ only in required keys:
    `dpma_statutes/corpus/build.py:44` and `ipo_in_statutes`, `ipo_in_mppp`, `tw`, and
    `legifrance` equivalents).
  - `run_build_cli(parser, build_fn)`: sets up logging, `asyncio.run` or a direct call, maps
    KeyboardInterrupt to 130 and Exception to 1, and prints "Wrote N".
- **Used today:** all 18 `corpus/build.py` files. Their 18 entry points are in `pyproject.toml:67-84`.
- **Lines:**
  - `main()`: 913 measured → about 15 per package for the argument definitions + about 40 shared.
    Saves about **600**.
  - `_fetch`, `_normalize_whitespace`, `_load_seed`: 180 → about 35 shared. Saves about **145**.
  - The tmp/rename and meta-write boilerplate inside `build_corpus`/`write_corpus` (about 15
    lines × 18) saves about **220**.
  - **Subtotal: about 965.**
- **Stays source-specific:** discovery (crawl, sitemap, or PDF list), page parsing, row mapping,
  and the extra meta keys.
- **Divergences:**
  - **Atomicity.** Eleven builds write to `.tmp` and rename. Seven delete the existing output and
    then write in place (`mpep/corpus/build.py:367`, `tmep:299`, `upc_statutes:218`,
    `ipos_statutes:255`, `ipos_manuals:215`, `ilpo_statutes:281`, `legifrance_ip:109`). An
    interrupted build in those seven leaves no corpus. A shared helper fixes this.
  - **`section_count` meta.** Written by mpep, tmep, all of families B and C except upc, and none
    of epc or the epo_*/ukipo_mopp crawlers, even though `mpep/corpus/schema.py:67-72` lists it as
    a standard key and `corpus_bootstrap.py` manifests carry it.
  - **Finalization.** Only family A calls `finalize_outline_corpus`. The statute builds never run
    FTS `optimize` or VACUUM.
- **Tests:** the `test_build.py` files in epo_guidelines, ukipo_mopp, ipos_statutes, ipos_manuals,
  ilpo_statutes, inpi_br_statutes, ipo_in_statutes, ipo_in_mppp, dpma_statutes, legifrance_ip, and
  tw_trade_secrets (11 of 18). mpep, tmep, epc, epo_pct, epo_up, epo_case_law, and upc have no build
  tests, so add smoke tests with an `httpx.MockTransport` before touching those.

### P8. MCP corpus-tool helpers (`mcp/tools/_corpus.py` or `mcp_data_core.mcp`)

- **Owns:**
  - `corpus_provenance(status, source_url, source_name)`, about 15 near-identical copies (e.g.
    `mcp/tools/epc.py:52`, `dpma_statutes.py:50`).
  - `truncate` (14 identical copies, e.g. `epc.py:69`).
  - `offset_to_page(offset, limit)`: the line `page = (offset // limit) + 1 if offset >= 0 else 1`
    appears verbatim in 12 modules.
  - `validate_limit`.
  - `hits_summary(label, query, n, has_more, version)`.
  - `fan_out(refs, fetch_one, concurrency=5)`: the semaphore plus `gather` (e.g.
    `epc.py:246-254`, `dpma_statutes.py:208-217`).
  - `dump_model`: the `_section_to_dict` and `_dump` copies.
- **Used today:** 16 tool modules plus the TMEP block in `trademarks.py:84-160`.
- **Lines:** helpers measured at 391 lines → about 40 shared + about 5 per module. Saves about
  **270**. Tool bodies (page math, summary, fan-out, envelope) save about 25 per module × 12 search
  plus get pairs, about **300**. **Subtotal: about 570.** Tool docstrings and `Annotated`
  descriptions, about 600 lines, must stay per connector (§5.6, §5.13).
- **Stays source-specific:** tool names and signatures, descriptions, the lean `_stub_hit`
  projection (12 variants), and `_summarize_section` (12 variants).
- **Divergences and risks:**
  - Each search or get tool calls `get_corpus_status()` twice, once for the summary and once
    inside the provenance helper (e.g. `epc.py:196` and `epc.py:60`). Each call opens the SQLite
    file, so every request does three opens: client, status, and status again. A shared helper
    should take the status as an argument and call it once.
  - `get_corpus_status()` ignores a client's `corpus_path` override.
  - Offsets that aren't a multiple of `limit` are silently rounded down to a page boundary.
  - Tests patch client classes by tool-module attribute (e.g. `tools.ipos.IposStatutesClient`,
    `tools.ilpo.IlpoStatutesClient`, `tools.ilpo.search`). Helpers must receive the class or
    callable at call time, never bind it at import.
- **Tests:** the per-package `test_mcp_envelope.py` files (16) check the envelope shape and
  provenance fields.

### P9. EPO legal-site crawler and the guidelines merge

- **Owns:** one `epo_legal` crawler: index fetch, link enumeration, BFS queue, `_SLUG_RE` gate,
  insert. It is parameterized by book path (`guidelines-epc`, `guidelines-pct`, `guidelines-up`,
  `case-law`, `epc`).
- **Evidence:** `epo_guidelines` vs `epo_pct_guidelines` differ by 18 lines out of 280 in
  `build.py` (only the path segment and description, `epo_guidelines/corpus/build.py:60,156`), by
  60 out of 280 in `client.py`, and by 0 in `schema.py`. They are the same connector. The
  epo_case_law vs epo_up_guidelines pair (symilar: 167 lines) and epc share `_fetch`, the crawl
  loop, and `_extract_main_content` (4 variants across 6 files). epo_up discovers via the sitemap
  (`epo_up_guidelines/corpus/build.py:74`).
- **Lines (incremental after P1–P8):** pct as a config of epo_guidelines (keeping its own
  `CorpusDB`, env var, tool names, and corpus file) saves about 350. The shared crawl loop for the
  other three saves about 250. **About 600.**
- **Risks:** the corpus filenames and env vars (`guidelines.db` / `GUIDELINES_CORPUS_PATH`,
  `pct_guidelines.db` / `PCT_GUIDELINES_CORPUS_PATH`) and the console-script names must not change.
  The catalog source records stay separate.
- **Tests:** epo_guidelines `test_build.py` (the only EPO build test) and the client tests for
  each package.

### P10. `usage_resource(package)` (minor)

13 of the `resources.py` files are 15-line copies differing only in package name (diff of 6
lines). **Saves about 130.** The others (legifrance 79 lines, dpma 29, tw 31, ipo_in_* 24–34)
carry extra content.

## 4. Totals

| primitive | est. lines removed |
|---|---|
| P1 corpus status factory | 1,125 |
| P2 FTS query translator | 255 |
| P3 hand-rolled DBs → CorpusDBBase | 160 (+36) |
| P4 declarative `fts_search` | 370 |
| P5 CorpusClient base | 365 |
| P6 outline generic layer | 2,200 (soft) |
| P7 build scaffolding | 965 |
| P8 MCP corpus helpers | 570 |
| P9 EPO crawler / guidelines merge | 600 |
| P10 usage resource helper | 130 |
| **total** | **about 6,700 (range 5,500–7,000)** |

That is roughly 28% of the slice's 24,100 lines. After this, a new outline corpus would be about
150 lines of config, citation parsing, and crawl parsing plus its MCP tool docstrings, against
about 1,000 + 270 today.

## 5. Recommended order

1. **P2 and P3 first.** They are small, and each fixes a real defect: FTS syntax errors on
   punctuation, and the four DBs missing `immutable=1`, the provider hook, and the shared
   exception. Add the missing tests first.
2. **P1.** It touches all 18 packages, but the existing status tests pin the behavior. Keep every
   package's current version policy as config.
3. **P7.** Start with the atomic-output and CLI helpers, adding build smoke tests for the seven
   untested builds before migrating them.
4. **P4 and P5**, then **P6** (outline), then **P8** (MCP), then **P9.**

Put P1–P5 in `mcp_data_core` (next to `corpus_db.py`) only if other consumers (law-tools) have
corpora too. Otherwise put them in `patent_client_agents/_corpus/` so you avoid a cross-package
release, given the PyPI propagation lag noted in project memory.

## 6. Other divergences found along the way

- tmep reports `corpus_version="current"`, while mpep normalizes that to `"unknown"`.
- `epc/api.py:61-69` `SectionInput` documents MPEP examples. The same text appears in the other
  outline `api.py` files that were copied from mpep.
- `default_corpus_path()` duplicates `CorpusDB.default_path()` in all 18 `db.py` files.
- The statute DBs bypass `_column_value`, so build-time compression can't be adopted there without
  a read-side change.
- `get_corpus_status()` always reads the default or env path, never a client's explicit
  `corpus_path`.
