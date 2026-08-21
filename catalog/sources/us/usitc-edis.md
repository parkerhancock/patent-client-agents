---
id: US/USITC/EDIS
name: USITC EDIS — Section 337 investigation dockets
jurisdictions:
- US
institution: U.S. International Trade Commission
source_type: case_lookup
official_url: https://edis.usitc.gov/
last_verified: 2026-08-21
source_status: active
rights:
- patent
- trademark
- design
- copyright
- trade_secret
- unfair_competition
access:
  availability: credentialed
  audience: registered_users
  formats:
  - json
  - xml
  - pdf
  automation_posture: byok_only
capabilities:
  pending_cases: full
  closed_cases: full
  party_search: partial
  broad_discovery: full
  exact_case_lookup: full
  docket_events: full
  filed_documents: full
  decisions: full
  patent_identifiers: partial
connector:
  status: shipped
  module: patent_client_agents.usitc
  blockers: []
category: adjudicative_records
coverage:
  order: 25
  name: USITC EDIS — Section 337 investigations
  rights:
  - patent
  - trademark
  last_verified: 2026-05-15
  wipo_st3_code: US
  data_types:
  - tribunal_proceedings
  - litigation
  access:
    method: rest_api
    auth: api_key
    auth_env:
    - USITC_EDIS_TOKEN
  status: active
  category: adjudicative_records
  transport: mcp_proxy
  notes: 'Section 337 patent + trademark enforcement investigations: docket

    entries, attachments, exclusion orders. Live docket data — treat as

    a snapshot at retrieved_at, not a corpus.

    '
---

# USITC EDIS — Section 337 investigation dockets

## What this source contains

The Electronic Document Information System is the USITC's filing and document
system for investigations. For Section 337 matters it provides investigation
metadata, status and phase filters, document entries, attachments, party
filings, orders, determinations, and Commission decisions.

## Scope limitations

EDIS covers USITC investigations rather than federal-court cases. Section 337
matters often allege patent or trademark infringement, but the system also
contains non-IP investigations and confidential material that is not publicly
downloadable. Patent identifiers are not a uniformly complete investigation
index.

## Access and connector assessment

Public investigation material is searchable, but API and attachment access
requires a user-generated EDIS token obtained through Login.gov. Tokens expire,
so automated access must use current user credentials and handle authentication
failures explicitly.

## Connector coverage

`patent_client_agents.usitc` searches EDIS investigations and documents, lists
attachments, and downloads individual or bounded batches of attachments. It
requires `USITC_EDIS_TOKEN` for EDIS operations.

## Known gaps

The connector does not expose confidential documents, does not turn document
titles into inferred claims, and does not substitute for PACER when parallel
district-court litigation exists.

## Evidence

- [USITC — About Section 337 and access to EDIS](https://www.usitc.gov/about_section_337.htm)
- [USITC EDIS](https://edis.usitc.gov/)
- [Connector documentation](https://docs.patentclient.com/api/usitc/)
