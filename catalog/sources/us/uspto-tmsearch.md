---
id: US/USPTO/TMSearch
name: USPTO Trademark Search (TESS replacement)
jurisdictions:
- US
institution: U.S. Patent and Trademark Office
source_type: registry
official_url: https://tmsearch.uspto.gov/
last_verified: 2026-05-15
source_status: active
category: registered_ip
rights:
- trademark
access:
  availability: credentialed
  audience: registered_users
  formats:
  - html
  automation_posture: unclear
capabilities:
  bibliographic: partial
  full_text: none
  prosecution: none
  legal_status: none
  assignments: none
  oppositions: none
  classification: none
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.uspto_tmsearch
  blockers: []
coverage:
  order: 8
  wipo_st3_code: US
  data_types:
  - bibliographic
  access:
    method: website_scrape
    auth: cookie_token
  status: active
  category: registered_ip
  transport: mcp_proxy
---

# USPTO Trademark Search (TESS replacement)

## What this source contains

U.S. Patent and Trademark Office publishes this data product for trademark. The compatibility
manifest declares the following covered data types: bibliographic.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

## Access and connector assessment

The declared access method is `website_scrape` with
authentication `cookie_token`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.uspto_tmsearch`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://tmsearch.uspto.gov/)
