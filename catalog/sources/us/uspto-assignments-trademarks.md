---
id: US/USPTO/Assignments/Trademarks
name: USPTO Trademark Assignment Center
jurisdictions:
- US
institution: U.S. Patent and Trademark Office
source_type: assignment_database
official_url: https://assignmentcenter.uspto.gov/
last_verified: 2026-05-15
source_status: active
category: registered_ip
rights:
- trademark
access:
  availability: public
  audience: public
  formats:
  - json
  automation_posture: permitted
capabilities:
  bibliographic: none
  full_text: none
  prosecution: none
  legal_status: none
  assignments: partial
  oppositions: none
  classification: none
  bulk_data: none
connector:
  status: shipped
  module: patent_client_agents.uspto_trademark_assignments
  blockers: []
coverage:
  order: 9
  wipo_st3_code: US
  data_types:
  - assignments
  access:
    method: rest_api
    auth: none
  status: active
  category: registered_ip
  transport: mcp_proxy
---

# USPTO Trademark Assignment Center

## What this source contains

U.S. Patent and Trademark Office publishes this data product for trademark. The compatibility
manifest declares the following covered data types: assignments.

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

The compatibility connector module is `patent_client_agents.uspto_trademark_assignments`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://assignmentcenter.uspto.gov/)
