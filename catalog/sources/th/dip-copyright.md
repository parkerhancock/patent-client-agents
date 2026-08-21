---
id: TH/DIP/Copyright
name: Thailand DIP — Copyright Notifications and Music Copyright
jurisdictions:
- TH
institution: Department of Intellectual Property, Thailand
source_type: registry
official_url: https://api.ipthailand.go.th/data-exchange/
last_verified: 2026-08-03
source_status: active
category: registered_ip
rights:
- copyright
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
  legal_status: none
  assignments: none
  oppositions: none
  classification: none
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.thai_dip
  blockers: []
coverage:
  order: 84
  wipo_st3_code: TH
  data_types:
  - bibliographic
  access:
    method: rest_api
    auth: api_key
    auth_env:
    - DIP_DATA_EXCHANGE_TOKEN
  status: beta
  category: registered_ip
  transport: mcp_proxy
  notes: Thailand uses a voluntary copyright notification dataset; this row does not imply constitutive
    registration. Tested with catalogue-derived synthetic fixtures; live compatibility is unverified.
    Private BYOK only.
---

# Thailand DIP — Copyright Notifications and Music Copyright

## What this source contains

Department of Intellectual Property, Thailand publishes this data product for copyright. The compatibility
manifest declares the following covered data types: bibliographic.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Thailand uses a voluntary copyright notification dataset; this row does not imply constitutive registration. Tested with catalogue-derived synthetic fixtures; live compatibility is unverified. Private BYOK only.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `api_key`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.thai_dip`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://api.ipthailand.go.th/data-exchange/)
