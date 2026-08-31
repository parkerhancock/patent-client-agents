---
id: JP/JPO
name: Japan Patent Office (JPO) — Open API
jurisdictions:
- JP
institution: Japan Patent Office
source_type: registry
official_url: https://ip-data.jpo.go.jp/
last_verified: 2026-05-15
source_status: active
category: registered_ip
rights:
- patent
- trademark
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
  prosecution: partial
  legal_status: partial
  assignments: none
  oppositions: none
  classification: none
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.jpo
  blockers: []
coverage:
  order: 23
  wipo_st3_code: JP
  data_types:
  - bibliographic
  - prosecution
  - legal_status
  access:
    method: rest_api
    auth: oauth2_password
    auth_env:
    - JPO_API_USERNAME
    - JPO_API_PASSWORD
  status: active
  category: registered_ip
  transport: mcp_proxy
---

# Japan Patent Office (JPO) — Open API

## What this source contains

Japan Patent Office publishes this data product for patent, trademark, design. The compatibility
manifest declares the following covered data types: bibliographic, prosecution, legal_status.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `oauth2_password`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.jpo`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://ip-data.jpo.go.jp/)
