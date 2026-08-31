---
id: US/CAFC/Opinions
name: U.S. Court of Appeals for the Federal Circuit — opinions and orders
jurisdictions:
- US
institution: U.S. Court of Appeals for the Federal Circuit
source_type: judgment_database
official_url: https://www.cafc.uscourts.gov/home/case-information/opinions-orders/
last_verified: 2026-08-21
source_status: active
rights:
- patent
- trademark
access:
  availability: public
  audience: public
  formats:
  - html
  - pdf
  automation_posture: unclear
capabilities:
  pending_cases: none
  closed_cases: partial
  party_search: partial
  broad_discovery: partial
  exact_case_lookup: partial
  docket_events: none
  filed_documents: partial
  decisions: full
  patent_identifiers: none
connector:
  status: shipped
  module: patent_client_agents.cafc
  blockers: []
category: adjudicative_records
coverage:
  order: 43
  name: U.S. Court of Appeals for the Federal Circuit — Opinions
  last_verified: 2026-05-15
  wipo_st3_code: US
  data_types:
  - case_law
  - litigation
  access:
    method: website_scrape
    auth: none
  status: active
  category: substantive_law
  transport: mcp_proxy
  update_strategy: live_proxy
  update_cadence: weekly
---

# U.S. Court of Appeals for the Federal Circuit — opinions and orders

## What this source contains

The Federal Circuit publishes opinions, Rule 36 judgments, and selected orders
with release date, appeal number, origin, case name, document type,
precedential status, and a linked PDF. The court states that opinions and select
orders from October 1, 2004 onward are publicly available through this page.

## Scope limitations

This is a publication index, not a pending-case list or docket. It does not
contain all filings or orders, and it includes many non-patent subjects within
the Federal Circuit's jurisdiction. Orders after 2012 that are not published on
the page are available through PACER.

## Access and connector assessment

The public page requires no account. Its searchable table is backed by a
WordPress endpoint that requires a page nonce and browser-like request headers;
because that endpoint is undocumented, the automation posture remains unclear.

## Connector coverage

`patent_client_agents.cafc` searches the opinions-and-orders table, filters by
date and origin, applies a conservative patent classifier, and downloads the
linked PDFs.

## Known gaps

The source cannot establish whether an appeal remains pending, provide a docket
history, retrieve party briefs, or identify the patents involved from
structured metadata. Patent classification is an aid and not a court-supplied
field.

## Evidence

- [Federal Circuit — Opinions & Orders](https://www.cafc.uscourts.gov/home/case-information/opinions-orders/)
- [Connector documentation](https://docs.patentclient.com/api/cafc/)
