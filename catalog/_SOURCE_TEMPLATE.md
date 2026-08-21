---
id: JP/Institution/Source
name: Human-readable source name
jurisdictions: [JP]
institution: Institution or vendor
source_type: case_list
official_url: https://example.com/
last_verified: 2026-08-21
source_status: active
category: adjudicative_records
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
# Omit this block for a catalog-only, unconnected source. For a shipped data
# product, it preserves the compatibility fields projected into
# coverage/sources.yaml. coverage.order values must be unique and contiguous.
coverage:
  order: 0
  wipo_st3_code: JP
  data_types: [tribunal_proceedings, litigation]
  access:
    method: website_scrape
    auth: none
  status: active
  category: adjudicative_records
  transport: mcp_proxy
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
- `category`: `adjudicative_records`, `registered_ip`, `substantive_law`,
  `fees`, `external`
- `source_type`: `assignment_database`, `classification_database`, `case_list`,
  `case_lookup`, `commercial_database`, `data_feed`, `external_dataset`,
  `fee_schedule`, `hearing_calendar`, `judgment_database`, `legal_corpus`,
  `registry`
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

## Capability profiles by category

- `adjudicative_records`: `pending_cases`, `closed_cases`, `party_search`,
  `broad_discovery`, `exact_case_lookup`, `docket_events`, `filed_documents`,
  `decisions`, `patent_identifiers`
- `registered_ip`: `bibliographic`, `full_text`, `prosecution`, `legal_status`,
  `assignments`, `oppositions`, `classification`, `bulk_data`
- `substantive_law`: `guidelines`, `case_law`, `statutes`, `treaties`,
  `full_text_search`, `citation_lookup`, `point_in_time`
- `fees`: `current_schedule`, `effective_date`, `historical_schedule`,
  `machine_readable`, `calculator`
- `external`: `query_api`, `bulk_data`

The compatibility projection retains the existing closed vocabularies described
in [`coverage/README.md`](../coverage/README.md). Common facts such as `id`,
`name`, `institution`, `rights`, `last_verified`, and `connector.module` are
taken from the canonical record. A field repeated inside `coverage` is an
explicit legacy-contract override and should be used only when exact downstream
compatibility requires it.
