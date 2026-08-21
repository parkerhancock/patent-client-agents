---
id: CN/CNIPA/Fees/Patents
name: CNIPA Fee Schedule — Patents
jurisdictions:
- CN
institution: China National Intellectual Property Administration
source_type: fee_schedule
official_url: https://english.cnipa.gov.cn/col/col3000/index.html
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
  order: 92
  wipo_st3_code: CN
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
  notes: Scrapes the CNIPA English mirror (english.cnipa.gov.cn/col/col3000). Single 2-column hierarchical
    table with Roman-numeral sections; the scraper expands year-banded annuities (e.g., "1-3 Years (Each
    Year) | 900") to per-year rows. v1 covers invention patents only; utility-model + design ship as separate
    routes when needed. Patent Law of the PRC + Implementing Regulations. Fee schedule set by State Council
    Pricing Bureau.
---

# CNIPA Fee Schedule — Patents

## What this source contains

China National Intellectual Property Administration publishes this data product for patent. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Scrapes the CNIPA English mirror (english.cnipa.gov.cn/col/col3000). Single 2-column hierarchical table with Roman-numeral sections; the scraper expands year-banded annuities (e.g., "1-3 Years (Each Year) | 900") to per-year rows. v1 covers invention patents only; utility-model + design ship as separate routes when needed. Patent Law of the PRC + Implementing Regulations. Fee schedule set by State Council Pricing Bureau.

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

- [Official source](https://english.cnipa.gov.cn/col/col3000/index.html)
