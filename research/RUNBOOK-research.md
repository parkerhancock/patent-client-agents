# Runbook — research agents

How an orchestrator agent spawns a research subagent for the coverage
pipeline. Two task types: **§A discovery** (write synopsis + wave file)
and **§B fee schedule** (*deliberately out of scope — see below*).

For each, this doc gives:
- Input — what the orchestrator passes
- Prompt template — copy/paste, fill blanks
- Output contract — file paths, STATE.yaml updates
- Common pitfalls

---

## §A Discovery research (synopsis + wave file)

**Trigger:** STATE.yaml row with `synopsis: null` and `next_action: synopsis_discovery`.

**Starting-point shortcut.** Before WebFetching, check
[`research/wipo_profiles/{iso2}.md`](wipo_profiles/) for WIPO's structured
overview of the jurisdiction — national IP office names + city, WIPO
membership year, treaty count, GII rank, and direct URLs into WIPO Lex,
the statistical IP profile PDF, PCT eGuide, and Madrid System member
profile. Saves 20+ minutes of opening tabs. If the file is missing, run:

```bash
uv run python scripts/wipo_country_profile_snapshot.py {ISO2}
```

That populates the snapshot; see
[`research/wipo_profiles/README.md`](wipo_profiles/README.md) for full
usage and what fields are extracted.

### Input the orchestrator needs

| Field | Source | Example |
|---|---|---|
| `entity_id` | STATE.yaml `.id` | `KR/KIPO` |
| `entity_name` | STATE.yaml `.name` | `KIPO Korea` |
| `layer` | STATE.yaml `.layer` | `national` |
| `iso2` | STATE.yaml `.iso2` | `KR` |
| `rights` | STATE.yaml `.rights` | `[patent, utility_model, trademark, design]` |
| `synopsis_dir` | derived: `multilateral/` or `regional/` or `national/` | `national/` |
| `synopsis_path` | derived: `<dir>/<iso2-prefix>-<office-slug>.md` | `national/kr-kipo.md` |
| `wave_dir` | `waves/<YYYY-MM-DD>-<subject>/` | `waves/2026-05-23-asia-pacific-discovery/` |
| `wave_file` | `<wave_dir>/<office-slug>.md` | `waves/2026-05-23-asia-pacific-discovery/kr-kipo.md` |
| `existing_detail_survey` | STATE.yaml `.detail_survey` (often non-null) | `connectors/kipo.md` |

### Prompt template

Copy this template, fill in `{{ … }}` blanks, pass to Agent (subagent_type: general-purpose, run_in_background: true).

```
You are doing API discovery research for the {{ entity_name }} ({{ entity_id }}) — a {{ layer }} IP office. Goal: determine whether {{ entity_name }} exposes a public, queryable REST/JSON/XML API that we can proxy directly from our connector at runtime, with zero on our side beyond an HTTP client.

The hard constraint: we will NOT download bulk data, host a search index, or maintain an offline corpus. We need a live API we can call per user query. If {{ entity_name }} only offers bulk dumps or HTML-only access, say so clearly — that's a "red" verdict and is just as useful to us as a "green."

Rights covered: {{ rights }}.

You will produce TWO files:

1. **Wave research file** at `{{ wave_file }}` — full primary-source-hyperlinked research with these 10 sections:
   1. Endpoint — base URL + per-right operations
   2. Auth — none / API key / OAuth / paper contract / paid; signup process; foreign-developer accessibility
   3. Query language — structured fields, free text, operators
   4. Pagination — offset/limit/cursor; max results per page; hard cap
   5. Response shape — JSON/XML; sample one search hit + one detail record
   6. Coverage scope — backfile depth; document counts; rights covered
   7. Rate limits / quotas — published numbers; per-key/per-IP/per-day
   8. Terms of service — does ToS permit programmatic / proxy use; redistribution rules
   9. Operational notes — language; geofencing; downtime; recent deprecations; egress patterns
   10. Verdict — green / yellow / red against zero-infra proxy constraint, with one-sentence reasoning

2. **Synopsis file** at `{{ synopsis_path }}` — distilled current-state strategic doc per the template at `research/templates/office-synopsis.md`. 150-200 lines. Sections:
   - Header table (layer, jurisdiction, rights, connector status, last_verified, manifest entry)
   - §1 Mission
   - §2 What's unique here (not covered by higher layers)
   - §2 substitution-gate table naming the best existing substitute,
     its material fidelity gap, and the build-or-skip decision
   - §3 Programmatic surfaces — per-surface mini-table with verdict (🟢/🟡/🔴) + primary-source URL
   - §4 Fees — link only. State the local currency, list the fee categories the office charges in structural terms, and name any discount programs. **Do not paste tables, percentages, or effective dates.** See [`templates/office-synopsis.md`](templates/office-synopsis.md) §4 for the policy.
   - §5 Connector strategy — what we cover today (cross-reference existing manifest IDs); what we should add; what we should NOT add (with reason); next steps
   - §6 Open questions
   - §7 References — primary sources only
   - §8 Change log — initial row dated today

Hyperlink discipline: every claim of fact must have a primary-source URL ({{ entity_name }}'s own domains, official terms-of-service page, official registration portal). Third-party blogs, Stack Overflow, "I think I recall" are not acceptable. If you cannot find a primary source for a specific point, write "no primary source found" rather than guessing.

Cross-reference the existing detail survey at {{ existing_detail_survey }} if it exists — flag any drift from older research with grounded findings.

After writing both files, return a ≤200-word summary to me with:
(a) the overall verdict (green / yellow / red),
(b) the single biggest risk or surprise,
(c) the two file paths.

Do NOT paste the full research into the return — that's what the files are for. Do NOT modify STATE.yaml — the orchestrator handles that.

Use WebSearch + WebFetch. Favor official domain primary sources over secondary research.
```

### Output contract

The agent writes exactly two files. The orchestrator:

1. Verifies both files exist.
2. Updates STATE.yaml row for `{{ entity_id }}`:
   - `synopsis: {{ synopsis_path }}`
   - `detail_survey:` (unchanged unless freshly written)
   - `verdict: <from agent's return summary>`
   - `verdict_basis: <one-line>`
   - `connector_status:` advance to `none` (if verdict = red) or `planned` (if verdict = green/yellow)
   - `next_action: spec_writing` (if connector should be planned) or `monitor` (if red) or `none`
   - `last_verified: <today>`

Do not set `next_action: spec_writing` unless the synopsis substitution gate
identifies a material gap that the proposed connector closes.

### Pitfalls

- **Path collision with monorepo root.** Earlier waves wrote to `/Users/parkerhancock/Projects/parker-monorepo/research/...` instead of the tool-local `tools/patent-client-agents/research/...`. The prompt above uses `research/...` relative paths inside the tool dir; the agent's cwd should be the tool root.
- **Older survey contradicts new finding.** Always flag this in the synopsis Change Log §8 and add a row to `BACKLOG.md` reconciliation log.
- **Office name with non-ASCII.** Use the ISO label or office abbreviation for the filename; original name in headers.
- **No primary source found.** Don't fabricate. Say so explicitly. Mark verdict as `tbd` if blocking; the orchestrator can queue follow-up.

---

## §B Fee schedule research — **not in scope**

We deliberately do **not** do fee-schedule research. Synopsis §4 lists
the categories of fees an office charges (in local currency), the
discount programs by name, and links to the official schedule. That is
the full extent of fee documentation in this repo. Reproducing tables,
percentages, or effective dates is out of scope — fees drift, the
office's own page is authoritative, and mirroring it would only
introduce stale data that misleads readers.

If an existing synopsis is missing the §4 fee-categories blurb, fill it
in by reading the official page; do **not** paste figures.

---

## §C Drift reconciliation research

**Trigger:** A synopsis or detail survey is stale (e.g., older 2026-05 connectors/ survey contradicts current state). STATE.yaml `last_verified > 90 days ago` is a soft trigger.

### Workflow

1. Spawn a discovery agent per §A, but specify:
   - Cross-reference the existing synopsis + detail survey
   - Output a *delta* in the wave file (what changed, primary sources)
   - Refresh the synopsis §5 (Connector strategy) and §8 (Change Log) to reflect current state
2. Add a row to `BACKLOG.md` reconciliation log if material change found.
3. Update STATE.yaml `last_verified` to today.

### Pitfalls

- Don't blow away the old detail survey — preserve as historical record under `connectors/`. The synopsis is the current-state truth; the survey is the snapshot.

---

## §D What's in scope for research agents vs. what isn't

Research agents are **markdown-only**. They do not:

- Modify `coverage/sources.yaml` (manifest changes happen at connector ship, by the coding agent or human integrator)
- Modify `src/` (production code)
- Modify `tests/` (test code)
- Run `scripts/verify_connector.py` (build gate, not research gate)
- Commit to git (orchestrator + human handle integration)

Research agents DO:

- Write to `research/waves/`, `research/multilateral/`, `research/regional/`, `research/national/`, `research/specs/`
- WebFetch, WebSearch
- Cite primary sources only

The clean separation matters: research mistakes are reversible (revert markdown); code mistakes touch users.

---

## §E Batch protocol

The orchestrator typically runs 4-5 research agents in parallel per batch. Workflow:

1. Read STATE.yaml. Filter for `next_action: synopsis_discovery`. Sort by tier/priority from BACKLOG.md.
2. Pick N (4-5).
3. Spawn N background agents using the template above. Pass each agent a self-contained prompt (no shared context).
4. **Do not poll.** Background agents notify on completion.
5. On each completion: integrate STATE.yaml update + synopsis §4 link (for §B).
6. Once all N complete: report to user, list `verdict` per entity, ask greenlight for next batch.

See PIPELINE.md §4 for the canonical batch protocol.
