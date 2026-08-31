---
id: EP/EPO/CaseLaw
name: EPO Boards of Appeal Case Law Compendium
jurisdictions:
- EP
institution: European Patent Office (Boards of Appeal)
source_type: legal_corpus
official_url: https://www.epo.org/en/legal/case-law
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
  case_law: partial
  statutes: none
  treaties: none
  full_text_search: partial
  citation_lookup: unknown
  point_in_time: unknown
connector:
  status: shipped
  module: patent_client_agents.epo_case_law
  blockers: []
coverage:
  order: 34
  wipo_st3_code: EP
  data_types:
  - case_law
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
  notes: 'Cadence follows the bundled-artifact rhythm (annual compendium

    republication), not individual decision issuance.

    '
---

# EPO Boards of Appeal Case Law Compendium

## What this source contains

European Patent Office (Boards of Appeal) publishes this data product for patent. The compatibility
manifest declares the following covered data types: case_law.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Cadence follows the bundled-artifact rhythm (annual compendium
republication), not individual decision issuance.

## Access and connector assessment

The declared access method is `mcp_passthrough` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.epo_case_law`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.epo.org/en/legal/case-law)
