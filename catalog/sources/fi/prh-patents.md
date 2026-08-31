---
id: FI/PRH/Patents
name: PRH Finland — National Patents, UMs, SPCs, EP-FI
jurisdictions:
- FI
institution: Patentti- ja rekisterihallitus (PRH)
source_type: registry
official_url: https://www.prh.fi/en/intellectualpropertyrights.html
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
  prosecution: partial
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
  order: 71
  wipo_st3_code: FI
  data_types:
  - bibliographic
  - prosecution
  - legal_status
  - classification
  access:
    method: rest_api
    auth: none
  status: active
  category: registered_ip
  transport: mcp_proxy
  notes: Search + per-record GET. PatentDossier (national) / PatentDossierUtilityModel (UM) / PatentEurope
    (EP-FI) / Spc all surface through the same endpoints. Server-side cap of 3,000 rows per query — narrow
    filters required for high-population applicants. The patent-search body has 30 fields with three inclusion-filter
    lists (dossierStatus / patentTypes / publicationTypes) supplied with full defaults by the client.
---

# PRH Finland — National Patents, UMs, SPCs, EP-FI

## What this source contains

Patentti- ja rekisterihallitus (PRH) publishes this data product for patent. The compatibility
manifest declares the following covered data types: bibliographic, prosecution, legal_status, classification.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Search + per-record GET. PatentDossier (national) / PatentDossierUtilityModel (UM) / PatentEurope (EP-FI) / Spc all surface through the same endpoints. Server-side cap of 3,000 rows per query — narrow filters required for high-population applicants. The patent-search body has 30 fields with three inclusion-filter lists (dossierStatus / patentTypes / publicationTypes) supplied with full defaults by the client.

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
