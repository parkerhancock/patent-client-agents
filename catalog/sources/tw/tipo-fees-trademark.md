---
id: TW/TIPO/Fees/Trademark
name: TIPO Taiwan — Fees (Trademark)
jurisdictions:
- TW
institution: Taiwan Intellectual Property Office (TIPO)
source_type: fee_schedule
official_url: https://www.tipo.gov.tw/en/tipo2/342.html
last_verified: 2026-05-19
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
  order: 105
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
  notes: 'Trademark Fee Standards 2024 (effective 2024-05-01), published as a bilingual zh-TW + EN PDF
    linked from tipo.gov.tw/en/tipo2/342.html. Per-class fees in TWD for application (NT$3,000), registration
    (NT$2,500), renewal on 10-year cycle (NT$4,000), opposition (NT$4,000), invalidation (NT$7,000), revocation
    (NT$7,000), plus per-good surcharge over 20 designated goods (NT$200/good) and per-retail-service
    surcharge over 5 in Class 35 (NT$500). Scraper uses a curated catalog of 30 entries verified against
    the live PDF: each entry''s English label and amount must co-occur within a 300-char window in normalized
    text. Drift raises loudly rather than silently mis-classifying.'
---

# TIPO Taiwan — Fees (Trademark)

## What this source contains

Taiwan Intellectual Property Office (TIPO) publishes this data product for trademark. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Trademark Fee Standards 2024 (effective 2024-05-01), published as a bilingual zh-TW + EN PDF linked from tipo.gov.tw/en/tipo2/342.html. Per-class fees in TWD for application (NT$3,000), registration (NT$2,500), renewal on 10-year cycle (NT$4,000), opposition (NT$4,000), invalidation (NT$7,000), revocation (NT$7,000), plus per-good surcharge over 20 designated goods (NT$200/good) and per-retail-service surcharge over 5 in Class 35 (NT$500). Scraper uses a curated catalog of 30 entries verified against the live PDF: each entry's English label and amount must co-occur within a 300-char window in normalized text. Drift raises loudly rather than silently mis-classifying.

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

- [Official source](https://www.tipo.gov.tw/en/tipo2/342.html)
