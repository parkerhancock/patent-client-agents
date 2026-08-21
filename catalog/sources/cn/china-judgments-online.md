---
id: CN/SPC/ChinaJudgmentsOnline
name: China Judgments Online
jurisdictions: [CN]
institution: Supreme People's Court of the People's Republic of China
source_type: judgment_database
official_url: https://wenshu.court.gov.cn/
last_verified: 2026-08-21
source_status: active
rights: [patent, utility_model, trademark, design, copyright, trade_secret, plant_variety, unfair_competition]
access:
  availability: credentialed
  audience: registered_users
  formats: [html]
  automation_posture: technically_blocked
capabilities:
  pending_cases: none
  closed_cases: partial
  party_search: partial
  broad_discovery: partial
  exact_case_lookup: partial
  docket_events: none
  filed_documents: none
  decisions: partial
  patent_identifiers: unknown
connector:
  status: blocked
  blockers: [account_required, no_api, unstable_coverage]
---

# China Judgments Online

## What this source contains

The official judgment site exposes search across civil, criminal,
administrative, compensation, enforcement, and other published court documents.
Its search prompt accepts causes of action, keywords, courts, parties, and
lawyers. Published decisions can reveal parties, adjudicated claims, outcomes,
and sometimes the patent or application involved.

## Scope limitations

This is a post-decision publication service, not a pending-case docket. The
public collection has experienced substantial removals and uneven publication,
so historical and court-by-court completeness cannot be assumed. Patent
identifiers are not represented as a verified structured search field in this
catalog.

## Access and connector assessment

The live site presents login and registration controls and no documented public
API. Existing repository research also records query caps, identity and mobile
requirements, and unstable access from outside China. Those restrictions make
a reliable open connector unsuitable at present.

## Connector coverage

No connector is shipped or planned. The SPC IP Court connector links to this
site for document publication but does not attempt to automate it.

## Known gaps

The source cannot establish that litigation is currently pending, and absence
of a decision cannot establish absence of a case. It supplies neither docket
events nor complaints and other party filings.

## Evidence

- [China Judgments Online](https://wenshu.court.gov.cn/)
- [SPC description of public judgment and process-information platforms](https://www.court.gov.cn/zixun/xiangqing/69022.html)
- [ChinaFile reporting on declining public judgment access](https://www.chinafile.com/reporting-opinion/viewpoint/verdicts-chinas-courts-used-be-accessible-online-now-theyre-disappearing)
