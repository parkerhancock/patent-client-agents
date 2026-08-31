---
id: BR/INPI/Fees/Trademark
name: INPI Brazil — Fees (Trademark)
jurisdictions:
- BR
institution: Instituto Nacional da Propriedade Industrial (INPI)
source_type: fee_schedule
official_url: https://www.gov.br/inpi/en/costs-and-payment
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
  order: 107
  wipo_st3_code: BR
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
  notes: INPI Brazil trademark fees in BRL, per-class for application (pre-approved vs free specification),
    first 10-year term, 10-yr renewal cycle, opposition, cancellation, and administrative invalidation.
    Source PDF at gov.br/inpi/en/costs-and-payment/schedule-of-fees-trademarks.pdf. Up-to-60% discount
    applies per Resolution 251/2019 §I.5. Same scraper-pattern as the patent route.
---

# INPI Brazil — Fees (Trademark)

## What this source contains

Instituto Nacional da Propriedade Industrial (INPI) publishes this data product for trademark. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

INPI Brazil trademark fees in BRL, per-class for application (pre-approved vs free specification), first 10-year term, 10-yr renewal cycle, opposition, cancellation, and administrative invalidation. Source PDF at gov.br/inpi/en/costs-and-payment/schedule-of-fees-trademarks.pdf. Up-to-60% discount applies per Resolution 251/2019 §I.5. Same scraper-pattern as the patent route.

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

- [Official source](https://www.gov.br/inpi/en/costs-and-payment)
