# Connector Migration Playbook

How to sweep the existing tool surface onto the standards in
[`CONNECTOR_STANDARDS.md`](CONNECTOR_STANDARDS.md). This is a working
document; expect to amend it as we learn from the first few migrations.

The canonical reference is the USPTO Applications migration:
- Code: [`src/patent_client_agents/mcp/tools/uspto.py`](src/patent_client_agents/mcp/tools/uspto.py)
  (`_odp_provenance`, `_summarize_application`, `search_applications`,
  `get_application`, `list_file_history`)
- Tests: [`tests/uspto_odp/test_mcp_envelope.py`](tests/uspto_odp/test_mcp_envelope.py)
- Audit (the diff this playbook closes):
  [`research/tool-surface-audit-2026-05-14.md`](research/tool-surface-audit-2026-05-14.md)

When in doubt: open USPTO Applications, copy its pattern, adapt for the
new source. Don't redesign.

---

## §1 The recipe (per tool)

For each tool you migrate, walk these steps in order:

1. **Read the audit row** for the tool in `research/tool-surface-audit-2026-05-14.md`
   so you know which §5 rules it currently breaks. Common ones:
   - §5.4 — needs `list[str]` support
   - §5.5 — needs a lean default + `full=True` opt-in
   - §5.6 — needs a "Related tools:" line in the docstring
   - §5.7 — name needs a jurisdiction prefix
   - §5.8 — needs a renamed verb or parameter
   - §5.13 — first sentence needs to pass the elevator test

2. **Change the return type annotation** from `-> dict` (or absent) to
   `-> ListEnvelope[dict]` or `-> ResponseEnvelope[dict]`. Single-record
   `get_*` tools that *don't* accept lists return `ResponseEnvelope`;
   anything list-shaped (search, list-accepting get, list_*, facet
   collections) returns `ListEnvelope`.

3. **Build a source-specific `_xxx_provenance(path)` helper** if the
   file doesn't already have one. One per upstream:
   ```python
   _USPTO_ODP_BASE = "https://api.uspto.gov"
   _USPTO_ODP_NAME = "USPTO Open Data Portal"

   def _odp_provenance(path: str) -> Provenance:
       return make_provenance(
           source_url=f"{_USPTO_ODP_BASE}{path}",
           source_name=_USPTO_ODP_NAME,
       )
   ```
   For `transport: mcp_local` substantive-law connectors, also pass
   `corpus_synced_at` and `corpus_version` (read from the connector's
   `get_corpus_status()` once that lands; for now, hardcode from
   `coverage/sources.yaml`).

4. **Write a `_summarize_xxx(record)` helper** for single records the
   tool returns. Markdown, ≤5 lines, leads with the most-quotable
   identifier (patent number, application number, decision date) and
   ends with a status or outcome. The summary is what the agent will
   paste into its reply; treat it as customer-facing text.

5. **Wrap the upstream call in an envelope.** Pattern:
   ```python
   async with FooClient() as client:
       result = await client.search_foo(...)

   dumped = _dump(result) if hasattr(result, "model_dump") else result
   items = list(dumped.get("results") or dumped.get("patentBag") or [])
   total = dumped.get("count") or dumped.get("recordTotalQuantity")
   return ListEnvelope[dict](
       summary=f"Foo — `{query}`: {len(items)} of {total} hits.",
       items=items,
       more_available=bool(total and len(items) + offset < int(total)),
       next_cursor=None,  # see §3 below for cursor patterns
       provenance=_foo_provenance("/api/v1/foo/search"),
   )
   ```

6. **For list-accepting `get_*`** (§5.4), accept
   `identifier: str | list[str]`, normalize to a list, fan out with
   bounded concurrency, return `ListEnvelope`:
   ```python
   _FOO_FANOUT_CONCURRENCY = 5

   numbers = [x] if isinstance(x, str) else list(x)
   semaphore = asyncio.Semaphore(_FOO_FANOUT_CONCURRENCY)

   async def _fetch_one(client, n):
       async with semaphore:
           return _dump(await client.get_foo(n))

   async with FooClient() as client:
       results = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])
   ```
   Order preservation matters — `asyncio.gather` preserves order; don't
   replace it with `as_completed`.

7. **Update the docstring**:
   - First sentence: elevator test (§5.13). No unexpanded acronyms.
   - Parameter descriptions: examples, accepted formats.
   - End with `Related tools: <name1>, <name2>.` per §5.6.
   - No "Returns: dict with keys ..." prose — envelope is universal.
   - ≤40 lines total (§5.10).

8. **Write the envelope test** in
   `tests/<source>/test_mcp_envelope.py`. Mock the upstream client at
   the boundary (`unittest.mock.patch` + `AsyncMock`); we're testing
   envelope shape, not the upstream API. Assert:
   - `isinstance(result, ListEnvelope)` (or `ResponseEnvelope`).
   - `result.provenance.source_name == "<expected>"`.
   - `result.provenance.source_url` contains the expected path.
   - `result.summary` contains identifying text from the input.
   - For list-accepting `get_*`: order preserved across the input list.
   - For search: `more_available` is `True` when `total > shown` and
     `False` when exhausted.

9. **Run `uv run ruff check && uv run ruff format && uv run pytest`** on
   the affected files. Fix until clean.

10. **Commit per connector**, not per tool. One PR per connector keeps
    review focused and rollback granular.

---

## §2 Per-shape templates

Five shapes cover ~all tools. Pick one, adapt.

### Shape A — `search_*` returning a list

`search_applications` is the canonical example. Lean by default; opt
into `full=True`. Returns `ListEnvelope[dict]` with `more_available`
computed from the upstream's total.

Key decisions:
- Where does the lean projection live? In the underlying client if it
  already supports a `full=` flag (USPTO ODP does); otherwise, project
  in the tool function.
- Where does `total` come from? Look for `count`, `recordTotalQuantity`,
  `totalElements`, `numFound`. Standardize on whichever the upstream
  returns.

### Shape B — single-record `get_*` (no list support yet)

Returns `ResponseEnvelope[dict]`. Use this only when the upstream
identifier resolution is genuinely 1:1 (e.g., `get_patent_family` —
the family graph for one number doesn't make sense to list-accept). For
anything portfolio-shaped, prefer Shape C.

```python
async def get_foo(foo_id: Annotated[str, "..."]) -> ResponseEnvelope[dict]:
    async with FooClient() as client:
        record = _dump(await client.get_foo(foo_id))
    return ResponseEnvelope[dict](
        summary=_summarize_foo(record),
        details=record,
        provenance=_foo_provenance(f"/api/v1/foo/{foo_id}"),
    )
```

### Shape C — list-accepting `get_*` (§5.4)

The portfolio-friendly default. Pattern in §1 step 6 above. Returns
`ListEnvelope` even when called with a single string.

Provenance URL:
- Single ID call: point at the specific record URL
  (`/api/v1/foo/{id}`).
- Multiple IDs: point at the collection URL (`/api/v1/foo`), since no
  single record URL applies.

### Shape D — facet fetch (`list_file_history`, `get_patent_claims`)

Returns a `ListEnvelope[dict]` of facet rows. Project to a lean shape
(§5.5) — strip the upstream nesting, keep the fields an agent
actually uses.

### Shape E — `download_*`

Already returns ResourceLinks + a `download_url` per the
`download_bulk_tool_result` pattern. **Do not** wrap these in
`ListEnvelope`. The existing shape is the contract for resource-aware
MCP clients; changing it breaks CoWork-style allowlists.

Open question for §5.9: do downloads need a `summary` + `provenance`
sidecar? Defer until we hit the first real need. Don't speculate.

---

## §3 Cursor patterns for the 7 pagination styles

The audit found 7 pagination styles in the catalog. All migrate to
opaque base64(JSON) cursors via
`law_tools_core.envelope.encode_cursor`. Map each upstream style to a
cursor payload:

| Upstream style | Used by | Cursor payload |
|---|---|---|
| `offset` + `limit` | USPTO ODP, CanLII, office_actions (`start`+`rows`) | `{"offset": N}` |
| `range_begin` + `range_end` | EPO OPS | `{"range_begin": N, "range_end": M}` |
| `page` + `size` | EUIPO, UPC | `{"page": N, "size": M}` |
| numeric `page` only | UPC decisions | `{"page": N}` |

The tool layer:
1. If the caller passes `next_cursor`, decode it and use the fields as
   the upstream call's pagination params.
2. After the call, if `total > shown + offset` (or equivalent), build a
   new cursor payload and `encode_cursor` it as `next_cursor`.
3. Set `more_available = (next_cursor is not None)`.

Don't lock the payload schema across sources — connectors decide their
own payload shape. Agents treat cursors as bytes.

---

## §4 Sweep order

Order picked for: (a) impact, (b) shape variety, (c) cleanest blast
radius. Each row is one PR.

| # | Connector(s) | Tools | Audit findings this closes | Status |
|---|---|---|---|---|
| 1 | USPTO Applications | search_applications, get_application, list_file_history | §5.9 envelope, §5.4 list-accept | ✅ |
| 2 | Trademarks (USPTO TSDR + TM Search) | search_trademarks, get_trademark, get_trademark_status, get_trademark_documents, get_trademark_last_update, **DELETE batch_trademark_status** | §5.4 (kill batch tool), §5.3 (collapse get_trademark args), §5.5 lean, §5.9 | ✅ |
| 3 | USPTO Publications (PPUBS) | search_patent_publications, get_patent_publication, resolve_publication_number | §5.9, §5.5 lean, §5.1 collapse with get_patent if feasible | ✅ |
| 4 | Google Patents | search_google_patents → rename `search_patents_global`, get_patent, **DROP get_patent_details** (fold into `view='details'` opt-in) | §5.1, §5.5, §5.7 jurisdiction prefix, §5.9 | pending |
| 5 | USPTO PTAB | search_ptab, get_ptab, list_ptab_children | §5.9, §5.13 elevator (expand PTAB on first use) | pending |
| 6 | USPTO Office Actions | search_office_actions, **ADD get_office_action** (fixes §5.2 orphan) | §5.9, §5.2 | pending |
| 7 | USPTO Petitions | search_petitions, get_petition (rename `petition_id` → `petition_number`) | §5.8 param name, §5.9 | pending |
| 8 | Patent + Trademark Assignments | search_patent_assignments, search_trademark_assignments, get_patent_assignment | §5.5 lean, §5.6 cross-refs, §5.9 | pending |
| 9 | EPO OPS | search_epo, get_epo_biblio, get_epo_family, get_epo_fulltext, get_epo_legal_events, get_epo_cql_help (reword) | §5.4 list-accept on all gets, §5.6 cross-refs, §5.9, §5.13 (cql_help) | pending |
| 10 | EUIPO | search_euipo_trademarks, get_euipo_trademark, search_euipo_designs, get_euipo_design | §5.6 cross-refs, §5.9 | ✅ |
| 11 | JPO | get_jpo_progress + facet fetches; **collapse get_jpo_applicant_by_*** (§5.3); **rename get_jpo_jplatpat_url / get_jpo_number_reference first sentences** (§5.13) | §5.3, §5.4, §5.6, §5.9, §5.13 | ✅ |
| 12 | UPC | search_upc_decisions, get_upc_decision, search_upc_statutes, get_upc_section, list_upc_* (vocab) | §5.6 cross-refs, §5.9, §5.8 (verb table for vocab `list_*`) | ✅ |
| 13 | USITC | search_usitc_investigations, **ADD get_usitc_investigation** (fixes §5.2 orphan), list_usitc_attachments, download_*, search_hts_tariffs, run_dataweb_report (rewrite §5.13) | §5.2, §5.9, §5.13 | pending |
| 14 | CAFC | search_cafc_opinions, search_cafc_patent_opinions, download_cafc_pdf | §5.6, §5.9; also category=substantive_law (verify Provenance includes corpus fields) | ✅ |
| 15 | CanLII | **rename `browse_*` → `search_*`** per §5.8; get_canlii_case (§5.4 list-accept), citator cross-refs | §5.4, §5.6, §5.8, §5.9 | pending |
| 16 | Copyright | search_copyright, get_copyright_record (kept `public_records_id` — upstream genuinely uses opaque IDs distinct from registration numbers) | §5.5 lean, §5.6 cross-refs, §5.9 | ✅ |
| 17 | MPEP (substantive-law template) | search_mpep, get_mpep_section, **implement `get_corpus_status()`** at module level | §5.6 (cross-ref), §5.9 (Provenance with corpus_synced_at/version), §4 callable rollout | ✅ |
| 18 | Remaining corpora (TMEP, EPC, EPO Guidelines, EPO PCT, EPO UP, EPO CaseLaw, MoPP, UPC Statutes) | three parallel sub-batches; all 8 corpora ship get_corpus_status() | §5.6, §5.9, §4; **validator check #3 flipped to hard error** | ✅ |
| 19 | WIPO Lex | search_wipo_lex_legislation, get_wipo_lex_legislation | §5.6, §5.9 | ✅ |
| 20 | CPC | lookup_cpc, search_cpc, map_cpc_classification (sharpened first sentences per §5.13) | §5.9, §5.13 | ✅ |
| 21 | Unitary patent helper | rename `get_unitary_patent_package` → `get_epo_unitary_patent_status` | §5.7, §5.8, §5.13, §5.9 | pending |

**Progress as of 2026-05-15: 13 of 21 rows complete (62%).**
~66 tools across 19 connectors are on the envelope. The 8 remaining
rows are all register-side (no more substantive-law corpora to migrate);
the next-easiest are row 8 (assignments), row 21 (one rename), and
row 13 (USITC adds one tool). The hardest are row 4 (Google Patents
collapse), row 9 (EPO OPS in a shared file), and rows 5+7 (PTAB +
Petitions share `uspto.py` with row 1 — sequence carefully).

Rows 17 and 18 finished the `get_corpus_status()` rollout. The
validator's check #3 is now a hard error; any new category-2
mcp_local connector that doesn't expose the callable will fail CI.

---

## §5 Pre-flight checklist (before opening the connector)

**Worktree + venv sanity (skip at your peril):**

- [ ] `pwd` reports a path under `.claude/worktrees/agent-<id>/`. If
      you're in the parent repo, your work will collide with the
      currently-running migration. Move now.
- [ ] `git rebase refactor/connector-standards-sweep` (or whatever
      branch carries the envelope foundation today). The fresh
      worktree base is usually older than the active branch.
- [ ] The venv's editable install points at YOUR worktree's `src/`:
      `uv run python -c "import patent_client_agents; print(patent_client_agents.__file__)"`
      should print a path under your worktree. If it points at the
      parent repo or a sibling worktree, run `uv sync --extra mcp
      --extra tmsearch --group dev` from your worktree to reset.

**Content prep:**

- [ ] Read the audit row(s) for every tool in the file.
- [ ] Open the USPTO Applications template side-by-side.
- [ ] Look up the upstream's pagination style in §3 above.
- [ ] Confirm the upstream's canonical base URL (for the provenance
      helper). For USPTO: `https://api.uspto.gov`. For EPO OPS:
      `https://ops.epo.org/3.2/rest-services`. For Google Patents:
      pattern the URL after the human-facing page.
- [ ] Confirm the `coverage/sources.yaml` entry for this connector is
      correct — especially `category`, `transport`, and (for
      substantive law) `update_strategy` / `update_cadence` /
      `corpus_version`.
- [ ] Decide which tools collapse, get renamed, or get deleted (rows
      2-4 above show the patterns).

---

## §6 Per-tool checklist (definition of done)

For every tool the PR touches:

- [ ] Return type is `ResponseEnvelope[dict]` or `ListEnvelope[dict]`.
- [ ] Provenance built via the source's `_xxx_provenance(path)` helper.
- [ ] `summary` is short Markdown, ≤5 lines, leading with the most
      quotable identifier.
- [ ] Docstring first sentence passes the elevator test (§5.13).
- [ ] Docstring ends with `Related tools: <names>.` (§5.6).
- [ ] Parameter names are practitioner-facing (`application_number`,
      not `id`).
- [ ] `get_*` tools accept `str | list[str]` if portfolio-shaped (§5.4).
- [ ] No `batch_*` variant introduced; existing batch tools deleted.
- [ ] No `get_by_*` family; one `get_thing` with auto-detected
      identifiers.
- [ ] `search_*` tools default to a lean projection with `full=True`
      opt-in (§5.5).
- [ ] Tests in `tests/<source>/test_mcp_envelope.py` cover envelope
      shape, provenance, summary content, and (for list-accepting
      gets) order preservation.
- [ ] `uv run ruff check . && uv run ruff format --check .` clean.
- [ ] `uv run pytest tests/<source>/` clean.

---

## §7 Connector-level acceptance criteria (the PR itself)

- [ ] One connector per PR. Don't bundle.
- [ ] `coverage/sources.yaml` updated if any field changed
      (typically `last_verified` to today's date).
- [ ] `uv run python scripts/build_coverage.py --check` clean (no new
      errors; previously-warning items can persist but should be
      called out in the PR description).
- [ ] CHANGELOG entry under the next-release header, naming the
      §5 rules closed and the tools renamed/deleted.
- [ ] If tool names changed: a one-paragraph migration note in the PR
      description listing the old → new mapping.

---

## §8 Common gotchas

- **Tool function defined inside `@mcp.tool(...)` decorator with type
  ignore comments.** The decorator captures the function for FastMCP
  registration. Don't try to reshape the decorated function in-place;
  edit the body.

- **Pydantic models from upstream clients.** Existing clients return
  Pydantic v2 models. `model_dump()` gives a dict; the existing
  `_dump()` helper in `uspto.py` also strips auth-required URLs. When
  copying this helper to other connectors, check whether the same
  URL-stripping is needed (USPTO ODP has auth-gated download URLs;
  EPO does not; EUIPO returns time-limited URLs that are safe to keep).

- **Mocking in tests.** Mock at the client boundary — patch
  `UsptoOdpClient` (or whichever client class the tool instantiates),
  not the HTTP layer below. See
  [`tests/uspto_odp/test_mcp_envelope.py`](tests/uspto_odp/test_mcp_envelope.py)
  for the pattern.

- **`asyncio.gather` for fan-out.** Preserves order, runs concurrently,
  respects the semaphore. Don't reach for `as_completed` unless you
  actually want completion-order; for §5.4 list-accepting gets, the
  caller expects positional alignment.

- **Recording new cassettes.** VCR cassettes already exist for most
  connectors; the envelope migration doesn't usually need new ones if
  you mock at the client boundary. If you do record live cassettes,
  scrub auth headers and run `gitleaks protect --staged` before
  committing.

- **CHANGELOG vs release tags.** The repo uses `v0.X.Y` tags; the
  in-flight branch can carry an unreleased CHANGELOG entry. Don't bump
  the version per-migration PR — bump it when a coherent group of
  migrations is ready to release.

- **`uv run` is slow first time, fast after.** Each migration PR is
  ~10 minutes of code + tests + lint. If a single `uv run pytest`
  takes more than a minute, you're recording cassettes you shouldn't
  be.

- **Worktree agents: never `cd` out of your worktree.** Multiple batches
  have hit this. Symptoms: your final `git commit` lands in the parent
  repo's branch (`refactor/connector-standards-sweep`) instead of your
  isolated worktree branch; OR Write/Edit tool calls write to absolute
  paths in the parent repo because earlier `cd` commands shifted the
  shell. Recovery is `git reset --soft HEAD~1` followed by
  `git restore --staged .` in the parent repo, then redo the commit
  in the worktree. Cheaper to just `pwd` before every commit and
  confirm you're under `.claude/worktrees/agent-<id>/`.

  **Defensive pattern for agents:** at the start of each meaningful
  shell call, prefix with `cd /Users/.../patent-client-agents/.claude/worktrees/agent-<id> &&`
  so cwd-drift doesn't compound silently. Use absolute paths for Edit
  / Write tool calls.

- **`uv sync --extra <X>` drops other extras.** Running
  `uv sync --extra tmsearch` mid-session removed `fastmcp` (from the
  `[mcp]` extra), breaking every MCP-layer test. Use the full form:
  `uv sync --extra mcp --extra tmsearch --group dev`. If your venv
  loses `fastmcp` or `playwright` mid-session, that's the recovery.

- **Editable install drift across worktrees.** `uv sync` updates the
  venv's editable install to point at the cwd's `src/`. Running it
  from inside a worktree redirects `import patent_client_agents` to
  that worktree's source tree. When the worktree is later removed, the
  install still points at the dead path (or worse, at a sibling
  worktree). Symptoms: validator emits warnings for callables you KNOW
  you implemented; tests import old versions of code. **Diagnose:**
  `uv run python -c "import patent_client_agents; print(patent_client_agents.__file__)"`.
  **Recover:** `cd` to the parent repo, then
  `uv sync --extra mcp --extra tmsearch --group dev`. Then remove
  stale worktrees: `git worktree remove --force --force <path>`.

- **Cherry-pick worktree commits from the PARENT repo, not from
  inside a worktree.** Cherry-picking inside a worktree creates the
  new commit on whatever branch that worktree is on (usually the
  isolated branch), not the integration branch. If you accidentally
  cherry-pick from a worktree, the integration branch in the parent
  repo is unchanged; the cherry-picked commit is orphaned. Verify with
  `pwd && git status` before every cherry-pick.

- **`get_corpus_status()` schema variation.** The template in this
  section reads `meta.source_version`, but the actual schema varies
  per corpus. Each agent migrated their corpus's actual schema:
  - MPEP / TMEP: `meta.source_version = "current"` (no real version tag)
  - EPC: `meta.epc_year = "2020"`
  - EPO Guidelines: `meta.guidelines_year = "2024"`
  - EPO Case Law: `meta.caselaw_year = "2022"`
  - PCT Guidelines: `meta.guidelines_year = "2024"`
  - EPO UP Guidelines: `meta.up_guidelines_year = "2026"`
  - UKIPO MoPP: derives `"snapshot-YYYY-MM-DD"` from `meta.snapshot_date`
    (gov.uk publishes no stable revision tag)
  - UPC Statutes: derives `"snapshot-YYYY-MM-DD"` from `meta.snapshot_date`
    (schema has no `source_version` column)

  When adapting the template, prefer the per-corpus key over a generic
  fallback to `"unknown"` if the key carries a meaningful vendor label.
  Never fabricate values — fall through to `"unknown"` if the meta is
  truly absent.

- **`get_corpus_status()` template for substantive-law `mcp_local`
  connectors** (extracted from row 17's MPEP migration). Copy this
  pattern verbatim across row 18's 8 sub-PRs:

  1. Module-level callable in `<corpus>/__init__.py`:
     ```python
     class CorpusStatus(TypedDict):
         corpus_synced_at: datetime | None
         corpus_version: str

     def get_corpus_status() -> CorpusStatus:
         try:
             with CorpusDB() as db:
                 version = db.meta_get("source_version") or "unknown"
                 synced_raw = db.meta_get("snapshot_date")
             return CorpusStatus(
                 corpus_synced_at=_parse_snapshot_date(synced_raw),
                 corpus_version=version,
             )
         except CorpusUnavailable:
             return CorpusStatus(corpus_synced_at=None, corpus_version="unknown")
         except Exception:  # pragma: no cover  # defensive
             return CorpusStatus(corpus_synced_at=None, corpus_version="unknown")
     ```
  2. Shared `_parse_snapshot_date(value)` helper lifts ISO `YYYY-MM-DD`
     to UTC midnight datetime; returns `None` on parse failure.
  3. In the MCP tool's `_xxx_provenance(path)` helper, call
     `status = get_corpus_status()` per request and pass both fields
     to `make_provenance(...)`. Never hardcode corpus values in
     `mcp/tools/<corpus>.py`.
  4. Validator: after the connector exposes the callable,
     `scripts/build_coverage.py --check` drops the connector-specific
     warning. After all 8 corpora ship, a one-line follow-up PR flips
     the warning to a hard error.

---

## §9 What this playbook is *not*

- Not a list of every connector's API quirks. Read the connector code
  and the audit; this playbook gives you the shape, not the specifics.
- Not a justification for redesigning a tool's underlying client. If
  you find a real client-level issue, file it separately; the
  migration sweep is scope-limited to the MCP tool layer + tests +
  manifest.
- Not a forever doc. Once the sweep is done, fold the durable bits
  back into `CONNECTOR_STANDARDS.md` and delete this file.
