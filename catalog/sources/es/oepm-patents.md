---
id: ES/OEPM/Patents
name: OEPM Spain — Patents and Utility Models (CEO)
jurisdictions:
- ES
institution: Oficina Española de Patentes y Marcas
source_type: registry
official_url: https://www.oepm.es/en/propiedad_industrial/servicios_de_informacion/web_services/
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
  prosecution: partial
  legal_status: partial
  assignments: none
  oppositions: none
  classification: none
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.oepm_spain
  blockers: []
coverage:
  order: 75
  wipo_st3_code: ES
  data_types:
  - bibliographic
  - prosecution
  - legal_status
  access:
    method: rest_api
    auth: account_required
    auth_env:
    - OEPM_CEO_USERNAME
    - OEPM_CEO_PASSWORD
  status: beta
  category: registered_ip
  transport: mcp_proxy
  notes: Exact-file SOAP lookups only. Tested against the public CEO WSDL with synthetic XML fixtures;
    live account compatibility is unverified. Private BYOK only.
---

# OEPM Spain — Patents and Utility Models (CEO)

## What this source contains

Oficina Española de Patentes y Marcas publishes this data product for patent. The compatibility
manifest declares the following covered data types: bibliographic, prosecution, legal_status.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Exact-file SOAP lookups only. Tested against the public CEO WSDL with synthetic XML fixtures; live account compatibility is unverified. Private BYOK only.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `account_required`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.oepm_spain`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.oepm.es/en/propiedad_industrial/servicios_de_informacion/web_services/)
