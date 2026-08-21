---
id: FR/INPI/Fees/Patent
name: INPI France — Fees (Patent)
jurisdictions:
- FR
institution: Institut National de la Propriété Industrielle (INPI)
source_type: fee_schedule
official_url: https://www.inpi.fr/ressources/propriete-intellectuelle/tarifs-procedures-et-prestations-de-linpi
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
  order: 108
  wipo_st3_code: FR
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
  notes: INPI France patent + utility-certificate + SPC fees in EUR. Source is the "Tarifs des procédures
    applicables au 27 avril 2026" PDF linked from inpi.fr/ressources/propriete-intellectuelle/tarifs-procedures-et-prestations-de-linpi
    and fetched via the inpi-block/download-document?id=20516 endpoint (anonymously accessible). Curated
    catalog of 14 patent entries (filing, search, claims-over-10 surcharge, grant, opposition, SPC) plus
    per-year annuity rows extracted for years 2-20 + SPC annual fee at year=21. The reduced rate applies
    to natural persons, non-profit research/education organisations, and companies <1000 employees with
    <25% non-qualifying capital. Statutory basis CPI Articles R.411-17 et seq.
---

# INPI France — Fees (Patent)

## What this source contains

Institut National de la Propriété Industrielle (INPI) publishes this data product for patent. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

INPI France patent + utility-certificate + SPC fees in EUR. Source is the "Tarifs des procédures applicables au 27 avril 2026" PDF linked from inpi.fr/ressources/propriete-intellectuelle/tarifs-procedures-et-prestations-de-linpi and fetched via the inpi-block/download-document?id=20516 endpoint (anonymously accessible). Curated catalog of 14 patent entries (filing, search, claims-over-10 surcharge, grant, opposition, SPC) plus per-year annuity rows extracted for years 2-20 + SPC annual fee at year=21. The reduced rate applies to natural persons, non-profit research/education organisations, and companies <1000 employees with <25% non-qualifying capital. Statutory basis CPI Articles R.411-17 et seq.

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

- [Official source](https://www.inpi.fr/ressources/propriete-intellectuelle/tarifs-procedures-et-prestations-de-linpi)
