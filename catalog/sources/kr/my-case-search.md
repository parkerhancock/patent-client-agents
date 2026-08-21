---
id: KR/Judiciary/MyCaseSearch
name: Korean Judiciary My Case Search
jurisdictions: [KR]
institution: Supreme Court of Korea
source_type: case_lookup
official_url: https://ssgo.scourt.go.kr/ssgo/index.on?cortId=www
last_verified: 2026-08-21
source_status: active
rights: [patent, utility_model, trademark, design, copyright, unfair_competition]
access:
  availability: manual_only
  audience: public
  formats: [html]
  automation_posture: technically_blocked
capabilities:
  pending_cases: partial
  closed_cases: partial
  party_search: none
  broad_discovery: none
  exact_case_lookup: full
  docket_events: partial
  filed_documents: none
  decisions: none
  patent_identifiers: none
connector:
  status: blocked
  blockers: [captcha, required_identifiers, no_api]
---

# Korean Judiciary My Case Search

## What this source contains

The judiciary's public case-search service supports exact lookup across Korean
courts, including Patent Court case categories. A user selects the court and
enters a year, case classification and serial number, together with a party
name. Returned information can show the case's progress and scheduled events.

## Scope limitations

The party name acts as an additional lookup credential; it is not an arbitrary
party-search field. Users must already know the court, case number components,
and a party. The service therefore cannot discover all cases involving a
company or identify unknown semiconductor suits.

## Access and connector assessment

The service is intended for interactive manual use and includes an
automatic-input-prevention challenge. It has no documented public API. These
controls and the required identifiers make unattended broad monitoring
infeasible even though a person can check a known matter.

## Connector coverage

No connector is planned while the interactive challenge and exact-identifier
requirements remain. The source is retained in the catalog because it is still
useful for manual verification of a known Korean case.

## Known gaps

There is no broad company search, public filing feed, pleading collection, or
patent-number field. The capability grades do not imply that every case type or
historical event remains available.

## Evidence

- [Korean Judiciary My Case Search](https://ssgo.scourt.go.kr/ssgo/index.on?cortId=www)
- [Supreme Court case-search entry page](https://help.scourt.go.kr/portal/information/events/search/search.jsp)
- [Official case-classification guide, including patent cases](https://www.scourt.go.kr/portal/information/event/guide/index3.html)
