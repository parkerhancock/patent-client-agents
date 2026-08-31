---
id: KR/KIPO/Fees/Patents
name: KIPO Fee Schedule — Patents
jurisdictions:
- KR
institution: Korean Intellectual Property Office
source_type: fee_schedule
official_url: https://www.kipo.go.kr/en/HtmlApp?c=92004&catmenu=ek03_04_01
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
  order: 95
  wipo_st3_code: KR
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
  notes: Scrapes the KIPO English IP-system fees page (HtmlApp c=92004). KRW. 2-column Description | Fee
    table with section headers (Application/Examination/Annual/Others). Annuity bands 1-3, 4-6, 7-9, 10-12,
    13-15, 16-25 years expanded to per-year rows. Per-claim surcharges appear as bare-amount rows after
    each "a. Basic fee" row and are paired by the scraper. Effective 2023-08-01 per KIPO Enforcement Rule
    amendment.
---

# KIPO Fee Schedule — Patents

## What this source contains

Korean Intellectual Property Office publishes this data product for patent. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Scrapes the KIPO English IP-system fees page (HtmlApp c=92004). KRW. 2-column Description | Fee table with section headers (Application/Examination/Annual/Others). Annuity bands 1-3, 4-6, 7-9, 10-12, 13-15, 16-25 years expanded to per-year rows. Per-claim surcharges appear as bare-amount rows after each "a. Basic fee" row and are paired by the scraper. Effective 2023-08-01 per KIPO Enforcement Rule amendment.

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

- [Official source](https://www.kipo.go.kr/en/HtmlApp?c=92004&catmenu=ek03_04_01)
