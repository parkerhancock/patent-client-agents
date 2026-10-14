# MCP layer refactoring analysis: `src/patent_client_agents/mcp/`

Read-only analysis, 2026-10-14, repo at `45cb1e0`. No repo files were edited.

Scope: `mcp/server.py` (95 lines), `mcp/full.py` (143), `mcp/__init__.py` (26), and 50 tool
modules under `mcp/tools/` (20,073 lines). Total 20,337 lines. Shared plumbing is in
`tools/mcp-data-core/src/mcp_data_core/` (`envelope.py`, `exceptions.py`, `mcp/{annotations,conditional,downloads,middleware,server_factory}.py`).

## Headline

The tool layer is large because the same five or six function bodies were hand-copied into
almost every module. The duplicate-code scan only caught 405 lines because the copies are
renamed and lightly edited, so they don't line up line by line. The real repetition is much
bigger. Counted by pattern:

| Pattern | Sites | Lines today |
|---|---|---|
| List-accepting `get_*` fan-out (`Semaphore` + `gather` + summary + envelope) | 68 tools / 41 files | 2,240 body lines (median 29.5) |
| Corpus `search_*`/`get_*_section` pairs + provenance + `_truncate` | 17 modules | 1,453 |
| `_dump` model serializer | 34 defs / 33 files, 12 variants | ~345 |
| `_*provenance` helpers | 59 defs / 50 files | 472 |
| `full: Annotated[bool, ...]` param declarations | 83 | 402 |
| Hand-rolled `limit` range checks / offset→page / cursor decode | 44 + 13 + 5 | ~150 |
| `asyncio.Semaphore(` | 73 / 41 files | (inside fan-out) |
| `async with XClient() as client` per call | 176 / 48 files | (lifecycle, not lines) |

**Estimated total removable: about 2,600 lines (≈13% of the MCP layer)** from primitives
P1–P9 below. Another ~320 is available if the `full` parameter docs are standardized (P10,
which is optional). None of this needs changing how tools are named or what they return.

mcp-data-core already provides the envelope models, `make_provenance`, `encode/decode_cursor`,
`conditional_tool`/`conditional_resource`/`register_source_if_configured`, `READ_ONLY`,
the download/resource helpers, and the `FriendlyErrors` middleware. Nothing in it covers
list fan-out, model dumping, paging params, date parsing, or corpus tools, so every module
writes its own version.

Before P1/P2/P5 can land, one standards decision is needed. CONNECTOR_STANDARDS.md §5.15 says
the `_provenance` / `_summarize_*` / `_stub_*` helpers are "deliberately per-module, not shared"
and that "repetition is acceptable." The proposals below keep `_stub_*` and `_summarize_*`
per-module, since those really do encode each connector's record shape. They centralize only
the control flow around those helpers (fan-out, paging, envelope assembly, corpus provenance).
§5.15 should be amended to say so. Otherwise reviewers will reject the change as going
against the standard.

---

## P1. `corpus_tools`: shared search/get bodies for bundled-corpus (`mcp_local`) connectors

**What it owns.** A `CorpusSpec` dataclass (client factory, `get_corpus_status` callable,
`source_name`, base URL, search provenance path, label used in summaries, lean-snippet cap,
fan-out concurrency) plus two coroutines:

- `corpus_search(spec, *, query, limit, offset, full, stub_hit, **client_kwargs) -> ListEnvelope`
  covers limit validation, offset→page translation, the `async with client`, dumping hits,
  lean/full projection, the "N hit(s) (more available)." summary, and provenance with
  `corpus_synced_at`/`corpus_version`.
- `corpus_get(spec, refs, *, fetch_one, summarize_one, provenance_path_for) -> ListEnvelope`
  covers list coercion, the empty-list error, bounded fan-out, summary for one versus many
  refs, and provenance.

Plus a shared `truncate(text, limit)` (14 identical copies today) and a
`corpus_provenance(spec, url)` (replaces about 20 near-identical helpers).

**Per-tool code that stays.** The `async def search_x(...)` / `get_x_section(...)` signatures with
their `Annotated` parameter text and docstrings stay where they are. That keeps tool
names, JSON schemas, and `from ...mcp.tools.mpep import search_mpep` imports in tests
working. Also staying: `_stub_hit` (the breadcrumb parsing differs: `chapter` vs `part`
prefixes, or `statute`/`section` keys), `_summarize_section`, and any special citation-to-path logic
(`epo_case_law._looks_like_section_ref`, `mpep` href vs section number). Each body
shrinks to a 3–5 line call.

**Where it's used today** (search tool / get tool line numbers):
`mpep.py:131/224`, `ukipo_mopp.py:116/199`, `epo_guidelines.py:129/213`,
`epo_pct_guidelines.py:115/200`, `epo_up_guidelines.py:118/202`, `epc.py:137/219`,
`epo_case_law.py:128/214`, `inpi_br_statutes.py:132/218`, `ipo_in_mppp.py:86/169`,
`ipo_in_statutes.py:101/192`, `dpma_statutes.py:94/184`, `tw_trade_secrets.py:102/184`,
`legifrance_ip.py:131/188`; second-generation shape: `ilpo.py:99/151`,
`ipos.py:126/172 and 259/305`, `upc.py:346/404`; TMEP inside `trademarks.py` (~l.500–560).
Most of the symilar hits are here, e.g. `mpep.py:61-97 ≈ ukipo_mopp.py:62-93`,
`epo_pct_guidelines.py:60-93 ≈ epo_up_guidelines.py:61-94`, `epc.py:110-183 ≈ epo_case_law.py:100-173`.

**Estimated lines removed.** Today's corpus tool bodies plus provenance and truncate helpers come
to 1,453 lines across 17 modules (measured with AST). What would remain is about 18 lines per
module (spec plus two short calls), about 30 for `ipos.py` with its two corpora, so ~330 in all.
**Net ≈ 1,100 lines.**

**Risks and differences between the copies.**

1. **Two parameter generations.** Thirteen modules take `limit/offset/syntax/sort/full`; `ilpo`,
   `ipos`, and `upc` take `per_page/page` and don't accept `full`. The primitive has to support both.
   Making them consistent would change public tool schemas, which counts as a separate,
   deliberate API change under §5.8.
2. **Offset is lossy.** `page = (offset // limit) + 1` appears 13 times (e.g. `mpep.py:185`).
   An offset that isn't a multiple of `limit` gets silently floored, so `offset=10, limit=25`
   returns rows 0–24, not 10–34. Moving this into one place lets it be fixed once, by
   rejecting misaligned offsets or slicing.
3. **Not-found handling differs.** `ilpo`, `ipos`, and `upc` drop `None` results and report
   "Not found: …". The v1 modules let the client raise. The primitive needs an explicit
   `on_missing="raise"|"drop"` setting.
4. **Default `syntax` differs.** It's `adj` (mpep, case law) in some modules and `and` (dpma) in others. Keep it per-tool.
5. **Tests monkeypatch module-level client classes** (e.g. `ilpo.IlpoStatutesClient`,
   `ipos.IposStatutesClient`). The spec must look the factory up at call time, e.g.
   `client=lambda: IlpoStatutesClient()` defined in the module, and must not capture the class
   object at import.

**Tests that protect it.** `tests/{mpep,tmep,ukipo_mopp,epo_guidelines,epo_pct_guidelines,
epo_up_guidelines,epc,epo_case_law,inpi_br_statutes,ipo_in_mppp,ipo_in_statutes,dpma_statutes,
tw_trade_secrets,legifrance_ip,ilpo_statutes,ipos_statutes,ipos_manuals,upc_statutes}/test_mcp_envelope.py`
check envelope shape, lean keys, summary contents, and corpus provenance against
fixture corpora. `tests/test_provenance_contracts.py::test_substantive_law_provenance_carries_corpus_fields`.
Gap: no test covers `offset` paging or `limit` bounds on corpus search. Add those before refactoring.

---

## P2. `fetch_many`: the list-accepting `get_*` fan-out (§5.4)

**What it owns.** It lives in mcp-data-core (`mcp_data_core.envelope` or a new `mcp_data_core.fanout`):

```python
def as_id_list(value: str | Sequence[str], *, tool: str, noun: str,
               cap: int | None = None, strip: bool = True) -> list[str]
async def gather_bounded(items, fn, *, concurrency: int = 5) -> list   # order-preserving
def partition_found(ids, results) -> tuple[list[dict], list[str]]      # for drop-on-None tools
def ids_summary(label, ids, items, not_found=()) -> str               # "Fetched N of M …; Not found: …"
```

Optionally it can also offer a one-call `get_many(ids, fetch_one, *, client, summarize_one, label,
provenance_one, provenance_many, concurrency, on_missing)` that returns the `ListEnvelope`.

**Per-tool code that stays.** The `_fetch_one` body (which client method to call, any id
classification), the single-record `_summarize_*`, and the provenance path for one id versus many.

**Where it's used today.** There are 68 tools with `Semaphore`+`gather` (full list in the
appendix), for example `uspto.py:257 get_application`, `epo_ops.py` ×9 (`get_epo_biblio`
… `get_epo_procedural_steps`, l.520–760 and 1040–1130), `jpo.py` ×3 (l.332/387/477),
`trademarks.py:298/367` plus the TSDR gets, `ip_australia_{patents,trademarks,designs}.py` (l.185–193),
`euipo.py:236/347`, `dpma_register.py:172/215/255`, `thai_dip.py` ×4, `canlii.py:418/510/714`.
List coercion shows up 67 times as `[x] if isinstance(x, str) else list(x)`, and 60 times as "requires at
least one …". Three modules already have private versions: `_coerce_list` in
`prh_fi.py:49`, `prv_se.py:62`, and `tipo_opdata.py:123`, and `_numbers` in `thai_dip.py:52` and `dpma_register.py:120`.

**Estimated lines removed.** The 68 fan-out tools have 2,240 body lines. The 17 corpus gets are
already counted in P1, which leaves about 51. Three are atypical (`usitc.download_usitc_investigation_documents`
at 163 lines, `canlii.search_canlii_ip_cases`, and `canada_federal_court.search_*`, which use fan-out for
enrichment). For the remaining ~45 standard gets the median body is 28 lines, of which about 15 are
list coercion, empty check, semaphore, nested fetch, `async with`, `gather`, summary branch, and envelope.
That leaves 10–13 lines per tool. **About 45 × 14 ≈ 600 lines.** Removing about 41 `_X_FANOUT_CONCURRENCY = 5`
constants with their comments adds ~60 more.

**Risks and differences between the copies.**

1. **Missing ids.** Eleven tools drop `None` and report "Not found" (`trademarks.get_trademark` l.322–352,
   `copyright`, `ilpo`, `ipos` ×2, `upc` ×2, `office_actions`, `usitc`, `canada_federal_court`); the rest
   raise on the first failure, which also aborts every other id because `gather` is called without
   `return_exceptions` (zero uses in the repo). That should be a per-tool setting, not a silent change.
2. **List size caps.** `LIST_ACCEPT_CAP = 50` applies only in six BYOK connectors (thai_dip, oepm_spain, kipo,
   iponz, ipi_swissreg, dpma_register) plus a few USPTO/USITC caps. Every other list `get_*` has no limit on
   list length; only concurrency is bounded. A shared `as_id_list(cap=…)` makes the choice visible.
3. **Concurrency.** It's 5 everywhere except EPO OPS (4, `epo_ops.py:104`, a rate-limit choice). Keep it as a parameter.
4. **Whitespace handling.** Some modules strip and filter empty ids (`_coerce_list`, `_numbers`); most don't. Changing that is a
   small behavior change.
5. Some `_fetch_one`s hold the semaphore only around the network call and normalize outside it,
   `trademarks.get_trademark` for example. That's harmless either way.

**Tests that protect it.** The 60 `tests/*/test_mcp_envelope.py` files exercise single and list
inputs for most gets (`uspto_odp`, `epo_ops`, `jpo/test_mcp_dispatch.py`, `uspto_tmsearch`, …).
`ilpo_statutes`, `ipos_*`, and `copyright` envelope tests assert not-found partitioning.
Gap: no test checks input order under concurrency, or that one failing id aborts or keeps
the others. Add one parametrized test of the primitive itself.

---

## P3. `dump()` in mcp-data-core in place of 34 `_dump` copies

**What it owns.** `dump(obj, *, by_alias=False, mode="python", exclude=None, strict=True)`
returns a dict and raises `TypeError` on anything that isn't a model or dict when `strict`. A recursive
`dump_any()` handles the `ipos`/`upc` variant that dumps lists and passes through None.

**Per-tool code that stays.** One line per module, e.g. `_dump = partial(dump, by_alias=True)`,
so call sites don't change. USPTO keeps a wrapper because it also runs `_strip_auth_urls`
(`uspto.py:74-115`).

**Where it's used today.** There are 12 behavioral variants. The 12-file cluster with no args and strict
checking: cafc, canlii, copyright, cpc, epo_ops, jpo, office_actions, patent_assignments, patents,
trademarks, usitc, wipo_lex. The 7-file `by_alias=True` cluster: euipo, inpi_br_bulk, ip_australia_*×4,
tipo_opdata. The 4-file `mode="json"`, non-strict cluster: dpma_register, ipi_swissreg, iponz, oepm_spain.
`ipos.py:84 ≡ upc.py:93` (recursive). `prh_fi ≡ prv_se`. One-offs: ilpo, inpi_pi, kipo_kipris,
publications (`mode="json"`), thai_dip (`exclude={"raw"}`).

**Estimated lines removed.** About 345 lines of definitions become about 34 one-line aliases, so **about 300 lines**.

**Risks.** The variants really do differ in `by_alias` and `mode`, and a wrong flag changes
camelCase vs snake_case keys, or dates vs ISO strings, in tool output. Each alias has to reproduce
its module's flags exactly. Strict and lenient behavior differ too (the lenient ones
call `.model_dump` on dicts and would raise `AttributeError`).

**Tests that protect it.** Every `test_mcp_envelope.py` asserts specific item keys. The
`euipo_*`, `ip_australia_*`, and `prh_fi`/`prv_se` tests check camelCase keys.

---

## P4. `provenance_for()` factory and cache-aware provenance

**What it owns.** It goes in `mcp_data_core.envelope`:
`provenance_for(base_url, source_name, *, corpus_status=None, **fixed) -> Callable[[str], Provenance]`.
The module then writes `_epo_provenance = provenance_for(_EPO_BASE, _EPO_NAME)`, which keeps the
§5.15 `_<office>_provenance` name you can grep for. With `corpus_status=get_corpus_status`, it reads
the corpus status on every call (needed by §4).

**Correctness gap this can fix.** §3 says `retrieved_at` is the *original* fetch time when
`cache_hit=True`. Today `cache_hit` is set only in `fees.py:69`; every other tool reports
`cache_hit=False` and `retrieved_at=now()` even when the response came from the hishel cache. Hishel
exposes `response.extensions["hishel_from_cache"]`, and `fees/scrapers/uspto.py:85,103` already reads it. If
`BaseAsyncClient` recorded the last response's cache flag and stored time in a `ContextVar`, and
`make_provenance` used it as the default, §3 would hold across all ~220 tools with no change to any tool module.
That is the most valuable part of this primitive, even though it removes no lines.

**Where it's used today.** There are 59 `_*provenance` defs in 50 files (472 lines). About 20 are corpus helpers
(covered by P1). The rest are 2–10 line wrappers, e.g. `uspto.py:36`, `epo_ops.py:112/842/847`,
`trademarks.py:76/80/84`, `ip_australia_designs.py:31`, `thai_dip.py:38`.

**Estimated lines removed.** About 39 non-corpus helpers average about 7 lines each and drop to 1 line,
**so about 180 lines** after excluding custom ones like `usitc._usitc_provenance(as_of_status=)`,
`dpma_register._provenance(service, operation, value)`, and `epo_ops._family_intelligence_provenance`.

**Risks.** The `source_url` composition differs: some helpers take a path and prepend the base, others take
a full URL (`dpma_statutes`, `ipo_in_mppp`, `inpi_br_statutes(url=None)`). The factory needs both forms.
Cache-aware provenance with concurrent fan-out needs per-task context. A `ContextVar` set inside
`_fetch_one` doesn't reach the parent, so for list gets either aggregate "any cache hit / oldest
retrieved_at" or report per-item. That needs a design decision.

**Tests that protect it.** `tests/test_provenance_contracts.py`, `tests/test_validate_mcp_contracts.py`
together with `scripts/validate_mcp_contracts.py` (schema-level provenance across the whole surface), and per-module
envelope tests that assert `source_url` and `source_name` strings. Add a VCR or fixture test that calls the same
tool twice and asserts `cache_hit=True` on the second call.

---

## P5. Paging and limit primitives (`Annotated` aliases plus `resolve_offset_page`)

**What it owns.** Shared `Annotated` aliases backed by pydantic `Field` constraints, for example
`Limit100 = Annotated[int, Field(ge=1, le=100, description="Maximum hits to return (1-100).")]`,
`Offset = Annotated[int, Field(ge=0, …)]`, and `NextCursor = Annotated[str | None, …]`. The bounds then
appear in the JSON schema that agents see, and FastMCP rejects bad values before the body runs.
It also includes `resolve_offset_page(offset, limit, next_cursor, *, label) -> (offset, limit)` and
`offset_cursor(offset, shown, limit, more) -> str | None`.

**Where it's used today.** There are 44 hand-written range checks (13 identical
`if limit < 1 or limit > 100` in the corpus modules, plus `_validate_limit` in `ipi_swissreg.py:117`,
`iponz_new_zealand.py:124`, and `thai_dip.py:97`, and inline checks in `china_spc_ip_court`,
`dpma_register` ×3, `japan_ip_high_court`, and `canlii`). No module uses `Field(ge=…, le=…)` today.
The cursor decode-and-validate block is copied at `cafc.py:68-78` (`_page_args`),
`publications.py:205-214`, and `uspto.py:1022-1031`, which are identical apart from the label.
`epo_ops.py:360` and `office_actions.py:277` use other cursor payloads. The docs drift too:
there are 10 different wordings for the limit parameter ("Maximum hits to return (1-100)", "Hits per page, 1..100",
"Hits per page (capped at 100)" …).

**Estimated lines removed.** About 44 check lines, about 30 cursor lines, and about 12 lines of `_validate_limit`
defs, minus the new aliases, comes to **about 100**. Fixing the 13 offset→page lines is counted in P1.

**Risks.** Errors from `Field` validation reach the agent as FastMCP/pydantic validation messages,
not as `ValidationError("limit must be between 1 and 100; got N")` strings. About 25 test lines assert those
messages or the bounds. Limits aren't uniform (100, 250, 1000, 25, 10000, `MAX_PAGE_SIZE`), so the
aliases have to take the bound as a parameter (`Limit(100)`) or be declared per module. Adding schema
constraints changes `tools/list` output, which is fine but is a visible contract change.

**Tests that protect it.** `tests/cafc/test_pagination.py`, plus the `next_cursor` tests in
`uspto_odp/test_ptab_envelope.py`, `uspto_publications`, `uspto_office_actions`, `epo_ops`,
`dpma_register`, `ipi_swissreg`, `iponz_new_zealand`, `thai_dip`, and `china_spc_ip_court` (`test_mcp_envelope.py`).

---

## P6. Hit-count summary helper

**What it owns.** `hits_summary(label, query, shown, *, total=None, more=False, scope=None, suffix=None)`
produces the `` `{label} — `{query}`: N hit(s)[ of T] (more available).`` lines that every search tool
writes by hand. It pairs with `ids_summary` from P2.

**Where it's used today.** Pluralization hand-rolled 32 times in 21 files (`'s' if len(...)`),
`" (more available)."` 14 times, the `"{shown} of {total}"` form 50 times, plus the module-local
`dpma_register._summary` (l.110), `thai_dip._search_result` (l.62), and `iponz`/`epo_ops` variants.

**Estimated lines removed.** About 60 net, after removing overlap with P1 and P2.

**Risks.** Summaries are free text that tests check with `in`, and agents quote them. Keep the
exact wording per connector by passing `label`/`scope`/`suffix`; `thai_dip` adds caveat
sentences, for example.

**Tests that protect it.** Envelope tests that assert the query or label appears in `summary`.

---

## P7. Small leaf helpers

| Helper | Copies today | Lines removed |
|---|---|---|
| `parse_iso_date(value, *, field)` → `date \| None`, raising `ValidationError` | `uspto.py:485` and `uspto.py:1251` (byte-identical in the same file), `usitc.py:127`, `canada_federal_court.py:38`, `japan_ip_high_court.py:45`, `cafc.py:226-229` inline; `patent_assignments.py:86` is multi-format (keep) | ~50 |
| CKAN release helpers: `ckan_resource_row(raw, id_key)`, `ckan_find_resource(dataset, id, id_key, source_name, source_url)` | `ilpo.py:244-310`, `inpi_br_bulk.py:97-171`, `ip_australia_bulk.py:91-161` (symilar flags 15+14+11+9 lines). Divergence: the id key is `resource_id` in two and `release_id` in IPA | ~60 |
| `register_download(mcp, prefix, fetch, *, uri_template, name, description, mime, requires_env=None)`, which pairs `register_source` with the `pca://` resource template | `patents.py:187-201`, `publications.py:130-144`, `uspto.py:157-190` (×2), `epo_ops.py:76-90`, `jpo.py:146-170`, and the `conditional_resource` blocks in 5 BYOK modules | ~50 |

**Risks.** The CKAN helpers are only worth doing if the connector-level CKAN clients are merged too
(another agent covers that). The download helper must keep resource `name` and `description` text,
because those are client-visible.

**Tests that protect it.** `tests/{ilpo_tm,inpi_br_bulk,ip_australia_bulk}/test_mcp_envelope.py`,
`tests/patent_client_agents/mcp/test_resources_e2e.py`, `test_download_file_history.py`,
`test_download_ptab_bulk.py`, `tests/*/test_env_gating.py` (11 files), and the date-filter tests in
`usitc`, `canada_federal_court`, and `japan_ip_high_court`.

---

## P8. Mount table in `full.py` (and optional import gating)

**What it owns.** `full.py` is 50 import lines plus 50 `ip_mcp.mount(...)` lines in a hand-kept
order. Replace them with one ordered tuple of `(module, attr)` and a loop using `importlib.import_module`.
Optionally, an entry could carry a `requires_env` so that wholly env-gated families are not imported at all
when their credentials are missing: jpo, canlii, euipo, inpi_pi, ip_australia_{patents,trademarks,designs},
ipi_swissreg, iponz, oepm_spain, thai_dip, tipo_opdata, kipo_kipris, dpma_register. Today those modules are
imported and their decorators simply skip registration.

**Estimated lines removed.** About 50.

**Risks.** Static analysis and IDE navigation lose the explicit imports. Mount order sets
`tools/list` order. Modules that run `register_source(...)` on import (the docstring at `full.py:12-14`
relies on that) must still be imported whenever their tools are mounted. Import gating would
change which download prefixes exist on a server without credentials, which is arguably more correct but needs
`test_env_gating.py` updates. The instruction text is also duplicated between `server.py:44-50` and
`full.py:73-89`, and the hard-coded "136 / 234" tool counts appear in both. `scripts/mcp_tool_counts.py --check-docs`
guards the counts, but the server instruction text has already drifted from `full.py`. Keep one source.

**Tests that protect it.** `scripts/mcp_tool_counts.py`, which builds the server in two env profiles and checks counts,
`scripts/validate_mcp_contracts.py`, and `tests/patent_client_agents/mcp/test_lazy_package.py`.

---

## P9. Error translation cleanups (no primitive needed, but fixes are cheap)

`FriendlyErrors` (`mcp_data_core/mcp/middleware.py:53-127`) already maps every `McpDataCoreError`
subclass. `ValidationError` subclasses both `McpDataCoreError` and `ValueError`, so the 173
`raise ValidationError` sites are fine, and no tool needs its own try/except translation. A few leaks remain:

- `patents.py:443` and `patents.py:575` raise a plain `ValueError` for "not found". These should be `NotFoundError`
  so agents get `[not-retryable] Not found: …`. Today the message passes through without the retryability tag.
- `jpo.py:114/138` and `china_spc_ip_court.py:67` raise a plain `ValueError` for validation. These should be
  `ValidationError`. (The fetcher-path `ValueError`s in `uspto.py:125/151` and `usitc.py:153` are in download routes, not tools.)
- Several date and cursor `try/except ValueError → ValidationError` blocks disappear once P5 and P7 land.

About 10 lines. Mainly a correctness change.

---

## P10 (optional). Shared `Full` parameter alias

There are 83 `full: Annotated[bool, "..."]` declarations taking 402 lines (about 4.8 lines each, mostly listing
the lean fields). A shared `Full = Annotated[bool, "False (default): lean rows. True: upstream-shaped rows."]`
would save about 320 lines. **Not counted in the headline**, because the per-connector text tells agents
which fields the lean view keeps. That is useful context, and §5.10 asks for format examples in parameter
docs. A middle option is a `full_param(lean_fields: str)` helper that builds the string, which saves about 2 lines each (~170).

---

## Client lifecycle (no line savings; measure before acting)

There are 176 `async with XClient() as client` sites in 48 files. Every tool call builds a new
`BaseAsyncClient`, which runs `cache_dir.mkdir`, builds an httpx client, and opens the hishel SQLite
storage (`mcp_data_core/base_client.py:95-150`), then closes all of it at the end of the call. A
process-lifetime client registry, opened lazily and closed in the server lifespan, would remove that
per-call setup. Risks:

1. Tests monkeypatch module-level client classes (17 sites patch `canlii.CanLIIClient`, 13 patch
   `uspto.UsptoOdpClient`, 13 patch `publications.PublicSearchClient`, …). A cache keyed by class would
   leak the patched instance between tests unless it's reset per test.
2. httpx/anyio clients are bound to an event loop, and pytest-asyncio uses a new loop for each test.
3. OAuth-token clients (JPO, EUIPO, IPA, INPI) hold refresh state.

Profile a hot tool such as `get_application` before deciding. The line count would not change.

---

## Startup cost and lazy registration

Measured with `.venv/bin/python -X importtime -c "import patent_client_agents.mcp.full"`, saved as
`importtime.txt` next to this file. Full import takes 2.23 s; `import patent_client_agents.mcp.server` peaks at 196 MB RSS.

| Layer | Time |
|---|---|
| `fastmcp` itself | ~0.24 s (48 MB RSS) |
| `mcp_data_core.mcp` package `__init__` (pulls `auth` → `fastmcp.server.auth.providers.google`) | ~0.25 s attributable to the Google provider (+~36 MB) |
| Tool modules' own code (decorators, schema generation) | 0.26 s total self time |
| Connector packages' own code (pydantic models, etc.) | 0.38 s self time |
| `markitdown` (from `google_patents/client.py:16`, top-level import; pulls magika, onnxruntime, numpy, pypdf) | **0.19 s, +37 MB** |
| `playwright.async_api` (`uspto_tmsearch/token_manager.py:29`) + `curl_cffi` (`uspto_tmsearch/client.py:21`) | **0.10 s + 0.05 s, +28 MB**. The comment at `client.py:18` says curl_cffi is "imported lazily," but it is a top-level try/except, so it isn't |
| `epo_ops` package (pulled in by `cpc`) | 0.07 s |

Recommendations, cheapest first:

1. **Move heavy optional imports inside the functions that use them**: `MarkItDown` inside
   `google_patents.client._html_to_markdown` (l.108), `async_playwright` inside the token-mint
   path (`token_manager.py:237`), and `AsyncSession` inside the TESS search call. That saves about 0.35 s and
   roughly 50–65 MB RSS with tiny diffs. Keep the `*_AVAILABLE` flags through `importlib.util.find_spec`.
2. **In mcp-data-core, stop importing `auth` eagerly from `mcp_data_core/mcp/__init__.py`.** Every tool module
   imports `mcp_data_core.mcp.annotations`, which runs the whole package `__init__` (auth, downloads,
   middleware, server_factory). Importing `mcp_data_core.mcp.annotations` alone, after `fastmcp`, costs 0.68 s.
   Making `make_auth` lazy, or importing the Google provider inside `make_auth` only when Google env vars are
   set, saves about 0.25 s for stdio and for law-tools mounts.
3. **Fully lazy tool registration is not worth it.** FastMCP builds tool schemas from function
   signatures, so registering without importing would need a generated static manifest plus deferred
   dispatch. The most it could save is about 0.64 s (tool and connector self time), and it would add a second
   source of truth for schemas. P8's import gating for credential-gated families (~0.08 s) is the
   only cheap piece.

Together, items 1 and 2 bring startup from about 2.2 s to about 1.6 s and peak RSS down by roughly
60–90 MB. That's an estimate; re-measure after the change.

---

## Totals

| Primitive | Lines removed (est.) |
|---|---|
| P1 corpus_tools | ~1,100 |
| P2 fetch_many / as_id_list / gather_bounded (+ fan-out constants) | ~660 |
| P3 dump() | ~300 |
| P4 provenance_for (+ cache-aware provenance, a correctness fix) | ~180 |
| P5 paging/limit aliases | ~100 |
| P6 hits_summary | ~60 |
| P7 parse_iso_date, CKAN helpers, register_download | ~160 |
| P8 mount table | ~50 |
| P9 error fixes | ~10 |
| **Total** | **≈2,600** (≈13% of 20.3k) |
| P10 optional `Full` alias | +170 to +320 |

Suggested order, with verification at each step:

1. Add tests for the gaps first: corpus offset/limit paging, fan-out order and partial failure,
   and a second-call cache-hit check.
2. Land P3, P7, and P9 (leaf helpers, low risk). Then run `uv run pytest`, `scripts/validate_mcp_contracts.py`, and
   `scripts/mcp_tool_counts.py --check-docs`.
3. Land P2 and P6 in mcp-data-core with their own unit tests. Migrate a few connectors per PR, matching the
   §5.9 migration pattern.
4. Amend §5.15, then land P1 corpus module by corpus module, with the per-corpus envelope tests as the guard.
5. Do the P4 factory, then cache-aware provenance as a separate mcp-data-core change.
6. Do the P5 schema-constraint aliases last, because they change `tools/list` schemas and error strings.

Startup items 1 and 2 can be done at any point, separately from the above.

## Appendix: list-accepting fan-out tools (68), body lines (excluding docstring)

canada_federal_court: search_canada_federal_court_patent_cases 59*, get_canada_federal_court_case 32 ·
canlii: search_canlii_ip_cases 72, get_canlii_case 29, get_canlii_legislation 31 ·
china_spc_ip_court: search_china_spc_ip_hearing_notices 56, get_china_spc_ip_hearing_notice 24 ·
copyright: get_copyright_record 28* · dpma_register: get_dpma_patent 18, get_dpma_trademark 17, get_dpma_design 17 ·
dpma_statutes: get_dpma_section 29 · epc: get_epc_section 36 · epo_case_law: get_epo_case_law_section 34 ·
epo_guidelines: get_epo_guidelines_section 34 · epo_ops: get_epo_biblio 31, get_epo_fulltext 25, get_epo_family 25,
get_epo_citations 26, get_epo_equivalents 26, get_epo_legal_events 25, get_epo_register_biblio 29,
get_epo_register_events 26, get_epo_procedural_steps 26 · epo_pct_guidelines 34 · epo_up_guidelines 33 ·
euipo: get_euipo_trademark 28, get_euipo_design 26 · ilpo: get_ilpo_section 34* · inpi_br_statutes 34 ·
ip_australia: get_ipa_design 28, get_ipa_patent 28, get_ipa_trademark 26 · ipo_in_mppp 28 · ipo_in_statutes 31 ·
ipos: get_ipos_section 35*, get_ipos_manual_section 34* · jpo: get_jpo_progress 31, get_jpo_progress_simple 31,
get_jpo_registration_info 31 · legifrance_ip 35 · mpep 45 · office_actions: get_office_action 40* ·
patents: get_patent 49 · prh_fi: get_prh_patent 22 · prv_se: get_prv_patent 22 · publications: get_patent_publication 35 ·
thai_dip: 15/10/10/10 · tipo_opdata: get_tipo_patent_events 47, get_tipo_trademark_events 41 ·
trademarks: get_trademark 41*, get_trademark_status 25, get_trademark_last_update 25, get_tmep_section 41 ·
tw_trade_secrets 29 · ukipo_mopp 30 · upc: get_upc_decision 31*, get_upc_section 32* ·
usitc: get_usitc_investigation 54*, download_usitc_investigation_documents 163* ·
uspto: get_application 25, get_patent_assignment 29, get_ptab 35, get_petition 27 · wipo_lex 25.
(* = drops or reports not-found ids instead of raising.)
