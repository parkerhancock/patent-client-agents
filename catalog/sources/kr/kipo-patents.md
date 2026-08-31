---
id: KR/KIPO/Patents
name: KIPO Korea — Patents and Utility Models (KIPRIS Plus)
jurisdictions:
- KR
institution: Korean Intellectual Property Office (KIPO)
source_type: registry
official_url: https://plus.kipris.or.kr/eng/
last_verified: 2026-05-17
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
  module: patent_client_agents.kipo_kipris
  blockers: []
coverage:
  order: 62
  wipo_st3_code: KR
  data_types:
  - bibliographic
  - classification
  - legal_status
  access:
    method: rest_api
    auth: api_key
    auth_env:
    - KIPO_KIPRIS_API_KEY
  status: active
  category: registered_ip
  transport: mcp_proxy
---

# KIPO Korea — Patents and Utility Models (KIPRIS Plus)

## What this source contains

Korean Intellectual Property Office (KIPO) publishes this data product for patent. The compatibility
manifest declares the following covered data types: bibliographic, classification, legal_status.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `api_key`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.kipo_kipris`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://plus.kipris.or.kr/eng/)
