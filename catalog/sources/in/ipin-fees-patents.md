---
id: IN/IPIN/Fees/Patents
name: IPO India Fee Schedule — Patents
jurisdictions:
- IN
institution: Office of the Controller General of Patents, Designs and Trade Marks (CGPDTM)
source_type: fee_schedule
official_url: https://ipindia.gov.in/form-and-fees.htm
last_verified: 2026-05-18
source_status: active
category: fees
rights:
- patent
access:
  availability: public
  audience: public
  formats:
  - pdf
  automation_posture: permitted
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
  order: 100
  wipo_st3_code: IN
  data_types:
  - fees
  access:
    method: pdf_download
    auth: none
  status: active
  category: fees
  transport: mcp_proxy
  update_strategy: live_proxy
  update_cadence: irregular
  notes: 'Scraped from the canonical Schedule 1 PDF (ipindia.gov.in/frontend/pdf/forms_and_official_fees/Schedule_1.pdf).
    pypdf + regex extraction. INR. 4 rate columns: small-applicant + other(s) × e-filing + paper. Paper-filing
    rows flagged via FeeCondition(trigger=paper_filing). All 18 renewal years (3-20) captured cleanly.
    Main numbered items (filing, exam, etc.) are PDF-structure-sensitive — a sanity check drops rows where
    rate columns appear misaligned (paper < e-file is impossible), so non-renewal coverage is partial
    in v1. PCT- specific fees live in Schedule 5 (separate PDF) and ship as a follow-up. Patents Rules
    2003 Schedule 1 (as amended through Patents (Amendment) Rules 2024).'
---

# IPO India Fee Schedule — Patents

## What this source contains

Office of the Controller General of Patents, Designs and Trade Marks (CGPDTM) publishes this data product for patent. The compatibility
manifest declares the following covered data types: fees.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Scraped from the canonical Schedule 1 PDF (ipindia.gov.in/frontend/pdf/forms_and_official_fees/Schedule_1.pdf). pypdf + regex extraction. INR. 4 rate columns: small-applicant + other(s) × e-filing + paper. Paper-filing rows flagged via FeeCondition(trigger=paper_filing). All 18 renewal years (3-20) captured cleanly. Main numbered items (filing, exam, etc.) are PDF-structure-sensitive — a sanity check drops rows where rate columns appear misaligned (paper < e-file is impossible), so non-renewal coverage is partial in v1. PCT- specific fees live in Schedule 5 (separate PDF) and ship as a follow-up. Patents Rules 2003 Schedule 1 (as amended through Patents (Amendment) Rules 2024).

## Access and connector assessment

The declared access method is `pdf_download` with
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

- [Official source](https://ipindia.gov.in/form-and-fees.htm)
