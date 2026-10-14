# fees/ refactoring analysis (read-only)

Scope: `src/patent_client_agents/fees/` (17,783 lines incl. 15,051 in `scrapers/`),
`src/patent_client_agents/mcp/tools/fees.py` (290), `scripts/build_fees_snapshot.py` (201),
`.github/workflows/fees-snapshot.yml`, `coverage/fees-snapshot/` (54 route files + index.json).
No repo files were edited. Helper scripts used for counting live in this scratchpad dir
(`ast_fees.py`, `golden_check.py`).

## Scope notes before the proposals

- `src/patent_client_agents/prh_fi/` (top-level) is the PRH *register* connector, not fees. Its only
  symilar hit is `_parse_iso_date` duplicated with `prv_se/models.py:20-54`; that belongs to a
  different slice. The fee scraper is `fees/scrapers/prh_fi.py` and is covered below.
- `xlrd` is not used anywhere in fees (only `japan_ip_high_court/client.py`). No fee scraper reads
  spreadsheets.
- No fee calculation / exposure logic lives in this repo. `estimate_patent_fee_exposure` and the
  rule-card tools are law-mcp tools from another repo. The only "calculation" here is the filter in
  `FeesClient.lookup_fee` (`fees/client.py`) which is duplicated in `mcp/tools/fees.py` (see P9).
- The symilar report's 220 duplicate lines in fees/ are almost entirely (a) the HTTP client
  `__init__` header block (11 of 17 pairs) and (b) `_slug`/`_unique` (4 pairs). Symilar
  under-counts: most duplication is semantically identical but textually varied (e.g. 18 money
  parsers, 9 `_slugify`s with different signatures), so the numbers below come from AST/grep counts,
  not symilar.

## Current shape

Every route is `async def scrape_<office>_<right>() -> FeeSchedule` with no args, owning a
per-office `BaseAsyncClient` subclass (23 classes, 793 lines total). Dispatch is a flat dict in
`fees/registry.py` (54 routes). Each module repeats the same skeleton:

1. `XFeesClient(BaseAsyncClient)` with `DEFAULT_BASE_URL/CACHE_NAME/DEFAULT_TIMEOUT/DEFAULT_TTL_SECONDS/HTTP2`,
   an `__init__` that only `setdefault`s TTL + a browser-UA header dict, and a 4-line `fetch_html`/`fetch_pdf`.
2. Text/amount helpers: `_parse_money`-family, `_extract_pdf_text`, `_row_cells`, `_slug(ify)`, `_unique`.
3. Office-specific `_categorize_*` (keyword if-chains), `_detect_condition`, `_build_*_fees` row walkers.
4. One `scrape_*` per right: `async with Client()` → parse → zero-rows guard → `FeeSchedule(...)`
   with 8 constant kwargs + long `notes`.

Size of each layer (AST, `scrapers/` only):

| Layer | Functions | Lines |
|---|---|---|
| HTTP client classes | 23 | 793 |
| `scrape_*` entrypoints | 54 | 1,958 |
| `_build_{patent,trademark,design}_fees` + `_build_fees` | 33 | 2,764 |
| `_categorize*` (patent/tm/design/plain/tm alias) | 30 | 1,100 |
| `_detect_condition` / `_detect_tm_condition` | 9 | 178 |
| money parsers (`_parse_money/_amount/_eur/_yen/...`) | 18 | ~245 |
| slug + unique helpers | 19 | ~160 |
| `_extract_pdf_text` | 8 (+PRH layout) | 57 (+~20) |
| HTML row/caption/heading helpers | 12 | ~75 |

### Common shape vs outliers

Follow the common HTML-table shape (fetch HTML → walk `<tr>` → categorize → FeeItem):
CIPO, CNIPA, IPAU, KIPO, JPO, HKIPD, IPOS, PRV, TURKPATENT, WIPO (x3), USPTO (parse side).

Follow the common PDF-text shape (fetch PDF → pypdf text → regex rows):
DPMA, IPIN, INPI-BR, OEPM, IMPI, ILPO; TIPO-TM and INPI-FR mix HTML and PDF.

Outliers that should stay bespoke (don't force them into a declarative spec):
- **EPO** (`epo.py`): JSON BFF (`fees.apps.epo.org/prod/bff/api/fees`), `_request_json`, EU money format.
- **EUIPO** (`euipo.py:121-140`): decodes Next.js `self.__next_f.push` SSR stream for TMs; designs are HTML.
- **EPO-UP** (`epo_unitary.py`): static dict in code, no fetch at all.
- **USPTO** (`uspto.py:48-146`): the only client with source-receipt / refresh / sha256 /
  revalidation semantics (99-line client); `client.get_schedule(refresh=True)` is hardwired to it.
- **UKIPO** (`ukipo.py:255-300`): index page plus semaphore fan-out over per-form sub-pages.
- **PRH** (`prh_fi.py:248-265`): pypdf `extraction_mode="layout"`; this is why pypdf is pinned `<6.15`.
- **IPAU** (`ipaustralia.py:189`): hand-coded renewal ladder supplements the scraped page.
- **KIPO** (`kipo.py:106-120`): wraps requests in `asyncio.timeout` deadline; two pages.
- **ILPO** (`ilpo.py:153-193`): Cloudflare-gated gov.il; 30-day TTL; live fetch is expected to fail from cloud egress.

## Proposed primitives

Ordered by (savings × safety). Line estimates are arithmetic from the AST counts above.

### P1. `FeeSourceClient` base + header presets (fetch + cache)

**Owns:** default TTL (7d), HTTP2 flag, header presets (`BROWSER_HTML`, `BROWSER_PDF`, `BOT_UA`,
`JSON`), and generic `fetch_text(path, context)` / `fetch_bytes(path, context)`. Subclasses become
5-6 class attributes (`DEFAULT_BASE_URL`, `CACHE_NAME`, `HEADERS = BROWSER_PDF | {...}`,
optional timeout/TTL). Lives in `fees/scrapers/_base.py` (or `fees/http.py`).

**Uses today (identical `__init__` + fetch):** `cipo.py:57`, `cnipa.py:53`, `dpma.py:66`,
`euipo.py:65`, `hk_ipd.py:160`, `impi.py:147`, `inpi_br.py:123`, `inpi_fr.py:112`,
`ipaustralia.py:72`, `ipindia.py:67`, `ipos.py:169`, `oepm.py:131`, `prh_fi.py:205`,
`prv_se.py:160`, `tipo.py:93`, `turkpatent.py:179`, `ukipo.py:62`, `wipo.py:60`, `epo.py:63`
(JSON variant). Partially: `jpo.py:87` (Sec-Fetch headers), `ilpo.py:153`, `kipo.py:80`.

**Savings:** 793 lines total. Excluding USPTO (99) and KIPO (59) leaves 21 clients / 635 lines,
avg 30. A declarative subclass plus office docstring is ~9 lines → ~21 × 21 = **~440 lines**, minus
~50 for the base module = **~390 net**.

**Stays office-specific:** base URL, cache name, paths, Accept-Language, JPO's Sec-Fetch set,
ILPO's Windows UA, KIPO's deadline wrapper, USPTO receipt logic, office docstrings explaining
WAF behavior (keep these — they are the institutional memory).

**Divergences/risks:** three distinct UA strings exist (Chrome/120 short, Chrome/120 with
"KHTML, like Gecko", Chrome/131 Windows) plus a bot UA (`patent-client-agents (https://patentclient.com)`
in USPTO/EPO). JPO notes the bare UA gets ReadTimeouts; some offices (memory: TESS, UPC) filter
Cloud Run egress. Preserve each office's exact header dict; do not "harmonize" UAs in the same PR.
Timeouts differ (30 vs 60), TTL differs (ILPO 30d). `CACHE_NAME` must not change or every
deployed cache is cold (harmless but causes a burst of upstream requests).

**Test protection:** weak. No fee test exercises a real client fetch; there are no fees VCR
cassettes (`tests/cassettes` has none). Header/TTL regressions only surface in the nightly live
build. Add a tiny parametrized test asserting each client's resolved headers/TTL/cache name equals a
recorded table before refactoring.

### P2. `OfficeProfile` + `build_schedule()` (schedule assembly + zero-rows guard)

**Owns:** per-office constants (`jurisdiction`, `issuing_body`, `office_code`, `currency`,
default `statutory_basis`) and one function
`build_schedule(profile, right, fees, *, effective_date, source_url, notes, statutory_basis=None, coverage=None)`
that raises the standard "parsed zero rows — structure may have changed" error and sets
`retrieved_at`. USPTO already has this as `_wrap` (`uspto.py:583-631`); generalize it.

**Uses today:** all 54 routes. Repeated constant kwargs e.g. `turkpatent.py:652-765` (3×
identical 6 kwargs + guard), `ilpo.py:1223-1325`, `prh_fi.py:820-920`, `oepm.py:875-990`,
`ipos.py:880-985`, `hk_ipd.py:866-984`, `jpo.py:396/952/997`, `kipo.py:332/1000/1042`,
`wipo.py:205/348/481`. Zero-rows guard text appears in 22 files; `retrieved_at=date.today()` in 23.

**Savings:** `scrape_*` = 1,958 lines / 54 routes (avg 36, of which ~15-20 are `notes` prose).
Removable boilerplate per route ≈ 9 lines (guard 4, five constant kwargs, `retrieved_at`) →
53 non-USPTO routes × 9 = **~475**, minus ~40 for the helper/profiles = **~435 net**. For PDF
offices that serve three rights from one document (ILPO, IMPI, OEPM, PRH, INPI-FR) a
`scrape_rights(client_cls, fetch, {right: builder})` pattern would cut a further ~5 lines/route.

**Stays office-specific:** `notes` text, `effective_date` choice, `source_url` per right,
statutory basis per right (ILPO, PRV have per-right dates/bases), `recurring_fee_coverage`.

**Divergences/risks:**
- `effective_date=date.today()` is used for CNIPA (`cnipa.py:368`), DPMA (`dpma.py:297`),
  EPO (`epo.py:285`), EUIPO-TM (`euipo.py:269`). This mislabels "fetch date" as effective date;
  the MCP envelope (`mcp/tools/fees.py` `_fees_provenance`) reports it as `effective_date`. The
  primitive should force an explicit `EffectiveDate` choice (`known(date)` / `unknown`), which is a
  behavior change for those four routes. Flag, don't fold silently into a refactor PR.
- `retrieved_at=date.today()` is set at parse time, not byte-retrieval time, even on a hishel cache
  hit. This is why **every nightly snapshot PR rewrites all 55 files** (verified in `e45293c`: 54
  route files change by one `retrieved_at` line, USPTO by 8, index by 116) even when no fee changed.
  Fix belongs in P8, but the profile helper is the single place to wire it.

**Test protection:** good for the 10 fixture-backed offices; `tests/fees/test_envelope_compliance.py`
asserts envelope fields. Golden snapshot comparison (P10) catches any field drift.

### P3. `slug()` + `CodeAllocator` (fee-code synthesis)

**Owns:** `slug(*parts, max_part=40, translit=None, fallback=None) -> str` and
`CodeAllocator.unique(slug)` (the `-2`, `-3` suffixing).

**Uses today:** variadic copies `hk_ipd.py:267` (`_slugify`, 40) + `hk_ipd.py:278` (`_unique`),
`ilpo.py:924` (40), `ipos.py:536` (`_slug`, 50) + `:547`, `prh_fi.py:578` (60, Finnish translit) +
`:591`, `prv_se.py:614` (50) + `:625`, `tipo.py:146` (40, accepts int/None, fallback `"tipo-fee"`),
`kipo.py:521` `_kr_slug` + `_unique_kr`. Fixed-format variants that would call `slug()`:
`cipo.py:328`, `cnipa.py:177`, `jpo.py:242`, `kipo.py:204`, `ipaustralia.py:183`,
`ipindia.py:207`, `impi.py:434`.

**Savings:** ~160 lines across 19 functions. Variadic copies + uniques (~95 lines) collapse to
imports; fixed-format ones shrink to 1-3 line wrappers (~65 → ~25). **~120 net.**

**Stays office-specific:** code prefix/format (`cn-<roman>-...`, `jp-...-y<year>`,
`<type>-y<year>-<tier>` for CIPO, `in-item-N-...` for IPIN).

**Divergences/risks:** codes are public identifiers on patentclient.com/fees and the snapshot, so
output must be byte-identical. Differences to preserve: truncation length (15/30/35/40/50/60),
truncate-after-strip ordering (can leave a trailing `-`; all copies do `strip("-")[:n]`, keep it),
PRH's å/ä/ö/ü transliteration, TIPO's `str(p)` coercion + fallback, CIPO's tier initial suffix.
Medium-low risk if parameterized, high payoff in consistency.

**Test protection:** codes for every fixture-backed route are in the committed snapshots; a
golden diff on `code` catches any change. Routes without fixtures (CIPO, CNIPA, IPAU, IPIN, TIPO-patent,
KIPO-patent) have no byte fixtures, so only the live nightly would catch drift.

### P4. `parse_amount()` / `find_amounts()` (amount + currency normalization)

**Owns:** one tolerant number normalizer parameterized by convention:
`parse_amount(raw, *, decimal: Literal[".", ","], thousands: str, marker: re.Pattern | None,
mode: "whole"|"first", nil: Mapping[str, Decimal|None]) -> Decimal | None` and
`find_amounts(raw, ...) -> list[Decimal]`. Offices bind it with `functools.partial`.

**Uses today (18 copies):** `cipo.py:97`, `cnipa.py:91`, `dpma.py:134`, `epo.py:101`,
`euipo.py:94`, `hk_ipd.py:197`, `ipaustralia.py:112`, `ipindia.py:155`, `kipo.py:149`,
`oepm.py:178`, `prh_fi.py:283`, `inpi_br.py:167`, `inpi_fr.py:163`, `turkpatent.py:222`,
`uspto.py:164`, `jpo.py:145` (`_parse_yen`), `ipos.py:210` (`_parse_sgd_amounts`),
`prv_se.py:205` (`_parse_sek_amounts`).

**Savings:** ~245 lines (bodies + docstrings + their `_AMOUNT_RE`s). Each becomes a 1-3 line
partial → **~170 net**.

**Stays office-specific:** currency-marker regex (€, $, ¥, S$, kr/SEK, TL), compound-cell
splitting (`jpo._split_base_and_per_claim`, `ipos._split_add_on_amounts`, `kipo._electronic_paper_amounts`),
"no fee"/"see description" sentinels.

**Divergences/risks (the main reason to go carefully):**
- Return on failure differs: most return `None`; `prh_fi._parse_amount` raises; HK maps `"Nil"`
  to `Decimal("0")`.
- Match mode: CNIPA/CIPO/USPTO require a whole-string match; KIPO/HK/IPAU/JPO take the first
  match; EUIPO takes the first `€N` and ignores `(max. €1 000)` caps.
- Separator handling: EPO/OEPM/INPI-BR strip every `.` (would turn `"0.75"` into `75`); INPI-FR
  has a heuristic for mixed `.`/`,`; DPMA treats `,` as decimal and strips NBSP; KIPO rejects decimals.
- Logging: EPO/EUIPO log a warning on parse failure; others are silent.
A unified function must reproduce each of these exactly through parameters, or behavior will drift on
odd cells. Medium risk.

**Test protection:** `tests/fees/test_parsers.py` has direct unit tests for USPTO, EPO, EUIPO, CIPO,
CNIPA, DPMA, TIPO (`_parse_nt`), INPI-BR. Fixture-backed offices are covered via golden output.
Unprotected: IPIN, IPAU, INPI-FR, KIPO-patent page. Add table-driven tests per binding first.

### P5. `pdf_text()` (PDF extraction)

**Owns:** `pdf_text(data, *, layout=False, collapse_ws=False, ascii_only=False, page_sep="\n")`
plus a single import site for pypdf, with the `<6.15` pin's reason documented next to it.

**Uses today:** `dpma.py:102`, `ilpo.py:201`, `impi.py:184`, `inpi_br.py:178`, `inpi_fr.py:151`,
`ipindia.py:104`, `oepm.py:170`, `tipo.py:437` (ASCII-only), `prh_fi.py:245-270` (layout mode,
per-page handling).

**Savings:** 57 + ~10 of PRH boilerplate → **~45 net**. Small, but it centralizes the pypdf
version sensitivity: today a pypdf upgrade has to be verified in nine places.

**Stays office-specific:** PRH's post-layout line handling; TIPO's CJK stripping rationale.

**Risks:** low. Note that IPIN's copy doesn't `.strip()` the result while INPI-BR/INPI-FR/OEPM do;
DPMA/ILPO/IMPI keep newlines (their regexes depend on them). Expose both modes.

**Test protection:** strong for PDF offices with fixtures (PRH, ILPO, IMPI, OEPM); none for DPMA,
IPIN, INPI-BR, INPI-FR, TIPO-TM (no fixture PDFs committed).

### P6. HTML table primitives

**Owns:** `row_cells(tr, *, visible_only=False, br_as_newline=False)`, `table_caption(table, *, thead_fallback=False)`,
`nearest_heading(el, tags=("h2","h3","h4"), max_depth=20)`, `find_table(doc, *, contains=(...))`,
`iter_rows(table)` yielding normalized cell lists, and optionally `iter_section_tables(doc, "h2")`.

**Uses today:** `_row_cells` in `hk_ipd.py:437`, `ipos.py:466` (visible-text variant),
`kipo.py:220`, `prv_se.py:386`, `turkpatent.py:427`, `wipo.py:131`; `_table_caption` in
`jpo.py:187`, `kipo.py:215`, `uspto.py:331` (thead variant); nearest heading in
`jpo.py:168`, `ukipo.py:235`, `ipaustralia.py:217` (`_preceding_heading`); table finding in
`cnipa.py:207-214`, `kipo.py:538`; `cnipa._walk_table_rows` (`cnipa.py:184`);
section walker `prv_se.py:648`.

**Savings:** ~75 lines of helpers + scattered `cssselect("tr")`/`text_content().strip()` idioms in
13 files → **~70 net**.

**Stays office-specific:** header-row predicates (`hk_ipd._is_header_row`, `turkpatent._is_header_row`
are office-vocabulary checks), column semantics.

**Risks:** low. IPOS's aria-hidden/sr-only filter and KIPO's `<br>`→newline `_cell_text` must be flags,
not the default. JPO's heading search includes h4, UKIPO's does not.

**Test protection:** good for HK/IPOS/PRV/TURKPATENT/JPO/KIPO-TM fixtures; WIPO is at 16% coverage,
UKIPO 47%, IPAU 69%, CNIPA 25%.

### P7. Year-band / renewal-ladder helpers

**Owns:** `expand_years(label, pattern) -> range | None` for "1-3 Years", "4 to 6 years",
"6th-10th year"; `renewal_items(ladder: Mapping[int, Decimal], *, code_fmt, label_fmt, ...)`.

**Uses today:** `cnipa.py:87,284-300`, `jpo.py:140,440` (two identical regexes in one file),
`kipo.py:146,486`, `hk_ipd.py:407-411`, `ipos.py:390-394`, `ipaustralia.py:189-215`,
`epo_unitary.py` (static ladder), `ukipo.py` (ladder per `tests/fees/test_uk_au_renewals.py`),
`tipo.py` (`_parse_year_band`, `_emit_annuity_rows`), `inpi_br.py` (`_years_for_code`).

**Savings:** **~50 net**; low confidence, the regexes genuinely differ by language.

**Risks:** banded rows also drive codes (`-y{year}`), so golden diffs cover it.

### P8. Source receipt / freshness (generalize USPTO's)

**Owns:** the `content_sha256`, `bytes_retrieved_at`, `source_checked_at`, `cache_state`,
`refresh_outcome` bookkeeping currently implemented only in `uspto.py:73-146` (receipt file in the
cache dir) and consumed by `FeeSchedule` fields and `mcp/tools/fees.py:_fees_provenance`.
Moving it into `FeeSourceClient` (P1) gives every office real retrieval timestamps and a uniform
`refresh=True` path.

**Savings:** about zero lines net (USPTO's ~70 lines move into the base); value is behavioral:
- `client.get_schedule(refresh=True)` stops being hardwired to USPTO (`fees/client.py`
  `get_schedule`, which re-imports the three USPTO scrapers inline).
- `_fees_provenance` stops special-casing `office_code == "USPTO"`.
- The snapshot can derive `retrieved_at` from bytes rather than `date.today()`, ending the
  all-files-change nightly PR.

**Risks:** behavior change across 53 routes; the provenance compliance test
(`tests/fees/test_envelope_compliance.py`) and `tests/fees/test_source_freshness.py` (USPTO-only)
would need extending. Do it as its own phase.

### P9. Registry / dispatch consolidation

**Owns:** one `OfficeProfile` per office (from P2) that carries aliases, rights → scraper, and
display order. `_DISPATCH`, `OFFICES`, and `_OFFICE_ALIASES` are derived from it.

**Uses today:** `fees/registry.py` (24 imports + 54 dispatch lines + 28-line `OFFICES` tuple that
must be kept in sync by hand), `fees/client.py` `_OFFICE_ALIASES` (~150 lines of aliases, plus
EP/WIPO special cases in `resolve_jurisdiction`), `scripts/build_fees_snapshot.py` reaching into
private `_DISPATCH` and `client._to_meta`, `FeesClient.list_schedules` also importing `_DISPATCH`.
Filter logic duplicated: `FeesClient.lookup_fee` `_match` vs the list comprehension in
`mcp/tools/fees.py` `lookup_fee` (same semantics, separately maintained). `api.estimate_freshness`
and `client._to_meta` both compute `days_since_retrieval`.

**Savings:** registry ~50, duplicate filter ~10, freshness ~5 → **~60 net**. Aliases stay as data.

**Risks:** low. `list_supported_routes()` order is used for index.json ordering; keep insertion order.
Tests: `tests/fees/test_client.py` covers resolver/alias behavior.

### P10. Keyword categorizer tables (the "declarative" lever)

**Owns:** `Categorizer(rules=[(("late payment", "late filing"), FeeCategory.late_fee), ...],
default=FeeCategory.other)` with ordered first-match semantics, optional `all_of`/`none_of`, and a
regex variant. Same shape for `ConditionRules` → `FeeCondition`.

**Uses today:** 30 `_categorize*` functions, 1,100 lines: `hk_ipd.py:295,339,377`,
`ipos.py:256,310,340`, `prh_fi.py:448,497,524`, `prv_se.py:258,534,578`,
`turkpatent.py:254,292,321`, `jpo.py:197,547,745`, `inpi_br.py:249,280`, `tipo.py:247`,
`ukipo.py:184,400`, `euipo.py:141,295`, `cipo.py:166`, `dpma.py:155`, `epo.py:117`,
`ipaustralia.py:129`, `oepm.py:576`. Keyword-test lines (`"x" in d`) per file: PRV 64, HK 49,
IPOS 47, PRH 47, TURKPATENT 39, KIPO 35, EUIPO 33, JPO 27, USPTO 25 (≈530 total).
Conditions: 9 `_detect_condition` functions, 178 lines.

**Savings:** a two-line `if ... in d: return X` becomes one tuple row; nested/compound branches
stay as code. Estimate 30-35% of 1,100 + 25% of 178 → **~350 net**.

**Stays office-specific:** the rule tables themselves (they are the office knowledge), CNIPA's
Roman-numeral section mapping (`cnipa.py:118`, already table-like), OEPM code-prefix mapping.

**Risks:** highest of the set. First-match order matters (comments in `hk_ipd.py:300-303` say so
explicitly), and several categorizers mix description, heading, and code arguments with `and not`
conditions. Convert one office at a time, only behind a golden test.

**Test protection:** golden snapshots for fixture-backed offices catch category drift exactly; the
non-fixture offices (CIPO, DPMA, EPO, EUIPO, IPAU, UKIPO, INPI-BR, TIPO-patent) are effectively
unprotected (25-47% coverage) and should get byte fixtures before conversion.

## Totals

| Primitive | Net lines removed | Risk |
|---|---|---|
| P1 FeeSourceClient + header presets | ~390 | low (keep headers verbatim) |
| P2 OfficeProfile + build_schedule | ~435 | low (separate the effective_date fix) |
| P3 slug + CodeAllocator | ~120 | low-med (codes are public IDs) |
| P4 parse_amount family | ~170 | medium |
| P5 pdf_text | ~45 | low |
| P6 HTML table helpers | ~70 | low |
| P7 year-band / ladder | ~50 | low-med |
| P8 source receipt (USPTO → all) | ~0 (behavioral) | medium, own phase |
| P9 registry/dispatch/filter dedup | ~60 | low |
| P10 keyword categorizer tables | ~350 | high, per-office |
| **Total** | **~1,690** (~11% of 15.1k scraper lines) | |

P1+P2+P3+P5+P6+P9 (~1,120 lines) are mechanical and low risk. The bulk of the code (2,764 lines of
`_build_*_fees` row walkers plus office notes) is genuinely office-specific and would not become
declarative without a much larger table-spec DSL, which I would not recommend given how irregular the
sources are (Next.js streams, layout-mode PDFs, bilingual PDFs, fan-out sub-pages).

## Snapshot pipeline findings

- `scripts/build_fees_snapshot.py` is clean and small (201 lines, tested by
  `tests/test_build_fees_snapshot.py`, 187 lines). It reaches into private `registry._DISPATCH` and
  `client._to_meta`; P9 would expose public equivalents.
- Nightly churn: because every scraper sets `retrieved_at=date.today()` (23 files) and four use
  `effective_date=date.today()`, each nightly PR changes all 54 route files plus index.json even when
  no fee moved (`git show e45293c --stat`: 55 files, 125/125 lines). Reviewers can't spot real
  fee changes. Cheapest fix independent of the refactor: in the build script, if a route's JSON is
  equal to the previous file ignoring `retrieved_at`/`effective_date-when-today`, keep the old file.
  Better fix is P8.
- Workflow (`.github/workflows/fees-snapshot.yml`) needs no refactor.

## Can the committed snapshots serve as golden outputs?

Partly. I fed the committed fixtures into the scrapers (patching the client fetch methods) and
compared `model_dump(mode="json")` against `coverage/fees-snapshot/*.json`, ignoring
`retrieved_at`/`bytes_retrieved_at`/`source_checked_at` (`golden_check.py` in this dir):

- **Exact match (12 routes):** PRH ×3, ILPO ×3, IMPI ×3, TURKPATENT ×3.
- **Mismatch (3 routes):** OEPM ×3. The fixture (`oepm_tasas_2026-04-01.pdf`) is older than the live
  PDF; 1 code differs and ~all amounts differ. The snapshot is current; the fixture is stale.
- Not checked but likely usable: HKIPD, IPOS, PRV, JPO (TM/design page), KIPO TM/design (fixtures exist).
- **No source fixture at all (≈24 routes):** USPTO ×3, EPO, EUIPO ×2, CNIPA, CIPO, DPMA, IPAU, UKIPO ×2,
  IPIN, TIPO ×2, INPI-BR ×2, INPI-FR ×3, WIPO ×3, KIPO patent. EPO-UP is static and needs none. For these
  the snapshot JSON is an output with no reproducible input, so it cannot serve as a golden test on its
  own. Coverage confirms it: wipo 16%, ipindia 24%, cnipa 25%, cipo 27%, euipo 28%, inpi_fr 28%,
  dpma 33%, epo 34%, uspto 37%, tipo 38%, inpi_br 39%, ukipo 47% (whole fees suite: 663 tests pass, 68%
  line coverage of fees/).

Recommended safety net before any refactor PR:
1. Capture raw bytes for every live route once (from the hishel cache after a snapshot build, or a
   one-off `--vcr-record`), commit them under `tests/fees/fixtures/`, and refresh the stale OEPM PDF.
2. Add one parametrized characterization test: fixture bytes → scraper → `model_dump` equals a
   committed golden JSON with the timestamp fields masked. Generate the goldens from the current code
   (not from the nightly snapshot, which tracks live upstream and will drift).
3. Keep the nightly snapshot as a second, live check rather than the primary gate.

## Suggested order

1. Golden harness + byte fixtures (above).
2. P5, P6, P3, P1 (mechanical; golden diff must be empty).
3. P2 + P9 (assembly and registry; golden diff must be empty).
4. P4 per office with table tests.
5. P10 per office, one PR each.
6. P8 + effective_date honesty fix + snapshot churn fix as a deliberate behavior change.
