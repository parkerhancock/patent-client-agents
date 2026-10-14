# patent-client-agents: refactor plan before Rust migration

Date: 2026-10-14. Baseline: `main` at 45cb1e0, 96,109 source lines, 3,767 tests passing.

Source reports in this folder: `source-corpus.md`, `source-mcp.md`,
`source-api_clients.md`, `source-fees.md` and `source-scrapers_misc.md`. The
duplicate-code scan was `pylint symilar -d 8` with comments, docstrings, imports and
signatures ignored. The agents read mcp-data-core 0.11.3; 0.12.0 (released the same
day) already contains the `_build_url` fix and per-host request pacing.

## Size of the opportunity

Verbatim duplication is only 3.9% (3,785 lines in repeated blocks of 8+ lines).
Most of the savings come from code that has the same structure but was renamed or
lightly edited in each copy.

| Slice | Lines today | Est. removable | Biggest primitive |
| --- | --- | --- | --- |
| Bundled document collections (18 pkgs + their tool modules) | ~24,100 | ~6,700 | Shared outline layer, status factory, build scaffold |
| Live API clients (27 pkgs) | ~23,800 | ~3,900 | `one_shot()` factory replacing 17 `api.py` wrapper layers |
| Fees (`fees/`) | ~15,100 | ~1,690 | `OfficeProfile` + `FeeSourceClient` base |
| MCP layer, excluding collection tools (counted above) | ~20,300 | ~1,500 | Bounded fan-out for list-accepting `get_*`, shared `dump()` |
| Scrapers, courts, shared modules | ~12,700 | ~975 | Generic model builders, delete bespoke Google cache |
| **Source total** | **~96,100** | **~14,800 (~15%)** | |
| Tests | | ~2,350 | Corpus-status contract tests, shared MockTransport |

All estimates come from the agents' line counts and haven't been checked by
implementing anything. The corpus estimate is the softest of them: 2,200 of its
6,700 lines depend on how cleanly the 8 outline packages fold into one generic layer.

## Status (updated 2026-10-14)

Phase 0 is closed and Phase 1 is done. Fixed and merged:

- the 4 bugs confirmed below
- the fee effective dates (#117)
- 8 more bugs found while tightening tests: the TMSearch lean fields,
  Thai DIP exact match, EPO quota headers, Assignment Center provenance,
  TMEP "current" version, INPI Brazil titles, TIPO goods classes, EUIPO
  multilingual fields, and PPUBS stale caseId (#112-#127)

The `_build_url` passthrough and `transport=` shipped in mcp-data-core
0.12.0 and 0.13.0.

Test-suite work done in Phase 0:

- Removed the DELETE-verdict tests that no other coverage depends on, with no
  coverage loss (#118). The rest are listed in `tests-kept-for-coverage.md`.
- Fixed tests that passed without checking behavior (#119-#121).
- Moved the IP Australia, EUIPO, Thai DIP, IPONZ, Swiss IPI, EPO/CPC, PRH,
  PRV and PPUBS suites from `client=` to `transport=`, so auth runs under
  test (#122-#126).

Left open when Phase 0 stopped:

- About 149 `client=` uses in tests. Most are the `api.py` wrapper tests,
  which go away with `one_shot()` in Phase 4.
- Envelope shape-assertion cleanup. This is smaller than estimated: about 300
  assertions and 24 shape-only tests, since `validate_mcp_contracts.py`
  already checks shape.
- Moving `test_core.py` and `test_cache.py` to mcp-data-core.
- Gap tests:
  - fee source fixtures for 15 routes
  - collection paging, including the `offset // limit` rounding
  - collection build smoke tests
  - a Google Patents page fixture
  - `ApplicationsClient` over HTTP

## Bugs found

These were confirmed by running code or by reading the line that causes them:

1. **Searches with punctuation crash.** In TMEP `and`/`or` mode, the query
   `1207.01(a) confusion` raises `OperationalError: fts5: syntax error near "."`
   (reproduced). The corpus report lists 10 packages with the same problem.
2. **Malformed download URL.** CKAN `download_resource` produces a bad URL.
   `BaseAsyncClient._build_url` (`mcp-data-core/.../base_client.py:230`) adds
   `base_url` to the front of every path, including absolute URLs. This affects
   `ilpo_tm`, `inpi_br_bulk` and `ip_australia_bulk`.
3. **Google Patents PDFs come back corrupted from cache.** The first fetch is fine.
   On a cache hit the content type is `None` and the bytes don't match (reproduced).
   `unified` then quietly falls through to PPUBS/EPO.
4. **Fees report the fetch date as the effective date.** CNIPA patent, DPMA patent,
   EPO patent and EUIPO trademark set `effective_date` to the fetch date. The
   snapshot merged in #104 published those dates.

These were reported by the agents and not re-checked by me:

5. `ttl_seconds` in mcp-data-core never forces caching, so responses without cache
   headers are refetched every time.
6. Provenance `cache_hit` is never set outside `fees.py`, and `retrieved_at` is always
   "now", even for cached responses. This breaks CONNECTOR_STANDARDS §3.
7. `page = (offset // limit) + 1` in 13 collection tools silently rounds down any
   offset that isn't a multiple of the limit.
8. Rate limiters and auth tokens live on each client instance, and every MCP call
   builds a new client. The 10 requests/minute limits for JPO and INPI aren't
   enforced across calls, and JPO, Swissreg, INPI, EUIPO and IP Australia fetch a new
   token on every call.
9. Four collection packages (`ipos_statutes`, `ipos_manuals`, `ilpo_statutes`,
   `inpi_br_statutes`) skip `CorpusDBBase`. They miss `immutable=1` for gcsfuse
   mounts.
10. The `usitc` resource getters import `law_tools.usitc.docs`, which isn't a
    dependency.
11. Five clients (`iponz`, `swissreg`, `oepm`, `thai_dip`, `dpma`) call `self._client`
    directly, so they get no retry and no error logging.
12. Every nightly fee snapshot rewrites all 55 files because `retrieved_at` changes
    each day, even when no fee changed.

## Proposed order

The ordering principle is to lock down behavior first, then fix bugs in small PRs,
then extract primitives into mcp-data-core, and only then collapse each connector
family onto them. Each step is its own PR with the suite green.

### Phase 0: safety net (no behavior change)

- Capture source bytes for every fee route and generate characterization goldens
  from the current scrapers. About 24 routes have no fixture today, and some of
  their scrapers have only 16–47% coverage.
- Add tests that don't exist yet:
  - collection offset/limit paging
  - fan-out ordering and partial failure
  - a second-call cache hit
  - a Google HTML→Markdown golden
  - EUIPO request paths
  - smoke tests for the 7 collection builds that have none
- Amend CONNECTOR_STANDARDS §5.15. It currently says helpers stay in each module and
  repetition is acceptable. Shared helpers will fail review until it changes.

### Phase 1: bug fixes (small, independent PRs)

- Absolute-URL passthrough in `BaseAsyncClient._build_url` (fixes 2). Done in
  mcp-data-core 0.12.0. This repo needs to bump to `>=0.12.0`, add a full-URL test
  for the CKAN downloads, and drop the PRH and USPTO ODP `_build_url` overrides.
- A TTL-forcing cache policy in mcp-data-core, then delete `google_patents/cache.py`
  (fixes 3 and 5).
- One shared FTS query translator, using the quoting the statute packages already do
  (fixes 1).
- Move the four collection packages onto `CorpusDBBase` (fixes 9).
- Record hishel's from-cache flag in the base client, so provenance is right
  everywhere (fixes 6).
- Fees: use the real effective date or `None`, and only bump `retrieved_at` when
  content changes (fixes 4 and 12).
- Paging fix (7), module-level token cache and rate limiter (8), the usitc import
  (10), routing the five bypassing clients through `_request` (11), and `ValueError`
  → `NotFoundError` at `mcp/tools/patents.py:443` and `:575`.

### Phase 2: startup cost

- Import markitdown, playwright and curl_cffi only inside the functions that use
  them. Replace markitdown with markdownify for Google Patents (needs the Phase 0
  golden first).
- Stop importing the Google auth provider on every `mcp_data_core.mcp` import.
- Drop unused runtime dependencies: the `markitdown[pdf]` extra, `python-dateutil`,
  `pyyaml`, `zstandard`, and the duplicated `tenacity` line. Verify each one with
  `grep` before removing it.
- The target is ~1.6 s and well under the current 196 MB at import. Re-measure
  afterward.

### Phase 3: primitives in `patent_client_agents.shared`

Decided 2026-10-14: these live in a `shared/` package inside this repo, not in
mcp-data-core. That avoids a release per change and leaves law-tools
untouched. A proven helper can move down later if law-tools needs it. The
cache-hit flag goes in a thin `BaseAsyncClient` subclass in `shared/client.py`.
The list below was written for mcp-data-core; read it as `shared/`.

These are shared with law-tools, which has 21 `BaseAsyncClient` subclasses, so
keep the changes additive.

- `dump()` with explicit flags, `provenance_for()`, `as_id_list` / `gather_bounded` /
  `ids_summary`, and the `Limit`/`Offset` parameter types.
- `ApiModel` plus `LenientDate`, `EmptyStrNone` and `CoerceList`.
- A token-auth class with refresh-and-retry-once. Process-wide per-host pacing
  (`MIN_REQUEST_INTERVAL`) already exists in mcp-data-core 0.12.0.
- `one_shot()` for module-level wrapper functions.
- A collection status factory, an FTS search spec and a build-script runner with
  atomic writes.

### Phase 4: move each connector family onto the primitives

Do the families in order of savings divided by risk:

1. Bundled document collections: status factory → build scaffold → MCP helpers → the
   outline generic layer. Merge `epo_guidelines` and `epo_pct_guidelines`; the agent
   found they differ only by a path segment.
2. The `api.py` layers via `one_shot()`, the CKAN trio, the IP Australia trio, the
   EUIPO pair, and the declarative USPTO ODP resource spec.
3. Fees: `FeeSourceClient`, `OfficeProfile`, slug/code allocator, `parse_amount`. Do
   the keyword categorizers last, because rule order matters there.
4. The MCP fan-out and `dump()` sweep across tool modules.

### Phase 5: breaking cleanup (next major or minor release)

- Remove the deprecated `client=` paths (~690 lines repo-wide). Tests that inject
  fake clients through `client=` need rewriting first.
- Delete the dead Google client methods and stale AGENTS.md lines about `archive/`.

## How this sets up the Rust work

After Phase 4, the CPU work sits in a handful of shared modules instead of ~60
copies:

- the FTS query translator and search spec
- the HTML parsing builders
- `parse_amount` and PDF text extraction in fees
- the base client

Each one has characterization tests from Phase 0, so it can be swapped for a PyO3
module behind the same Python interface and checked against the same goldens.
Profile the hosted server under real traffic before choosing among them. The
measurements so far suggest the startup fix in Phase 2 matters more than any of
them.

## Test-suite audit (added 2026-10-14)

All 3,798 collected tests were classified against one rubric: a test earns its place
if it would still pass after a correct refactor and fail after a real bug. Detail is
in `tests-audit-{A,B,C}.csv` and `.md`. A covers fees, jpo, uspto_odp,
google_patents and epo_ops; B covers the other API clients and scrapers; C covers
the document collections and the top-level tests.

| Verdict | Tests | Share | Test-body lines |
| --- | --- | --- | --- |
| Keep | 1,926 | 51% | 13,702 |
| Rewrite as behavior test | 1,393 | 37% | 16,243 |
| Delete | 479 | 13% | 3,000 |

The line counts cover test function bodies only. Fixtures and helpers follow the
tests that use them.

Patterns:

- Fees is mostly sound: 567 of its 656 tests are keep.
- Most rewrites have good assertions but inject fakes through the deprecated
  `client=` argument. A `transport=` injection seam that keeps `auth` attached would
  make most of them mechanical to convert.
- The per-tool envelope and provenance checks repeat in every `test_mcp_envelope.py`.
  One contract test over the tool registry replaces the shape half of them.
- The 99 tests in `test_core.py` and `test_cache.py` test mcp-data-core and belong in
  that package.

### Bugs found by the audit

These were confirmed in code or by running it:

- TMSearch compact output has empty serial, owner, dates and status.
  `mcp/tools/trademarks.py:42` dumps snake_case, but the stub and summary read
  camelCase.
- Thai DIP `get_trademark` uses a wildcard match on the application number
  (`thai_dip/client.py:57`) and returns `rows[0]`.
- EPO 403 quota headers are never read. `epo_ops/client.py:256` copies the
  lowercased httpx headers into a plain dict, then looks them up in mixed case.

These were reported by the agents and not checked by me:

- INPI design search filters on the trademark status field.
- USITC `download_attachment` uses the raw Content-Disposition header as the filename.
- The assignments provenance tests pin the retired `assignment-api.uspto.gov` host.
- KIPO provenance uses a disabled hard-coded BASE_URL.

### Tests that pass while checking the wrong thing (fix or delete first)

- The `usitc/test_date_filtering.py` tests reimplement the filter in the test body.
- The `uspto_assignments` filter test asserts `filtered <= unfiltered`.
- The TIPO, TSDR, and some JPO cassette tests assert only `isinstance(list)` or
  "None or valid".
- The 24 PTAB cassette tests are skipped in CI because they need a real API key even
  in replay mode, and they assert only `count >= 0`.
- MPEP `test_version_string_is_source_version_from_meta` asserts `'unknown'`.
- `TestForbiddenErrorBuilder` pins the EPO header bug above.

### Largest coverage gaps

- 15 of 25 fee offices have no recorded source page. IP India and the WIPO
  PCT/Madrid/Hague routes have no tests.
- EUIPO request paths and its OAuth setup.
- The IP Australia token fetch.
- Error mapping for KIPO, TIPO, CanLII, AU and PRV.
- The UPC client and the EPO CPC methods.
- The USITC download and search tools.
- `ApplicationsClient` over real HTTP handling.
- A real Google Patents page fixture.
- Collection paging and punctuation, and missing-collection handling.
- Eight collection builds have no smoke test.
