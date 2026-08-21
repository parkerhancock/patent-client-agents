---
id: CA/FederalCourt/CourtFiles
name: Federal Court of Canada — Court Files
jurisdictions:
- CA
institution: Federal Court of Canada
source_type: case_lookup
official_url: https://www-u.fct-cf.gc.ca/en/court-files-and-decisions/court-files
last_verified: 2026-08-21
source_status: active
rights:
- patent
- trademark
- copyright
access:
  availability: public
  audience: public
  formats:
  - html
  - json
  - pdf
  automation_posture: unclear
capabilities:
  pending_cases: partial
  closed_cases: partial
  party_search: full
  broad_discovery: partial
  exact_case_lookup: full
  docket_events: full
  filed_documents: partial
  decisions: none
  patent_identifiers: partial
connector:
  status: shipped
  module: patent_client_agents.canada_federal_court
  blockers: []
category: adjudicative_records
coverage:
  order: 27
  wipo_st3_code: CA
  data_types:
  - tribunal_proceedings
  - litigation
  access:
    method: rest_api
    auth: none
  status: active
  category: adjudicative_records
  transport: mcp_proxy
  update_strategy: live_proxy
  update_cadence: weekly
  notes: 'Official party/corporation search, exact case-file metadata, public

    parties/counsel, IP names and numbers, and recorded docket entries.

    The upstream search does not publish an authoritative open/closed

    status; connector status assessments are conservative docket-text

    inferences and are labeled as such.

    '
---

# Federal Court of Canada — Court Files

## What this source contains

The Federal Court's Court Files service searches Registry records by party or
corporation, court-file number, intellectual-property name or reference, and
related case. Exact file records include parties and counsel, filing date and
city, IP references, related cases, and the Registry's recorded entries.

## Scope limitations

The Registry does not publish a definitive open-or-closed field. Pending and
closed capability grades are therefore partial: recent recorded-entry text can
support a cautious assessment, but silence is not status evidence. Some court
records are confidential, and online document availability is limited.

## Access and connector assessment

The public site requires no account. The connector uses the JSON endpoints that
support the court's web interface; they are not presented as a separately
documented public API, so the automation posture remains unclear despite the
shipped read-only connector.

## Connector coverage

`patent_client_agents.canada_federal_court` searches parties, retrieves exact
case metadata, lists recorded entries, and exposes public document downloads
when the Registry supplies them. Any status assessment is labeled as an
inference with its textual basis.

## Known gaps

The source does not provide full-text party discovery, an authoritative case
status, every filed document, or the court's reported decisions. Decisions must
be obtained from a separate judgments source such as the court website or
CanLII.

## Evidence

- [Federal Court — Court Files](https://www-u.fct-cf.gc.ca/en/court-files-and-decisions/court-files)
- [Federal Court online-access user guide](https://www.fct-cf.gc.ca/Content/assets/pdf/base/2022-09-07-ENG-User-Guide-Online-Access.pdf)
- [Connector documentation](https://docs.patentclient.com/api/canada-federal-court/)
