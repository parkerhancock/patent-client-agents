---
id: NZ/IPONZ/Patents
name: IPONZ New Zealand — Patents
jurisdictions:
- NZ
institution: Intellectual Property Office of New Zealand
source_type: registry
official_url: https://www.iponz.govt.nz/about-iponz/iponz-api/
last_verified: 2026-08-03
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
  classification: partial
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.iponz_new_zealand
  blockers: []
coverage:
  order: 78
  wipo_st3_code: NZ
  data_types:
  - bibliographic
  - full_text
  - legal_status
  - classification
  access:
    method: rest_api
    auth: api_key
    auth_env:
    - IPONZ_SUBSCRIPTION_KEY
  status: beta
  category: registered_ip
  transport: mcp_proxy
  notes: Public OpenAPI and XSD-contract tested with synthetic XML fixtures; live MBIE subscription compatibility
    is unverified. Private BYOK only. Optional caller-supplied bearer tokens use IPONZ_ACCESS_TOKEN.
---

# IPONZ New Zealand — Patents

## What this source contains

Intellectual Property Office of New Zealand publishes this data product for patent. The compatibility
manifest declares the following covered data types: bibliographic, full_text, legal_status, classification.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Public OpenAPI and XSD-contract tested with synthetic XML fixtures; live MBIE subscription compatibility is unverified. Private BYOK only. Optional caller-supplied bearer tokens use IPONZ_ACCESS_TOKEN.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `api_key`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.iponz_new_zealand`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.iponz.govt.nz/about-iponz/iponz-api/)
