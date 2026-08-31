---
id: US/USITC/HTS
name: USITC HTS — Harmonized Tariff Schedule
jurisdictions:
- US
institution: U.S. International Trade Commission
source_type: external_dataset
official_url: https://hts.usitc.gov/
last_verified: 2026-05-15
source_status: active
category: external
rights: []
access:
  availability: public
  audience: public
  formats:
  - json
  automation_posture: permitted
capabilities:
  query_api: partial
  bulk_data: partial
connector:
  status: shipped
  module: patent_client_agents.usitc
  blockers: []
coverage:
  atlas_standalone_reason: out_of_scope
  order: 29
  last_verified: null
  wipo_st3_code: US
  data_types:
  - bulk_data
  access:
    method: rest_api
    auth: none
  status: external
  notes: 'Tariff-code reference data — out of IP-data scope but shipped via

    the shared USITC connector module. ``external`` for the same

    reason as DataWeb; do not build new IP tools against it.

    '
---

# USITC HTS — Harmonized Tariff Schedule

## What this source contains

U.S. International Trade Commission publishes this data product for non-IP reference data. The compatibility
manifest declares the following covered data types: bulk_data.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Tariff-code reference data — out of IP-data scope but shipped via
the shared USITC connector module. ``external`` for the same
reason as DataWeb; do not build new IP tools against it.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.usitc`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://hts.usitc.gov/)
