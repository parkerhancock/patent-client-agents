---
id: SE/PRV/SPCs
name: PRV Sweden — Supplementary Protection Certificates
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
  classification: none
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.prv_se
  blockers: []
coverage:
  order: 70
  wipo_st3_code: SE
  data_types:
  - bibliographic
  - legal_status
  access:
    method: rest_api
    auth: none
  status: active
  category: registered_ip
  transport: mcp_proxy
  notes: Swedish SPCs (patent-term extensions under EU Reg. 469/2009 + 1610/96). Uses an advanced-search
    body where each filter wraps as ``{value, searchType}``; the client requires at least one filter because
    an empty body returns HTTP 500.
---

# PRV Sweden — Supplementary Protection Certificates

## What this source contains

Patent- och registreringsverket (PRV) publishes this data product for patent. The compatibility
manifest declares the following covered data types: bibliographic, legal_status.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Swedish SPCs (patent-term extensions under EU Reg. 469/2009 + 1610/96). Uses an advanced-search body where each filter wraps as ``{value, searchType}``; the client requires at least one filter because an empty body returns HTTP 500.

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
