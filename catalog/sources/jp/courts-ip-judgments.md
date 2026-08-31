---
id: JP/Courts/IPJudgmentSearch
name: Courts of Japan intellectual-property judgment search
jurisdictions:
- JP
institution: Supreme Court of Japan
source_type: judgment_database
official_url: https://www.courts.go.jp/hanrei/search7/index.html
last_verified: 2026-08-21
source_status: active
rights:
- patent
- utility_model
- trademark
- design
- copyright
- unfair_competition
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
  party_search: none
  broad_discovery: partial
  exact_case_lookup: partial
  docket_events: none
  filed_documents: none
  decisions: partial
  patent_identifiers: partial
connector:
  status: candidate
  blockers: []
category: adjudicative_records
---

# Courts of Japan intellectual-property judgment search

## What this source contains

The judiciary's public case-law search covers IP High Court judgments and
selected Supreme Court, other high-court, and district-court IP decisions.
Search fields include keywords, decision date, case number, originating court,
case type, right type, result, and issues. Result pages link to judgment and,
when available, summary PDFs.

## Scope limitations

This is a judgment database, not a filing or pending-case database. The site
expressly warns that not every judicial decision is included. The IP High Court
states that its own collection contains nearly all judgments since the court
was established in 2005, but only some orders and other rulings. Other Japanese
courts are represented by selected important IP decisions.

## Access and connector assessment

The search and PDFs are public and require no account. The interface is HTML
without a documented public API. A connector appears technically feasible, but
automation terms, stable query behavior, and pagination should be verified
before implementation.

## Connector coverage

No connector is currently shipped. This remains a candidate for closed-case
research and decision retrieval; it would not solve pending-litigation
monitoring.

## Known gaps

There is no party-name search field, no public chronological docket, and no
pleading collection. An absence from search results does not establish that no
case was filed or decided.

## Evidence

- [Courts of Japan IP judgment search](https://www.courts.go.jp/hanrei/search7/index.html)
- [Japan IP High Court description of its judgment database](https://www.ip.courts.go.jp/app/hanrei_jp/search?reload=1)
- [Courts of Japan search-result field guide](https://www.courts.go.jp/hanrei/search1/index.html)
