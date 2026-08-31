---
id: US/USPTO/ODP/PTAB
name: USPTO Open Data Portal — PTAB trial proceedings
jurisdictions:
- US
institution: U.S. Patent and Trademark Office (Patent Trial and Appeal Board)
source_type: case_lookup
official_url: https://data.uspto.gov/apis/ptab-trials
last_verified: 2026-08-21
source_status: active
rights:
- patent
access:
  availability: credentialed
  audience: registered_users
  formats:
  - json
  - csv
  - pdf
  automation_posture: byok_only
capabilities:
  pending_cases: full
  closed_cases: full
  party_search: full
  broad_discovery: full
  exact_case_lookup: full
  docket_events: partial
  filed_documents: full
  decisions: full
  patent_identifiers: full
connector:
  status: shipped
  module: patent_client_agents.uspto_odp
  blockers: []
category: adjudicative_records
coverage:
  order: 1
  name: USPTO Open Data Portal — PTAB proceedings
  last_verified: 2026-05-15
  wipo_st3_code: US
  data_types:
  - tribunal_proceedings
  - prosecution
  access:
    method: rest_api
    auth: none
  status: active
  category: adjudicative_records
  transport: mcp_proxy
---

# USPTO Open Data Portal — PTAB trial proceedings

## What this source contains

The USPTO Open Data Portal exposes structured proceedings, decisions, and public
documents for PTAB trials, including inter partes review, post-grant review,
covered-business-method review, and derivation proceedings. Records include
trial status, parties, challenged patent identifiers, filing and decision dates,
and downloadable public documents.

## Scope limitations

This is an administrative patent-trial source, not Article III court litigation.
Coverage begins with the proceeding types and dates published by the PTAB; the
trial-decision documentation states that public trial material is available from
September 2012. A sequence of filed documents provides partial procedural
history but should not be represented as a court docket outside PTAB.

## Access and connector assessment

The API requires a USPTO API key. The Open Data Portal also began requiring a
USPTO.gov account sign-in in June 2026, with additional profile fields required
in August 2026. Automated access is therefore suitable only with a user's own
current credentials.

## Connector coverage

`patent_client_agents.uspto_odp` searches and retrieves PTAB trial proceedings,
decisions, and documents and can bulk-download public trial documents and
decisions. It requires `USPTO_ODP_API_KEY`.

## Known gaps

The source does not cover district-court or appellate litigation, sealed PTAB
material, or non-public submissions. Its event history is reconstructed from
published proceeding metadata and documents rather than a separate docket-event
feed.

## Evidence

- [USPTO Open Data Portal — PTAB Trials APIs](https://data.uspto.gov/apis/ptab-trials)
- [USPTO PTAB trial-decision search documentation](https://data.uspto.gov/apis/ptab-trials/search-decisions)
- [Connector documentation](https://docs.patentclient.com/api/uspto-odp/)
