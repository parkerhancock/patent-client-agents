# Fee schedules

October 21, 2026. EPO fees were the first TypeScript fee connector and the
reference for porting the other offices in the Python `fees` package; USPTO
fees followed.

## The pattern

A fee connector turns one office's published schedule into a validated
`FeeSchedule` ([models](../packages/client/src/fees/models.ts)). The contract:

- **Closed vocabularies.** `category`, `tier`, `right` and condition `trigger`
  use the Python enums value for value. Map new fee types to the closest value
  and explain nuance in `label` and `notes`.
- **Exact amounts.** Amounts are decimal strings (`"1595.00"`), never floats.
  Parse the office's notation exactly or fail; never guess at separators.
- **Two dates.** `effective_date` is what the office publishes, null when it
  publishes none, and is repeated in provenance with an `as_of_status`
  explanation. `provenance.retrieved_at` is when the bytes were fetched. Never
  substitute one for the other.
- **Codes over keywords.** Where an office publishes stable fee codes, map
  codes explicitly to categories, years and conditions. Codes without a
  mapping still appear, as `other`, and are listed in `unmapped_codes` so
  upstream drift is visible instead of silently miscategorized. Keyword
  heuristics are for offices without codes.
- **Honest coverage.** `recurring_fee_coverage` is computed from the parsed
  rows: `complete` only when every expected renewal or maintenance year is
  present, otherwise `partial` with `missing_years`. An empty renewal lookup is
  authoritative only when coverage is complete.
- **Fail on shape change.** Validate the upstream envelope with Zod and fail
  with `INVALID_RESPONSE` rather than emitting an empty or partial schedule.
  Fail too when the source starts publishing something the parser ignores but
  that would change meaning (the EPO feed's `validUntil`).
- **One schedule per right.** Distinct rights get distinct routes even from
  one feed (EPO application fees versus Unitary Patent fees).

`FeesClient` ([index](../packages/client/src/fees/index.ts)) resolves office
names with the alias table generated from Python, so every name resolves the
same way in both runtimes. Routes not yet ported raise `NOT_PORTED`; rights an
office does not have raise `UNSUPPORTED_RIGHT`. Adding an office means one
module that returns `FeeSchedule`s, one line per route in `FeesClient`, a
recorder entry and tests. The MCP tools need no change.

## EPO

`EpoFeesClient` ([source](../packages/client/src/fees/epo.ts)) reads the
undocumented JSON feed behind the EPO Schedule of Fees app
(`https://fees.apps.epo.org/prod/bff/api/fees`), as Python does. One payload
holds both schedules:

| Route | Codes | Renewals |
| --- | --- | --- |
| `EP/EPO/patent` | EPC and PCT fees; 033-050 renewals, 093-110 late fees | Years 3-20 |
| `UP/EPO-UP/patent` | 701, 713, 732-750 renewals, 752-770 late fees, 771 | Years 2-20 |

This corrects the Python port in three places, which still behaves the old way:

1. Python's EPO schedule includes the Unitary Patent codes 732-770 as EP
   renewals, so an EPO renewal lookup for years 3-20 returns two conflicting
   amounts (year 10: 1865.00 and 1175.00). Its notes also describe 732-750 as EP
   renewal years 2-20 and 100-110 as IP5 fees; both are wrong.
2. Python's keyword categorizer puts "Fee for a European search" (002) in
   `other`. Explicit codes fix this.
3. Python's EPO-UP route is a static transcription of RFeesUPP Article 2. Here
   it comes live from the same feed, and a test checks that the live ladder
   equals the transcribed Article 2 table. Its effective date is therefore
   unpublished (null) instead of the Python constant 2023-06-01.

Percentage fees (123, further processing at 50% of the late fee) carry a note
because the feed lists them as 0.00. PCT reductions 316-319 are reductions, not
charges, and say so. Rule 7a EPC micro-entity reductions and the Unitary Patent
licence-of-right reduction are not applied.

## USPTO

`UsptoFeesClient` ([source](../packages/client/src/fees/uspto.ts)) parses the
HTML fee schedule page
(`https://www.uspto.gov/learning-and-resources/fees-and-payment/uspto-fee-schedule`),
as Python does. USPTO publishes no JSON or CSV fee feed; the only other
official form is the PDF of the same schedule, so the page remains the source.
One fetch serves all three routes, and concurrent requests share it.

| Route | Content | Recurring fees |
| --- | --- | --- |
| `US/USPTO/patent` | Utility fees plus the procedural, PTAB, PCT and service fees every application shares | Maintenance years 4, 8, 12 |
| `US/USPTO/design` | Fees specific to design applications, including Hague | Not applicable |
| `US/USPTO/trademark` | Electronic and paper fees, post-registration, TTAB, Madrid | Renewal year 10 |

Every fee code is mapped explicitly. Patent rows carry one code per entity
tier (1xxx large, 2xxx small, 3xxx micro); 4011 is the small-entity
electronic filing fee and maps to `small` only. Rows with one code and one
amount for everyone (PCT fees to foreign offices, service fees, pro hac vice)
use tier `none`. Trademark rows become an electronic fee (7xxx) and, where
paper filing is allowed, a paper fee (6xxx) with a `paper_filing` condition;
combined filings join their codes with `+` (`7201+7205` for Sections 8 and 9).
Zero-dollar rows the page lists without a code are keyed by their rule
(`37 CFR 1.18(d)(1)`). Maintenance fees are due 3.5, 7.5 and 11.5 years after
grant and are stored as years 4, 8 and 12, as in Python.

The effective date is the one the page states (January 19, 2025). The page
also states a revision date (August 14, 2026), which goes in
`provenance.as_of_status` and the notes and is never used as the effective
date. A future effective date is reported as scheduled.

The parser fails with `INVALID_RESPONSE` when a section appears or disappears,
a column header changes, the effective-date header is missing, an amount is
not plain dollars, or a fee code is malformed. Fees the page gives only as
"variable" or "paid to WIPO" (1619, 1782, 7951-7954) are omitted and named in
the notes. Enrollment, penalty, Fastener Quality Act and general service fees
are not IP-right fees and are skipped, as in Python. Plant-specific fees are
omitted because there is no plant route.

This corrects the Python scraper, which still behaves the old way:

1. Its keyword split on "- Design" sends the design issue fee (1502), the
   Hague design issue fee, the design size fee and the Hague transmittal fee
   to the utility schedule, along with plant search, examination, size and
   issue fees. The reissue search and examination fees (1114, 1314) mention
   Design CPA reissues, so Python files them under design only and the
   utility schedule loses them. Here they are in both.
2. It skips two-code rows, so the third-party submission fee (1818/2818) is
   missing.
3. It files the Section 9 grace-period and deficiency fees as renewals at year
   10, so a renewal lookup returns them; here the grace fee is a late fee and
   the deficiency fee is `other`.
4. Its caption rules make every PCT national and international stage fee a
   filing fee, including search, examination and excess-claim fees, and its
   trademark per-class condition (`classes_over`, threshold 1) implies the
   first class is free. Here per-class fees use threshold 0.
5. It emits single-amount rows such as PCT foreign-office fees three times,
   once per tier, under one code.

### Cross-check

Amounts were compared with 37 CFR as published in the eCFR (title 37 issue of
August 26, 2026, fetched October 21, 2026): utility, design, provisional and
reissue filing fees (1.16(a), (b), (d), (e)), utility and design issue fees
(1.18(a), (b)(1)), the three maintenance fees (1.20(e)-(g)) at all three
tiers, and the trademark paper and electronic application and renewal fees
(2.6(a)(1), (a)(5)). All match the page and are pinned in the tests.

## KIPO

`KipoFeesClient` ([source](../packages/client/src/fees/kipo.ts)) parses
KIPO's two English fee pages, as Python does: patents
(`https://www.kipo.go.kr/en/HtmlApp?c=92004&catmenu=ek03_04_01`, which also
has utility model and PCT tables) and trademarks and designs
(`...?c=93006&catmenu=ek04_04_01`). Both pages answer plain requests and were
recorded live on October 22, 2026.

| Route | Content | Recurring fees |
| --- | --- | --- |
| `KR/KIPO/patent` | 66 fees: application, examination, annual fees, conversions | Renewal years 1-25, basic and per claim |
| `KR/KIPO/trademark` | 24 fees: per-class application, registration, renewal, opposition | Renewal year 10 (lump sum and installment) |
| `KR/KIPO/design` | 60 fees: application by examination track, examination, annual fees, divisions | Renewal years 1-20 for each of two tracks |

Each table has two columns. A fee with sub-items ("a. Basic fee / b.
Additional fee for each claim") has a description cell with a rowspan, and
the following rows carry only further amounts; the parser follows the
rowspan instead of guessing from cell text. Every known row is matched by
section and exact wording to an explicit rule that also checks how many
amounts it has and whether they are labelled electronic or paper. A row with
no rule still appears, as `other`, and is listed in `unmapped_codes`; a known
row that disappears or changes shape fails with `INVALID_RESPONSE`. KIPO
publishes no fee codes, so codes are readable slugs with Python's prefixes
(`kr-`, `kr-tm-`, `kr-des-`), for example `kr-annual-fee-y10` and
`kr-tm-renewal-installment`. The effective date is the one the pages state
("in effect since August 1, 2023", as Python has it), and each page's "Last
updated" date goes in `provenance.as_of_status`. Amounts are whole won.
Paper rates are separate fees with a `paper_filing` condition. KIPO's fee
reductions are a separate refund program, so every fee has tier `none`.
Utility model and PCT tables are not routed, as in Python.

Annual patent fees are a basic fee plus a fee for each claim, both per year;
each year gets a renewal row and an `excess_claims` row (claims_over,
threshold 0). Trademark charges for designated goods beyond 10 in a class are
`excess_classes` rows without a condition, because the closed trigger
vocabulary counts classes, not goods; the notes say so. Designs have two
annual-fee tracks (after substantive and after partial-substantive
examination), so a renewal lookup by year returns one row per track.

This corrects the Python scraper, which still behaves the old way:

1. A rowspan continuation cell ("18,000(electronic) 20,000(paper-based)") is
   read as a section header, so every examination fee after the priority
   claim (substantive examination, reexamination, preferential examination)
   is filed as `other`.
2. Amounts on continuation rows are dropped unless the description ends in
   "Basic fee", which only annual-fee rows do: the per-claim examination fee
   (51,000), the per-claim reexamination fee (10,000), the paper page fee
   (1,000) and the additional priority-claim fee are missing, and so are the
   paper rates on the patent page.
3. Annual fees are `maintenance` (the USPTO 3.5/7.5/11.5-year category)
   rather than `renewal`, and the per-claim annual fee is one row per band
   with no year, so a lookup by year never returns it. Per-claim conditions
   use threshold 1; KIPO charges for every claim.
4. Reexamination is filed as `ptab` and the patent-term-extension application
   as `extension` (extension of time). Here they are `examination` and `other`.
5. The trademark goods surcharge carries `classes_over` with threshold 10,
   which reads as "more than ten classes"; its renewal rows have no year.
6. The design divisional row loses its second rate pair (59,000 electronic,
   69,000 paper); the two design application tracks have nearly identical
   labels; paper rows have no `paper_filing` condition; and a trailing
   "Application fee" cell is read as a section header, so later trademark
   codes name the wrong section.

## JPO

`JpoFeesClient` ([source](../packages/client/src/fees/jpo.ts)) parses the
JPO schedule of fees page
(`https://www.jpo.go.jp/e/system/process/tesuryo/hyou.html`), as Python does.

**Blocked for live recording.** On October 22, 2026 the JPO's CloudFront edge
answered every plain request from this machine with HTTP 403 and a "page not
found" body, including the English home page and `robots.txt`, with the
project user agent and with curl's default. Python gets through by sending a
Chrome user agent and browser `Sec-Fetch-*` headers; this port does not
impersonate a browser. The routes are registered and send the project user
agent; where the JPO refuses, they fail with the HTTP 403 rather than return
anything. The parser is built and tested against the page Python's tests
saved on May 20, 2026 (`tests/fixtures/fees/jpo-hyou-2026-05-20.htm`, kept as
`.htm` so Biome does not lint it). There is no JPO cassette and no `jpo`
recorder operation.

| Route | Content | Recurring fees |
| --- | --- | --- |
| `JP/JPO/patent` | 253 fees: filing, examination (two cohorts), annual fees (four cohorts), opposition and trials, shared procedural fees | Renewal years 1-25, basic and per claim |
| `JP/JPO/trademark` | 38 fees: application, registration and renewal (full or installment), defensive marks, opposition and trials, shared procedural fees | Renewal year 10 |
| `JP/JPO/design` | 52 fees: application, secret design, annual fees, appeal and trial, shared procedural fees | Renewal years 1-25 |

The page has numbered sections (1. Application ... 6. After Registration);
sections 1-4 have one table per right under "(1)Patents" ... "(4)Trademarks",
and sections 5 and 6 are single tables for every right. Rowspans and colspans
are expanded into a grid so continuation rows keep their labels. Fee cells
must be `¥X`, `¥X + ¥Y per claim|classification|sheet` or `¥X per
classification`; anything else fails with `INVALID_RESPONSE`, as do a
missing effective-date heading and a table outside the numbered sections.
Rows are mapped by section, right and wording; unknown rows appear as
`other` and are listed in `unmapped_codes`. The effective date is the one the
page states ("Schedule of fees (on or after April 1, 2022)", Python's date).

The per-claim, per-classification and per-sheet parts of a fee are separate
`excess_claims`, `excess_classes` and `excess_pages` rows with threshold 0.
Examination fees differ for applications filed before and after April 1,
2019, and patent annual fees by filing date (1988) and examination-request
date (April 1, 2004); every cohort is listed, the current one without a code
suffix (`jp-annual-fee-y10`, `jp-annual-fee-exam-pre-2004-y10`, ...), so a
patent renewal lookup by year returns four rows. Design annual fees are
¥8,500 for years 1-3 and ¥16,900 from year 4 to the end of a term of 15, 20
or 25 years depending on the filing date; years 16-25 say which designs they
apply to. Section 5 procedural fees and the general-succession and
owner-name fees of section 6 appear in all three schedules with all four
rights listed; transfer-of-right fees and the two Article 50 extension fees go
to their own right only.

This corrects the Python scraper, which still behaves the old way:

1. It de-duplicates rows by the first 60 characters of the description, so
   it drops the examination fee where another International Searching
   Authority made the search report (¥124,000 + ¥3,600 per claim; ¥106,000
   before 2019) and the design Article 50 extension (¥7,200).
2. It reads only the first two cells of rowspan rows, so it loses the patent
   transfer fee (¥15,000) and every on-line certificate, inspection and copy
   fee (it keeps one unlabelled "-over the counter" row of ¥1,400), and files
   the utility model, design and trademark transfer fees in the patent
   schedule as `other`.
3. Annual fees are `maintenance` instead of `renewal`; the PCT and
   designated-search examination fees are `filing`; patent trials are `ptab`
   (the USPTO board) while trademark and design trials are `trial`;
   registration of a patent term extension is `extension` (extension of
   time); foreign-language applications and PCT national phase entry are
   `other`.
4. The trademark and design schedules have none of the shared procedural
   fees (extensions of time, certificates, inspection), and design labels
   keep footnote marks ("Design application ※1").

## IPO India

`IpIndiaFeesClient` ([source](../packages/client/src/fees/ipindia.ts)) parses
the First Schedule to the Patents Rules, 2003, from the PDF Python uses
(`https://ipindia.gov.in/frontend/pdf/forms_and_official_fees/Schedule_1.pdf`,
8 pages, recorded live on October 22, 2026). The route is `IN/IPIN/patent`:
330 fees from entries 1-59, with renewal years 3-20 complete.

The PDF is a seven-column table: entry number, what the fee is for, form,
then four rates. The rate columns are **e-filing** for natural persons,
startups, small entities and educational institutions (tier `small`) and for
other applicants (tier `large`), then **physical filing** for the same two
groups. The parser uses the shared `pdfPageItems` helper and the x positions
of the column header on page 1, groups text into per-column lines across
pages, and treats a height at which all four rate columns start with an
amount or "No fee" / "Not allowed" / "Not applicable" as a rate row. Rate
rows labelled "(i)", "(ii)" ... take their description from the matching
sub-item. Each entry number is checked against the wording it must still
have; an entry whose wording changed is `other` and listed in
`unmapped_codes`. Codes are `in-<entry>[-<sub-item>|-y<year>]-<tier>-<mode>`,
for example `in-1-ii-small-efile` or `in-18-y10-large-paper`. Physical-filing
fees carry a `paper_filing` condition. "No fee" cells are fees of 0; "Not
allowed" and "Not applicable" cells are omitted and named in the notes of the
same row. A physical rate below the e-filing rate of the same group fails
with `INVALID_RESPONSE`. Patent-agent register fees (entries 34-38) are not
fees on a patent right and are left out, as the USPTO enrollment fees are;
entry 58 is charged "as applicable" and has no amount.

The PDF states no effective date, so `effective_date` is null and
`as_of_status` says so. Its content, including the certificate of
inventorship (Form 8A) and grace-period (Form 31) fees, matches the Patents
(Amendment) Rules, 2024; the notes say this rather than adopting Python's
constant of March 15, 2024.

This corrects the Python scraper, which still behaves the old way:

1. It reads the four rates as small e-filing, small paper, other e-filing,
   other paper. The PDF's order is small e-filing, other e-filing, small
   physical, other physical, so every Python India fee in the middle two
   columns has the wrong tier and mode: for the year-3 renewal it lists 4,000
   as the small-entity paper fee (the other-applicant e-filing fee) and 880 as
   the other-applicant e-filing fee (the small-entity physical fee). Its
   "paper is never below e-filing" check passes because of the swap.
2. Its regular expressions capture only entries 6, 18 and 59 (80 fees). The
   filing fee (entry 1, which has an asterisk), every entry with sub-items or
   "Not allowed" cells, examination, opposition and restoration are missing.
3. Renewal fees are `maintenance` rather than `renewal`.
4. Its landing page constant (`https://ipindia.gov.in/form-and-fees.htm`)
   returns HTTP 404; the PDF URL still works.

## EUIPO

**Blocked; not ported.** `EP/EUIPO/trademark` and `EP/EUIPO/design` still
report `NOT_PORTED`. On October 22, 2026 `www.euipo.europa.eu` answered every
plain request (both fee pages, the home page and `robots.txt`) with a
CloudFront "Request blocked" HTTP 403, with the project user agent and with
curl's default. Python gets through with a Chrome user agent and browser
`Sec-Fetch-*` headers. Python's tests keep no saved EUIPO fee page (only
parser unit tests), so there was nothing to build the parser against. The
fees themselves are fixed in Annex I of Regulation (EU) 2017/1001 and in the
annex to Regulation (EU) 2024/2822, but EUR-Lex answered a plain request with
a 202 challenge page, so that route was not pursued either.

## MCP

`get_fee_schedule`, `list_fee_jurisdictions` and `lookup_fee` keep the Python
names and lookup semantics (no year excludes renewal rows; tier applies only to
tiered rows). They are registered unconditionally because neither source needs
credentials, and they require the `fees:read` scope over HTTP. The `get_fees`
facade serves USPTO by routing alone; it accepts `refresh` only for USPTO, as
Python does, and since nothing is cached every call already fetches the page.

## Verification and limits

`bun run record:fees` recorded both EPO routes live on October 21, 2026: 112
EPC fees and 41 Unitary Patent fees, no unmapped codes, complete renewal
coverage. It recorded the USPTO page the same day: 412 patent, 42 design and
113 trademark fees, no unmapped codes.
[Tests](../tests/fees.test.ts) replay those recordings and check specific
amounts, the 50% late-fee relation for every year, the Article 2 cross-check,
amount parsing, drift detection, schema rules, resolver parity, MCP filters and
the `fees:read` scope. The USPTO tests check the eCFR amounts, tier codes,
route membership, trademark paper and combined codes, single-fetch sharing and
page drift.

There is no response cache: each call fetches the source (the EPO feed is
about 23 KB, the USPTO page about 210 KB). Python caches both for seven days
and keeps a USPTO revalidation receipt; neither is ported, and the
`get_fee_schedule` and `lookup_fee` tools have no `refresh` input.
Nothing is deployed.

`bun run record:fees` also records KIPO (both pages) and the IPO India PDF;
both were recorded live on October 22, 2026 with the project user agent
(`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`),
which the KIPO, JPO and IPO India clients send. Their tests
([KIPO](../tests/fees-kipo.test.ts), [JPO](../tests/fees-jpo.test.ts),
[IPO India](../tests/fees-ipindia.test.ts)) check counts, published amounts
for every right, renewal ladders, cohorts, column order, drift handling and
alias routing. Because `listSchedules` fetches every route with
`Promise.all`, `list_fee_jurisdictions` fails whenever one source refuses,
as the JPO does from this machine; making it report per-route failures is a
change to the shared client and is left for when the remaining offices land.
