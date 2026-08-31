---
id: TW/TIPO/Fees/Patent
name: TIPO Taiwan — Fees (Patent)
jurisdictions:
- TW
institution: Taiwan Intellectual Property Office (TIPO)
source_type: fee_schedule
official_url: https://www.tipo.gov.tw/en/tipo2/326.html
last_verified: 2026-05-19
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
  order: 104
  wipo_st3_code: TW
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
  notes: 'Schedule of Patent Fees (TWD) covering all three Taiwan patent types under one office: invention
    patents (20-yr term), utility model patents (10-yr term), and design patents (15-yr term). The schedule
    prints standard rates with sibling SME-tier rows ("natural person, school, or small and medium-sized
    enterprise") for annuity years 1-3 and 4-6; design year-1 SME annuity is NT$0. Per-claim surcharge
    over 10 claims (NT$800 invention substantive exam, NT$600 utility model TER); per-50-page surcharge
    over 50 pages (NT$500). Source HTML table at tipo.gov.tw/en/tipo2/326.html — direct lxml scrape; annuity
    rows expanded per-year so lookup-by-year works.'
---

# TIPO Taiwan — Fees (Patent)

## What this source contains

Taiwan Intellectual Property Office (TIPO) publishes this data product for patent. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Schedule of Patent Fees (TWD) covering all three Taiwan patent types under one office: invention patents (20-yr term), utility model patents (10-yr term), and design patents (15-yr term). The schedule prints standard rates with sibling SME-tier rows ("natural person, school, or small and medium-sized enterprise") for annuity years 1-3 and 4-6; design year-1 SME annuity is NT$0. Per-claim surcharge over 10 claims (NT$800 invention substantive exam, NT$600 utility model TER); per-50-page surcharge over 50 pages (NT$500). Source HTML table at tipo.gov.tw/en/tipo2/326.html — direct lxml scrape; annuity rows expanded per-year so lookup-by-year works.

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

- [Official source](https://www.tipo.gov.tw/en/tipo2/326.html)
