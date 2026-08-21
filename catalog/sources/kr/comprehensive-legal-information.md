---
id: KR/Judiciary/ComprehensiveLegalInformation
name: Korean Judiciary Comprehensive Legal Information System
jurisdictions: [KR]
institution: Supreme Court of Korea
source_type: judgment_database
official_url: https://glaw.scourt.go.kr/wsjo/intesrch/sjo022.do
last_verified: 2026-08-21
source_status: active
rights: [patent, utility_model, trademark, design, copyright, unfair_competition]
access:
  availability: public
  audience: public
  formats: [html, pdf]
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
---

# Korean Judiciary Comprehensive Legal Information System

## What this source contains

The Supreme Court describes its Comprehensive Legal Information System as a
free public search service for Supreme Court and lower-court precedents,
legislation, court rules, internal regulations, and legal literature. The
judiciary reports that the system includes roughly 80,000 Supreme Court
precedents and 60,000 lower-court decisions. Patent Court decisions also appear
through the Patent Court's highlighted-decision pages and attached PDFs.

## Scope limitations

The public decision collection concerns finalized or selected decisions, not
new complaints or currently pending matters. Personal information is anonymized
before publication, and a court may withhold a decision from public disclosure.
The Patent Court's separate highlighted-decision board is curated rather than a
complete docket.

## Access and connector assessment

Public users can search and view decisions without obtaining party access. The
search stack is HTML and exposes no documented public API. A decision-search
connector may be possible, but stable request mechanics, reuse terms, and the
relationship between the central system and Patent Court board require focused
technical verification.

## Connector coverage

No connector is shipped. This remains a candidate for closed-case and decision
research, not pending-litigation discovery.

## Known gaps

The source has no public pending-case feed, docket events, complaints, or
reliable party-name discovery because published judgments are anonymized.
Patent-number coverage depends on the text and metadata of individual decisions.

## Evidence

- [Supreme Court of Korea description of public services and decision access](https://www.scourt.go.kr/eng/judiciary/eCourt/public.jsp)
- [Korean Judiciary Comprehensive Legal Information System](https://glaw.scourt.go.kr/wsjo/intesrch/sjo022.do)
- [Patent Court highlighted decision example with attached judgment](https://patent.scourt.go.kr/dcboard/new/DcNewsViewAction.work?cbub_code=000700&gubun=44&pageIndex=1&searchWord=&seqnum=27897)
- [Supreme Court English IP-law decisions](https://www.scourt.go.kr/eng/supreme/decisions/NewDecisionsList.work?mode=5)
