---
id: CH/IPI/Patents
name: Swiss IPI — Patents and Patent Publications (Swissreg datadelivery)
jurisdictions:
- CH
institution: Swiss Federal Institute of Intellectual Property
source_type: registry
official_url: https://www.swissreg.ch/
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
  module: patent_client_agents.ipi_swissreg
  blockers: []
coverage:
  order: 49
  wipo_st3_code: CH
  data_types:
  - bibliographic
  - classification
  - full_text
  - legal_status
  access:
    method: rest_api
    auth: oauth2_password
    auth_env:
    - IPI_DATA_USERNAME
    - IPI_DATA_PASSWORD
  status: beta
  category: registered_ip
  transport: mcp_proxy
  notes: Schema-tested with synthetic XML fixtures derived from public IPI XSDs; live account compatibility
    is unverified. Covers the unified CH and LI patent territory. Signed Terms of Use and an IPI account
    are required. Optional MFA uses IPI_DATA_TOTP_TOKEN. Community validation and sanitized response samples
    are welcome.
---

# Swiss IPI — Patents and Patent Publications (Swissreg datadelivery)

## What this source contains

Swiss Federal Institute of Intellectual Property publishes this data product for patent. The compatibility
manifest declares the following covered data types: bibliographic, classification, full_text, legal_status.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Schema-tested with synthetic XML fixtures derived from public IPI XSDs; live account compatibility is unverified. Covers the unified CH and LI patent territory. Signed Terms of Use and an IPI account are required. Optional MFA uses IPI_DATA_TOTP_TOKEN. Community validation and sanitized response samples are welcome.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `oauth2_password`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.ipi_swissreg`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.swissreg.ch/)
