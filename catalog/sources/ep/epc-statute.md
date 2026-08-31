---
id: EP/EPC/Statute
name: European Patent Convention (EPC)
jurisdictions:
- EP
institution: European Patent Office
source_type: legal_corpus
official_url: https://www.epo.org/en/legal/epc
last_verified: 2026-05-15
source_status: active
category: substantive_law
rights:
- patent
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
  module: patent_client_agents.epc
  blockers: []
coverage:
  order: 32
  wipo_st3_code: EP
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
  last_synced: 2026-05-15
  corpus_version: unknown — needs verification
---

# European Patent Convention (EPC)

## What this source contains

European Patent Office publishes this data product for patent. The compatibility
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

The compatibility connector module is `patent_client_agents.epc`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.epo.org/en/legal/epc)
