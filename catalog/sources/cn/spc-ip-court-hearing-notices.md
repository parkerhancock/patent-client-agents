---
id: CN/SPC_IPCourt/HearingNotices
name: China SPC Intellectual Property Court hearing notices
jurisdictions:
- CN
institution: Supreme People's Court Intellectual Property Court
source_type: hearing_calendar
official_url: https://ipc.court.gov.cn/zh-cn/news/more-4-15.html
last_verified: 2026-08-21
source_status: active
rights:
- patent
- utility_model
- design
- copyright
- trade_secret
- plant_variety
access:
  availability: public
  audience: public
  formats:
  - html
  automation_posture: permitted
capabilities:
  pending_cases: partial
  closed_cases: none
  party_search: partial
  broad_discovery: partial
  exact_case_lookup: none
  docket_events: none
  filed_documents: none
  decisions: none
  patent_identifiers: none
connector:
  status: shipped
  module: patent_client_agents.china_spc_ip_court
  blockers: []
category: adjudicative_records
coverage:
  order: 21
  name: Supreme People's Court Intellectual Property Court — Hearing Notices
  rights:
  - patent
  - design
  - copyright
  - trade_secret
  - plant_variety
  wipo_st3_code: CN
  data_types:
  - tribunal_proceedings
  - litigation
  access:
    method: website_scrape
    auth: none
  status: active
  category: adjudicative_records
  transport: mcp_proxy
  update_strategy: live_proxy
  update_cadence: daily
  notes: 'Public scheduled-hearing notices from China''s national appellate

    court for technology-related IP matters. Notices usually identify

    hearing date, party roles, venue, and dispute type, but often omit

    case and patent numbers. This is a hearing calendar, not a complete

    docket or an authoritative open/closed case-status service.

    '
---

# China SPC Intellectual Property Court hearing notices

## What this source contains

The national appellate IP court publishes dated notices of scheduled public
hearings. A notice commonly identifies the hearing date, party roles and names,
venue, and dispute type. The archive can be searched by Chinese company, party,
or technology terms.

## Scope limitations

The notices cover scheduled hearings at the SPC Intellectual Property Court,
not all Chinese patent litigation. They commonly omit the court case number,
patent number, filings, and later disposition. A hearing notice shows that a
hearing was scheduled; it does not prove that the matter remains pending.

## Access and connector assessment

The HTML index and notice pages are public and require no credentials. The
official site is directly readable from the connector's deployment environment.

## Connector coverage

`patent_client_agents.china_spc_ip_court` searches recent notice-index pages,
retrieves exact notice IDs, and searches the broader court site. It does not
invent case or patent identifiers absent from the source.

## Known gaps

There is no complete national filing list, exact-case docket, chronological
event history, pleading collection, or authoritative open/closed status.

## Evidence

- [Official SPC IP Court hearing-notice index](https://ipc.court.gov.cn/zh-cn/news/more-4-15.html)
- [SPC IP Court website](https://ipc.court.gov.cn/zh-cn/index)
- [Connector documentation](https://docs.patentclient.com/api/china-spc-ip-court/)
