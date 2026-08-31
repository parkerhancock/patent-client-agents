---
id: IL/ILPO/TradeMarks
name: ILPO Israel — Trade Marks (data.gov.il)
jurisdictions:
- IL
institution: Israel Patent Office (Ministry of Justice)
source_type: data_feed
official_url: https://data.gov.il/dataset/trademarks
last_verified: 2026-05-16
source_status: active
category: registered_ip
rights:
- trademark
access:
  availability: public
  audience: public
  formats:
  - unknown
  automation_posture: permitted
capabilities:
  bibliographic: partial
  full_text: none
  prosecution: none
  legal_status: partial
  assignments: none
  oppositions: none
  classification: none
  bulk_data: partial
connector:
  status: shipped
  module: patent_client_agents.ilpo_tm
  blockers: []
coverage:
  order: 20
  wipo_st3_code: IL
  data_types:
  - bulk_data
  - bibliographic
  - legal_status
  access:
    method: bulk_download
    auth: none
  status: active
  category: registered_ip
  transport: mcp_proxy
  notes: 'data.gov.il CKAN catalog publishes the ILPO national TM register

    under a free open-data licence. The live ILPO TM portal at

    trademarks.justice.gov.il is ASP.NET / Kendo UI with no documented

    API — the CKAN feed is the proper on-ramp.

    '
---

# ILPO Israel — Trade Marks (data.gov.il)

## What this source contains

Israel Patent Office (Ministry of Justice) publishes this data product for trademark. The compatibility
manifest declares the following covered data types: bulk_data, bibliographic, legal_status.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

data.gov.il CKAN catalog publishes the ILPO national TM register
under a free open-data licence. The live ILPO TM portal at
trademarks.justice.gov.il is ASP.NET / Kendo UI with no documented
API — the CKAN feed is the proper on-ramp.

## Access and connector assessment

The declared access method is `bulk_download` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.ilpo_tm`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://data.gov.il/dataset/trademarks)
