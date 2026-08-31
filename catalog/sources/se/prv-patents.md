---
id: SE/PRV/Patents
name: PRV Sweden — National Patents
jurisdictions:
- SE
institution: Patent- och registreringsverket (PRV)
source_type: registry
official_url: https://www.prv.se/en/knowledge-and-support/search-databases/
last_verified: 2026-05-19
source_status: active
category: registered_ip
rights:
- patent
access:
  availability: public
  audience: public
  formats:
  - json
  automation_posture: permitted
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
  module: patent_client_agents.prv_se
  blockers: []
coverage:
  order: 67
  wipo_st3_code: SE
  data_types:
  - bibliographic
  - legal_status
  - classification
  access:
    method: rest_api
    auth: none
  status: active
  category: registered_ip
  transport: mcp_proxy
  notes: Simple-search + per-record GET (applicationType=NAT default). EP-validated patents reachable
    via EPO OPS at INPADOC fidelity; this entry covers the SE-national-only slice. SPC search endpoint
    returned HTTP 500 on probe — deferred to v0.2.
---

# PRV Sweden — National Patents

## What this source contains

Patent- och registreringsverket (PRV) publishes this data product for patent. The compatibility
manifest declares the following covered data types: bibliographic, legal_status, classification.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Simple-search + per-record GET (applicationType=NAT default). EP-validated patents reachable via EPO OPS at INPADOC fidelity; this entry covers the SE-national-only slice. SPC search endpoint returned HTTP 500 on probe — deferred to v0.2.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.prv_se`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.prv.se/en/knowledge-and-support/search-databases/)
