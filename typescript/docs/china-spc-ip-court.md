# China SPC IP Court hearing notices

October 22, 2026. `ChinaSpcIpCourtClient`
([source](../packages/client/src/china-spc-ip-court.ts)) ports the Python
`china_spc_ip_court` package: the hearing-notice index, single notices and
the full-site search of the Supreme People's Court Intellectual Property
Court (最高人民法院知识产权法庭) at https://ipc.court.gov.cn. The models are Zod
schemas with Python's field names.

## Source

The court publishes no API. Three HTML pages are read:

- `/zh-cn/news/more-4-15.html?page=N`, the hearing-notice index (开庭公告),
  newest first, five notices a page, 394 pages on October 22.
- `/zh-cn/news/view-<id>.html`, one notice. The title carries the hearing
  date in Arabic numerals; the body gives the time, courtroom, parties and
  cause of action in Chinese prose, which the parser splits with Python's
  regular expressions.
- `/zh-cn/search.html?content=<q>&page=N`, the site search over news, case
  write-ups and notices, 20 results a page, oldest first.

The site sits behind a QI-ANXIN cloud WAF. Plain requests with the project's
user agent (`patent-client-agents (+https://github.com/...)`) succeed; Python
sends a Chrome user agent, which is not needed. A request with no user agent
gets a 404. The site sends no CORS headers, so the relay allows
`ipc.court.gov.cn` for browsers ([runtimes](runtimes.md)).

Timestamps (`published_at`) are the site's local times without an offset, as
in Python. Hearing dates and the `future_only` filter use the China calendar
(UTC+8).

## Python bugs corrected

Checked against the live site and a sample of 44 notices from 2019 to 2026,
parsed by both implementations:

1. Every article page carries 开庭公告 in its menu, so Python's not-a-notice
   check never fires: `get_hearing_notice("48")` returns the court's
   introduction as a hearing notice. The port requires 开庭公告 in the
   article title.
2. A missing ID is answered with the site's error page and HTTP 451. Python
   raises an HTTP error, so a list request fails outright; the port raises
   `NOT_FOUND`, and lists report the ID in `not_found`.
3. The search pager links are path-style (`.../page/28.html`). Python looks
   only for `?page=`, so `total_pages` is always 1 and multi-page searches
   report `more_available: false` with no cursor. The port reads both forms.
4. A page past the end is answered with another page (the index serves its
   last page, the search its first). Python returns those rows again; the port
   returns none.
5. 一审第三人 (first-instance third party) is not a Python role, so the party
   before it keeps 一审 on its name ("特维斯股份有限公司及一审") and the third
   party is labelled 第三人. This affected 21 of the 44 sampled notices.
6. Python deletes every space in the notice text, which joins Latin party
   names ("UNIVERSITYOFVIENNA"). The port keeps single spaces between Latin
   characters; Chinese text is unchanged.
7. Notices before about 2021 write the hour with 点 (上午九点), and some notices
   cover several cases (两案, 四案). Python finds no time, courtroom, cause of
   action or parties in those; the port does.

With those exceptions the port's output matches Python's field for field on
the sample. Notices that list many cases in a table (multi-day sessions in
2019 and 2020) and causes of action outside Python's list (其他专利行政纠纷,
植物新品种行政复议) still have no `dispute_type`.

## MCP tools

The full toolset serves three tools under the `spc:read` scope, with Python's
parameters and envelopes:

- `search_china_spc_ip_hearing_notices` reads 1-50 index pages, fetches each
  notice (five at a time), filters by `future_only` and OR-terms, and sorts by
  hearing date. When `future_only` is set it skips notices whose index title
  already dates the hearing in the past, which Python fetches and discards.
- `get_china_spc_ip_hearing_notice` takes an ID, an official URL or a list of
  up to 50, with misses in `not_found`.
- `search_china_spc_ip_court_site` returns one search page; `next_cursor` is
  the next page number.

The connector is not in the curated facade, as in Python.

## Tests

`bun run record:china-spc-ip-court` records one session
([recorder](../tests/china-spc-ip-court-recordings.ts)): the hearing search
tool over two index pages and their ten notices, a page past the end, a list
lookup with an official URL, an article and a missing ID, and three searches.
The [tests](../tests/china-spc-ip-court.test.ts) replay it offline, check the
[real-notice fixture](../tests/fixtures/china-spc-ip-court/notices.json)
(seven notices with Python's output for each) and Python's parser fixtures,
and cover request encoding, input validation, not-found handling, the tools
and the `spc:read` scope. Both smoke tests parse a fixture notice, under Node
and in Chromium.
