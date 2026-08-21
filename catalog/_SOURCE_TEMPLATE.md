---
id: JP/Institution/Source
name: Human-readable source name
jurisdictions: [JP]
institution: Institution or vendor
source_type: case_list
official_url: https://example.com/
last_verified: 2026-08-21
source_status: active
rights: [patent]
access:
  availability: public
  audience: public
  formats: [html]
  automation_posture: unclear
capabilities:
  pending_cases: unknown
  closed_cases: unknown
  party_search: unknown
  broad_discovery: unknown
  exact_case_lookup: unknown
  docket_events: unknown
  filed_documents: unknown
  decisions: unknown
  patent_identifiers: unknown
connector:
  status: candidate
  blockers: []
---

# Human-readable source name

## What this source contains

Describe the upstream source and the records it publishes.

## Scope limitations

State omissions, time limits, court limits, language limits, and whether the
source covers pending matters, decisions, or both.

## Access and connector assessment

Describe who can use the source and whether automated access is technically and
legally supportable.

## Connector coverage

Identify the shipped connector, or explain why no connector exists.

## Known gaps

State what this source cannot answer.

## Evidence

- [Primary source](https://example.com/)

## Controlled vocabularies

- `source_status`: `active`, `retired`, `announced`, `unverified`
- `source_type`: `case_list`, `case_lookup`, `commercial_database`,
  `hearing_calendar`, `judgment_database`
- `availability`: `public`, `credentialed`, `commercial`, `parties_only`,
  `manual_only`, `unavailable`, `unknown`
- `audience`: `public`, `registered_users`, `parties`, `subscribers`,
  `institutions`
- `formats`: `html`, `pdf`, `xls`, `json`, `xml`, `csv`, `proprietary`,
  `unknown`
- `automation_posture`: `permitted`, `byok_only`, `approval_required`,
  `contract_required`, `prohibited`, `technically_blocked`, `unclear`
- each capability: `full`, `partial`, `none`, `unknown`
- `connector.status`: `shipped`, `candidate`, `planned`, `blocked`, `skipped`,
  `external`
- `connector.blockers`: `account_required`, `captcha`,
  `commercial_contract`, `geofence`, `identity_verification`, `license`,
  `no_api`, `parties_only`, `required_identifiers`, `tos`, `unknown`,
  `unstable_coverage`
