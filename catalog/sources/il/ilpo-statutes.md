---
id: IL/ILPO/Statutes
name: ILPO Israel — IP statutes (Patents, TM, Designs, Copyright, Commercial Torts)
jurisdictions:
- IL
institution: Israel Patent Office (Ministry of Justice)
source_type: legal_corpus
official_url: https://www.wipo.int/wipolex/en/legislation/members/profile/IL
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
  module: patent_client_agents.ilpo_statutes
  blockers: []
coverage:
  order: 42
  wipo_st3_code: IL
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
  corpus_version: WIPO Lex authoritative EN
  notes: 'Five Israeli IP statutes — Patents Law 5727-1967, Trade Marks

    Ordinance 5732-1972, Designs Law 5777-2017, Copyright Act

    5768-2007, and **Commercial Torts Law 5759-1999** (the

    distinctive piece: Israel''s standalone trade-secret statute,

    Arts. 6-9, with statutory damages in Art. 13). Bundled corpus

    is built from WIPO Lex authoritative EN translations.

    '
---

# ILPO Israel — IP statutes (Patents, TM, Designs, Copyright, Commercial Torts)

## What this source contains

Israel Patent Office (Ministry of Justice) publishes this data product for patent, trademark, design, copyright. The compatibility
manifest declares the following covered data types: statutes.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Five Israeli IP statutes — Patents Law 5727-1967, Trade Marks
Ordinance 5732-1972, Designs Law 5777-2017, Copyright Act
5768-2007, and **Commercial Torts Law 5759-1999** (the
distinctive piece: Israel's standalone trade-secret statute,
Arts. 6-9, with statutory damages in Art. 13). Bundled corpus
is built from WIPO Lex authoritative EN translations.

## Access and connector assessment

The declared access method is `mcp_passthrough` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.ilpo_statutes`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.wipo.int/wipolex/en/legislation/members/profile/IL)
