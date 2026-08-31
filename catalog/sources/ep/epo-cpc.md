---
id: EP/EPO/CPC
name: Cooperative Patent Classification (CPC)
jurisdictions:
- EP
institution: European Patent Office / U.S. Patent and Trademark Office
source_type: classification_database
official_url: https://www.cooperativepatentclassification.org/
last_verified: 2026-05-15
source_status: active
category: registered_ip
rights:
- patent
access:
  availability: credentialed
  audience: registered_users
  formats:
  - json
  automation_posture: byok_only
capabilities:
  bibliographic: none
  full_text: none
  prosecution: none
  legal_status: none
  assignments: none
  oppositions: none
  classification: partial
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.cpc
  blockers: []
coverage:
  order: 12
  wipo_st3_code: EP
  data_types:
  - classification
  access:
    method: rest_api
    auth: oauth2_client_credentials
    auth_env:
    - EPO_OPS_API_KEY
    - EPO_OPS_API_SECRET
  status: active
  category: registered_ip
  transport: mcp_proxy
---

# Cooperative Patent Classification (CPC)

## What this source contains

European Patent Office / U.S. Patent and Trademark Office publishes this data product for patent. The compatibility
manifest declares the following covered data types: classification.

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

The compatibility connector module is `patent_client_agents.cpc`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.cooperativepatentclassification.org/)
