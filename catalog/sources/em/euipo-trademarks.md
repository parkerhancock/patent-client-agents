---
id: EM/EUIPO/Trademarks
name: EUIPO — European Union Trademarks
jurisdictions:
- EM
institution: European Union Intellectual Property Office
source_type: registry
official_url: https://api.euipo.europa.eu/trademark-search/
last_verified: 2026-05-15
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
  classification: none
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.euipo_trademarks
  blockers: []
coverage:
  order: 13
  wipo_st3_code: EM
  data_types:
  - bibliographic
  - legal_status
  access:
    method: rest_api
    auth: oauth2_client_credentials
    auth_env:
    - EUIPO_CLIENT_ID
    - EUIPO_CLIENT_SECRET
  status: active
  category: registered_ip
  transport: mcp_proxy
---

# EUIPO — European Union Trademarks

## What this source contains

European Union Intellectual Property Office publishes this data product for trademark. The compatibility
manifest declares the following covered data types: bibliographic, legal_status.

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

The compatibility connector module is `patent_client_agents.euipo_trademarks`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://api.euipo.europa.eu/trademark-search/)
