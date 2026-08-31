---
id: SG/IPOS/Manuals
name: IPOS Singapore — examination & work manuals (PEG / TM / Designs)
jurisdictions:
- SG
institution: Intellectual Property Office of Singapore
source_type: legal_corpus
official_url: https://www.ipos.gov.sg/about-ip/patents/managing-patent
last_verified: 2026-05-16
source_status: active
category: substantive_law
rights:
- patent
- trademark
- design
access:
  availability: public
  audience: public
  formats:
  - unknown
  automation_posture: permitted
capabilities:
  guidelines: partial
  case_law: none
  statutes: none
  treaties: none
  full_text_search: partial
  citation_lookup: unknown
  point_in_time: unknown
connector:
  status: shipped
  module: patent_client_agents.ipos_manuals
  blockers: []
coverage:
  order: 41
  wipo_st3_code: SG
  data_types:
  - guidelines
  access:
    method: mcp_passthrough
    auth: none
  status: active
  category: substantive_law
  transport: mcp_local
  update_strategy: scheduled_recrawl
  update_cadence: quarterly
  last_synced: 2026-05-16
  corpus_version: unknown — needs verification
---

# IPOS Singapore — examination & work manuals (PEG / TM / Designs)

## What this source contains

Intellectual Property Office of Singapore publishes this data product for patent, trademark, design. The compatibility
manifest declares the following covered data types: guidelines.

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

The compatibility connector module is `patent_client_agents.ipos_manuals`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.ipos.gov.sg/about-ip/patents/managing-patent)
