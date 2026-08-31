---
id: WO/WIPO/Fees/Hague
name: WIPO Hague System — Schedule of Fees
jurisdictions:
- WO
institution: World Intellectual Property Organization (WIPO) — International Bureau
source_type: fee_schedule
official_url: https://www.wipo.int/hague/en/fees/sched.html
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
  order: 103
  wipo_st3_code: WO
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
  notes: 'Hague System international design fees in CHF: basic + per- additional-design, publication,
    standard designation (3 levels), and per-period renewals (periods 1-5 map to years 5/10/15/20/25).
    Per-country individual designation fees live in a separate ~50- row table on wipo.int. Source: wipo.int/hague/en/fees/sched.html.'
---

# WIPO Hague System — Schedule of Fees

## What this source contains

World Intellectual Property Organization (WIPO) — International Bureau publishes this data product for design. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Hague System international design fees in CHF: basic + per- additional-design, publication, standard designation (3 levels), and per-period renewals (periods 1-5 map to years 5/10/15/20/25). Per-country individual designation fees live in a separate ~50- row table on wipo.int. Source: wipo.int/hague/en/fees/sched.html.

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

- [Official source](https://www.wipo.int/hague/en/fees/sched.html)
