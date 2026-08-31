---
id: JP/IPHC/PatentUtilityModelCaseLists
name: Japan IP High Court patent and utility-model case lists
jurisdictions:
- JP
institution: Japan Intellectual Property High Court
source_type: case_list
official_url: https://www.courts.go.jp/ip/vc-files/ip/jikenitiran.xls
last_verified: 2026-08-21
source_status: active
rights:
- patent
- utility_model
access:
  availability: public
  audience: public
  formats:
  - xls
  automation_posture: permitted
capabilities:
  pending_cases: partial
  closed_cases: partial
  party_search: none
  broad_discovery: partial
  exact_case_lookup: partial
  docket_events: none
  filed_documents: none
  decisions: none
  patent_identifiers: partial
connector:
  status: shipped
  module: patent_client_agents.japan_ip_high_court
  blockers: []
category: adjudicative_records
coverage:
  order: 22
  name: Japan Intellectual Property High Court — Patent and Utility-Model Case Lists
  rights:
  - patent
  wipo_st3_code: JP
  data_types:
  - tribunal_proceedings
  - litigation
  access:
    method: bulk_download
    auth: none
  status: active
  category: adjudicative_records
  transport: mcp_proxy
  update_strategy: live_proxy
  update_cadence: weekly
  notes: 'Official weekly workbook of pending and recently closed suits seeking

    cancellation of JPO patent or utility-model decisions. Records include

    court case number, proceeding type, patent/application number, division,

    and scheduled judgment or disposition fields. The workbook does not

    publish party names and is not a general patent-infringement docket.

    '
---

# Japan IP High Court patent and utility-model case lists

## What this source contains

The court publishes one weekly Excel workbook with separate sheets for pending
and recently closed suits seeking cancellation of JPO patent and utility-model
decisions. Records include the court case number, proceeding type,
patent/application identifier, assigned division, and scheduled judgment or
disposition fields.

## Scope limitations

This is not a general patent-infringement docket. It omits party names,
pleadings, motion practice, and docket events. Closed matters are removed about
three years after termination. Its exact-case and patent-identifier coverage is
therefore limited to the workbook's narrow subject matter and retention period.

## Access and connector assessment

The workbook is public, requires no credentials, and is linked from the court's
homepage. The court states that it is normally updated each Tuesday, or on the
second court business day when Monday is a holiday.

## Connector coverage

`patent_client_agents.japan_ip_high_court` downloads and parses both sheets.
The MCP tools search the contained records and retrieve exact case numbers.

## Known gaps

The source cannot identify whether a company is a plaintiff or defendant and
does not cover ordinary district-court infringement filings. A scheduled date
or closed-list entry is not a substitute for a docket sheet or filed documents.

## Evidence

- [Japan IP High Court homepage and case-list description](https://www.courts.go.jp/ip/)
- [Official weekly case workbook](https://www.courts.go.jp/ip/vc-files/ip/jikenitiran.xls)
- [Connector documentation](https://docs.patentclient.com/api/japan-ip-high-court/)
