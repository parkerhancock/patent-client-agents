---
id: US/USITC/IDS
name: USITC Investigations Database System — IP investigation index
jurisdictions:
- US
institution: U.S. International Trade Commission
source_type: case_list
official_url: https://ids.usitc.gov/
last_verified: 2026-08-21
source_status: active
rights:
- patent
- trademark
- design
- copyright
- trade_secret
- unfair_competition
access:
  availability: public
  audience: public
  formats:
  - html
  - json
  automation_posture: permitted
capabilities:
  pending_cases: full
  closed_cases: full
  party_search: full
  broad_discovery: full
  exact_case_lookup: full
  docket_events: partial
  filed_documents: partial
  decisions: partial
  patent_identifiers: full
connector:
  status: shipped
  module: patent_client_agents.usitc
  blockers: []
category: adjudicative_records
coverage:
  order: 26
  name: USITC IDS — IP investigation index
  rights:
  - patent
  - trademark
  last_verified: 2026-05-15
  wipo_st3_code: US
  data_types:
  - tribunal_proceedings
  - litigation
  access:
    method: rest_api
    auth: none
  status: active
  category: adjudicative_records
  transport: mcp_proxy
  notes: 'Investigation-level index of IP proceedings. Lighter-weight surface

    than EDIS — useful for cross-investigation discovery before pulling

    EDIS attachments.

    '
---

# USITC Investigations Database System — IP investigation index

## What this source contains

IDS is the USITC's public investigation-level index. Section 337 entries can
identify the investigation, participants, staff, procedural dates, status,
asserted intellectual property and patent numbers, product categories,
associated litigation, orders, and selected links into EDIS.

## Scope limitations

IDS is an investigation index rather than the complete document repository.
Its dates and selected document links provide procedural milestones, not every
docket event or filing. It covers USITC proceedings only and includes many
non-IP investigation types alongside Section 337 matters.

## Access and connector assessment

The website and its public JSON investigation feed require no credentials. The
feed is large and should be cached rather than downloaded repeatedly.

## Connector coverage

`patent_client_agents.usitc` retrieves the public IDS feed and returns
structured investigation records. The MCP surface provides substring filters
for discovering investigations before a deeper EDIS lookup.

## Known gaps

IDS cannot replace EDIS for a complete document history or attachments. A
linked document or milestone does not show that every filing in the
investigation is available through IDS.

## Evidence

- [USITC Investigations Database System](https://ids.usitc.gov/)
- [USITC public IDS investigation feed](https://ids.usitc.gov/investigations.json)
- [USITC — About Section 337](https://www.usitc.gov/about_section_337.htm)
