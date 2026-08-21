---
id: SG/IPOS/Statutes
name: IPOS Singapore — IP statutes (Patents / Trade Marks / Designs / Copyright)
jurisdictions:
- SG
institution: Intellectual Property Office of Singapore
source_type: legal_corpus
official_url: https://sso.agc.gov.sg/Act/PA1994
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
  module: patent_client_agents.ipos_statutes
  blockers: []
coverage:
  order: 40
  wipo_st3_code: SG
  data_types:
  - statutes
  access:
    method: mcp_passthrough
    auth: none
  status: active
  category: substantive_law
  transport: mcp_local
  update_strategy: scheduled_recrawl
  update_cadence: irregular
  last_synced: 2026-05-16
  corpus_version: unknown — needs verification
---

# IPOS Singapore — IP statutes (Patents / Trade Marks / Designs / Copyright)

## What this source contains

Intellectual Property Office of Singapore publishes this data product for patent, trademark, design, copyright. The compatibility
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

The compatibility connector module is `patent_client_agents.ipos_statutes`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://sso.agc.gov.sg/Act/PA1994)
