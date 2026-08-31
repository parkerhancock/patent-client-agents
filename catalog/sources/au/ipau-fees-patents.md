---
id: AU/IPAU/Fees/Patents
name: IP Australia Fee Schedule — Patents
jurisdictions:
- AU
institution: IP Australia
source_type: fee_schedule
official_url: https://www.ipaustralia.gov.au/patents/timeframes-and-fees
last_verified: 2026-05-18
source_status: active
category: fees
rights:
- patent
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
  order: 96
  wipo_st3_code: AU
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
  notes: 'Scrapes IP Australia''s timeframes-and-fees page (13 small Action | Fee tables). AUD. Fees revised
    2024-10-01 per the four-yearly fee review; PCT-fee equivalents updated 2026-01-01. v1 GAP: annual
    renewal fees (years 5-20) live in Schedule 7 of the Patents Regulations 1991 and are not on this page
    — follow-up scraper needed to pull them from the Federal Register of Legislation.'
---

# IP Australia Fee Schedule — Patents

## What this source contains

IP Australia publishes this data product for patent. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Scrapes IP Australia's timeframes-and-fees page (13 small Action | Fee tables). AUD. Fees revised 2024-10-01 per the four-yearly fee review; PCT-fee equivalents updated 2026-01-01. v1 GAP: annual renewal fees (years 5-20) live in Schedule 7 of the Patents Regulations 1991 and are not on this page — follow-up scraper needed to pull them from the Federal Register of Legislation.

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

- [Official source](https://www.ipaustralia.gov.au/patents/timeframes-and-fees)
