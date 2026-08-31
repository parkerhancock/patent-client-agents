---
id: TR/TURKPATENT/Fees/Trademark
name: TÜRKPATENT — Fees (Trademark)
jurisdictions:
- TR
institution: Türk Patent ve Marka Kurumu (TÜRKPATENT)
source_type: fee_schedule
official_url: https://www.turkpatent.gov.tr/
last_verified: 2026-08-02
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
  order: 112
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
  notes: Scrapes the official trademark fee table in TRY. The connector models first-class filing, additional-class
    charges, grant, renewal, opposition, cancellation, and recordation fees.
---

# TÜRKPATENT — Fees (Trademark)

## What this source contains

Türk Patent ve Marka Kurumu (TÜRKPATENT) publishes this data product for trademark. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Scrapes the official trademark fee table in TRY. The connector models first-class filing, additional-class charges, grant, renewal, opposition, cancellation, and recordation fees.

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
