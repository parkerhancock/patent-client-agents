# Connector specs

Per-connector specs that bridge **synopsis** (strategic) → **coding agent input** (concrete deliverables).

## When to write a spec

When STATE.yaml row crosses from `connector_status: planned` toward
`spec_ready`. Trigger conditions:

- `verdict ∈ {green, yellow_byok, yellow_paid}`
- `synopsis: <non-null>` (strategic context exists)
- `connector_status: planned`
- `next_action: spec_writing`

When the spec is written, set:

- `connector_spec: specs/<id>-connector-spec.md`
- `connector_status: spec_ready`
- `next_action: connector_build`

## File naming

`specs/<iso2-or-region>-<office-slug>-connector-spec.md`

Examples:
- `specs/kr-kipo-connector-spec.md` — KIPO Korea BYOK connector
- `specs/wo-wipo-lex-synopsis-cleanup-spec.md` — not a register; statute-corpus spec
- `specs/up-epo-unitary-helpers-spec.md` — Unitary Patent helper recipes on existing EPO OPS

## Template

Specs are short — **50-100 lines target**. Just enough that a coding
agent has everything it needs to build without re-interpreting the
synopsis. The synopsis tells you *what's available and why we want it*;
the spec tells you *what to build, exactly*.

```markdown
# Connector spec — {{ office_name }} ({{ entity_id }})

**Source synopsis:** [`../{{ synopsis_path }}`](../{{ synopsis_path }})
**Source fee research:** [`../fee-schedules/{{ fee_path }}`](../fee-schedules/{{ fee_path }}) (if exists)
**Authoring date:** YYYY-MM-DD
**Verdict basis:** copy from STATE.yaml `.verdict_basis`

## §1 Package layout

**Package name:** `patent_client_agents.{{ package_slug }}`

**Directory:** `src/patent_client_agents/{{ package_slug }}/`

**Canonical template to copy:** `src/patent_client_agents/{{ template_slug }}/`
*(pick the closest existing connector — JPO for username+password BYOK; IP Australia for OAuth2 BYOK; IPO India statutes for static-law corpus; etc.)*

**Modules:**
- `__init__.py` — public exports
- `api.py` — async one-shot helpers
- `client.py` — context-managed client
- `models.py` — Pydantic v2 response models
- `resources.py` — USAGE_RESOURCE_URI + get_usage_resource()
- (optional) `corpus/` for static-law connectors

## §2 Auth model

**Env vars:** `{{ ENV_VAR_NAMES }}`

**Auth shape:** none / api_key / oauth2_client_credentials / username_password / paid_contract

**Tool registration gating:** Tools should only mount when env vars are present (CONNECTOR_STANDARDS §7.x). On the hosted demo without keys, this connector's tools should not appear.

## §3 Tool surface

Tools the agent should expose, with §5.x compliance per CONNECTOR_STANDARDS:

| Tool | Type | Returns | List-accept? | Notes |
|---|---|---|---|---|
| `search_{{ slug }}_patents` | search | ListEnvelope | n/a | query, optional filters |
| `get_{{ slug }}_patent` | fetch | ListEnvelope | yes (§5.4) | accept str or list[str] |
| `search_{{ slug }}_trademarks` | ... | ... | ... | ... |
| ... | ... | ... | ... | ... |

For each tool, specify:
- Input arguments (with types and `Annotated[..., "description"]`)
- Output envelope shape
- Lean vs `full=True` projection per §5.5
- Cross-reference to "Related tools" in docstring per §5.6
- Citation form parsing if applicable (e.g., `parse_citation(text) -> (section, statute)`)

## §4 Manifest entries

Add to `coverage/sources.yaml`:

```yaml
- id: {{ entity_id }}/Patents     # one row per right covered
  name: {{ office_name }} — Patents
  jurisdiction: {{ iso2 }}
  wipo_st3_code: {{ wipo_st3 }}
  issuing_body: {{ official_name }}
  rights: [patent]
  data_types: [bibliographic, full_text, prosecution, legal_status]
  access:
    method: {{ method }}            # rest_api / mcp_passthrough / etc
    auth: {{ auth }}                 # api_key / oauth2_* / none
    auth_env: [{{ ENV_VARS }}]       # if auth != none
  status: active
  connector:
    module: patent_client_agents.{{ package_slug }}
  last_verified: {{ date }}
  category: registered_ip
  transport: mcp_proxy               # or mcp_local for corpus-backed
  update_strategy: live_proxy        # or scheduled_recrawl
```

## §5 Test coverage

**Existing test layout to mirror:** `tests/{{ template_slug }}/`

Tests required:
- `conftest.py` — fixtures (corpus fixture if static; cassette / mock setup if live)
- `test_api.py` — module-level async helpers
- `test_client.py` — client methods, parse_citation, edge cases
- `test_mcp_envelope.py` — envelope shape, ListEnvelope, lean vs full, Provenance fields
- (for corpus-backed) `test_build.py`, `test_corpus_status.py`

**Coverage target:** ≥80% per file. Verifier enforces.

**Cassettes:** for live API connectors, record vcrpy cassettes during local development with `--vcr-record=once`. Strip auth headers (conftest does this automatically — see `tests/conftest.py` REDACT_HEADERS).

## §6 Open issues / spec ambiguity

- Things the synopsis didn't fully resolve. List explicitly so the coding agent doesn't guess.

## §7 References

- Synopsis: [`../{{ synopsis_path }}`](../{{ synopsis_path }})
- Detail survey: [`../connectors/{{ survey_path }}`](../connectors/{{ survey_path }}) (if exists)
- Wave research: [`../waves/{{ wave_path }}`](../waves/{{ wave_path }}) (if exists)
- Fee research: [`../fee-schedules/{{ fee_path }}`](../fee-schedules/{{ fee_path }}) (if exists)
- Canonical template connector: `src/patent_client_agents/{{ template_slug }}/`
- CONNECTOR_STANDARDS.md §x.y
```

## When the spec is the wrong artifact

Some "connectors" are too small for a full spec. Examples:

- **Synopsis-only entities** — offices we've decided to skip. No connector → no spec.
- **Helper recipes on existing connectors** — e.g., `get_unitary_patent_status(ep_number)` is a helper on EPO OPS, not a new connector. Skip the spec; add the recipe directly per MIGRATION_PLAYBOOK row 21.
- **Doc-only updates** — REUD terminology cleanup is a one-line PR, not a spec-grade build.

When the synopsis §5 says "what we should add" and it's ≤1 day work, just do it; spec discipline is for connector-grade builds.

## Index

Specs in this folder (added as they're written):

| Spec | Office | Authoring date | Status |
|---|---|---|---|
| [`tw-tipo-connector-spec.md`](tw-tipo-connector-spec.md) | TIPO Taiwan — OpenData REST (green) | 2026-05-16 | spec_ready |
| [`kr-kipo-connector-spec.md`](kr-kipo-connector-spec.md) | KIPO Korea — KIPRIS Plus (yellow BYOK) | 2026-05-16 | spec_ready |
| [`fr-inpi-connector-spec.md`](fr-inpi-connector-spec.md) | INPI France — TM + Design (yellow BYOK) | 2026-05-16 | spec_ready |
