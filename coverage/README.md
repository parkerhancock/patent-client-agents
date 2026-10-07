# Coverage manifest

Generated compatibility artifacts describing what data sources
`patent-client-agents` covers and how fresh each one is. Canonical human-edited
records live under [`../catalog/sources/`](../catalog/sources/). See
[`../CONNECTOR_STANDARDS.md`](../CONNECTOR_STANDARDS.md) for the contract
every entry must satisfy.

## Files

- **`sources.yaml`** — generated closed-vocabulary compatibility manifest. One
  entry per catalog record carrying a `coverage` block. The catalog builder
  writes it, and `../scripts/build_coverage.py` enforces every projected field.
- **`coverage.json`** — build artifact. Per-data-product view of
  granular sources. Consumed by
  `patentclient-web/assets/coverage.js` for the existing map + matrix.
- **`atlas.json`** — build artifact. Per-office view of strategic
  entities, fused from generated `coverage/sources.yaml` *and*
  `../research/STATE.yaml`. Each entity carries verdict + verdict_basis,
  synopsis_url (deep-link into `docs.patentclient.com/patent-client-index/`),
  connector_status, and any shipped `sources.yaml` rows nested under
  `shipped_sources`. The compatibility field `unattached_sources` contains
  intentionally standalone products, such as court repositories and
  cross-office services. Every standalone row declares an
  `atlas_standalone_reason`; an unexplained row fails the build. Consumed by
  `patentclient-web/assets/atlas.js`.

See [`../ATLAS_INTEGRATION.md`](../ATLAS_INTEGRATION.md) for the
office-centric data model and cross-consumer plan.

## Workflow

```bash
# After editing a canonical catalog record:
uv run python scripts/build_source_catalog.py

# After regenerating sources.yaml or editing research/STATE.yaml:
uv run python scripts/build_coverage.py --check   # validate, don't write
uv run python scripts/build_coverage.py           # writes coverage.json + atlas.json
```

CI first checks that catalog outputs are current, then validates the projected
manifest. A non-zero exit fails the build.

The README hero image (`docs/_static/atlas_hero.png`) is also generated
from the `patentclient-web` shared atlas renderer. From the monorepo,
regenerate or check it with:

```bash
uv run --project tools/patent-client-agents --extra tmsearch \
  python tools/patentclient-web/scripts/render_atlas_hero.py \
  --atlas-json tools/patent-client-agents/coverage/atlas.json \
  --output tools/patent-client-agents/docs/_static/atlas_hero.png \
  --check
```

Do not make `patent-client-agents` CI check out `patentclient-web`
unless the workflow has an explicit cross-repo token; GitHub's default
`GITHUB_TOKEN` cannot read private sibling repositories.

## Schema summary

| Field | Required when | Vocabulary |
|---|---|---|
| `id` | always | `^[A-Z]{2,3}(/[A-Za-z0-9_]+)+$` |
| `name` | always | free text |
| `jurisdiction` | always | ISO 3166 alpha-2, or `UPC`, or `UP` |
| `wipo_st3_code` | optional | WIPO ST.3 code |
| `issuing_body` | always | free text |
| `rights` | always | ⊆ `{patent, trademark, design, copyright, plant_variety, gi, trade_secret}` |
| `data_types` | always | ⊆ `{bibliographic, full_text, prosecution, legal_status, assignments, oppositions, tribunal_proceedings, litigation, classification, guidelines, case_law, statutes, treaties, bulk_data, fees}` |
| `access.method` | always | `{rest_api, bulk_download, website_scrape, pdf_download, ftp, mcp_passthrough}` |
| `access.auth` | always | `{none, api_key, oauth2_client_credentials, oauth2_password, cookie_token, account_required}` |
| `access.auth_env` | when auth ≠ none | list of env var names |
| `status` | always | `{active, beta, planned, candidate, blocked, external, deprecated}` |
| `notes` | when status ∈ {blocked, deprecated, candidate, external} | free text |
| `connector.module` | when status ∈ {active, beta} | importable Python module path |
| `last_verified` | when status ∈ {active, beta} | YAML date, max 365d old |
| `category` | when status ∈ {active, beta} | `{registered_ip, adjudicative_records, substantive_law, fees}` |
| `transport` | when status ∈ {active, beta} | `{mcp_proxy, mcp_local}` |
| `update_strategy` | when category=substantive_law | `{live_proxy, scheduled_recrawl, vendor_changefeed, manual}` |
| `update_cadence` | when category=substantive_law | `{weekly, monthly, quarterly, semiannual, annual, irregular}` |
| `last_synced` | when category=substantive_law + transport=mcp_local | YAML date |
| `corpus_version` | when category=substantive_law + transport=mcp_local | free text |
| `atlas_standalone_reason` | when a source intentionally has no `research/STATE.yaml` entity | `{adjudicative_body, cross_office_service, independent_legal_authority, out_of_scope}` |

## Validator checks beyond shape

1. Every active/beta entry has `category`.
2. Every active/beta entry has `transport`.
3. `transport=mcp_local` + `category=substantive_law` connectors must
   expose a module-level `get_corpus_status()` callable. This is a hard
   CI error.
4. `category=substantive_law` requires `update_strategy` + `update_cadence`.
5. For `update_strategy ∈ {scheduled_recrawl, vendor_changefeed}` with a
   non-`irregular` cadence, `last_synced` must be ≤ `2 × cadence` days old.
   Beyond that, CI fails until the recrawl runs.
6. `update_strategy: manual` emits a CI warning every run — meant to be
   transient. Resolve by promoting to one of the three other strategies.

## Top-30 coverage tracking

`scripts/build_coverage.py` computes a `top30_filing_volume` rollup
keyed off the 2023 WIPO IP Statistics Data Center filing volumes:

```
CN US JP KR DE IN BR CA AU MX
RU GB FR IT ES SE NL CH BE PL
DK TW SG HK TH MY PH VN ID KH
```

A jurisdiction is "tracked" when it appears in **any** status
(active, beta, candidate, blocked, external). The "missing" list is the
ground-truth gap.
