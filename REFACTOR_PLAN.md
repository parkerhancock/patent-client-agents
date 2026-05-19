# Refactor Plan

Concrete cleanup plan derived from the 2026-05-19 retrospective. The codebase is in good shape overall — `CONNECTOR_STANDARDS.md` is being followed, the 21-row migration shipped cleanly, and the newest connectors (`prh_fi`, `prv_se`) hit the template cold. This plan addresses the few real debts that remain.

Goal: ship in four discrete PRs, smallest blast radius first. Each phase has a clean rollback path. Nothing here changes public MCP tool names or behavior — downstream agents see no contract change.

---

## Phase 1 — Split `mcp/tools/international.py`

**Why.** `international.py` is 1,719 LOC mixing EPO (11 tools), CPC (3 tools), and JPO (12 tools) in one file. Its own docstring admits the grouping. This is the cleanest §5.7 violation in the tree ("one connector per file") and the largest file in the MCP layer.

**What changes.**

| New file | Source range in `international.py` | Tools |
|---|---|---|
| `mcp/tools/epo_ops.py` | helper 67-128 (`_fetch_epo_pdf`, `_epo_patent_pdf_resource`); tools 304-685 + 965-1130 | `search_epo`, `get_epo_cql_help`, `get_epo_biblio`, `get_epo_fulltext`, `get_epo_family`, `get_epo_legal_events`, `convert_epo_number`, `get_epo_unitary_patent_status`, plus the EPO PDF download |
| `mcp/tools/cpc.py` | 801-963 | `lookup_cpc`, `search_cpc`, `map_cpc_classification` |
| `mcp/tools/jpo.py` | helpers 129-260 (`_fetch_jpo_document_bundle`, `_jpo_document_bundle_resource`); tools 1138-end | All 12 `get_jpo_*` tools |

Delete `international.py` once registrations are repointed.

**Steps.**
1. Read `mcp/tools/international.py` end-to-end. Note shared imports + the module-level provenance/projection helpers; each new file gets only the helpers it actually uses.
2. Create `epo_ops.py`, `cpc.py`, `jpo.py`. Copy verbatim — do not "tidy" while moving.
3. Update `src/patent_client_agents/mcp/__init__.py` to import tool registrations from the three new modules instead of `international`. The `JPO_API_USERNAME`/`JPO_API_PASSWORD` env-gating logic moves into `jpo.py`'s registration block.
4. Delete `international.py` and its `__pycache__`.
5. Run the test suite. The cassettes don't care which module the tool lives in.

**Verification.**
- `uv run pytest -q` green.
- `uv run ruff check src/ tests/` clean (likely a few unused-import fixups).
- Start the MCP server locally and confirm `tools/list` returns the same tool names with identical schemas. The diff against a pre-split capture should be empty.
- `python -c "from patent_client_agents.mcp import server; ..."` import still works.

**Rollback.** Revert the PR. No data, schema, or wire-format changes — pure file move.

---

## Phase 2 — Extract `CorpusDBBase` to `law_tools_core`

**Why.** Twelve local-corpus connectors each ship a 176–228-line `corpus/db.py` that is 90%+ identical. Seven of them are *exactly* 213 lines — byte-similar copy-paste of the same `CorpusUnavailable` exception, `CorpusSection`/`CorpusHit` dataclasses, `default_corpus_path`, `_resolve_corpus_path`, `CorpusDB` class, and `_row_to_section` row mapper. Total: 2,514 LOC. Expected post-extraction: ~500 LOC across connectors, ~250 LOC in `law_tools_core`, net ~1,800 LOC removed.

Beyond LOC, the FTS5 + recency contract (`get_corpus_status()` from §4 of standards) ends up defined in one place instead of twelve.

**Affected connectors (12).** `mpep`, `epc`, `ukipo_mopp`, `tw_trade_secrets`, `dpma_statutes`, `legifrance_ip`, `ipo_in_statutes`, `epo_up_guidelines`, `epo_pct_guidelines`, `ipo_in_mppp`, `epo_case_law`, `epo_guidelines`.

**What changes.**

Add `src/law_tools_core/corpus_db.py` exposing:

```python
class CorpusUnavailable(LawToolsCoreError): ...

@dataclass(frozen=True)
class CorpusSection: ...          # the common projection shape
@dataclass(frozen=True)
class CorpusHit: ...              # FTS5 hit + snippet + rank

class CorpusDBBase:
    """SQLite + FTS5 read-only client for bundled corpora.

    Subclasses declare:
      CONNECTOR_NAME: str           # e.g. "mpep"
      ENV_VAR: str                  # e.g. "PATENT_CLIENT_MPEP_CORPUS"
      DEFAULT_FILENAME: str         # e.g. "mpep.sqlite"
      SECTION_TABLE: str            # FTS5 virtual table name
      ROW_TO_SECTION: ClassVar[Callable[[sqlite3.Row], CorpusSection]]
    """
    def get_corpus_status(self) -> CorpusStatus: ...
    def get_section(self, section_id: str) -> CorpusSection | None: ...
    def search(self, query: str, *, limit: int = 20) -> list[CorpusHit]: ...
```

Schema-specific bits (`corpus/schema.py`, `corpus/build.py`) stay in each connector — those are the part that legitimately differs. Only `corpus/db.py` collapses to a thin subclass:

```python
# src/patent_client_agents/mpep/corpus/db.py
from law_tools_core.corpus_db import CorpusDBBase, CorpusSection

def _row_to_section(row): ...     # mpep-specific projection if needed

class CorpusDB(CorpusDBBase):
    CONNECTOR_NAME = "mpep"
    ENV_VAR = "PATENT_CLIENT_MPEP_CORPUS"
    DEFAULT_FILENAME = "mpep.sqlite"
    SECTION_TABLE = "mpep_sections"
    ROW_TO_SECTION = staticmethod(_row_to_section)
```

**Steps.**
1. Write `law_tools_core/corpus_db.py` by copying `mpep/corpus/db.py` and parameterizing the connector-specific constants. Add unit tests in `tests/law_tools_core/test_corpus_db.py` (use a tiny in-memory SQLite fixture).
2. Migrate `mpep` first. Smallest blast radius — it has the most test coverage, so we'll catch regressions early.
3. Run `uv run pytest tests/mpep -q`. Fix anything that surfaces.
4. Migrate the remaining 11 connectors in order of test-suite size (ascending): `tw_trade_secrets`, `ipo_in_mppp`, `epc`, `epo_pct_guidelines`, `epo_up_guidelines`, `epo_case_law`, `epo_guidelines`, `dpma_statutes`, `legifrance_ip`, `ipo_in_statutes`, `ukipo_mopp`. One commit per connector keeps git bisect useful if something breaks downstream.
5. After all 12: grep for `from .corpus.db import CorpusUnavailable` etc. and consolidate any straggler imports to point at `law_tools_core.corpus_db`.

**Verification.**
- `uv run pytest -q` green at every step.
- LOC delta: `git diff --stat main` should show ~1,800 lines removed in `src/patent_client_agents/*/corpus/db.py` and ~250 added in `src/law_tools_core/corpus_db.py`.
- `get_corpus_status()` shape unchanged for every connector — capture before/after with a small script and diff.
- MCP server still starts; `get_mpep_section`, `get_epc_section`, etc. return identical payloads against a fixed input.

**Rollback.** Per-connector revert is independent — Phase 2 is N+1 commits, not one. Revert just the affected connector if a regression appears.

---

## Phase 3 — Update `CONNECTOR_STANDARDS.md`

Depends on Phases 1 + 2 landing first, so the doc cites them as enforcement precedent.

**Why.** Two patterns deserve to be promoted from convention to documented standard:

1. **Fixture-based testing.** `prh_fi` and `prv_se` use `httpx.MockTransport` against committed JSON fixtures in `tests/<connector>/fixtures/`. No VCR cassettes, no auth scrubbing, no replay overhead. This is the right default for stateless contract tests on small connectors. Today it exists as an unwritten "the new ones do it this way" — codify it.

2. **The per-module helper shape.** Every MCP tool module grows `_provenance()`, `_summarize_<entity>()`, `_stub_<entity>()`, `_project_<entity>_row()` helpers. They're domain-specific by necessity but follow a uniform skeleton. Document the skeleton once so future modules don't drift.

**What changes.**

- Add §5.14 "Testing patterns" — covers VCR cassettes (default for connectors with real upstream calls) vs. fixture-based (default for stateless contract tests on small surfaces). Cite `prh_fi` and `prv_se` as canonical templates.
- Add §5.15 "Per-module helper conventions" — names, shapes, when to add one vs. inline. Two paragraphs, no more.
- Update §5.7 with a one-line note: "Cross-office bundling (e.g. the former `international.py`) is forbidden. See Phase 1 of REFACTOR_PLAN for the corrective split."
- Update §2 to reference `law_tools_core.corpus_db.CorpusDBBase` as the standard substrate for `mcp_local` corpora.

**Steps.**
1. Read the existing `CONNECTOR_STANDARDS.md` end-to-end. Place new sections where they fit topically; don't append blindly.
2. Cross-reference `prh_fi` and `prv_se` file paths so future readers can copy from a live template.
3. Open a PR. This is a docs-only change — review should focus on accuracy against the current code, not prose polish.

**Verification.**
- `uv run mkdocs build --strict` passes (docs hooks include `--strict` per CLAUDE.md).
- `scripts/build_coverage.py --check` still green (this only validates the manifest, but worth confirming the doc reorg didn't break a referenced anchor).

**Rollback.** Trivial — docs only.

---

## Phase 4 — Tighten CI gates

**Why.** `.github/workflows/ci.yml` runs `ty check src/` with `continue-on-error: true`, so type errors don't fail CI. Coverage is uploaded to Codecov but no threshold gates anything. Free wins.

**What changes.**

1. Remove `continue-on-error: true` from the `ty check` step. Fix any type errors that surface before merging — they shouldn't be many; the suite has been passing with type-clean code de-facto for a while.
2. Add a coverage floor to the pytest step. Initial target: **60%**. Not aspirational. The point is to prevent regressions, not chase 100%. Use `--cov-fail-under=60`.
3. Audit `scripts/build_coverage.py --check` is still in the workflow and blocking — it is, but confirm during the same PR.
4. Leave Codecov upload untouched.

**Steps.**
1. Capture current type-check output: `uv run ty check src/ 2>&1 | tee /tmp/ty-snapshot.txt`. Decide what to fix and what to suppress (`# type: ignore[...]` with a comment, sparingly).
2. Capture current coverage: `uv run pytest --cov=patent_client_agents --cov-report=term`. Confirm we're already above 60%; if not, lower the initial floor to current-minus-2% and ratchet up later.
3. Edit `.github/workflows/ci.yml`. Single PR.

**Verification.**
- Open a deliberately-broken type PR (e.g. wrong return type on one function) → CI fails. Revert.
- Open a deliberately-uncovered PR (delete a tested branch without removing the test) → CI fails. Revert.

**Rollback.** Revert the workflow change. No code touched.

---

## Non-goals (explicit)

These came up in the retrospective and are **not** part of this plan:

- **Extracting per-module `_provenance` / `_summarize_*` / `_stub_*` helpers.** Each is 2–10 lines and domain-specific. A generic helper would be less readable than the duplication. Phase 3 documents the convention; that's sufficient.
- **Pagination abstraction across proxy connectors.** Real divergence (offset/limit, cursor, page-number) by upstream. A shared helper would be a fiction over genuinely different APIs.
- **Pydantic model base classes / mixins.** Proposed in the audit but the duplication is shallow and Pydantic's own `BaseModel` already provides what we'd extract.
- **Auth env-var resolver.** Each connector's auth is different enough that a shared resolver would be a thin shim. `coverage/sources.yaml access.auth_env` already documents the per-connector convention.
- **Backporting fixture-based tests to old connectors.** Phase 3 just documents the option; old cassettes work fine.

---

## Strategic calls (not refactors — decisions)

Surfaced here so we don't lose them. These are product/architecture calls that need a decision, not code changes:

- **Fees subsystem ceiling.** `FEES_TOP30_GAP.md` is honest: 11/30 shipped, +5–7 unlockable with a paid stealth-HTTP service ($30–300/mo), 6–8 structurally blocked. Decide: invest in stealth infra (and accept recurring spend + external dependency), declare 22–24/30 the honest ceiling and stop, or revisit specific high-value blockers individually. The architecture is sound — this is a budget call.
- **`green_transitive` rating optics.** 39 ARIPO/OAPI states now show "covered" via EPO OPS AP/OA codes. Clever modeling, but the atlas headline number can mislead. Decide whether the atlas UI distinguishes transitive from native, and how prominently. Copy edit, not code.

---

## Phase ordering & PR cadence

1. **Phase 1** — single PR, ~1 hour. Pure file move.
2. **Phase 2** — N+1 PRs over 1–2 days. One base PR adding `CorpusDBBase`, then one PR per connector migration. Sequence by test-suite size ascending so failures surface cheap.
3. **Phase 3** — single docs PR, ~1 hour. Lands after Phases 1+2 so it can cite them.
4. **Phase 4** — single workflow PR, ~30 minutes plus whatever type/coverage fixes surface.

Total expected wall-clock: 2–3 days of focused work. Total expected diff: ~1,800 LOC removed, ~250 LOC added in `law_tools_core`, three new files in `mcp/tools/`, one file deleted, two CI lines changed, one docs file edited.
