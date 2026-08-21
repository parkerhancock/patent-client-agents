---
id: AU/IPAustralia/Designs
name: IP Australia — Australian Designs Search
jurisdictions:
- AU
institution: IP Australia
source_type: registry
official_url: https://www.ipaustralia.gov.au/tools-and-research/professional-resources/data-services
last_verified: 2026-05-16
source_status: active
category: registered_ip
rights:
- design
access:
  availability: credentialed
  audience: registered_users
  formats:
  - json
  automation_posture: byok_only
capabilities:
  bibliographic: partial
  full_text: none
  prosecution: none
  legal_status: partial
  assignments: none
  oppositions: none
  classification: partial
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.ip_australia_designs
  blockers: []
coverage:
  order: 17
  wipo_st3_code: AU
  data_types:
  - bibliographic
  - legal_status
  - classification
  access:
    method: rest_api
    auth: oauth2_client_credentials
    auth_env:
    - IPAUSTRALIA_CLIENT_ID
    - IPAUSTRALIA_CLIENT_SECRET
  status: active
  category: registered_ip
  transport: mcp_proxy
---

# IP Australia — Australian Designs Search

## What this source contains

IP Australia publishes this data product for design. The compatibility
manifest declares the following covered data types: bibliographic, legal_status, classification.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `oauth2_client_credentials`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.ip_australia_designs`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.ipaustralia.gov.au/tools-and-research/professional-resources/data-services)
