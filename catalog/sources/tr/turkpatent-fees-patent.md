---
id: TR/TURKPATENT/Fees/Patent
name: TÜRKPATENT — Fees (Patent and Utility Model)
jurisdictions:
- TR
institution: Türk Patent ve Marka Kurumu (TÜRKPATENT)
source_type: fee_schedule
official_url: https://www.turkpatent.gov.tr/
last_verified: 2026-08-02
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
  order: 111
  wipo_st3_code: TR
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
  notes: Scrapes the official patent and utility-model fee table. Amounts use the all-in TOPLAM TUTAR
    column and retain base fee, VAT, and stamp-duty components in notes. The 2026 authority is Resmî Gazete
    31-12-2025, fifth supplementary issue, BİK/TÜRKPATENT 2026/1.
---

# TÜRKPATENT — Fees (Patent and Utility Model)

## What this source contains

Türk Patent ve Marka Kurumu (TÜRKPATENT) publishes this data product for patent. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Scrapes the official patent and utility-model fee table. Amounts use the all-in TOPLAM TUTAR column and retain base fee, VAT, and stamp-duty components in notes. The 2026 authority is Resmî Gazete 31-12-2025, fifth supplementary issue, BİK/TÜRKPATENT 2026/1.

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

- [Official source](https://www.turkpatent.gov.tr/)
