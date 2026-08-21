---
id: DE/DPMA/Patents
name: DPMA Germany — Patents and Utility Models (DPMAconnectPlus)
jurisdictions:
- DE
institution: Deutsches Patent- und Markenamt
source_type: registry
official_url: https://dpmaconnect.dpma.de/
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
  full_text: none
  prosecution: none
  legal_status: partial
  assignments: none
  oppositions: none
  classification: partial
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.dpma_register
  blockers: []
coverage:
  order: 52
  wipo_st3_code: DE
  data_types:
  - bibliographic
  - classification
  - legal_status
  access:
    method: rest_api
    auth: account_required
    auth_env:
    - DPMA_CONNECTPLUS_USERNAME
    - DPMA_CONNECTPLUS_PASSWORD
  status: beta
  category: registered_ip
  transport: mcp_proxy
  notes: Mock-only tested with synthetic namespace-bearing XML fixtures; live compatibility is unverified.
    Covers patents and utility models. Basic Auth and a registered static IP are required. Private BYOK
    only. Community validation and sanitized response samples are welcome.
---

# DPMA Germany — Patents and Utility Models (DPMAconnectPlus)

## What this source contains

Deutsches Patent- und Markenamt publishes this data product for patent. The compatibility
manifest declares the following covered data types: bibliographic, classification, legal_status.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Mock-only tested with synthetic namespace-bearing XML fixtures; live compatibility is unverified. Covers patents and utility models. Basic Auth and a registered static IP are required. Private BYOK only. Community validation and sanitized response samples are welcome.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `account_required`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.dpma_register`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://dpmaconnect.dpma.de/)
