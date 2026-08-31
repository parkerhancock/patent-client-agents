---
id: GB/UKIPO/Fees/Trademarks
name: UKIPO Fee Schedule — Trademarks
jurisdictions:
- GB
institution: UK Intellectual Property Office
source_type: fee_schedule
official_url: https://www.gov.uk/government/publications/trade-mark-forms-and-fees
last_verified: 2026-05-18
source_status: active
category: fees
rights:
- trademark
access:
  availability: public
  audience: public
  formats:
  - html
  automation_posture: unclear
capabilities:
  current_schedule: partial
  effective_date: partial
  historical_schedule: unknown
  machine_readable: partial
  calculator: unknown
connector:
  status: shipped
  module: patent_client_agents.fees
  blockers: []
coverage:
  order: 98
  wipo_st3_code: GB
  data_types:
  - fees
  access:
    method: website_scrape
    auth: none
  status: active
  category: fees
  transport: mcp_proxy
  update_strategy: live_proxy
  update_cadence: irregular
  notes: Scrapes the gov.uk trade-mark-forms-and-fees detail page; 17 inline Form | Title | Cost tables.
    Renewals tagged year=10 (UKIPO TM 10-year cycle). Effective 2026-04-01.
---

# UKIPO Fee Schedule — Trademarks

## What this source contains

UK Intellectual Property Office publishes this data product for trademark. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Scrapes the gov.uk trade-mark-forms-and-fees detail page; 17 inline Form | Title | Cost tables. Renewals tagged year=10 (UKIPO TM 10-year cycle). Effective 2026-04-01.

## Access and connector assessment

The declared access method is `website_scrape` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.fees`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.gov.uk/government/publications/trade-mark-forms-and-fees)
