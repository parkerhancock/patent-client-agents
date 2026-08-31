---
id: US/USITC/DataWeb
name: USITC DataWeb — trade statistics
jurisdictions:
- US
institution: U.S. International Trade Commission
source_type: external_dataset
official_url: https://dataweb.usitc.gov/
last_verified: 2026-05-15
source_status: active
category: external
rights: []
access:
  availability: credentialed
  audience: registered_users
  formats:
  - json
  automation_posture: byok_only
capabilities:
  query_api: partial
  bulk_data: partial
connector:
  status: shipped
  module: patent_client_agents.usitc
  blockers: []
coverage:
  atlas_standalone_reason: out_of_scope
  order: 28
  last_verified: null
  wipo_st3_code: US
  data_types:
  - bulk_data
  access:
    method: rest_api
    auth: api_key
    auth_env:
    - USITC_DATAWEB_TOKEN
  status: external
  notes: 'Trade-stats backend reachable through the shared USITC connector

    module, but trade statistics are out of patent-client-agents''

    IP-data scope. Kept as ``external`` so the MCP tools that already

    ship aren''t dropped from the catalog; new IP work should not depend

    on this surface.

    '
---

# USITC DataWeb — trade statistics

## What this source contains

U.S. International Trade Commission publishes this data product for non-IP reference data. The compatibility
manifest declares the following covered data types: bulk_data.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Trade-stats backend reachable through the shared USITC connector
module, but trade statistics are out of patent-client-agents'
IP-data scope. Kept as ``external`` so the MCP tools that already
ship aren't dropped from the catalog; new IP work should not depend
on this surface.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `api_key`. Consult the official source
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

- [Official source](https://dataweb.usitc.gov/)
