---
id: DE/DPMA/Statutes
name: DPMA Germany — IP statutes (PatG, MarkenG, GebrMG, DesignG, UrhG, GeschGehG)
jurisdictions:
- DE
institution: Deutsches Patent- und Markenamt
source_type: legal_corpus
official_url: https://www.gesetze-im-internet.de/patg/
last_verified: 2026-05-16
source_status: active
category: substantive_law
rights:
- patent
- trademark
- design
- copyright
access:
  availability: public
  audience: public
  formats:
  - unknown
  automation_posture: permitted
capabilities:
  guidelines: none
  case_law: none
  statutes: partial
  treaties: none
  full_text_search: partial
  citation_lookup: unknown
  point_in_time: unknown
connector:
  status: shipped
  module: patent_client_agents.dpma_statutes
  blockers: []
coverage:
  order: 55
  wipo_st3_code: DE
  data_types:
  - statutes
  access:
    method: mcp_passthrough
    auth: none
  status: active
  category: substantive_law
  transport: mcp_local
  update_strategy: scheduled_recrawl
  update_cadence: annual
  last_synced: 2026-05-16
  corpus_version: seed v1
---

# DPMA Germany — IP statutes (PatG, MarkenG, GebrMG, DesignG, UrhG, GeschGehG)

## What this source contains

Deutsches Patent- und Markenamt publishes this data product for patent, trademark, design, copyright. The compatibility
manifest declares the following covered data types: statutes.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

## Access and connector assessment

The declared access method is `mcp_passthrough` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.dpma_statutes`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.gesetze-im-internet.de/patg/)
