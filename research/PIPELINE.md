# Coverage Pipeline — orchestration entrypoint

**Purpose:** turn the research → decide → build cycle into something an
agent can run autonomously (in user-gated batches) until we reach global
coverage of registered-IP offices and substantive-law sources.

**You are reading this because:** a fresh session said "continue the
pipeline" or equivalent. This doc tells you the workflow, where state
lives, and which runbook to use for which work.

---

## §1 Mental model

```
┌─────────────────────────────────────────────────────────────────────┐
│ For each entity in the IP-system catalog (~43 entities total):     │
│                                                                     │
│   1. Synopsis exists?           NO  → spawn research-discovery agent│
│   2. Fee research filled?       NO  → spawn fee-research agent      │
│   3. Verdict decided?           NO  → human decision needed         │
│   4. Verdict = build?           YES → write spec → spawn build agent│
│                                 NO  → mark closed, no further work  │
│   5. Connector spec written?    NO  → spawn spec-author agent       │
│   6. Connector shipped?         NO  → spawn build agent in worktree │
│   7. Verify_connector PASS?     NO  → fix; coding agent iterates    │
│   8. Manifest entry added?      NO  → finalize PR-ready branch      │
│                                                                     │
│ Pipeline ticks each entity through these states until terminal:    │
│   - SHIPPED (active connector in manifest), or                     │
│   - CLOSED (verdict = red, no connector to be built)               │
└─────────────────────────────────────────────────────────────────────┘
```

State lives in **[`STATE.yaml`](STATE.yaml)** — one row per entity,
fields track each gate above. Agents read it to pick next work; agents
update it on completion.

## §2 What to read first (new-session bootstrap)

In order:

1. **This file (`PIPELINE.md`)** — the workflow
2. **[`STATE.yaml`](STATE.yaml)** — current state of all entities
3. **[`COVERAGE_STRATEGY.md`](COVERAGE_STRATEGY.md)** — strategic frame; layered system, substitution rules, decision heuristics
4. **[`BACKLOG.md`](BACKLOG.md)** — ranked priorities + reconciliation log
5. **The runbook for the work type you're about to spawn:**
   - [`RUNBOOK-research.md`](RUNBOOK-research.md) — for synopsis discovery, fee research, drift reconciliation
   - [`RUNBOOK-connector-build.md`](RUNBOOK-connector-build.md) — for connector implementation in a worktree
6. **The relevant template:**
   - [`templates/office-synopsis.md`](templates/office-synopsis.md) — synopsis structure
   - [`specs/`](specs/) — per-connector specs (sibling READMEs)

## §3 Pipeline step types

### Step type A — Discovery research

**Input:** entity row in STATE.yaml with `synopsis: null` or `synopsis_status: stale`.

**Goal:** produce a wave research file under `waves/<date>-<subject>/<office>.md` AND a synopsis file under `multilateral|regional|national/<id>.md`.

**Tool:** subagent following [`RUNBOOK-research.md`](RUNBOOK-research.md) §A.

**On completion:** agent updates STATE.yaml row — sets `synopsis: <path>`, `synopsis_status: filled`, `last_verified: <date>`, sets `rating: <green|yellow_byok|...|watch>`, sets `next_action: <spec_writing|none>`.

> **Note:** We deliberately do **not** do fee-schedule research. Synopses
> describe what fee categories exist and link to the office's official
> schedule. Reproducing fee figures is not our job — see the §4 policy
> in [`templates/office-synopsis.md`](templates/office-synopsis.md).

### Step type C — Spec authoring (manual or agent)

**Input:** entity row with `verdict ∈ {green, yellow_byok}` AND `connector_status: planned` AND `connector_spec: null`.

**Goal:** produce `specs/<id>-connector-spec.md` per the canonical structure in [`specs/README.md`](specs/README.md).

**Tool:** specs are short (~50-100 lines); usually faster to write manually, but a subagent can also produce a draft.

**On completion:** STATE.yaml row → `connector_spec: <path>`, `connector_status: spec_ready`.

### Step type D — Connector build

**Input:** entity row with `connector_status: spec_ready`.

**Goal:** implement the connector per spec in a worktree, run verify_connector.py to PASS, push a PR-ready branch.

**Tool:** subagent in worktree following [`RUNBOOK-connector-build.md`](RUNBOOK-connector-build.md).

**On completion:** agent commits + pushes branch; reports branch name + verify_connector verdict. STATE.yaml row → `connector_status: in_progress` (pending human integration into main).

**Critical:** coding agents modify production code. Always run in a worktree (`isolation: "worktree"` on the Agent tool). Never let multiple coding agents edit the same files concurrently.

### Step type E — Human integration

Coding-agent output is a PR-ready branch. Human reviews, merges, updates STATE.yaml to `connector_status: shipped`. Pipeline ticks.

## §4 Running a batch

A "batch" is N parallel agents of the same type. Recommended batch sizes (lessons from prior fan-out waves):

| Step type | Recommended batch | Notes |
|---|---|---|
| A (discovery research) | 4-5 | Independent; web-fetch agents tolerate concurrency |
| C (spec writing) | Usually 1-3 | Often faster manual |
| D (connector build) | 2-3 | Each in own worktree; verify_connector serialized |

**Batch protocol:**

1. Read STATE.yaml. Find entities matching the next-action filter (e.g., `next_action: synopsis_discovery`).
2. Pick N (usually 4-5 for research; 2-3 for build).
3. Spawn N parallel subagents using the matching runbook's prompt template (fill in entity-specific fields).
4. **Wait for completion** — the Agent tool notifies on background completion; **do not poll**.
5. As each completes, integrate its STATE.yaml update.
6. Report batch results to user; **wait for greenlight** before spawning next batch.

User-gated by design (CONTROL > RAW VELOCITY). The user's choice in
2026-05-16 was **batched, not fully autonomous** — see decision log
below.

## §5 The "next unblocked thing" query

To find the next batch of work, scan STATE.yaml for rows where:

```yaml
# Discovery batch candidates
status_filter:
  synopsis: null
  blocked_by: []
  # rank by tier/priority from BACKLOG.md
  
# Spec writing batch candidates
status_filter:
  rating: green | yellow_byok
  connector_status: planned
  connector_spec: null
  blocked_by: []
  
# Build batch candidates
status_filter:
  connector_status: spec_ready
  blocked_by: []
```

Run `uv run python scripts/next_actions.py` to list unblocked active rows.
Use `--action`, `--status`, or `--rating` to select a batch. CI runs
`--check-stats` to keep the summary synchronized with entity rows.

## §6 What to tell the user at each step

After running a batch:

> "Ran [batch type] batch of N agents:
> - ✅ [Entity 1] — [one-line result, e.g., synopsis filled, verdict green]
> - ✅ [Entity 2] — [one-line result]
> - 🟡 [Entity 3] — [one-line, e.g., verdict yellow, requires BYOK design]
> - 🔴 [Entity 4] — [one-line, e.g., no API; closed]
>
> STATE.yaml updated. Next unblocked batch ready: [batch type] for N entities. Greenlight to proceed?"

## §7 What NOT to do

- **Don't relaunch failed agents from the last batch in the next batch** — diagnose first. The 2026-05-16 fan-out wave taught us this; failed agents hit the same watchdog wall on retry.
- **Don't run coding agents outside worktrees** — production code, conflicts.
- **Don't write a synopsis without primary-source citations** — the whole research pipeline depends on grounded research, not memory.
- **Don't add or change canonical `catalog/sources/` records from a research-only agent** — catalog changes happen at integration, not in research. `coverage/sources.yaml` is generated from those records.
- **Don't skip verify_connector** — it's the merge gate, not a suggestion.

## §8 Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-16 | Use STATE.yaml as central machine-parseable state | User chose Recommended; matches existing coverage/sources.yaml format |
| 2026-05-16 | Batched autonomy with user-gating between batches | User chose Recommended; safe for coding agents that touch production code |
| 2026-05-16 | Per-connector specs at `specs/<id>-connector-spec.md` | User chose Recommended; bridges synopsis → coding agent input |
| 2026-05-16 | Coding agents run in worktrees | Matches existing `.claude/worktrees/` pattern from May 2026-05-16 fan-out |

## §9 What's missing — future improvements

- `scripts/update-state.py` — script that takes a research-agent output file + updates the STATE.yaml row programmatically
- Automated quarterly recheck cron — re-run discovery agents on entities with `last_verified > 90 days ago`
- A status dashboard — render STATE.yaml as a coverage matrix HTML page

For now, state updates remain manual. The next-actions script selects and validates batches.
