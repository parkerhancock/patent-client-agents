---
id: US/USPTO/TSDR
name: USPTO Trademark Status & Document Retrieval (TSDR)
jurisdictions:
- US
institution: U.S. Patent and Trademark Office
source_type: registry
official_url: https://tsdrapi.uspto.gov/
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
  prosecution: partial
  legal_status: partial
  assignments: none
  oppositions: none
  classification: none
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.uspto_tsdr
  blockers: []
coverage:
  order: 7
  wipo_st3_code: US
  data_types:
  - bibliographic
  - prosecution
  - legal_status
  access:
    method: rest_api
    auth: api_key
    auth_env:
    - USPTO_TSDR_API_KEY
  status: active
  category: registered_ip
  transport: mcp_proxy
---

# USPTO Trademark Status & Document Retrieval (TSDR)

## What this source contains

U.S. Patent and Trademark Office publishes this data product for trademark. The compatibility
manifest declares the following covered data types: bibliographic, prosecution, legal_status.

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

The compatibility connector module is `patent_client_agents.uspto_tsdr`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://tsdrapi.uspto.gov/)
