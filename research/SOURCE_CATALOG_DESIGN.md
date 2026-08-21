# Worldwide source catalog design

**Status:** JP/CN/KR pilot implemented 2026-08-21; expansion and manifest
migration remain TODO

## Purpose

Create one human-readable source of truth for the data sources that could
support patent and IP research in each jurisdiction. The catalog must describe
not only shipped connectors, but also sources that are manual, restricted,
commercial, technically blocked, legally unsuitable for automation, retired,
or merely known to exist.

The pilot schema, validator, canonical records, and generated country and
worldwide views now live under `catalog/`. No current coverage or research
manifest should be treated as migrated until the remaining work below is
complete.

## Decisions

### Markdown is canonical

Each materially distinct upstream source gets one Markdown record. Markdown is
the source of truth because most important facts are explanations: what a
source contains, which proceedings it omits, what is required to search it,
why a connector is blocked, and what evidence supports those conclusions.

A small YAML frontmatter block may hold only fields that software needs to
validate, filter, or aggregate. Long limitations and research conclusions stay
in the Markdown body. A separate hand-maintained YAML database would recreate
the drift problem this catalog is intended to solve.

### The record represents a source, not a connector

Create a separate record when an upstream interface has a materially different
access method, legal posture, capability set, update cadence, or blocker. A
single institution may therefore have several records. For example, Japan may
have separate records for the JPO API, J-PlatPat, the IP High Court case list,
published court judgments, and any general-court docket service.

Connector state is an attribute of a source. It is not a prerequisite for a
source record.

### Known but inaccessible sources belong in the catalog

The catalog must preserve four distinct questions:

1. Does the source exist and is it currently operating?
2. Who can access it?
3. Is it machine-readable and suitable for automation?
4. Have we built a connector?

This separation allows a record to say, for example, that a Korean court source
exists and supports manual exact-case lookup, but requires identifiers and a
CAPTCHA, cannot support party-name discovery, and has no connector. The source
is useful knowledge even when the connector status is `blocked` or `skipped`.

### Capabilities are explicit and graded

Use `full`, `partial`, `none`, or `unknown` for important capabilities rather
than booleans. At minimum, litigation-oriented records should address:

- pending cases
- closed cases
- party search
- broad discovery
- exact-case lookup
- docket events
- filed documents
- decisions
- patent identifiers

This prevents a source with a narrow weekly case list from appearing equivalent
to a searchable docket merely because both contain some litigation data.

### Country and worldwide views are generated

The canonical records should generate:

- a country page grouping connected, connectable, restricted, commercial, and
  unavailable sources
- a worldwide comparison matrix
- machine-readable coverage and atlas artifacts needed by downstream software

Generated pages and JSON are views, not places for manual edits.

## Implemented pilot layout

Group records by jurisdiction while retaining one file per source:

```text
catalog/sources/
  jp/
    jpo-api.md
    jplatpat.md
    ip-high-court-case-list.md
    court-judgments.md
    general-court-dockets.md
  cn/
    ...
  kr/
    ...
```

Regional and multilateral sources should use corresponding identifiers, such
as `upc/`, `epo/`, or `wipo/`, rather than being forced into a country.

## Pilot record shape

The pilot uses this working shape. It adds a `name`, a `rights` list, a
`jurisdictions` list for multi-country sources, plural `formats`, and plural
connector `blockers` to the initial proposal:

```yaml
---
id: JP/IPHC/PatentUtilityModelCaseLists
name: Japan IP High Court patent and utility-model case lists
jurisdictions: [JP]
institution: Intellectual Property High Court
source_type: case_list
official_url: https://www.courts.go.jp/ip/
last_verified: 2026-08-21
source_status: active
access:
  availability: public
  audience: public
  formats: [xls]
  automation_posture: permitted
capabilities:
  pending_cases: partial
  closed_cases: partial
  party_search: none
  broad_discovery: none
  exact_case_lookup: partial
  docket_events: none
  filed_documents: none
  decisions: none
  patent_identifiers: partial
connector:
  status: shipped
  module: patent_client_agents.japan_ip_high_court
  blockers: []
---
```

Candidate controlled vocabularies:

- `source_status`: `active`, `retired`, `announced`, `unverified`
- `availability`: `public`, `credentialed`, `commercial`, `parties_only`,
  `manual_only`, `unavailable`, `unknown`
- `automation_posture`: `permitted`, `byok_only`, `approval_required`,
  `contract_required`, `prohibited`, `technically_blocked`, `unclear`
- `connector.status`: `shipped`, `candidate`, `planned`, `blocked`, `skipped`,
  `external`
- possible blocker values: `captcha`, `no_api`, `license`, `tos`,
  `commercial_contract`, `geofence`, `required_identifiers`, `parties_only`,
  `unknown`

The Markdown body should use these headings:

```markdown
## What this source contains
## Scope limitations
## Access and connector assessment
## Connector coverage
## Known gaps
## Evidence
```

## Relationship to current files

The repository is partway toward this design, but current artifacts answer
different questions:

- `CATALOG.md` and `src/patent_client_agents/catalog/sources/` document
  implemented Python clients. They generally do not inventory unconnected or
  inaccessible sources by jurisdiction.
- `coverage/sources.yaml` is the human-edited manifest for shipped source
  coverage and generated coverage artifacts. It can represent several statuses,
  but is currently connector-centered and contains little narrative evidence.
- `research/STATE.yaml` tracks office or entity research and connector roadmap
  state. Its unit of record is broader than an individual upstream source.
- `research/national/`, `research/regional/`, and `research/multilateral/`
  contain useful institutional synopses, but repeat some source and connector
  status and are not a complete source inventory.
- `research/ip-research-courts.md` is an older survey and should not be treated
  as current catalog state without re-verification.

During migration, the office synopses can remain as institutional background,
but source scope and connector status should stop being duplicated there.
`coverage/sources.yaml` and the relevant source-level fields in
`research/STATE.yaml` should eventually be generated from the canonical
Markdown records or retired. That decision should be made only after the pilot.

## Implementation and remaining migration plan

- [x] Draft pilot source records for Japan, China, and Korea, including
      shipped, connectable, manual, commercial, and blocked litigation
      sources.
- [x] Render one country page for each pilot jurisdiction and compare the
      result against the research questions that prompted this design:
      pending-case coverage, party discovery, exact-case lookup, documents,
      and patent identifiers.
- [x] Establish pilot controlled vocabularies and validation rules.
- [x] Place the source inventory in a new top-level `catalog/` tree, leaving
      connector API documentation under `src/patent_client_agents/catalog/`.
- [x] Build validation and generation tooling for country pages and the
      worldwide matrix, including separate upstream and connected-capability
      rollups.
- [ ] Decide whether and how the canonical records should generate
      `coverage.json` and `atlas.json` without weakening their existing
      connector and office-level contracts.
- [ ] Expand the source inventory beyond the initial eight records and three
      jurisdictions.
- [ ] Migrate current source records without losing narrative limitations or
      provenance.
- [ ] Generate or retire overlapping fields in `coverage/sources.yaml` and
      `research/STATE.yaml` only after parity checks pass.
- [ ] Replace or clearly archive stale standalone surveys after their useful
      findings have been incorporated.

## Non-goals for the deferred work

- Do not imply that every known source is automatable.
- Do not equate published judgments with pending-case or docket coverage.
- Do not treat EPO OPS or INPADOC legal-status data as worldwide litigation
  filing data; litigation coverage requires court or litigation-specific
  sources.
- Do not force narrative evidence or nuanced limitations into YAML fields.
- Do not migrate existing manifests until the JP/CN/KR pilot proves the model.
