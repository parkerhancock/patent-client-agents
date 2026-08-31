---
id: EP/EPO/OPS
name: EPO Open Patent Services (OPS)
jurisdictions:
- EP
institution: European Patent Office
source_type: registry
official_url: https://developers.epo.org/ops-v3-2
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
  bibliographic: partial
  full_text: partial
  prosecution: none
  legal_status: partial
  assignments: none
  oppositions: none
  classification: none
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.epo_ops
  blockers: []
coverage:
  order: 11
  wipo_st3_code: EP
  data_types:
  - bibliographic
  - full_text
  - legal_status
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

# EPO Open Patent Services (OPS)

## What this source contains

European Patent Office publishes this data product for patent. The compatibility
manifest declares the following covered data types: bibliographic, full_text, legal_status.

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

The compatibility connector module is `patent_client_agents.epo_ops`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://developers.epo.org/ops-v3-2)
