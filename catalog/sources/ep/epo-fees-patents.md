---
id: EP/EPO/Fees/Patents
name: EPO Schedule of Fees — Patents
jurisdictions:
- EP
institution: European Patent Office
source_type: fee_schedule
official_url: https://www.epo.org/en/applying/fees
last_verified: 2026-05-18
source_status: active
category: fees
rights:
- patent
access:
  availability: public
  audience: public
  formats:
  - json
  automation_posture: permitted
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
  order: 89
  data_types:
  - fees
  access:
    method: rest_api
    auth: none
  status: active
  category: fees
  transport: mcp_proxy
  update_strategy: live_proxy
  update_cadence: irregular
  notes: Sources from the EPO Schedule-of-Fees SPA's backing BFF (fees.apps.epo.org/prod/bff/api/fees).
    The BFF is undocumented but stable. Covers EPC renewals years 2-20 (codes 732-750) and Unitary Patent
    renewals (codes 033-050). Amounts in EUR.
---

# EPO Schedule of Fees — Patents

## What this source contains

European Patent Office publishes this data product for patent. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Sources from the EPO Schedule-of-Fees SPA's backing BFF (fees.apps.epo.org/prod/bff/api/fees). The BFF is undocumented but stable. Covers EPC renewals years 2-20 (codes 732-750) and Unitary Patent renewals (codes 033-050). Amounts in EUR.

## Access and connector assessment

The declared access method is `rest_api` with
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

- [Official source](https://www.epo.org/en/applying/fees)
