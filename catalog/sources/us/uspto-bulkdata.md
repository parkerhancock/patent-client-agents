---
id: US/USPTO/BulkData
name: USPTO Bulk Data Storage System (BDSS)
jurisdictions:
- US
institution: U.S. Patent and Trademark Office
source_type: data_feed
official_url: https://data.uspto.gov/bulkdata
last_verified: 2026-05-15
source_status: active
category: registered_ip
rights:
- patent
- trademark
access:
  availability: public
  audience: public
  formats:
  - json
  automation_posture: permitted
capabilities:
  bibliographic: none
  full_text: none
  prosecution: none
  legal_status: none
  assignments: none
  oppositions: none
  classification: none
  bulk_data: partial
connector:
  status: shipped
  module: patent_client_agents.uspto_bulkdata
  blockers: []
coverage:
  order: 6
  wipo_st3_code: US
  data_types:
  - bulk_data
  access:
    method: rest_api
    auth: none
  status: active
  category: registered_ip
  transport: mcp_proxy
---

# USPTO Bulk Data Storage System (BDSS)

## What this source contains

U.S. Patent and Trademark Office publishes this data product for patent, trademark. The compatibility
manifest declares the following covered data types: bulk_data.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.uspto_bulkdata`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://data.uspto.gov/bulkdata)
