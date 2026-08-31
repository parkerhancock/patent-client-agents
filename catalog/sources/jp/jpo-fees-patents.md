---
id: JP/JPO/Fees/Patents
name: JPO Fee Schedule — Patents
jurisdictions:
- JP
institution: Japan Patent Office
source_type: fee_schedule
official_url: https://www.jpo.go.jp/e/system/process/tesuryo/hyou.html
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
  order: 99
  wipo_st3_code: JP
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
  notes: Scrapes the JPO English fee page (jpo.go.jp/e/system/process/tesuryo/hyou.html). JPY. Patent
    annuities + examination requests are uniformly claim-count-dependent ("¥X + ¥Y per claim"); the scraper
    splits each into a base FeeItem plus a separate excess_claims FeeItem with FeeCondition. Year bands
    1-3, 4-6, 7-9, 10-25 expanded to per-year rows (Japan has a 25-year term for some patent categories).
    Two cohorts (current vs legacy by 2004/2019 fee revisions) captured with notes. JPO requires full
    Sec-Fetch-* browser headers or the request hangs with ReadTimeout — the scraper's HTTP client sets
    them.
---

# JPO Fee Schedule — Patents

## What this source contains

Japan Patent Office publishes this data product for patent. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Scrapes the JPO English fee page (jpo.go.jp/e/system/process/tesuryo/hyou.html). JPY. Patent annuities + examination requests are uniformly claim-count-dependent ("¥X + ¥Y per claim"); the scraper splits each into a base FeeItem plus a separate excess_claims FeeItem with FeeCondition. Year bands 1-3, 4-6, 7-9, 10-25 expanded to per-year rows (Japan has a 25-year term for some patent categories). Two cohorts (current vs legacy by 2004/2019 fee revisions) captured with notes. JPO requires full Sec-Fetch-* browser headers or the request hangs with ReadTimeout — the scraper's HTTP client sets them.

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

- [Official source](https://www.jpo.go.jp/e/system/process/tesuryo/hyou.html)
