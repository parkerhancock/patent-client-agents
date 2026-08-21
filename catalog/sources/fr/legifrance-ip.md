---
id: FR/Legifrance/IP
name: Légifrance — French IP statutes (Code de la propriété intellectuelle + Code de commerce L.151 trade
  secrets)
jurisdictions:
- FR
institution: Direction de l'information légale et administrative (DILA)
source_type: legal_corpus
official_url: https://www.legifrance.gouv.fr/codes/texte_lc/LEGITEXT000006069414/
last_verified: 2026-05-16
source_status: active
category: substantive_law
rights:
- patent
- trademark
- design
- copyright
- trade_secret
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
  module: patent_client_agents.legifrance_ip
  blockers: []
coverage:
  order: 56
  wipo_st3_code: FR
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

# Légifrance — French IP statutes (Code de la propriété intellectuelle + Code de commerce L.151 trade secrets)

## What this source contains

Direction de l'information légale et administrative (DILA) publishes this data product for patent, trademark, design, copyright, trade_secret. The compatibility
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

The compatibility connector module is `patent_client_agents.legifrance_ip`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.legifrance.gouv.fr/codes/texte_lc/LEGITEXT000006069414/)
