---
id: GB/UKIPO/Fees/Patents
name: UKIPO Fee Schedule — Patents
jurisdictions:
- GB
institution: UK Intellectual Property Office
source_type: fee_schedule
official_url: https://www.gov.uk/government/publications/patent-forms-and-fees
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
  order: 97
  wipo_st3_code: GB
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
  notes: 'UKIPO publishes one gov.uk publication page per patent form (~30 forms). The scraper reads the
    index detail page (form number/title/sub-URL), then fans out to fetch each sub-page (bounded concurrency
    5, hishel cache 7d) and extracts the £-amount from the "Cost" section. Effective 2026-04-01 — first
    major UKIPO fee rise in years (~25% average). v1 GAP: renewal fees are published as a range (£90-£810);
    per-year schedule is in The Patents (Fees) Rules 2007 statutory instrument and needs a follow-up scraper
    against legislation.gov.uk.'
---

# UKIPO Fee Schedule — Patents

## What this source contains

UK Intellectual Property Office publishes this data product for patent. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

UKIPO publishes one gov.uk publication page per patent form (~30 forms). The scraper reads the index detail page (form number/title/sub-URL), then fans out to fetch each sub-page (bounded concurrency 5, hishel cache 7d) and extracts the £-amount from the "Cost" section. Effective 2026-04-01 — first major UKIPO fee rise in years (~25% average). v1 GAP: renewal fees are published as a range (£90-£810); per-year schedule is in The Patents (Fees) Rules 2007 statutory instrument and needs a follow-up scraper against legislation.gov.uk.

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

- [Official source](https://www.gov.uk/government/publications/patent-forms-and-fees)
