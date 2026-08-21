---
id: WO/Clarivate/DartsIP
name: Clarivate Darts-IP litigation intelligence
jurisdictions: [CN, JP, KR]
institution: Clarivate
source_type: commercial_database
official_url: https://clarivate.com/intellectual-property/litigation-intelligence/
last_verified: 2026-08-21
source_status: active
rights: [patent, utility_model, trademark, design, copyright, unfair_competition]
access:
  availability: commercial
  audience: subscribers
  formats: [proprietary]
  automation_posture: contract_required
capabilities:
  pending_cases: partial
  closed_cases: partial
  party_search: partial
  broad_discovery: partial
  exact_case_lookup: partial
  docket_events: none
  filed_documents: partial
  decisions: partial
  patent_identifiers: partial
connector:
  status: external
  blockers: [commercial_contract]
---

# Clarivate Darts-IP litigation intelligence

## What this source contains

Clarivate markets Darts-IP as a searchable global IP-litigation database with
more than ten million cases from more than 140 countries and 4,100 courts and
offices. Its patent data groups decisions, complaints, hearings, and other
available documents at a case level and extracts parties, action type, patents,
issues, outcomes, and related legal information.

## Scope limitations

Coverage varies by jurisdiction and document type. Clarivate's methodology says
that decisions are available in most jurisdictions, while complaints and
hearing materials are available in main IP forums. That is not equivalent to a
complete, event-by-event docket, and the pilot has not independently audited
the current China, Japan, or Korea holdings. Capability grades are therefore
partial rather than full.

## Access and connector assessment

Search, reports, document access, and API delivery are commercial services.
API integration may be technically possible under a negotiated data contract,
but it is a procurement and license decision rather than an open-connector
build.

## Connector coverage

No first-party connector is shipped. Darts-IP remains an external commercial
option and should be evaluated with a subscriber coverage sample before relying
on it for pending-case monitoring in any one jurisdiction.

## Known gaps

The public product pages do not establish country-specific completeness,
latency, retention, or which Chinese, Japanese, and Korean courts provide
complaints rather than decisions only. The database should not be labeled a
complete docket without contract documentation and sample validation.

## Evidence

- [Clarivate IP Litigation Intelligence](https://clarivate.com/intellectual-property/litigation-intelligence/)
- [Darts-IP patent-case methodology and document description](https://patents.darts-ip.com/)
- [Clarivate worldwide patent-litigation data overview](https://clarivate.com/intellectual-property/lp/gain-unparalleled-access-to-worldwide-patent-litigation-data/)
