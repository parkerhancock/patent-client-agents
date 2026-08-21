---
id: CA/CanLII
name: CanLII — Canadian case law
jurisdictions: [CA]
institution: Canadian Legal Information Institute
source_type: judgment_database
official_url: https://www.canlii.org/en/
last_verified: 2026-08-21
source_status: active
rights: [patent, trademark]
access:
  availability: public
  audience: public
  formats: [html, json]
  automation_posture: byok_only
capabilities:
  pending_cases: none
  closed_cases: partial
  party_search: partial
  broad_discovery: full
  exact_case_lookup: full
  docket_events: none
  filed_documents: none
  decisions: partial
  patent_identifiers: partial
connector:
  status: shipped
  module: patent_client_agents.canlii
  blockers: []
---

# CanLII — Canadian case law

## What this source contains

CanLII aggregates decisions from Canadian courts and tribunals, including the
Federal Court, Federal Court of Appeal, Supreme Court of Canada, Patent Appeal
Board, and Trademarks Opposition Board. Records include case title, citation,
docket number, decision date, keywords, canonical URL, and citator
relationships; the public website also supplies decision text.

## Scope limitations

CanLII is a decision database rather than a court registry. A case ordinarily
appears after a decision is published, coverage and transfer timing vary by
court, and temporary or permanent omissions are possible. It cannot establish
that a matter is pending or supply pleadings and docket activity.

## Access and connector assessment

The website is public. The supported REST API requires a CanLII API key issued
on request, and high-volume scraping is discouraged. Connector automation is
therefore limited to deployments using their own approved API key.

## Connector coverage

`patent_client_agents.canlii` lists case databases, browses decisions by
database and date, retrieves exact case metadata, and follows case and
legislation citations. It requires `CANLII_API_KEY`.

## Known gaps

The API does not provide pending cases, docket entries, filings, or decision
full text. Patent numbers may appear in titles, keywords, or text but are not a
uniform structured field. Use the Federal Court Court Files source for live
registry information.

## Evidence

- [CanLII database scope](https://www.canlii.org/databases)
- [CanLII API documentation](https://github.com/canlii/API_documentation/blob/master/EN.md)
- [Connector documentation](https://docs.patentclient.com/api/canlii/)
