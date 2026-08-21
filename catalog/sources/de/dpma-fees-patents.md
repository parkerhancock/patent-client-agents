---
id: DE/DPMA/Fees/Patents
name: DPMA Fee Schedule — Patents
jurisdictions:
- DE
institution: Deutsches Patent- und Markenamt (DPMA)
source_type: fee_schedule
official_url: https://www.dpma.de/english/services/fees/patents/index.html
last_verified: 2026-05-18
source_status: active
category: fees
rights:
- patent
access:
  availability: public
  audience: public
  formats:
  - pdf
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
  order: 94
  wipo_st3_code: DE
  data_types:
  - fees
  access:
    method: pdf_download
    auth: none
  status: active
  category: fees
  transport: mcp_proxy
  update_strategy: live_proxy
  update_cadence: irregular
  notes: 'Scraped from the DPMA cost-info PDF (form A 9510.1) because the English HTML fee page only lists
    years 3-6 of the annual fee schedule and punts to the PDF for years 7-20. pypdf + regex extraction
    of the uniform "<6-digit code> <description> ... <amount>" row format. Fee numbers in the 31x range
    are patents. Statutory basis: PatKostG (Patentkostengesetz).'
---

# DPMA Fee Schedule — Patents

## What this source contains

Deutsches Patent- und Markenamt (DPMA) publishes this data product for patent. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Scraped from the DPMA cost-info PDF (form A 9510.1) because the English HTML fee page only lists years 3-6 of the annual fee schedule and punts to the PDF for years 7-20. pypdf + regex extraction of the uniform "<6-digit code> <description> ... <amount>" row format. Fee numbers in the 31x range are patents. Statutory basis: PatKostG (Patentkostengesetz).

## Access and connector assessment

The declared access method is `pdf_download` with
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

- [Official source](https://www.dpma.de/english/services/fees/patents/index.html)
