---
id: CA/CIPO/Fees/Patents
name: CIPO Fee Schedule — Patents
jurisdictions:
- CA
institution: Canadian Intellectual Property Office
source_type: fee_schedule
official_url: https://ised-isde.canada.ca/site/canadian-intellectual-property-office/en/patents/fees-patents
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
  order: 93
  wipo_st3_code: CA
  data_types:
  - fees
  access:
    method: website_scrape
    auth: none
  status: active
  category: fees
  transport: mcp_proxy
  update_strategy: live_proxy
  update_cadence: annual
  notes: Scrapes the CIPO patent fee page (ic.gc.ca/eic/site/cipointernet-internetopic.nsf/eng/wr00142.html).
    4 unique HTML tables; small + standard entity tiers in CAD. Maintenance fees use English-band descriptions
    (e.g., "second, third and fourth anniversaries") which the scraper expands to per-year rows. CIPO
    publishes annually with a January 1 effective date; Patent Rules SOR/2019-251 Schedule of Fees.
---

# CIPO Fee Schedule — Patents

## What this source contains

Canadian Intellectual Property Office publishes this data product for patent. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Scrapes the CIPO patent fee page (ic.gc.ca/eic/site/cipointernet-internetopic.nsf/eng/wr00142.html). 4 unique HTML tables; small + standard entity tiers in CAD. Maintenance fees use English-band descriptions (e.g., "second, third and fourth anniversaries") which the scraper expands to per-year rows. CIPO publishes annually with a January 1 effective date; Patent Rules SOR/2019-251 Schedule of Fees.

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

- [Official source](https://ised-isde.canada.ca/site/canadian-intellectual-property-office/en/patents/fees-patents)
