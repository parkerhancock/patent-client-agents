---
id: AU/IPAustralia/Bulk
name: IP Australia — IP RAPID (data.gov.au bulk register)
jurisdictions:
- AU
institution: IP Australia
source_type: data_feed
official_url: https://data.gov.au/data/dataset/intellectual-property-government-open-data
last_verified: 2026-05-16
source_status: active
category: registered_ip
rights:
- patent
- trademark
- design
- plant_variety
access:
  availability: public
  audience: public
  formats:
  - unknown
  automation_posture: permitted
capabilities:
  bibliographic: partial
  full_text: none
  prosecution: none
  legal_status: partial
  assignments: none
  oppositions: none
  classification: none
  bulk_data: partial
connector:
  status: shipped
  module: patent_client_agents.ip_australia_bulk
  blockers: []
coverage:
  order: 18
  wipo_st3_code: AU
  data_types:
  - bulk_data
  - bibliographic
  - legal_status
  access:
    method: bulk_download
    auth: none
  status: active
  category: registered_ip
  transport: mcp_proxy
---

# IP Australia — IP RAPID (data.gov.au bulk register)

## What this source contains

IP Australia publishes this data product for patent, trademark, design, plant_variety. The compatibility
manifest declares the following covered data types: bulk_data, bibliographic, legal_status.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

## Access and connector assessment

The declared access method is `bulk_download` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.ip_australia_bulk`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://data.gov.au/data/dataset/intellectual-property-government-open-data)
