---
id: BR/INPI/Fees/Patent
name: INPI Brazil — Fees (Patent)
jurisdictions:
- BR
institution: Instituto Nacional da Propriedade Industrial (INPI)
source_type: fee_schedule
official_url: https://www.gov.br/inpi/en/costs-and-payment
last_verified: 2026-05-19
source_status: active
category: fees
rights:
- patent
access:
  availability: public
  audience: public
  formats:
  - html
  automation_posture: unclear
capabilities:
  current_schedule: partial
  effective_date: partial
  historical_schedule: unknown
  machine_readable: partial
  calculator: unknown
connector:
  status: shipped
  module: patent_client_agents.fees
  blockers: []
coverage:
  order: 106
  wipo_st3_code: BR
  data_types:
  - fees
  access:
    method: website_scrape
    auth: none
  status: active
  category: fees
  transport: mcp_proxy
  update_strategy: live_proxy
  update_cadence: irregular
  notes: 'INPI Brazil patent fees in BRL covering invention patents (20-yr term), utility model patents
    (15-yr term), and certificates of addition. Source is the English-language Schedule of Fees PDF at
    gov.br/inpi/en/costs-and-payment/schedule-of-fees-patents.pdf (the pt-BR landing at /servicos/tabelas-de-retribuicao
    is Plone role-restricted "Conteúdo Restrito" but the EN PDFs under /en/costs-and-payment/ are anonymously
    accessible — path discovered 2026-05-19). 60 fee codes expanded to 272 FeeItems via per-year annuity
    bands × large/small tier siblings. The "discounted" column maps to EntityTier.small per Resolution
    251/2019 §I.5 (up to 60% reduction for individuals, micro-enterprises, SMEs, cooperatives, ICTs, non-profits,
    and public bodies). Statutory basis Lei 9.279/1996 + Ordinance MDIC 39/2014 + ME Ordinance 516/2019
    + INPI Resolution 251/2019. v1 GAPS: (a) multi-tier per-claim surcharges published as prose not numeric
    columns; (b) PCT-section variable-amount rows; (c) Portaria 10/2025 update not yet reflected in the
    EN PDF.'
---

# INPI Brazil — Fees (Patent)

## What this source contains

Instituto Nacional da Propriedade Industrial (INPI) publishes this data product for patent. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

INPI Brazil patent fees in BRL covering invention patents (20-yr term), utility model patents (15-yr term), and certificates of addition. Source is the English-language Schedule of Fees PDF at gov.br/inpi/en/costs-and-payment/schedule-of-fees-patents.pdf (the pt-BR landing at /servicos/tabelas-de-retribuicao is Plone role-restricted "Conteúdo Restrito" but the EN PDFs under /en/costs-and-payment/ are anonymously accessible — path discovered 2026-05-19). 60 fee codes expanded to 272 FeeItems via per-year annuity bands × large/small tier siblings. The "discounted" column maps to EntityTier.small per Resolution 251/2019 §I.5 (up to 60% reduction for individuals, micro-enterprises, SMEs, cooperatives, ICTs, non-profits, and public bodies). Statutory basis Lei 9.279/1996 + Ordinance MDIC 39/2014 + ME Ordinance 516/2019 + INPI Resolution 251/2019. v1 GAPS: (a) multi-tier per-claim surcharges published as prose not numeric columns; (b) PCT-section variable-amount rows; (c) Portaria 10/2025 update not yet reflected in the EN PDF.

## Access and connector assessment

The declared access method is `website_scrape` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.fees`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.gov.br/inpi/en/costs-and-payment)
