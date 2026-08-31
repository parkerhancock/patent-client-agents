---
id: US/USPTO/ODP/Petitions
name: USPTO Open Data Portal — petition decisions
jurisdictions:
- US
institution: U.S. Patent and Trademark Office
source_type: judgment_database
official_url: https://data.uspto.gov/apis/petition-decision
last_verified: 2026-08-21
source_status: active
rights:
- patent
access:
  availability: credentialed
  audience: registered_users
  formats:
  - json
  - pdf
  automation_posture: byok_only
capabilities:
  pending_cases: none
  closed_cases: partial
  party_search: partial
  broad_discovery: partial
  exact_case_lookup: full
  docket_events: none
  filed_documents: partial
  decisions: full
  patent_identifiers: partial
connector:
  status: shipped
  module: patent_client_agents.uspto_petitions
  blockers: []
category: adjudicative_records
coverage:
  order: 2
  name: USPTO Open Data Portal — Petitions
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

# USPTO Open Data Portal — petition decisions

## What this source contains

The USPTO petition-decision API publishes structured records for decided
petitions, including a decision-record identifier, applicant name, patent
number where supplied, petition and decision dates, petition type, deciding
office, issues considered, disposition, and an associated decision document.

## Scope limitations

This source concerns USPTO administrative petitions, not court litigation or
PTAB AIA trials. It is decision-centered and does not provide a pending-petition
register, docket events, party filings, or a complete procedural file. Applicant
and patent fields are not populated uniformly across every petition type.

## Access and connector assessment

The API requires a USPTO API key and current Open Data Portal account access.
Automation is appropriate with a user's own credentials and subject to the
USPTO's published API limits.

## Connector coverage

`patent_client_agents.uspto_petitions` searches petition decisions, retrieves an
exact decision record, and downloads decision documents through the shared
USPTO Open Data Portal client. It requires `USPTO_ODP_API_KEY`.

## Known gaps

The source cannot establish that a petition is pending, does not expose a
chronological docket, and should not be used as evidence that a party is
involved in patent litigation.

## Evidence

- [USPTO Open Data Portal — Petition Decision API](https://data.uspto.gov/apis/petition-decision)
- [USPTO petition-decision search documentation](https://data.uspto.gov/apis/petition-decision/search)
- [Connector documentation](https://docs.patentclient.com/api/uspto-petitions/)
