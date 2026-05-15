# Connector Standards

How we build connectors for `patent-client-agents`. These are the rules every
new data source must satisfy before it ships, and the contract every existing
connector is being migrated onto.

Audience: IP professionals using Claude / ChatGPT / other agentic clients.
Architecture: MCP-first. We proxy directly from upstream when we can, and fall
back to a locally-bundled corpus when volume is small and refresh cadence is
predictable. Authentication is the connector's problem — end users never see
API keys.

This document is the contract. The [`scripts/build_coverage.py`](scripts/build_coverage.py)
validator enforces the §6 manifest fields against [`coverage/sources.yaml`](coverage/sources.yaml).
The [`research/tool-surface-audit-2026-05-14.md`](research/tool-surface-audit-2026-05-14.md)
audit measures the live tool surface against §5.

---

## §1 Coverage scope

We chase two distinct kinds of source:

**Category 1 — Registered IP** (`category: registered_ip`). The primary
register of a patent, trademark, design, copyright, plant-variety, or GI
right. Examples: USPTO ODP applications, EPO OPS biblio, EUIPO trademarks,
JPO J-PlatPat, USPTO Assignment Center.

The contract for category-1 connectors:
- Every response carries access-time provenance (§3).
- We do not warehouse or stale-cache rights data; we proxy live.
- Cache TTLs are short and conservative (default ~24h, often less); the
  upstream register is always the system of record.

**Category 2 — Substantive law** (`category: substantive_law`). The statutes,
regulations, examination guidelines, and case law from reviewing courts that
control how rights are granted and litigated. Examples: MPEP, EPO Guidelines,
UKIPO MoPP, EPC, CAFC opinions, EPO Boards of Appeal case law, WIPO Lex
legislation.

The contract for category-2 connectors:
- Every response carries recency metadata: when the corpus was last synced
  and what version it represents (§4).
- An explicit update strategy + cadence is declared in the manifest and
  enforced by CI staleness gates.
- Connectors expose a `get_corpus_status()` callable so agents can answer
  "how stale is this?" without guessing.

**Coverage targets.** The top 30 patent offices by 2023 filing volume (WIPO
IP Statistics Data Center) are the priority list:

```
CN US JP KR DE IN BR CA AU MX
RU GB FR IT ES SE NL CH BE PL
DK TW SG HK TH MY PH VN ID KH
```

Out of scope for now: every district court in every jurisdiction, every IP
office's website static content, anything that requires manual scraping per
filing. We cover the offices that issue rights and the reviewing tribunals
that interpret them.

---

## §2 Architecture defaults

**MCP-first.** Every connector exposes its functionality through the
patent-client-agents MCP server. The Python library API is a side-effect of
the MCP tool surface, not the other way around. Tool design (§5) is the
primary user interface.

**Proxy first, bundle as fallback.**
- `transport: mcp_proxy` — connector calls upstream live on every request.
  Used when upstream is available, stable, and rate-friendly. This is the
  default for category-1 sources.
- `transport: mcp_local` — connector serves from a locally-bundled corpus.
  Used when (a) volume is small enough to embed in the wheel or pull at
  install time, (b) upstream has a predictable changelog or sync cadence, or
  (c) upstream blocks egress / has aggressive rate limits. This is the
  default for stable category-2 corpora (MPEP, EPC, EPO Guidelines).

**Auth lives in the connector process.** Every required credential is
sourced from env vars listed in `coverage/sources.yaml access.auth_env`.
End users never paste API keys into the agent. If a source requires
account-level auth (OAuth password grant, cookie tokens), the connector
handles refresh internally.

**HTTP scaffolding is shared.** All clients extend
`law_tools_core.BaseAsyncClient` and inherit `hishel` + SQLite caching with
WAL pragmas via `RetryingAsyncSqliteStorage`, plus `tenacity` retry via
`default_retryer` (4 attempts, exponential jitter). New connectors do not
roll their own HTTP layer.

**Cloud Run egress is the deployment target.** Some upstreams filter Cloud
Run egress harder than residential IPs (USPTO TESS via AWS WAF;
unifiedpatentcourt.org via Cloudflare). New connectors are tested against
the deployment environment, not just localhost.

---

## §3 Provenance for registered IP

Every category-1 response carries the following fields, surfaced through the
response envelope (§5.9):

| Field | Meaning |
|---|---|
| `retrieved_at` | UTC timestamp of the original upstream fetch. When `cache_hit=True`, this is the cached fetch time, not the cache-read time. |
| `source_url` | The canonical upstream URL the data came from. Stable enough that an attorney can click it and verify. |
| `source_name` | Human-readable upstream name, mirroring `coverage/sources.yaml name`. |
| `cache_hit` | `True` if served from cache; `False` if a network round-trip occurred. |
| `connector_version` | The `patent_client_agents` package version. Lets bug reports tie back to a release. |

Rationale: legal practitioners cite to a register at a point in time. The
register can change tomorrow. We make "what was true when I asked" first-class
metadata, not a footnote.

---

## §4 Recency for substantive law

Every category-2 response carries the same `retrieved_at` / `source_url` /
`source_name` / `cache_hit` / `connector_version` fields, plus:

| Field | Meaning |
|---|---|
| `corpus_synced_at` | When the bundled corpus was last refreshed from upstream. |
| `corpus_version` | Vendor-style version string (e.g. MPEP "R-07.2022"). When unknown, the string `"unknown — needs verification"`. |

Every category-2 connector exposes a module-level
`get_corpus_status()` callable that returns these fields without requiring
a live upstream call. CI uses it to detect drift.

**Update strategy** is declared per connector in `coverage/sources.yaml`:

- `live_proxy` — no bundled corpus; freshness is whatever the upstream
  serves on demand.
- `scheduled_recrawl` — connector author re-runs a recrawl script on a
  fixed cadence and republishes the wheel.
- `vendor_changefeed` — upstream publishes a changelog / release tag we
  subscribe to.
- `manual` — interim only. Flagged as a CI warning every run; resolve by
  promoting to one of the three other strategies.

**Update cadence** is also declared: `weekly`, `monthly`, `quarterly`,
`semiannual`, `annual`, `irregular`. The validator gates `last_synced` at
`2 × cadence` in days for `scheduled_recrawl` / `vendor_changefeed`
strategies — beyond that, CI fails until the recrawl runs. `irregular`
skips the gate.

---

## §5 MCP tool design

The rules that keep the catalog navigable as it grows past 100 tools.

### §5.1 Catalog discipline

**One canonical tool set per data type.** Never two tools that an agent
might pick between for the same record. If two upstreams both expose the
same record (e.g., US patent text from PPUBS and Google Patents), the
connector picks one as primary, cascades internally, and exposes one tool.

The smell to watch for: docstrings that triage between sibling tools.
"Prefer X for case A; use Y for case B" inside descriptions means an agent
needs a decision tree before it can pick a tool. Collapse instead.

Soft cap: a single data type should rarely need more than ~5 tools
(search + get + 1-3 facet fetches + a download). If you're past that,
the data type is probably two data types fused together.

### §5.2 Search + fetch baseline

The default pattern for every record-bearing source is one `search_*` tool
and one `get_*` tool.

- `search_*` returns hits with stable identifiers.
- `get_*` takes those identifiers and returns the full record.

Facet fetches (e.g., `get_patent_claims`, `get_patent_figures`) are
allowed when the facet is independently useful and the full-record fetch
would be wastefully large. Facet fetches are not required to have a
matching `search_*`.

Orphan search tools (no matching `get_*`) are a smell — usually it means
we're displaying hits an agent cannot then act on. Resolve before merging.

### §5.3 Identifier handling

We never ship a `get_by_application` / `get_by_publication` /
`get_by_patent_no` family for the same record type. There is one
`get_thing` tool that accepts multiple identifier formats and dispatches
internally.

- The argument is named after the thing being fetched (`application_number`,
  `serial_number`), not `identifier` and never `id`.
- The docstring lists every accepted format with an example.
- If two identifiers point to different facets, an `identifier_type`
  discriminator is acceptable but discouraged — prefer auto-detection.

### §5.4 List-accepting fetches, no batch tools

**No `batch_*` tools.** Ever. When portfolio work is common, the `get_*`
tool accepts `identifier: str | list[str]` and returns a `ListEnvelope`
even when the caller passes a single string. This keeps the catalog at
one tool per data type and the response shape stable.

The list-accepting form fans out internally with bounded concurrency;
agents do not orchestrate the fan-out.

### §5.5 Lean-by-default payloads

`search_*` tools return a lean per-row view by default — enough for an
agent to triage hits without bloating the context window. A `full=True`
parameter opts into the upstream-shaped row.

The lean view typically includes: stable identifier, headline name/title,
status, primary date, top-level classification. The opt-in `full=True`
view includes everything the upstream returns.

Rule of thumb: a 50-hit lean page should fit comfortably under ~10k tokens.
If your lean rows are larger than that, they aren't lean.

### §5.6 Cross-references in tool descriptions

Every tool in a related set names its siblings in its docstring. Search
tools name the matching fetch. Fetch tools name the matching search.
Facet fetches name the parent fetch. Corpus pairs (e.g., MPEP search +
section get) name each other.

The goal: an agent reading any single tool's description can navigate to
the workflow partner without re-querying `tools/list`.

Format: a short "Related tools:" line at the end of the docstring listing
the tool names. No further prose — the agent looks them up.

### §5.7 Jurisdiction prefix convention

US tools are unprefixed (US is the default jurisdiction in this catalog).
Every other jurisdiction is prefixed with the office abbreviation:

- `search_applications` (US, unprefixed)
- `search_epo`, `get_epo_biblio` (EPO)
- `search_jpo_*`, `get_jpo_*` (JPO)
- `search_euipo_*`, `get_euipo_*` (EUIPO)
- `search_canlii_*` (Canada)
- `search_ukipo_*` (UKIPO)

Worldwide / multi-jurisdiction tools (e.g., Google Patents) name the
*scope*, not the source: `search_patents_global` over `search_google_patents`.

### §5.8 Naming (verbs and parameters)

Verb table (preferred):

| Verb | Meaning |
|---|---|
| `search_*` | Query a record set, return hits. |
| `get_*` | Fetch a single record (or list per §5.4) by identifier. |
| `list_*` | Enumerate children of a known parent (e.g., `list_file_history` for an application). |
| `download_*` | Pull a binary asset (PDF, document) to disk. Returns a `download_url` + MCP `pca://` resource URI. |
| `lookup_*` | Vocabulary lookup against a closed taxonomy (e.g., `lookup_cpc`). |
| `resolve_*` | Format conversion / canonical-id resolution. |
| `convert_*` | Number format conversion (e.g., `convert_epo_number`). |
| `map_*` | Cross-reference one identifier to another (e.g., `map_cpc_classification`). |

Avoid: `browse_*`, `fetch_*`, `query_*`, `find_*`, `retrieve_*` — pick
from the table.

Parameter names are practitioner-facing: `application_number`,
`serial_number`, `registration_number`, `publication_number`,
`docket_number`. Never bare `id`.

### §5.9 Output shape (response envelope)

**Every tool returns a `ResponseEnvelope` or `ListEnvelope`.** Implemented
in `law_tools_core.envelope`. No tool returns a raw upstream payload.

```python
class Provenance(BaseModel):
    retrieved_at: datetime           # UTC; cache_hit=True → original fetch time
    source_url: str                  # canonical upstream URL
    source_name: str                 # mirrors coverage/sources.yaml `name`
    cache_hit: bool = False
    connector_version: str

class ResponseEnvelope(BaseModel, Generic[T]):
    summary: str                     # short Markdown, ≤5 lines
    details: T
    provenance: Provenance

class ListEnvelope(BaseModel, Generic[T]):
    summary: str
    items: list[T]
    next_cursor: str | None = None   # opaque base64(JSON)
    more_available: bool = False
    provenance: Provenance
```

The three design calls:
1. A `get_*` tool that accepts a list always returns `ListEnvelope`, even
   when called with a single identifier. Response shape is stable.
2. `next_cursor` is opaque base64(JSON). Connectors decide the payload;
   agents treat it as bytes and pass it back unchanged.
3. `Provenance` is a separate model on every envelope (not flattened).
   We can evolve provenance fields without changing the envelope contract.

The `summary` field is short Markdown (≤5 lines) that an agent can quote
directly without re-summarizing the JSON. For lists, `summary` describes
the result set ("4 active applications filed 2020-2022"); for single
records, it describes the record ("US patent 11,234,567 — issued
2023-04-11, expires 2041-08-17").

For category-2 responses, `Provenance` additionally carries
`corpus_synced_at` and `corpus_version` (§4).

**Template: USPTO Applications** — the migrated `search_applications`,
`get_application`, and `list_file_history` tools in
[`src/patent_client_agents/mcp/tools/uspto.py`](src/patent_client_agents/mcp/tools/uspto.py)
are the reference for new connectors. They show the canonical pattern
for envelope construction, source-specific provenance helpers
(`_odp_provenance`), Markdown summary builders (`_summarize_application`),
and §5.4 list-accepting `get_*` with bounded-concurrency fan-out. Shape
expectations are pinned by
[`tests/uspto_odp/test_mcp_envelope.py`](tests/uspto_odp/test_mcp_envelope.py).

### §5.10 Token discipline

Tool docstrings are the most-loaded text in the catalog. Keep them tight:
- First sentence: a one-line elevator pitch (§5.13).
- Parameter docs: format examples, not prose.
- Response shape: omit — the envelope (§5.9) is universal.
- Related tools: a single line listing names.

Hard cap: 40 lines of docstring per tool. If you can't fit, the tool is
doing too much.

### §5.11 Read-only

Every tool is annotated `READ_ONLY` via MCP tool annotations. No tool in
this catalog mutates upstream state. If we ever need to (e.g., file an
e-payment for a USPTO petition), it lives in a separate write-tier package
behind explicit user consent flows.

### §5.12 Error semantics

Connector errors raise `ApiError` (or a subclass) from `law_tools_core.exceptions`.
`ApiError.__str__()` appends the log file path so agents can inspect details
without keeping full stacktraces in context. File logging is configured per
consumer app via `law_tools_core.logging.configure(app_name)`.

Validation / config errors that aren't upstream failures raise plain
`Exception` subclasses. The MCP layer surfaces both kinds as MCP error
responses; agents see a structured `code` + `message`, not a Python
traceback.

### §5.13 Elevator test

**A non-IP attorney reading `tool_name` + the first sentence of the
docstring can guess what the tool does.** If they can't, rename or rewrite.

Acronyms (PTAB, J-PlatPat, DataWeb, MoPP) are expanded on first use in the
first sentence. Jargon ("package," "biblio") is replaced or defined.

---

## §6 Manifest contract

Every connector has an entry in `coverage/sources.yaml`. The
[`scripts/build_coverage.py`](scripts/build_coverage.py) validator enforces
the closed vocabularies below; CI fails on any deviation.

| Field | Required | Vocabulary |
|---|---|---|
| `id` | always | `^[A-Z]{2,3}(/[A-Za-z0-9_]+)+$` (e.g., `US/USPTO/ODP/Applications`) |
| `name` | always | free text |
| `jurisdiction` | always | ISO 3166 alpha-2 or one of `UPC`, `UP` |
| `wipo_st3_code` | optional | WIPO ST.3 code |
| `issuing_body` | always | free text |
| `rights` | always | subset of `{patent, trademark, design, copyright, plant_variety, gi}` |
| `data_types` | always | subset of `{bibliographic, full_text, prosecution, legal_status, assignments, oppositions, tribunal_proceedings, litigation, classification, guidelines, case_law, statutes, treaties, bulk_data}` |
| `access.method` | always | `{rest_api, bulk_download, website_scrape, pdf_download, ftp, mcp_passthrough}` |
| `access.auth` | always | `{none, api_key, oauth2_client_credentials, oauth2_password, cookie_token, account_required}` |
| `access.auth_env` | when auth ≠ none | list of env var names |
| `status` | always | `{active, beta, planned, candidate, blocked, external, deprecated}` |
| `notes` | required for status ∈ {blocked, deprecated, candidate, external} | free text |
| `connector.module` | required for status ∈ {active, beta} | Python module path; must exist on disk |
| `last_verified` | required for status ∈ {active, beta} | YAML date; max 365d old |
| `category` | required for status ∈ {active, beta} | `{registered_ip, substantive_law}` |
| `transport` | required for status ∈ {active, beta} | `{mcp_proxy, mcp_local}` |
| `update_strategy` | required for category=substantive_law | `{live_proxy, scheduled_recrawl, vendor_changefeed, manual}` |
| `update_cadence` | required for category=substantive_law | `{weekly, monthly, quarterly, semiannual, annual, irregular}` |
| `last_synced` | required for category=substantive_law + transport=mcp_local | YAML date |
| `corpus_version` | required for category=substantive_law + transport=mcp_local | free text |

Validator checks beyond shape:

1. Every active/beta entry has `category`.
2. Every active/beta entry has `transport`.
3. `transport=mcp_local` + `category=substantive_law` connectors should
   expose a `get_corpus_status()` callable (currently a CI warning, hard
   error in a follow-up PR).
4. `category=substantive_law` requires `update_strategy` + `update_cadence`.
5. For `update_strategy ∈ {scheduled_recrawl, vendor_changefeed}` with a
   non-irregular cadence, `last_synced` must be ≤ `2 × cadence` days old.
6. `update_strategy: manual` emits a CI warning every run.

**Classification rules for ambiguous sources:**

- **CPC** — `registered_ip`. CPC is a classification system used to index
  the patent register; it sits on the registered-IP side even though it's
  also referenced in substantive examination work.
- **USITC investigations** — `registered_ip`. By analogy to PTAB: a
  tribunal proceeding adjudicating registered patents is part of the
  registered-IP lifecycle, not substantive law.
- **EPO Case Law** — `substantive_law`, cadence `annual`. The bundled
  artifact is the Boards of Appeal compendium republished annually; even
  though individual decisions issue continuously upstream, the cadence
  follows the bundled-artifact rhythm.

---

## §7 New-connector checklist

Before merging a new connector:

- [ ] Entry added to `coverage/sources.yaml` with every §6 required field.
- [ ] `uv run python scripts/build_coverage.py --check` passes with no
      errors and no unexpected warnings.
- [ ] Client extends `law_tools_core.BaseAsyncClient`. No bespoke HTTP layer.
- [ ] Auth credentials sourced from env vars listed in `access.auth_env`.
- [ ] Every MCP tool returns a `ResponseEnvelope` or `ListEnvelope` (§5.9).
- [ ] Every MCP tool passes the elevator test (§5.13).
- [ ] Tool docstrings cross-reference siblings (§5.6).
- [ ] Search tools have a lean default + `full=True` opt-in (§5.5).
- [ ] `get_*` tools accept `list[str]` for portfolio workflows (§5.4).
- [ ] No `batch_*` tools.
- [ ] No `get_by_*` family — single `get_thing` with auto-detected identifier.
- [ ] For category-2 connectors: module-level `get_corpus_status()` callable.
- [ ] VCR cassettes recorded and auth headers scrubbed; `gitleaks protect --staged` clean.
- [ ] `CHANGELOG.md` entry under the next-release header.

---

## §8 Open questions

- **`get_corpus_status()` rollout.** All `mcp_local` connectors today carry
  `corpus_version: "unknown — needs verification"`. The callable rollout
  PR will both (a) implement `get_corpus_status()` per connector and
  (b) flip the validator check from warning to hard error.
- **Provenance for cascaded sources.** When `get_patent` cascades
  PPUBS → Google Patents, which `source_url` wins? Current plan: the
  upstream that actually served the response, with a `fallback_attempted`
  flag in `details`.
- **Cursor envelope schema.** Opaque base64(JSON), but we should pick a
  per-connector schema convention to keep cursor decode logic predictable.
- **Write-tier package.** Not in scope today, but the §5.11 read-only
  constraint reserves the namespace.
