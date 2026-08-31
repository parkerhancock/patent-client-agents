---
id: US/USPTO/Fees/Designs
name: USPTO Fee Schedule — Designs
jurisdictions:
- US
institution: U.S. Patent and Trademark Office
source_type: fee_schedule
official_url: https://www.uspto.gov/learning-and-resources/fees-and-payment/uspto-fee-schedule
last_verified: 2026-05-18
source_status: active
category: fees
rights:
- design
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
  order: 88
  wipo_st3_code: US
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
  notes: Design-specific rows only (filing, search, exam, issue, Design CPA). Shared procedural fees (extensions,
    appeals, petitions) come from US/USPTO/Fees/Patents.
---

# USPTO Fee Schedule — Designs

## What this source contains

U.S. Patent and Trademark Office publishes this data product for design. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Design-specific rows only (filing, search, exam, issue, Design CPA). Shared procedural fees (extensions, appeals, petitions) come from US/USPTO/Fees/Patents.

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

- [Official source](https://www.uspto.gov/learning-and-resources/fees-and-payment/uspto-fee-schedule)
