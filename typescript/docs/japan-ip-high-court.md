# Japan IP High Court case lists

October 22, 2026. `JapanIpHighCourtClient`
([source](../packages/client/src/japan-ip-high-court.ts)) ports the Python
`japan_ip_high_court` package: the Intellectual Property High Court's weekly
lists of pending and recently closed suits against JPO patent and
utility-model decisions (審決取消訴訟 and the like).

## Source

The court publishes one legacy Excel workbook,
https://www.courts.go.jp/ip/vc-files/ip/jikenitiran.xls, with two sheets:
係属中事件一覧表 (pending, with the scheduled judgment date) and
終局事件一覧表 (closed, with termination date, disposition and any further
appeal). Each sheet carries its as-of date in its second row. The lists do not
name the parties and are not an infringement docket. No key or cookie is
needed; the file answers plain requests with or without a user agent or
referer, and the client sends the project's honest user agent.

The October 22 download (last modified October 20) is as of October 16, 2026:
34 pending and 219 closed cases, every one 行ケ.

## Parsing

The workbook is BIFF8, which no dependency in the workspace reads, so
[`runtime/xls.ts`](../packages/client/src/runtime/xls.ts) adds a small
portable reader (exported as `readXls` and `xlsSerialDate`): the Compound
File container (regular and mini streams), the shared string table across
CONTINUE records, and NUMBER, RK, MULRK, LABELSST, LABEL, BOOLERR and cached
FORMULA values. Formatting, merged cells and charts are ignored; encrypted and
pre-BIFF8 files are refused. Dates follow xlrd, including the 1900 leap-year
quirk and the 1904 date mode.

`parseJapanIpHighCourtWorkbook` then follows Python's `parse_case_workbook`
row for row: data rows start at the fourth row, a row counts only when its
serial-number cell is numeric, the case number is rebuilt from the era, year,
type and serial cells, the filing year comes from the era (令和, 平成, 昭和),
and the subject number is typed as patent, patent application, utility model,
utility-model application, opposition or other. A workbook that will not
open, lacks either sheet or has an unparseable year or date fails with
`INVALID_RESPONSE` rather than returning a short list. For the recorded
workbook the TypeScript output equals Python's
([parity fixture](../tests/fixtures/japan-ip-high-court/python-parity.json))
in every field of all 253 cases.

Case numbers match after NFKC normalization, whitespace removal and
lowercasing, so `令和7年 (行ケ) 第10011号` finds `令和7年（行ケ）第10011号`.
Python uses `casefold`; the two agree for Japanese case numbers.

## MCP tools

The full toolset serves `search_japan_ip_high_court_cases` and
`get_japan_ip_high_court_case` under the `jpcourt:read` scope, with Python's
parameters, defaults, filtering, sorting and summaries. Search defaults to
pending cases, OR-matches normalized query terms against every field, filters
dates on the scheduled judgment (pending) or termination (closed) date, and
returns up to 250 records. The get tool takes one case number or up to 50; a
single miss is a not-found error and list misses go to `not_found`. Each call
downloads the workbook once (about 138 KB). Python keeps a six-hour HTTP
cache; the TypeScript port has no runtime response cache, as elsewhere.

## Runtimes

The reader uses only `DataView` and `TextDecoder`, so the parser runs in Bun,
Node and browsers; both smoke tests parse the archived workbook
([fixture](../tests/fixtures/japan-ip-high-court/jikenitiran.xls.gz)). The
court sends no CORS headers, so browsers reach it through the relay, which now
allows `www.courts.go.jp`. The relay drops the referer and user agent, which
the court does not require.

## Tests

`bun run record:japan-ip-high-court` records one download
([recorder](../tests/japan-ip-high-court-recordings.ts)). The
[tests](../tests/japan-ip-high-court.test.ts) replay it against the Python
parity fixture, and use a test-only BIFF8 writer
([builder](../tests/xls-builder.ts)) to build workbooks from the Python test
rows and edge cases: split shared strings, RK, MULRK, LABEL, formula results,
1904 dates, missing sheets and bad cells. They also cover the request headers,
every MCP option, not-found handling and the HTTP scope.
