---
id: EP/EUIPO/Fees/Trademarks
name: EUIPO EUTM Fee Schedule
jurisdictions:
- EP
institution: European Union Intellectual Property Office
source_type: fee_schedule
official_url: https://www.euipo.europa.eu/en/trade-marks/before-applying/fees-payable-direct-to-the-euipo
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
  order: 90
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
  notes: Extracts F-xxx (EUTM) and M-xxx (Madrid) fees from the EUIPO Next.js SSR stream. EUR. 10-year
    renewal cycle. EUTMR Annex I.
---

# EUIPO EUTM Fee Schedule

## What this source contains

European Union Intellectual Property Office publishes this data product for trademark. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Extracts F-xxx (EUTM) and M-xxx (Madrid) fees from the EUIPO Next.js SSR stream. EUR. 10-year renewal cycle. EUTMR Annex I.

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

- [Official source](https://www.euipo.europa.eu/en/trade-marks/before-applying/fees-payable-direct-to-the-euipo)
