---
id: US/USCO/Registrations
name: U.S. Copyright Office — Public Records
jurisdictions:
- US
institution: U.S. Copyright Office (Library of Congress)
source_type: registry
official_url: https://publicrecords.copyright.gov/
last_verified: 2026-05-15
source_status: active
category: registered_ip
rights:
- copyright
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
  assignments: partial
  oppositions: none
  classification: none
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.copyright
  blockers: []
coverage:
  order: 10
  wipo_st3_code: US
  data_types:
  - bibliographic
  - assignments
  - legal_status
  access:
    method: rest_api
    auth: none
  status: active
  category: registered_ip
  transport: mcp_proxy
---

# U.S. Copyright Office — Public Records

## What this source contains

U.S. Copyright Office (Library of Congress) publishes this data product for copyright. The compatibility
manifest declares the following covered data types: bibliographic, assignments, legal_status.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.copyright`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://publicrecords.copyright.gov/)
