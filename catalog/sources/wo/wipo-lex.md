---
id: WO/WIPO/Lex
name: WIPO Lex — global IP legislation & treaties
jurisdictions:
- WO
institution: World Intellectual Property Organization
source_type: legal_corpus
official_url: https://www.wipo.int/wipolex/en/main/
last_verified: 2026-05-15
source_status: active
category: substantive_law
rights:
- patent
- trademark
- design
- copyright
- gi
access:
  availability: public
  audience: public
  formats:
  - json
  automation_posture: permitted
capabilities:
  guidelines: none
  case_law: none
  statutes: partial
  treaties: partial
  full_text_search: partial
  citation_lookup: unknown
  point_in_time: unknown
connector:
  status: shipped
  module: patent_client_agents.wipo_lex
  blockers: []
coverage:
  order: 46
  wipo_st3_code: WO
  data_types:
  - statutes
  - treaties
  access:
    method: rest_api
    auth: none
  status: active
  category: substantive_law
  transport: mcp_proxy
  update_strategy: live_proxy
  update_cadence: irregular
---

# WIPO Lex — global IP legislation & treaties

## What this source contains

World Intellectual Property Organization publishes this data product for patent, trademark, design, copyright, gi. The compatibility
manifest declares the following covered data types: statutes, treaties.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.wipo_lex`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.wipo.int/wipolex/en/main/)
