# Runbook — connector build agents

How an orchestrator agent spawns a coding subagent to build a new
connector per spec. **Higher consequence than research agents** — touches
production code, so always run in a worktree and always gate on
`verify_connector.py`.

---

## §1 Pre-conditions

Before spawning a build agent, STATE.yaml row must show:

- `synopsis: <non-null>` — strategic context exists
- `verdict: green | yellow_byok | yellow_paid` — the office is buildable
- `connector_spec: <non-null>` — concrete deliverable spec exists at `specs/<entity-slug>-connector-spec.md`
- `connector_status: spec_ready`
- `blocked_by: []`

If any of these is missing, do not spawn — first close the gap with the
appropriate research/spec-writing pass.

---

## §2 Input the orchestrator needs

| Field | Source | Example |
|---|---|---|
| `entity_id` | STATE.yaml `.id` | `KR/KIPO` |
| `entity_name` | STATE.yaml `.name` | `KIPO Korea` |
| `synopsis_path` | STATE.yaml `.synopsis` | `national/kr-kipo.md` |
| `spec_path` | STATE.yaml `.connector_spec` | `specs/kr-kipo-connector-spec.md` |
| `verdict` | STATE.yaml `.verdict` | `yellow_byok` |
| `package_name` | from spec | `patent_client_agents.kipo_kipris` |
| `canonical_template` | choose closest existing | `patent_client_agents.jpo` (for username+password BYOK) or `patent_client_agents.ip_australia_patents` (for OAuth2 BYOK) |
| `manifest_ids` | from spec | `[KR/KIPO/Patents, KR/KIPO/Trademarks, KR/KIPO/Designs]` |
| `display_name` | for verify_connector --jurisdiction | `KIPO Korea` |

---

## §3 Prompt template

Pass to Agent with `isolation: "worktree"` (mandatory) and `subagent_type: general-purpose`.

```
You are implementing a new connector for {{ entity_name }} ({{ entity_id }}) per the spec at {{ spec_path }}.

**Inputs to read first, in this order:**
1. `{{ spec_path }}` — the concrete deliverable spec (env vars, tool names, response shapes, test fixtures)
2. `{{ synopsis_path }}` — strategic context (what's unique, what we should NOT add, primary-source URLs)
3. `CONNECTOR_STANDARDS.md` — the contract every connector must satisfy (§5 tool design rules, §6 manifest entry, §7 connector shapes)
4. The canonical template connector: `src/patent_client_agents/{{ canonical_template_package }}/` — copy this and adapt

**Your deliverables:**

1. **Source package** at `src/patent_client_agents/{{ package_name_last_segment }}/` with:
   - `__init__.py` — public API exports
   - `api.py` — async one-shot helpers
   - `client.py` — context-managed client
   - `models.py` — Pydantic v2 response models
   - `corpus/` (for static-law connectors) OR live API modules (for register connectors)
   - `resources.py` — usage cheat-sheet text + USAGE_RESOURCE_URI
   - `py.typed`
   - For BYOK: env-gated tool registration (check env var presence in `mcp/__init__.py`)

2. **MCP tool module** at `src/patent_client_agents/mcp/tools/{{ package_name_last_segment }}.py`:
   - Envelope-shaped per §5.9 (ListEnvelope / ResponseEnvelope)
   - Lean default + `full=True` opt-in per §5.5
   - List-accepting `get_*` tools per §5.4
   - "Related tools:" cross-references in docstrings per §5.6
   - Jurisdiction-prefixed verb naming per §5.7/§5.8

3. **Tests** at `tests/{{ package_name_last_segment }}/` mirroring an existing connector's test layout:
   - `conftest.py`
   - `test_api.py`, `test_build.py` (if static), `test_client.py`, `test_corpus_status.py` (if static), `test_mcp_envelope.py`
   - Target ≥80% per-file coverage; verify_connector enforces

4. **Manifest entries** in `coverage/sources.yaml`:
   - One row per right covered, IDs per §6 closed vocabulary: `{{ manifest_ids }}`

5. **Doc updates** (verify_connector requires):
   - `CHANGELOG.md` `[Unreleased]` section mentioning the package
   - `README.md` Coverage table row
   - `CLAUDE.md` architecture diagram entry

**The build gate:**

After writing all of the above, run from the repo root:

  uv run python scripts/verify_connector.py --jurisdiction "{{ display_name }}" {{ package_name_last_segment }}

This runs 5 checks: ruff check, ruff format --check, ty check, pytest --cov ≥80% per file, doc updates. **All five must PASS.** If any fail, iterate until they pass — do not claim done with failing checks.

**Workflow:**

1. Set up the worktree (you're already in it via isolation: worktree).
2. Read inputs (1-5 above) and the spec carefully.
3. Copy the canonical template package as a starting point. Run search-replace on the package name.
4. Adapt to {{ entity_name }}'s actual API surface per the spec.
5. Write the tests next (force yourself to understand the API by writing test cases).
6. Run `uv run pytest tests/{{ package_name_last_segment }}/ -q -p no:beartype` until green.
7. Run the verifier. Fix until VERDICT: PASS.
8. Commit on a branch named `feature/{{ branch_slug }}`.
9. **Do not push without explicit permission** — the human integrates branches.

**Pitfalls to avoid (lessons from prior fan-out waves):**

- **Watchdog stalls at 600s.** Long uv operations, long pytest runs, slow web fetches all risk this. Keep operations short; use the bundled seed pattern (static `data/seed.jsonl`) for static-law connectors.
- **Editable-install drift.** Do not run `uv sync` from inside the worktree — it can point the parent venv at the wrong source tree. Inherit the parent venv.
- **Worktree base inconsistency.** Verify the worktree was created from a recent main (or the current feature branch) before starting. `git log --oneline -3` should show the verify_connector commit (cb44af3 or later).
- **Manifest validation.** `scripts/build_coverage.py` validates `coverage/sources.yaml`. Run it before claiming done if you added manifest rows.
- **Plain `_FakeModel` not `BaseModel(extra="allow")`** in envelope tests — `ty` does not understand Pydantic's dynamic kwargs and emits unknown-argument errors. See `tests/ipo_in_statutes/test_mcp_envelope.py` for the pattern.

**Reporting on completion:**

Return ≤300 words to the orchestrator with:
- VERDICT (PASS/FAIL)
- Coverage % per file
- Branch name + SHA
- Any deviations from spec (with reason)
- Any open items left for human integration

Do NOT modify STATE.yaml — the orchestrator handles that.
```

---

## §4 Output contract

The agent produces:

- A working branch with the new package + tests + manifest entry + doc updates
- `verify_connector.py` VERDICT: PASS on that branch
- Return summary with branch name and SHA

The orchestrator:

1. Verifies the branch + SHA exist.
2. Verifies the agent reports VERDICT: PASS (run the verifier independently if any doubt).
3. Updates STATE.yaml row for `{{ entity_id }}`:
   - `connector_status: in_progress` (waiting for human integration)
   - `manifest_ids: [...]` from the spec
   - `last_verified: <today>`
4. Reports to user: branch name, SHA, verifier result, recommendation to cherry-pick onto an integration branch.

Human handles the merge to main + final STATE.yaml update to `connector_status: shipped`.

---

## §5 Pitfalls — coding agents

In addition to the agent-side pitfalls in §3:

### Don't relaunch failed coding agents identically

If a coding agent fails (watchdog, test failures it can't resolve), do NOT
spawn an identical one. Diagnose:

- Is the spec ambiguous? Tighten the spec first.
- Is the canonical template the wrong shape? Pick a closer existing connector.
- Is the upstream API not what the synopsis said? Re-research first.

The 2026-05-16 fan-out wave's main lesson: failed agents stall on the same wall when retried.

### Don't run multiple coding agents on overlapping files

Each connector lives in its own package, but:
- `CHANGELOG.md` — all agents append to `[Unreleased]`; merge conflicts likely
- `README.md` — same
- `CLAUDE.md` — same
- `coverage/sources.yaml` — same
- `src/patent_client_agents/mcp/__init__.py` — all register tool modules; merge conflicts likely

When fanning out multiple coding agents, accept that these shared files will conflict on integration. Resolution is always "keep both sides" (additive). Use `git rerere` or resolve manually per cherry-pick.

### Don't skip the verifier

`verify_connector.py` is the merge gate, not a suggestion. Five checks:
1. ruff check (lint)
2. ruff format --check
3. ty check (zero diagnostics)
4. pytest --cov ≥80% per file
5. CHANGELOG/README/CLAUDE.md mention

A connector that doesn't pass all five is not shippable.

---

## §6 Batch protocol

The orchestrator runs coding agents in **smaller batches** than research
agents (2-3 max), because:

- Each touches production code
- Shared files (CHANGELOG, manifest, MCP `__init__`) collide
- verify_connector is serialized in CI

Workflow:

1. Read STATE.yaml. Filter for `connector_status: spec_ready` and `blocked_by: []`. Sort by tier/priority.
2. Pick 2-3 entities.
3. For each, set up a worktree from the latest integration branch (e.g., `feature/ip-australia-connector` per the 2026-05-16 wave) and spawn a build agent with the prompt above.
4. **Do not poll.** Background agents notify on completion.
5. On each completion: verify VERDICT: PASS, update STATE.yaml.
6. Once all complete: report to user, list branches + verdicts, ask greenlight for integration.

See PIPELINE.md §4 for the canonical batch protocol.

---

## §7 What's in scope vs. what isn't

Coding agents DO:
- Write to `src/patent_client_agents/<new_package>/`
- Write to `tests/<new_package>/`
- Append manifest rows to `coverage/sources.yaml`
- Append CHANGELOG/README/CLAUDE.md entries
- Run `verify_connector.py`
- Commit on a feature branch

Coding agents do NOT:
- Push branches (human decides)
- Cherry-pick across branches (orchestrator or human decides)
- Modify other connectors' packages
- Modify `CONNECTOR_STANDARDS.md` (architecture changes are human-gated)
- Modify `scripts/verify_connector.py` (the gate itself)
- Modify STATE.yaml (orchestrator's job)

---

## §8 Iteration tips for the build agent

If the verifier fails, the most common fix patterns:

| Failure | Likely fix |
|---|---|
| `ruff check` | Auto-fix with `uv run ruff check --fix`; address remaining diagnostics |
| `ruff format --check` | `uv run ruff format src/.../ tests/.../` |
| `ty check unknown-argument` | Replace `BaseModel(extra="allow")` test fakes with plain `_FakeModel` class |
| `ty check` other | Add type annotations; usually a missing parameter type |
| `pytest --cov < 80%` per-file | Add tests for uncovered branches; check which file is below threshold |
| `pytest failures` | Read test output; usually a Pydantic model field mismatch with API response |
| `CHANGELOG missing` | Append a `[Unreleased]` block with package name |
| `README missing` | Add jurisdiction display name to coverage table |
| `CLAUDE.md missing` | Add package entry to architecture diagram |

Most builds pass within 2-3 iterations once the template adaptation is right.
