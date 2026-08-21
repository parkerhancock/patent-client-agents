---
id: IN/IPO/Statutes
name: IPO India — IP statutes (Patents Act 1970, Designs Act 2000, Trade Marks Act 1999, Copyright Act
  1957, Patent Rules 2003)
jurisdictions:
- IN
institution: Office of the Controller General of Patents, Designs and Trade Marks
source_type: legal_corpus
official_url: https://ipindia.gov.in/patents/acts-rules
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
  module: patent_client_agents.ipo_in_statutes
  blockers: []
coverage:
  order: 47
  wipo_st3_code: IN
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

# IPO India — IP statutes (Patents Act 1970, Designs Act 2000, Trade Marks Act 1999, Copyright Act 1957, Patent Rules 2003)

## What this source contains

Office of the Controller General of Patents, Designs and Trade Marks publishes this data product for patent, trademark, design, copyright. The compatibility
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

The compatibility connector module is `patent_client_agents.ipo_in_statutes`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://ipindia.gov.in/patents/acts-rules)
