---
id: FI/PRH/Trademarks
name: PRH Finland — National Trademarks
jurisdictions:
- FI
institution: Patentti- ja rekisterihallitus (PRH)
source_type: registry
official_url: https://www.prh.fi/en/intellectualpropertyrights.html
last_verified: 2026-05-19
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
  module: patent_client_agents.prh_fi
  blockers: []
coverage:
  order: 72
  wipo_st3_code: FI
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
  notes: Nice classification; ~283k national TMs back to 1891. Mark images served at /opendata/trademark/image/...
    (URL-only on this row; no download surface in v1). EUTM coverage via planned EUIPO connector; Madrid
    IRs via WIPO Madrid Monitor.
---

# PRH Finland — National Trademarks

## What this source contains

Patentti- ja rekisterihallitus (PRH) publishes this data product for trademark. The compatibility
manifest declares the following covered data types: bibliographic, legal_status, classification.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Nice classification; ~283k national TMs back to 1891. Mark images served at /opendata/trademark/image/... (URL-only on this row; no download surface in v1). EUTM coverage via planned EUIPO connector; Madrid IRs via WIPO Madrid Monitor.

## Access and connector assessment

The declared access method is `rest_api` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.prh_fi`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.prh.fi/en/intellectualpropertyrights.html)
