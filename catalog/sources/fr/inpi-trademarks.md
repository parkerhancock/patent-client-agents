---
id: FR/INPI/Trademarks
name: INPI France — National Trademarks
jurisdictions:
- FR
institution: Institut National de la Propriété Industrielle (INPI)
source_type: registry
official_url: https://data.inpi.fr/content/editorial/apis_pi
last_verified: 2026-05-17
source_status: active
category: registered_ip
rights:
- trademark
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
  module: patent_client_agents.inpi_pi
  blockers: []
coverage:
  order: 65
  wipo_st3_code: FR
  data_types:
  - bibliographic
  - legal_status
  - classification
  access:
    method: rest_api
    auth: cookie_token
    auth_env:
    - INPI_USERNAME
    - INPI_PASSWORD
  status: active
  category: registered_ip
  transport: mcp_proxy
  notes: WIPO ST.66 v1.0. BYOK — production deployers must register a personal data.inpi.fr account. ``cookie_token``
    is the closest closed-vocabulary match for INPI's session-bearer + XSRF flow.
---

# INPI France — National Trademarks

## What this source contains

Institut National de la Propriété Industrielle (INPI) publishes this data product for trademark. The compatibility
manifest declares the following covered data types: bibliographic, legal_status, classification.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

WIPO ST.66 v1.0. BYOK — production deployers must register a personal data.inpi.fr account. ``cookie_token`` is the closest closed-vocabulary match for INPI's session-bearer + XSRF flow.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `cookie_token`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.inpi_pi`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://data.inpi.fr/content/editorial/apis_pi)
