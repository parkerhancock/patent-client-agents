---
id: WO/Google/Patents
name: Google Patents (worldwide aggregator)
jurisdictions:
- WO
institution: Google LLC (aggregator; not an issuing authority)
source_type: registry
official_url: https://patents.google.com/
last_verified: 2026-05-15
source_status: active
category: registered_ip
rights:
- patent
access:
  availability: public
  audience: public
  formats:
  - html
  automation_posture: unclear
capabilities:
  bibliographic: partial
  full_text: partial
  prosecution: none
  legal_status: none
  assignments: none
  oppositions: none
  classification: none
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.google_patents
  blockers: []
coverage:
  atlas_standalone_reason: cross_office_service
  order: 24
  wipo_st3_code: WO
  data_types:
  - bibliographic
  - full_text
  access:
    method: website_scrape
    auth: none
  status: active
  category: registered_ip
  transport: mcp_proxy
  notes: 'Non-authoritative aggregator; primary use is cross-jurisdiction reach

    where authoritative registers (PPUBS, EPO OPS, JPO) don''t reach.

    '
---

# Google Patents (worldwide aggregator)

## What this source contains

Google LLC (aggregator; not an issuing authority) publishes this data product for patent. The compatibility
manifest declares the following covered data types: bibliographic, full_text.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Non-authoritative aggregator; primary use is cross-jurisdiction reach
where authoritative registers (PPUBS, EPO OPS, JPO) don't reach.

## Access and connector assessment

The declared access method is `website_scrape` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.google_patents`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://patents.google.com/)
