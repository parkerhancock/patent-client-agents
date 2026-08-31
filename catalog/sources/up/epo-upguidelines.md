---
id: UP/EPO/UPGuidelines
name: Unitary Patent Guidelines
jurisdictions:
- UP
institution: European Patent Office (Unitary Patent Court Division)
source_type: legal_corpus
official_url: https://www.epo.org/en/legal/guidelines-up
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
  guidelines: partial
  case_law: none
  statutes: none
  treaties: none
  full_text_search: partial
  citation_lookup: unknown
  point_in_time: unknown
connector:
  status: shipped
  module: patent_client_agents.epo_up_guidelines
  blockers: []
coverage:
  order: 36
  wipo_st3_code: UP
  data_types:
  - guidelines
  access:
    method: mcp_passthrough
    auth: none
  status: active
  category: substantive_law
  transport: mcp_local
  update_strategy: scheduled_recrawl
  update_cadence: annual
  last_synced: 2026-05-15
  corpus_version: unknown — needs verification
---

# Unitary Patent Guidelines

## What this source contains

European Patent Office (Unitary Patent Court Division) publishes this data product for patent. The compatibility
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

The compatibility connector module is `patent_client_agents.epo_up_guidelines`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.epo.org/en/legal/guidelines-up)
