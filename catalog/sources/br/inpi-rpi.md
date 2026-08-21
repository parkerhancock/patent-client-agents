---
id: BR/INPI/RPI
name: INPI Brazil — Revista da Propriedade Industrial (dados.gov.br)
jurisdictions:
- BR
institution: Instituto Nacional da Propriedade Industrial
source_type: data_feed
official_url: https://dados.gov.br/dados/conjuntos-dados/revista-da-propriedade-industrial-rpi
last_verified: 2026-05-16
source_status: active
category: registered_ip
rights:
- patent
- trademark
- design
- gi
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
  module: patent_client_agents.inpi_br_bulk
  blockers: []
coverage:
  order: 19
  wipo_st3_code: BR
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
  notes: 'Brazil''s weekly official IP bulletin (patents, trade marks,

    designs, GIs, IC topographies, software programs, technology

    contracts, and INPI communications). Open license per Decreto

    8.777/2016. The catalog API endpoint is the legacy CKAN

    ``package_show`` action on dados.gov.br; if the portal retires

    that route, only the bulk client needs to swap.

    '
---

# INPI Brazil — Revista da Propriedade Industrial (dados.gov.br)

## What this source contains

Instituto Nacional da Propriedade Industrial publishes this data product for patent, trademark, design, gi. The compatibility
manifest declares the following covered data types: bulk_data, bibliographic, legal_status.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Brazil's weekly official IP bulletin (patents, trade marks,
designs, GIs, IC topographies, software programs, technology
contracts, and INPI communications). Open license per Decreto
8.777/2016. The catalog API endpoint is the legacy CKAN
``package_show`` action on dados.gov.br; if the portal retires
that route, only the bulk client needs to swap.

## Access and connector assessment

The declared access method is `bulk_download` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.inpi_br_bulk`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://dados.gov.br/dados/conjuntos-dados/revista-da-propriedade-industrial-rpi)
