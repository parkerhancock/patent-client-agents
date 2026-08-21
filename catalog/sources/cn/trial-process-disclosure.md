---
id: CN/SPC/TrialProcessDisclosure
name: China Trial Process Information Disclosure Network
jurisdictions:
- CN
institution: Supreme People's Court of the People's Republic of China
source_type: case_lookup
official_url: https://splcgk.court.gov.cn/gzfwww/
last_verified: 2026-08-21
source_status: active
rights:
- patent
- utility_model
- trademark
- design
- copyright
- trade_secret
- plant_variety
- unfair_competition
access:
  availability: parties_only
  audience: parties
  formats:
  - html
  automation_posture: technically_blocked
capabilities:
  pending_cases: full
  closed_cases: partial
  party_search: none
  broad_discovery: none
  exact_case_lookup: full
  docket_events: full
  filed_documents: full
  decisions: full
  patent_identifiers: unknown
connector:
  status: blocked
  blockers:
  - identity_verification
  - parties_only
  - no_api
category: adjudicative_records
---

# China Trial Process Information Disclosure Network

## What this source contains

The SPC designates this network as the unified platform for courts to disclose
case-process information. For an authenticated participant, the governing rule
requires disclosure of filing and closing information, parties, the judicial
panel, procedural events, hearing dates and places, specified litigation
documents, decisions, records of hearings and evidence exchanges, and certain
electronic case-file materials.

## Scope limitations

The detailed information is disclosed to parties, legal representatives,
litigation representatives, and defense counsel after identity verification.
Only matters with major social impact may receive broader public process
disclosure. It therefore cannot support public company-name discovery across
pending Chinese cases.

## Access and connector assessment

Identity numbers, lawyer credentials, organization identifiers, and a verified
mobile number are part of the access model. The current web application also
rejects ordinary non-browser retrieval and has no documented public API. A
general-purpose connector would conflict with the source's participant-specific
access boundary even if its technical controls were bypassed.

## Connector coverage

No connector is planned. A party may use the official service manually for its
own matters; that access does not authorize a shared docket-search service.

## Known gaps

The service provides no public broad discovery or arbitrary party search. The
catalog has not verified whether patent identifiers are consistently structured
within party-accessible records.

## Evidence

- [China Trial Process Information Disclosure Network](https://splcgk.court.gov.cn/gzfwww/)
- [SPC rule governing online trial-process disclosure](https://www.court.gov.cn/zixun/xiangqing/85532.html)
