---
id: TW/TIPO/Trademarks
name: TIPO Taiwan — Trademarks
jurisdictions:
- TW
institution: Intellectual Property Office, Ministry of Economic Affairs (TIPO/MOEA)
source_type: registry
official_url: https://cloud.tipo.gov.tw/S220/opdata/
last_verified: 2026-05-16
source_status: active
category: registered_ip
rights:
- trademark
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
  module: patent_client_agents.tipo_opdata
  blockers: []
coverage:
  order: 61
  wipo_st3_code: TW
  data_types:
  - bibliographic
  - legal_status
  - classification
  access:
    method: rest_api
    auth: api_key
    auth_env:
    - TIPO_API_KEY
  status: active
  category: registered_ip
  transport: mcp_proxy
  notes: Nice classification; image URLs only (no rendering in v1)
---

# TIPO Taiwan — Trademarks

## What this source contains

Intellectual Property Office, Ministry of Economic Affairs (TIPO/MOEA) publishes this data product for trademark. The compatibility
manifest declares the following covered data types: bibliographic, legal_status, classification.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Nice classification; image URLs only (no rendering in v1)

## Access and connector assessment

The declared access method is `rest_api` with
authentication `api_key`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.tipo_opdata`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://cloud.tipo.gov.tw/S220/opdata/)
