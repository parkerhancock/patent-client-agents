---
id: UPC/UPC/Decisions
name: Unified Patent Court — decisions and orders
jurisdictions: [UPC]
institution: Unified Patent Court
source_type: judgment_database
official_url: https://www.unifiedpatentcourt.org/en/decisions-and-orders
last_verified: 2026-05-15
source_status: active
rights: [patent]
access:
  availability: public
  audience: public
  formats: [html, pdf]
  automation_posture: unclear
capabilities:
  pending_cases: none
  closed_cases: partial
  party_search: partial
  broad_discovery: partial
  exact_case_lookup: partial
  docket_events: none
  filed_documents: partial
  decisions: partial
  patent_identifiers: none
connector:
  status: shipped
  module: patent_client_agents.upc_decisions
  blockers: []
---

# Unified Patent Court — decisions and orders

## What this source contains

The UPC publishes a paginated list of decisions and orders. Each listed item can
include a case identifier, division, type of action, parties, procedural
language, and one or more decision or order PDFs.

## Scope limitations

The list is a publication surface, not the UPC case-management register. It
does not provide pending filings, docket events, pleadings, a comprehensive
document file, or structured asserted-patent identifiers. Publication of a
decision or order is not a complete status history for the case.

## Access and connector assessment

The listing pages and linked PDFs are public. Per-item detail pages were behind
an interactive Cloudflare challenge when the connector was verified, and the
listing is an undocumented Drupal view rather than a supported API. The
automation posture therefore remains unclear.

## Connector coverage

`patent_client_agents.upc_decisions` reads the public listing pages, applies the
available court, division, document-type, and language filters, resolves exact
case identifiers by walking the index, and downloads linked PDFs.

## Known gaps

The connector cannot search the non-public CMS register, cannot identify new
cases before a decision or order is published, and cannot recover documents or
patent numbers absent from the public row and PDF.

## Evidence

- [UPC — Decisions and orders](https://www.unifiedpatentcourt.org/en/decisions-and-orders)
