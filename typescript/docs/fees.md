# Fee schedules

October 21, 2026. EPO fees were the first TypeScript fee connector and the
reference for porting the other offices in the Python `fees` package; USPTO
fees followed. On October 22, 2026 CIPO, CNIPA, DPMA, IP Australia, ILPO and
IMPI were ported.

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

## CIPO

`CipoFeesClient` ([source](../packages/client/src/fees/cipo.ts)) parses CIPO's
patent fee page
(`https://ised-isde.canada.ca/site/canadian-intellectual-property-office/en/patents/patent-fees`).
The page holds one panel per year ("2026 list of fees for patents" and, from
autumn, next year's list marked subject to change), each with four tables:
extension of time, applications, international applications and patents.
The client takes the latest list whose year has started, checks that the
column headers name that year, and uses January 1 of it as the effective
date, which the page states ("On January 1, 2026, certain fees ...
increased by 2.7%").

| Route | Content | Recurring fees |
| --- | --- | --- |
| `CA/CIPO/patent` (163 fees) | Application, examination, final, PCT, post-grant and copy fees | Maintenance, anniversaries 2-20 |

Fees that differ for small entities have a `small` and a `large` row; fees
that do not are one untiered row. CIPO's maintenance fees are annual, so
they are categorized `renewal` (the vocabulary keeps `maintenance` for the
USPTO's 3.5/7.5/11.5-year fees) and expanded from the word bands ("second,
third and fourth") to one row per anniversary, separately for pending
applications and granted patents. The 20th-anniversary fee is also due each
later year; maintenance of category 1 patents counts from the issue date and
is categorized `other` with its anniversary year. Fees the page gives only as
"See description" (PCT international filing and handling fees and their late
fees) are omitted and named in the notes. CIPO publishes no fee codes; codes
use Python's slug (fee type, year, tier), numbered when a slug repeats.

Not yet recorded live: on October 22, 2026 every request to
`ised-isde.canada.ca`, the fee page included, returned 503 with the site's
"temporarily offline while we carry out urgent maintenance" page. The tests
run against the Internet Archive's raw capture of the same page from October
6, 2026 (`tests/fixtures/fees/cipo-patent-fees-2026-10-06.html.gz`, served
with that capture's date); `bun scripts/record-fees.ts cipo` records the
live page once the site is back, after which the tests should replay that
cassette instead.

This corrects the Python scraper:

1. It reads only four-cell rows, but each fee type cell spans its sub-rows,
   so every second and later row of a group is dropped: maintenance years
   5-19, the standard examination fee, both per-claim fees, the final-fee
   page fee and more (84 fees instead of 163).
2. It treats the second set of tables as a print copy and keeps the first by
   caption, which is only correct while the current year's panel comes
   first; its effective date is the constant 2026-01-01.
3. It categorizes every PCT fee as filing, uses threshold 0 for the
   final-fee page surcharge (the page says over 100 pages), and files
   re-examination as `ptab`.
4. Its codes collide (application and patent maintenance rows, two late
   fees), and it emits untiered fees twice, as small and large.
5. It requests the retired `www.ic.gc.ca` URL and relies on the redirect.

## CNIPA

`CnipaFeesClient` ([source](../packages/client/src/fees/cnipa.ts)) parses the
English fee page (`https://english.cnipa.gov.cn/col/col3000/index.html`), one
table with a domestic part in Roman-numeral sections, rows split by right
("1. Invention", "2. Utility Model", "3. Design"), and a PCT part.

| Route | Content | Recurring fees |
| --- | --- | --- |
| `CN/CNIPA/patent` (48 fees) | Invention-patent domestic fees, PCT international-phase and national-entry fees | Annual fees, years 1-20 |

As in Python, only invention rows are routed; utility model and design rows
on the same page are not. Annual fees are published in bands and expanded to
one row per year. The page publishes no effective date. The late annual-fee
surcharge (5% of the annual fee per month) has no fixed amount and is noted,
not emitted. Codes are Python's slugs.

This corrects the Python scraper:

1. It reads the PCT rows as domestic sections I and II, so the PCT search,
   preliminary examination, copy and restoration fees become `filing` fees
   with domestic-looking codes. They are now `cn-pct-…` with their own
   categories.
2. The second excess-page tier (over 300 pages) carries threshold 30.
3. Reexamination and invalidation are `ptab`; they are now `appeal` and
   `cancellation`. Extension-of-time fees, charged per month, now say so.

## DPMA

`DpmaFeesClient` ([source](../packages/client/src/fees/dpma.ts)) parses form A
9510.1 (`https://www.dpma.de/docs/english/formulare/allg_eng/a9510_1.pdf`)
with the shared PDF helper. Rows are six-digit fee numbers with a dot leader
and a whole-euro amount; a row's text may wrap onto following lines.

| Route | Content | Recurring fees |
| --- | --- | --- |
| `DE/DPMA/patent` (101 fees) | Fee numbers 31x xxx: application, search, examination, annual fees, SPCs and other requests | Annual fees, years 3-20; SPC years as 21-26 |

Every patent fee number is mapped explicitly; unknown 31x numbers appear as
`other` in `unmapped_codes`. Each annual fee has a licence-of-right row at
half the amount and a 50-euro late surcharge, both carrying the same year.
Supplementary protection certificate annual fees are stored as years 21-26,
following the INPI France convention. Fee 311 100 (paper filing) is stated as
150% of 311 000 and is stored at that amount with a `paper_filing`
condition. The PDF's edition ("July 2026") goes in `as_of_status`; DPMA
publishes no effective date. Utility model, trade mark and design fees in the
same PDF are not routed, as in Python.

This corrects the Python scraper:

1. Its single-line pattern drops every row whose text wraps: 311 500, 311
   600, 313 800, 313 810, 313 820, 313 900 and 314 100.
2. The claim surcharges 311 050 and 311 160 have no `claims_over`
   condition because the qualifying words are on the next line.
3. Licence-of-right rows are `other` with no year (the notes say they are
   maintenance rows with a year), late surcharges have no year, and SPC
   annual fees are `other`.
4. SPC duration extensions are `extension` (extension of time), and the
   search for an extended patent is `examination`.

## IP Australia

`IpAustraliaFeesClient` ([source](../packages/client/src/fees/ipaustralia.ts))
reads two pages: procedural fees from
`https://www.ipaustralia.gov.au/patents/timeframes-and-fees` and the standard
patent renewal table from
`https://www.ipaustralia.gov.au/manage-my-ip/how-to-renew-my-ip-right`.

| Route | Content | Recurring fees |
| --- | --- | --- |
| `AU/IPAU/patent` (67 fees) | Filing, search, examination, acceptance, claim, amendment, extension, re-examination and copy fees | Renewals, anniversary years 4-24 |

Each renewal year has an online fee and the higher fee for other payment
methods, which carries a `paper_filing` condition, as do postal application
fees. Years 20-24 apply only to extended pharmaceutical patents and say so.
The grace-period surcharge (100 dollars per month) is a `late_fee`. Claim
fees depend on whether examination was requested before or on/after 1
October 2024, and the notes say which; for the acceptance rows published as
"$300 plus $125 per claim" the per-claim part is the fee (the $300 is the
acceptance fee itself). The pages publish no schedule date; the effective
date is 2024-10-01, when the current claim fees began, and becomes null if
the page stops referring to it. Innovation patent renewals are not included.
Codes are Python's slugs.

This corrects the Python scraper:

1. Its renewal ladder is a hard-coded copy of years 4-19; it is now read from
   the renewal page, with years 20-24 and the other-payment fees.
2. "Examination of more than 30 claims" (250 dollars per claim over 30) has
   threshold 20, and the acceptance rows store the base amounts ($300 as an
   examination fee, $1550 with threshold 20) instead of the per-claim fees.
3. Postal fees have no paper condition, and re-examination is `ptab`.

## ILPO

`IlpoFeesClient` ([source](../packages/client/src/fees/ilpo.ts)) parses the
Hebrew-only annual fee notice
(`https://www.gov.il/BlobFolder/news/ilpo-fees/he/news_fees-2026.pdf`). The
gov.il landing page answers plain requests with a Cloudflare 403, but the PDF
itself is served, so it is recorded live; Python's docstring says both are
blocked. The PDF is right-to-left, so lines are rebuilt from text positions
with `pdfPageItems`: item numbers sit at the right margin, amounts in a
column at the left. Items are matched by their number path (`8(ב)(1)`), and
the parser fails if an expected item is missing or an unknown one appears.

| Route | Content | Recurring fees |
| --- | --- | --- |
| `IL/ILPO/patent` (47 fees) | Patent items 1-22, PCT authority fees, patent term extension fees | Renewal periods ending years 6, 10, 14, 18, 20; extensions as years 21-25 |
| `IL/ILPO/trademark` (19 fees) | Trade mark items 1-14 and three Madrid handling fees | Renewal, year 10 |
| `IL/ILPO/design` (21 fees) | Designs Law 5777-2017 items 1-15 | Renewal periods ending years 10, 15, 20, 25 |

The effective date (2026-01-01) is read from the notice. Labels are English
summaries; the Hebrew notice and the Reshumot publication control. Renewals
are paid for periods and stored at the last year each covers, as in Python.
Items with the 40% first-application reduction (patent items 1 and 10,
design items 1 and 2) have a `large` row and a `small` row at 60%, rounded to
the nearest shekel as Python does. Legacy design fees (pre-2018 designs) and
the maximum-costs table are not routed. The PDF URL names the year; it must
be updated when the 2027 notice is published.

This corrects the Python scraper:

1. It misreads the patent term extension table: the fourth-year extension
   fee (7,223) and the opposition fee (2,402) are lost, the cancellation fee
   is labeled as the fourth-year fee, and the extension fees are years 1-3,
   two of them at year 1. They are now years 21-25.
2. The whole-term renewal (14,410) is a year-20 renewal next to item 12(5),
   and the all-periods design renewal (3,535) a year-25 renewal next to item
   5(4), so lookups return two amounts. Both are alternatives and are now
   `other`.
3. The full-amount rows of reducible items have tier `none`, so a
   small-entity lookup returns both amounts; they are now `large`.
4. Restoration requests are `other`; they are now `petition`.

## IMPI

`ImpiFeesClient` ([source](../packages/client/src/fees/impi.ts)) parses the
consolidated tariff Acuerdo
(`https://www.gob.mx/cms/uploads/attachment/file/824879/Acuerdo.Tarifa.12.05.23.pdf`).
Rows are article codes (`1 a`, `1 a bis`, `14b`, `16 quáter`) with MXN
amounts; every code is mapped explicitly to routes and categories.

| Route | Content | Recurring fees |
| --- | --- | --- |
| `MX/IMPI/patent` (109 fees) | Articles 1-5, 13, patent information services and procedural fees | Annuities, years 1-20 |
| `MX/IMPI/utility_model` (83 fees) | Articles 9 a-9 e bis, 10, 12 a (utility models and integrated-circuit layout designs) | Annuities, years 1-15 |
| `MX/IMPI/design` (44 fees) | Articles 9 f-9 g, 11, 12 b, 37 III | Renewals at years 5, 10, 15, 20 |
| `MX/IMPI/trademark` (34 fees) | Article 14, Madrid fees paid to IMPI (36 b), procedural fees | Renewal, year 10 |

The utility_model route is new: Python bundles utility models and layout
designs into the patent schedule, where their annuities collide with patent
annuities, so they now have their own route. Rows eligible for the Disposición Cuarta 50% reduction
(Articles 1 a-1 f, 2-13, 19-23, 26 BIS) have a `large` row and a `small`
row at half, rounded half-to-even as Python does; other rows are untiered.
Procedural Articles 16-18 and 27-34 appear in every schedule. Amounts exclude
16% VAT. Article 15 (appellations of origin) has no route; Article 35 (PCT)
and the CHF fees of Articles 36-37 are omitted. The effective date is the
DOF date of the last reform (2023-05-12), read from the PDF; the March 2024
indigenous-community waiver is not in the PDF and is not applied.

This corrects the Python scraper:

1. The Madrid fees paid to IMPI (Article 36 b, items 1-4) are read as
   Articles 1-4 and land in the patent schedule, one as a year-1 annuity.
2. It misses rows without "$" or without a space after the article number:
   9 e (layout design filing), 14b (trade mark opposition, 3,704.09), 14f
   and 14g.
3. Annuities are stored once at a representative year (1, 6, 11); they are
   now one row per year, and design renewals one row per renewal.
4. Categories: trade mark filing (14 a) is `grant`, patent correction (1 f)
   is `extension`, design filing (9 f) is `other`, transfer recording (32)
   is `cancellation`, and the per-page fees are `other`.
5. Rows without a reduction are tier `large`, so a small-entity lookup drops
   every trade mark fee; they are now untiered. Article 13 and the patent
   information services no longer appear in the trade mark schedule, and
   the trade mark search report (24) appears only there.

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

## OEPM (Spain)

`OepmFeesClient` ([source](../packages/client/src/fees/oepm.ts)) reads OEPM's
single fee PDF, "Tasas y precios públicos"
(`https://www.oepm.es/export/sites/portal/comun/documentos_relacionados/PDF/TASAS_y_PRECIOS_PUBLICOS.pdf`),
with the shared pdfjs helper. One fetch serves all three routes. The effective
date is the one page 1 prints ("desde el 1 de abril de 2026").

| Route | Fees | Recurring fees |
| --- | --- | --- |
| `ES/OEPM/patent` | 369: patents and utility models at three applicant tiers, procedural fees, annual fees, SPCs, EP validation, topographies, PCT | Annual fees, years 3-20 |
| `ES/OEPM/trademark` | 71: marks and trade names, per class, with renewals and surcharges | Renewal year 10 |
| `ES/OEPM/design` | 92: per-design bands for filing, opposition and renewal | Renewal year 5 |

Fee codes are OEPM's, as `oepm-<code>` like Python. Rows printed without a code
of their own extend the code they sit with: further classes (`oepm-MT01-class`),
multi-design bands (`oepm-DT40-11-20`), surcharge columns of the transitional
quinquennia (`oepm-DQR1-25`) and per-page fees (`oepm-CM04-page`). PCT fees,
which the PDF lists without codes except PCT1, use descriptive codes
(`oepm-pct-transmittal`). The full rate (IT/IE, I3/I5, IP) is tier `large`; the
SME and individual-entrepreneur rate (YT/YE, YP) and the public-university rate
(UT/UE, I7/I8, UP) are both `small` and are told apart by their notes, as in
Python. Paper rows carry a `paper_filing` condition. Agent registration (BB01,
BB02) and the public prices are not IP-right fees and are omitted.

Multi-column tables are parsed as blocks: the code and column count of each are
checked, and one code listed at two amounts fails. Every amount was compared
with the PDF text for the routes' spot checks in the
[tests](../tests/fees-oepm.test.ts).

This corrects the Python scraper, which still behaves the old way:

1. Its trademark catalog labels most codes with the meaning of a neighbouring
   row: MT17/ME17 (a class not paid with the application) as the first-class
   application fee, MT18/ME18 as the further-class fee, MT07/ME08 (urgent
   resolution) as a priority claim, MT08/ME09 (priority) as an assignment, and
   MT15/ME10 (recordals) as a class not paid. The real application fees,
   MT01/ME01 (150.45 and 127.88 for the first class, 97.48 and 82.84 for each
   further class) and the collective-mark MT02/ME02, are never emitted, and
   its catalog calls ME01 and ME02 oppositions.
2. Its "common" bucket puts the patent-section procedural fees (I3xx, I5xx,
   I7xx, I8xx) and the transitional design codes (DQR) into the trademark and
   design schedules and the trademark and design procedural fees (CM, CI, CX,
   XC) into the patent schedule. The OEPM ISA search fee PCT1 lands in all
   three schedules as a transfer fee.
3. It skips the annual-fee table, so the patent schedule has no renewals. Here
   years 3-20 come at every tier with their 25% and 50% surcharges, and
   licence-of-right rates (IR, 2R, 5R) are kept with their year.
4. It files SPC maintenance fees CP01-CP55 as renewals for years 1-5, so a
   year-3 renewal lookup would return an SPC fee. They are single fees set by
   the SPC's term, not annual fees, and carry no year here.
5. The design filing row matched DT40 to the 21-30 band amount (56.66); the
   other bands, the opposition bands (DT45) and the renewal table (DT41-DT43,
   DE41-DE43) were missing. The transitional quinquennia kept one of three
   amounts.
6. Labels come from a 250-character text window and often carry another row's
   text; here every code has a catalog label. Smaller fixes: amendments
   (CM07) are `other`, not `transfer`; urgent resolution (IT03) is a
   `petition`, not an `extension`; the international registration request
   (MT03/ME06) is `madrid`.

## PRV (Sweden)

`PrvFeesClient` ([source](../packages/client/src/fees/prv-se.ts)) parses
PRV's three English fee pages, as Python does: patents
(`https://www.prv.se/en/patents/the-advanced-patent-guide/fees-and-payment/`),
trademarks and designs. The patent page keys each fee by a stable PRV ID
(SE-1, N-3, PCT-2), mapped explicitly; the trademark and design pages have no
IDs and are mapped by label. Codes match Python's slugs (`se-pat-n-3`,
`se-tm-e-service-...`).

| Route | Fees | Recurring fees |
| --- | --- | --- |
| `SE/PRV/patent` | 98: national, PCT, EP validation, SPC, certificates, consultancy | Annual fees, years 1-20 (1 and 2 are SEK 0) |
| `SE/PRV/trademark` | 42: e-service and other-channel rates, international | Renewal year 10 |
| `SE/PRV/design` | 18 | Renewal year 5 |

The pages publish no effective date, so `effective_date` is null. Each page
states when it was last edited (patents 2026-01-01, trademarks 2025-04-25,
designs 2023-03-18); that goes in `provenance.as_of_status` and the notes,
never in `effective_date`. Python's constants (2025-03-15, 2025-04-25,
2025-04-25) are not on the pages: its trademark date is the page's edit date
and its design date postdates the design page's last edit.

This corrects the Python scraper, which still behaves the old way:

1. It reads the SPC annual fee NT-2 as the year-2 annuity because its ID ends
   in 2, so a year-2 renewal lookup returns SEK 20 000 next to the real SEK 0.
2. Its formula check emits the "By quotation" consultancy rows KT-6 to KT-15
   at SEK 0, and the formula rows PCT-5, PCT-11 and PCT-18 at SEK 0; its own
   notes say they are skipped. Here they are omitted and named in the notes.
3. Fee reductions (PCT-3, PCT-4, PCT-9, PCT-10) are filing, search or
   examination charges in Python; here they are `other` and noted as
   reductions.
4. Design renewals are stored as year 10 although designs renew every five
   years, and the late-renewal surcharge is a renewal; here renewals are year
   5 and the surcharge is a late fee. Trademark per-class renewal fees and the
   increased renewal fee lacked year 10 and the renewal category.
5. Row labels run the fee name into its description ("SE-1: Filing fee
   Application fee: 500 SEK..."); here the description is in the notes.
   Re-establishment and reinstatement fees are petitions, SE-9 and SE-16 are
   excess-claim fees, EP-1 to EP-3 are translation fees, the PCT-2 sheet fee
   uses `sheets_over`, and other-channel rows carry `paper_filing`.

## UKIPO (United Kingdom)

`UkipoFeesClient` ([source](../packages/client/src/fees/ukipo.ts)) reads the
official CSV fee tables that the UK IPO links from its guidance "New fees from
1 April 2026"
(`https://www.gov.uk/government/publications/intellectual-property-office-new-fees-from-1-april-2026/new-fees-from-1-april-2026-for-designs-trade-marks-and-patents`).
The guidance page gives the effective date ("The new fees will take effect on
1 April 2026") and the link to each CSV, which is fetched from
assets.publishing.service.gov.uk. Amounts are the CSV's "New Fee" column. The
trade marks CSV is Windows-1252 and is decoded as such.

| Route | Fees | Recurring fees |
| --- | --- | --- |
| `GB/UKIPO/patent` | 67: application, search, examination, excess claims and pages, procedural, PCT, SPC | Renewal (maintenance) years 5-20 |
| `GB/UKIPO/trademark` | 43: domestic and the UK IPO's international handling fees | Renewal year 10 |

Python scrapes the gov.uk per-form pages instead. Most of those pages state no
amount, so Python takes the first pound figure anywhere on the page, which
gives one fee per form: the patent application form (1, 7, 9A and 10) yields
£75 and loses the search, examination, excess-claim and excess-page fees; the
grant-fee form yields only its £27 excess-claim fee; SPC annual fees yield only
year 1; late-renewal fees and the trademark class, series, expedited
examination and late-renewal fees are missing. The CSVs carry all of these.
The renewal ladder Python hard-codes for years 5-20 matches the CSV exactly, a
test checks that, and Python's `uk-patent-renewal-y<N>` codes are kept. Codes
for forms with several rows add the row label
(`uk-patent-form-9a-request-a-search-uk-application`). Restoring and renewing a
trade mark (TM13) is a late fee for year 10 rather than a renewal. The UK IPO
has design fees in a third CSV, but Python routes no UKIPO design schedule, so
none is added.

## WIPO (PCT, Madrid, Hague)

`WipoFeesClient` ([source](../packages/client/src/fees/wipo.ts)) parses the
three Schedules of Fees on wipo.int, as Python does. Amounts are whole Swiss
francs. The Hague page now lives at
`https://www.wipo.int/en/web/hague-system/fees/sched`; Python's old URL
redirects there.

| Route | Fees | Recurring fees | Effective date |
| --- | --- | --- | --- |
| `WO/WIPO-PCT/patent` | 7 | Not applicable | Not on the page (null) |
| `WO/WIPO-MADRID/trademark` | 30 | Renewal year 10 | February 1, 2023 |
| `WO/WIPO-HAGUE/design` | 32 | Renewal year 5 | July 1, 2026 |

Codes follow Python's item numbering (`wo-madrid-2-1-1`, `wo-hague-14bis-1`).
Labels include their parent items ("Basic fee - For one design"). Fees fixed by
each Contracting Party, and the Hague grace surcharge stated only in a
footnote, are omitted.

This corrects the Python scraper, which still behaves the old way:

1. Its effective dates are constants that the pages contradict: Madrid
   2024-11-11 against "as in force on February 1, 2023", Hague 2025-01-01
   against "as in force on July 1, 2026", and PCT 2026-04-01 where the page
   states none. Here the dates are read from the pages.
2. It reads the Madrid grace surcharge "50% of the amount of the fee payable
   under item 6.1" as CHF 50 and files it as a renewal; here it is CHF 326.50,
   computed from item 6.1, and a late fee.
3. Its Hague categorizer matches the first digit, so items 13-19 are filing
   fees and 20-22 publication fees; here they are recordals and other
   services. Renewal items 7 and 8 were year 10, although Hague registrations
   renew every five years; item 8 was not a renewal at all.
4. It reads only the first PCT amount, so the per-sheet fee (CHF 15 over 30
   sheets) is missing and reduction 4(a) appears as a CHF 100 filing fee;
   reductions 4(b) and 4(c) are missing. Madrid's unnumbered sub-rows under
   8.1-8.3 and the per-term fees of items 4.1 and 4.2 are missing, and Hague
   item 14bis is skipped.
5. Continued processing (Madrid 7.6) is a petition, not a transfer;
   limitation and division (7.3, 7.7) are `other`.

### Recordings

`feeRecordings("oepm" | "prv" | "ukipo" | "wipo")` recorded these sources live
on October 22, 2026 with plain requests and the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`;
none blocked them. The tests replay the recordings offline and check row
counts, spot amounts per right, renewal years, tiers, conditions, alias
resolution and drift failures.

## IPOS (Singapore)

`IposFeesClient` ([source](../packages/client/src/fees/ipos.ts)) parses the
three server-rendered IPOS "forms and fees" pages, as Python does:
`/about-ip/patents/forms-and-fees-singapore/`,
`/about-ip/trade-marks/forms-and-fees/` and `/about-ip/designs/forms-and-fees/`
on `www.ipos.gov.sg`. Each page has `Form | Description | Fee` tables keyed by
form code. The pages are large Next.js documents (the patent page is about
1.4 MB), so the recording is about 3 MB.

| Route | Fees | Recurring fees |
| --- | --- | --- |
| `SG/IPOS/patent` | 124 | PF15 renewal years 5-20, plus year 21 for each year after the 20th |
| `SG/IPOS/trademark` | 35 | Renewal year 10 |
| `SG/IPOS/design` | 26 | Extensions at years 10, 15, 20 and 25 |

Codes are Python's slugs (`sg-pat-pf1-request-for-the-grant-of-a-patent`,
`sg-tm-tm4-preapproved`, `sg-pat-pf15-y-5`), so the same row has the same code
in both runtimes. Categories come from the form code (PF1 filing, PF11 search,
PF12 examination, PF14 grant, TM28 cancellation, D13 cancellation) instead of
Python's description keywords; forms without a mapping appear as `other` and
are listed in `unmapped_codes`. The effective date stays Python's 2026-04-01,
the second tranche of the 2025 reform (Patents Circular 3/2025, Trade Marks
Circular 3/2025, Designs Circular 1/2025), because the pages state none of
their own; each page's "Last updated" date goes in `provenance.as_of_status`.
Screen-reader text ("opens in new tab") is excluded, as in Python. The PCT
receiving-office, ISA and IPEA tables on the patent page are not included, as
in Python.

This corrects the Python scraper, which still behaves the old way:

1. It emits every per-claim surcharge twice: once as a base fee (PF11 and
   PF12 at S$80 as search and examination fees, PF14 at S$40 as grant fees)
   and once as the `excess_claims` row. Here the surcharge is only the
   `excess_claims` row. PF13A's surcharge, over a claim count that depends on
   the application, is `excess_claims` with a null threshold, and PF14's
   (a)(iii)(B) surcharge is no longer dropped from the excess rows.
2. The second PF15 table (patents endorsed licence of right, half fees) is
   emitted as renewals too, so a renewal lookup for year 5 returns S$176 and
   S$88, and PF20 (restoration) repeats the ladder a third time. Here the
   licence-of-right fees are `other` (codes `sg-pat-pf15-lor-y-N`) and the
   restoration fees are late fees, so the lookup returns one fee. PF20's
   S$300 additional fee was a renewal for year 1; it is now a late fee without
   a year, and PF20's 20th-year row, which Python filed as `other`, is a late
   fee at year 20.
3. TM19 lists renewal (S$480), late renewal (S$700) and restoration (S$770)
   in one cell; Python makes all three renewals at year 10. Here only S$480
   is a renewal.
4. TM27 lists each amount before and "From 1 April 2026" after the reform;
   Python emits the superseded S$50 rates alongside the S$60 ones. Here only
   the amount in force is kept (codes `-v2`, `-v4`, `-v6`).
5. Keyword categories misfile many rows: the D3 design filing fee as
   `deferment`, D8 restoration and D13 revocation as `filing`, trademark CM6-CM8
   recordals as `filing`, TM HC3 extensions as `opposition`, patent CM4 and
   CM12 as `transfer`, PF58 (b)-(d) oppositions as `other` or `transfer`.
6. HC1 on the trademark page ("$1,000 for the first class and $800 for each
   subsequent class") puts the per-additional-class condition on the S$1,000
   first-class fee as well.
7. Its design notes say renewal rows are year 5 and registration lasts 15
   years; the rows are years 10-25 and registration lasts 25 years.

Multi-amount cells get labels from the cell's own headings ("Late renewal of
registration", "Second request"), which Python left identical.

## HK IPD (Hong Kong)

`HkIpdFeesClient` ([source](../packages/client/src/fees/hk-ipd.ts)) parses the
three Intellectual Property Department "forms and fees" pages,
`/en/{patents,trade-marks,designs}/forms-and-fees/index.html` on
`www.ipd.gov.hk`, as Python does. Each form (OP1, P10, T8, D11) is an
accordion with a small table; filing tables split e-filing and paper-filing
rates and trademark tables add a per-class column.

| Route | Fees | Recurring fees |
| --- | --- | --- |
| `HK/HKIPD/patent` | 75 | Standard-patent renewal years 4-20; short-term patent renewal at year 5 |
| `HK/HKIPD/trademark` | 42 | Renewal year 10 |
| `HK/HKIPD/design` | 37 | Extensions at years 10, 15, 20 and 25 |

Codes are Python's slugs, including its patent route tag (`hk-pat-ogp-`,
`hk-pat-rr-`, `hk-pat-stp-`, `hk-pat-gen-`). The form code now goes in each
fee's notes and drives the category. Tables are read as a grid with rowspan
and colspan expanded. Paper-filing rates are separate rows with a
`paper_filing` condition; "Nil" rows are zero fees, as in Python. A
short-term patent renewal and a standard-patent renewal both answer a year-5
renewal lookup; the code prefix tells them apart. The pages publish no
effective date, so `effective_date` is null and the page's revision date goes
in `provenance.as_of_status`.

This corrects the Python scraper, which still behaves the old way:

1. Its effective dates are the commencement dates of the ordinances or of
   the original-grant route (2019-12-19, 2003-04-04, 2000-06-27), not dates
   of the fee schedules. They are null here.
2. It drops rows whose fee cell is shared through rowspan: trademark
   revocation and invalidity applications and interventions (HK$800 each),
   merging registrations and deleting a mark from a series, and the HK$200
   per-class fee for a section 12 search.
3. It stores the short-term patent renewal at years 4 and 8. A short-term
   patent is renewed once, after its 4th year, so it is year 5 here, and it no
   longer conflicts with the standard-patent fee at year 4.
4. Trademark restoration with renewal (HK$4,000) is a renewal at year 10, and
   the HK$500 late renewal charge is only a note. Here both are late fees at
   year 10, so a renewal lookup returns the HK$2,670 renewal alone.
5. It reads "$2,000 for the first class and $1,000 for each additional class
   in respect of each additional application" (dividing a series) as one
   HK$2,000 per-additional-class fee. Here it is a HK$2,000 fee per
   additional application and a HK$1,000 fee per additional class.
6. It marks per-page copy fees with the `late_days` trigger. Here they use
   `pages_over` with threshold 0; per-copy fees carry a note instead.
7. It files the OP1 and P6 grant requests (the original-grant and short-term
   applications) as `grant`, the design set-of-articles filing fees as
   `other`, and restorations as `other`. Here they are `filing`, `filing` and
   `petition`.

## INPI France

`InpiFrFeesClient` ([source](../packages/client/src/fees/inpi-fr.ts)) reads
the "Tarifs des procédures applicables au …" PDF, found through its link on
the Tarifs landing page
(`/ressources/propriete-intellectuelle/tarifs-procedures-et-prestations-de-linpi`
on `www.inpi.fr`), with Python's fixed address
(`/inpi-block/download-document?id=20516`) as the fallback. Text comes from the
shared `pdfPageTexts` helper. One landing-page fetch and one PDF fetch serve
all three routes.

| Route | Fees | Recurring fees |
| --- | --- | --- |
| `FR/INPI-FR/patent` | 51 | Annuities 2-20 (the first is in the filing fee) |
| `FR/INPI-FR/trademark` | 14 | Renewal year 10 |
| `FR/INPI-FR/design` | 8 | Extensions at years 10, 15, 20 and 25 |

The PDF has no fee codes, so, as in Python, a catalog names each row. The
catalog is matched in document order within each section, and every amount is
read from the PDF; Python's catalog hard-codes the amounts and only checks
that a phrase is present. A missing or reordered row fails with
`INVALID_RESPONSE`; an amount line no catalog row claims appears as `other`
with an `inpi-fr-unmapped-` code. Codes are Python's (`inpi-fr-<row>-l`, plus
`-s` for the reduced rate). Rows with a reduced rate are tier `large` and
`small`; the rest are tier `none`. The effective date comes from the PDF
heading (2026-07-02, matching Python's constant). Late-payment surcharges are
percentages (50% of the fee due) and are omitted, as in Python.

This corrects the Python scraper, which still behaves the old way:

1. Its notes say the reduced rate for annuities 8-20 exists but pypdf drops
   it, and suggest estimating 50%. The PDF has no reduced rate after the 7th
   annuity; those rows are tier `none` here and nothing suggests an estimate.
2. Its notes give the reduced-rate threshold as fewer than 1,000 employees;
   the PDF says 250, which the notes now read from the footnote.
3. It puts a `classes_over` condition with threshold 1 on the one-class
   filing and renewal fees, which reads as a per-class charge beyond the
   first. The base fees now have no condition; the per-class fee carries it.
4. It stores one design extension fee at year 5. The fee is due for each of
   the four 5-year extensions, stored at years 10, 15, 20 and 25.
5. It omits the per-class renewal fee (€40), the €150 fees per additional
   earlier right in oppositions and invalidity actions, the €62 fee for
   transmitting an international (Madrid) application, and the €0.75 per-page
   copy fees for EP and PCT transmissions.

## TIPO (Taiwan)

`TipoFeesClient` ([source](../packages/client/src/fees/tipo.ts)) reads the
English patent fee table (`https://www.tipo.gov.tw/en/tipo2/326.html`) and the
bilingual Trademark Fee Standards PDF linked from
`https://www.tipo.gov.tw/en/tipo2/342.html`, as Python does. The PDF link is
discovered from the landing page on each call because TIPO names the file by
upload time. Both are fetched with plain requests.

| Route | Content | Recurring fees |
| --- | --- | --- |
| `TW/TIPO/patent` | 20 procedural rows plus annuities for invention (years 1-20), utility model (1-10) and design (1-15) patents, 110 fees | Complete |
| `TW/TIPO/trademark` | 30 catalog fees, enforced May 1, 2024 per the PDF | Renewal year 10 |

Taiwan's three patent kinds share the patent schedule, as in Python, because
Python routes no utility model or design schedule for TIPO. TIPO publishes row
numbers rather than fee codes, so codes keep Python's slugs
(`tipo-patent-<row>`, `tipo-annuity-<kind>-<year>-<tier>`, `tipo-tm-<entry>`).
Annuities carry a large and a small tier: the small tier is the reduced
annuity for natural persons, schools and small and medium-sized enterprises,
and the parser checks that each reduction row restates its year band and
amount. The bilingual trademark PDF interleaves Chinese and English, so a
curated catalog of 30 fees is verified against it: each entry's English phrase
must appear with its NT$ amount within 300 characters, or the parse fails. The
phrases were re-derived for pdf.js text extraction. The patent page publishes
no effective date; its "Update" stamp goes in `provenance.as_of_status`.

This corrects the Python scraper, which still behaves the old way:

1. Its patent effective date is 2024-05-01, the trademark schedule's date. The
   patent page states none, so it is null here.
2. Annuity years without a reduction (invention 7-20, utility model 7-10,
   design 7-15) had only a large-tier row, so a small-tier renewal lookup for
   those years returned nothing. Both tiers are present here at the standard
   amount. Python emits 83 patent fees; this emits 110.
3. Keyword order filed row 11 (supplementary invalidation reasons, post-grant
   amendments) as cancellation, row 14 (changes of name, inventor or agent) as
   transfer and rows 33-34 (attorney and agent licenses) as transfer. All are
   `other` here.
4. Per-class trademark conditions used threshold 1, which implies the first
   class is free; here they use threshold 0. The surcharges per good over 20
   and per retail service over 5 were encoded as `classes_over` 20 and 5; they
   carry no condition here, since the vocabulary has no per-good trigger, and
   say so in notes. The two e-filing discounts were positive filing fees; they
   are `other` with a note that they are reductions. The Classes 35-45 entry was
   verified against the Classes 1-34 text; it now has its own phrase.

## PRH (Finland)

`PrhFeesClient` ([source](../packages/client/src/fees/prh.ts)) parses the
fee regulation PDF, Maksuasetus 171/2026
(`https://www.prh.fi/material/sites/prh/attachments/tietoaprhsta/maksuasetusl-llehikoinen/5o12dsujn/Maksuasetus_171_2026.pdf`),
as Python does; PRH's English price-list pages are script-rendered shells with
no fees in the HTML. One fetch serves all three routes. The effective date
(April 1, 2026), the regulation number and the amended regulation (1216/2025)
are read from the PDF rather than hard-coded. The schedule `source_url` stays
Python's English price-list page for each right; provenance carries the PDF.

| Route | Content | Recurring fees |
| --- | --- | --- |
| `FI/PRH/patent` | §1 national patents, §2 utility models, §3 PCT, §4 European patents, §5 SPCs; 98 fees | Patent annuities years 1-20 complete |
| `FI/PRH/trademark` | §8, electronic and paper channels; 35 fees | Renewal year 10 |
| `FI/PRH/design` | §9; 22 fees | Renewal years 5, 10, 15, 20 |

Codes keep Python's slugs of the label text on the amount's line
(`fi-prh-pat-…`, `fi-prh-tm-electronic-…`). Labels are the full Finnish text:
wrapped lines are joined and a sub-heading prefixes the rows under it ("Maksu
uudelleenkäsiteltäväksi ottamisesta, ensimmäinen kerta"). Finland has no
entity tiers. The 20% surcharge on late annuities and the PCT percentage late
fees are stated as percentages and are not itemized; §6 topographies and §7
attorney fees are not included, as in Python. The URL is pinned to the
171/2026 PDF; a new regulation (normally each January) needs a new URL.

This corrects the Python scraper, which still behaves the old way:

1. The utility model renewal surcharges (Uudistamismaksun korotus) were
   renewals at year 1; they are late fees at years 4 and 8 here. The two-year
   renewal was stored at year 10; it falls due at the end of year 8.
2. Trademark renewals applied for after the registration period ended were
   renewals at year 10, so a renewal lookup returned eight amounts; they are
   late fees here.
3. The design renewal fee was stored only at year 10; it is stored at years 5,
   10, 15 and 20. The late design renewal surcharge was a renewal, the storage
   fee per specimen (säilytysmaksu) was `deferment`, and the non-electronic
   design filing fee had no paper condition.
4. Matching ignored Finnish inflection, so the opposition fee ("väitteen"),
   register entries ("merkinnästä") and the PCT additional and supplementary
   search fees ("uutuustutkimuksesta") fell to `other`. The trademark
   revocation and invalidation fee and the amendment fee matched
   "hakemusmaksu" and were filing fees.
5. The PCT search-fee refund (300 €) was a search fee; it is `other` with a
   note that it is a refund. The Madrid transmittal and replacement fees are
   `madrid`; patent limitation is `other`, not cancellation.
6. The certificate and Madrid rows after the paper-channel trademark block
   carried a paper condition; they have no electronic twin and apply to both
   channels.

## TÜRKPATENT (Türkiye)

`TurkpatentFeesClient` ([source](../packages/client/src/fees/turkpatent.ts))
parses the three HTML fee tables at `https://www.turkpatent.gov.tr/`
`patent-islem-ucretleri`, `marka-islem-ucretleri` and
`tasarim-islem-ucretleri`, as Python does. They answered plain requests; the
local resolver briefly failed to resolve `www.turkpatent.gov.tr` during
recording, which was a DNS fault on this machine, not blocking.

| Route | Content | Recurring fees |
| --- | --- | --- |
| `TR/TURKPATENT/patent` | 01.01.xx codes; 52 fees | Annuities years 3-20 |
| `TR/TURKPATENT/trademark` | 02.01.xx codes; 29 fees | Renewal year 10 |
| `TR/TURKPATENT/design` | 04.01.xx codes; 30 fees | Renewal years 5, 10, 15, 20 |

Every code is mapped explicitly; unknown codes would appear in
`unmapped_codes`. Patent amounts are the total (TOPLAM TUTAR), checked to equal
office fee plus VAT plus stamp duty, with the breakdown in notes. The
trademark and design effective date is January 1 of the tariff year in the
table header (2026); the patent table names no year, so its effective date is
null. The four patent rows given as formulas or in Swiss francs (01.01.20,
01.01.21, 01.01.43, 01.01.59) are omitted and named in the notes. The
additional-design fee (04.01.02) lists three bands in one cell and becomes
three fees with `multi_design` conditions.

This corrects the Python scraper, which still behaves the old way:

1. It emitted the three formula rows as fees of 0.00, so a late-fee lookup
   summed to nothing. They are omitted and described.
2. Keyword rules filed 01.01.04 (publication of a corrected European patent
   translation) as filing, 01.01.17 (certified copy) as grant, 01.01.56
   (search on converting a utility model) as filing and the Madrid
   transmittal fees 02.01.19 and 02.01.35 as filing.
3. Late renewals (02.01.24, and design 04.01.07 and 04.01.08) were renewals,
   so renewal lookups returned the late amounts too. They are late fees here.
   Design renewals were stored only at year 10; they are at years 5, 10, 15 and
   20, which is why the design schedule has 30 fees to Python's 18.
4. The reduced search and examination rates for natural persons and
   universities (01.01.48, 01.01.50) and Teknogirişim-badge companies
   (01.01.65) had tier none next to the standard rates; they are tier small
   and the standard rates tier large.
5. 02.01.02 (the second class only) had a per-unit condition, implying every
   class after the first; it is charged once.
6. Its docstring says utility model fees share the patent table. They are on a
   separate page (Faydalı Model İşlem Ücretleri) that neither runtime reads.

## INPI Brazil

`InpiBrFeesClient` ([source](../packages/client/src/fees/inpi-br.ts)) parses
INPI's English fee PDFs under `https://www.gov.br/inpi/en/costs-and-payment`.
The Portuguese tables redirect to a login and were not checked. The English
tables cite Ordinance MDIC 39/2014, ME Ordinance 516/2019 and INPI Resolution
251/2019 and date from 2020-2021; the parser fails if the citation changes.
INPI publishes no effective date, so it is null.

| Route | Source | Fees | Recurring fees |
| --- | --- | --- | --- |
| `BR/INPI-BR/patent` | `TabelaPatentesinglsapsalteraesCGRECincpapelpct.pdf` (April 2021) | 346 | Invention annual fees years 3-20 |
| `BR/INPI-BR/trademark` | `schedule-of-fees-trademarks.pdf` (December 2020) | 76 | Renewal year 10 |

The tables have code, service, amount and discounted-amount columns, and a
code is printed at the vertical center of its cell, which can hold several
priced lines. The parser therefore reads positioned text from `pdfPageItems`:
a line with its own code owns its amounts, and other priced lines take the
nearest code on the same page and in the same section whose line is bare or
is itself a "- " sub-line. Wrapped text joins a row when it starts in lower
case, closes a parenthesis or moves the cell's middle toward its code. Two
amounts become tiers large and small (the discount of up to 60%); one amount
means no discount (tier none); "No charge" is 0.00; "Variable" rows (287,
293, 800) are omitted and named. Annual-fee bands are expanded per year; fees
paid within the extended term are late fees for the same years. The
examination claim surcharges stated in prose (R$100, 200 and 500 per claim
for claims 11-15, 16-30 and 31 on) become three `excess_claims` rows per
tier. Codes keep Python's form (`inpi-br-222-l-y3`, `inpi-br-tm-374-s`), with
`n` for tier none and a suffix for a cell's second line (`-paper`,
`-additional-process-as`). Invention patents, utility models and certificates
of addition share the patent schedule, as in Python, and their renewal rows
differ by code and label.

This corrects the Python scraper, which still behaves the old way:

1. It reads the December 2020 patent table. The landing page's newest English
   patent table, from April 2021, adds paper-filing fees for codes 200 and
   271.
2. It pairs each amount pair with the nearest code printed before it in
   flattened text, but codes sit at the middle of their cells. The national
   filing fee (175.00/70.00) is credited to "251", read from "Resolution No.
   251" in the page header; the amendment fee of code 207 goes to 206, which is
   free; code 800, a variable fee, gets 65.00. In trademarks, 349 gets 35.00
   (code 348's fee), 3014 gets 710.00 (code 361's) and 800 and 251 appear with
   amounts.
3. It requires two amounts per row, so every fee without a discount is
   dropped, and it keeps one row per code, dropping paper rates. Python finds
   60 patent codes (272 fees) and 17 trademark codes (34 fees); here 93 patent
   codes (346 fees) and 62 trademark codes (76 fees). Codes 200, 201, 203 and
   207 and the PCT search and examination fees 266-269 are among those Python
   misses.
4. Extended-term annual fees (223-247, odd codes) were renewals for the same
   years, so a renewal lookup returned the regular and late amounts together.
   The extended-term issue and trademark fees (213, 373, 375) are late fees
   here too.
5. Its categories filed the publication fee (202) and the examination
   requests (203-205) as filing fees, and per-class fees used threshold 1.

## Recording

`bun scripts/record-fees.ts` records every fee operation; these four were
recorded live on October 22, 2026 with the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`
and plain requests. The PDF cassettes store bodies as hex, so they are large
(PRH 2.6 MB, INPI Brazil 1.5 MB, TIPO 0.6 MB). TÜRKPATENT's pages embed a
public Google API key and reCAPTCHA site key in their Next.js data; recording
replaces them with `[FILTERED]` so secret scanning passes, and the parser
never reads them. Tests replay them through
`feeRecordings` and, for routing and drift tests, through
`recordedFeeResponse`, which serves any recorded fee URL. The MCP fee tests
in `fees.test.ts` and `facade-epo-tm-ref.test.ts` wrap their EPO and USPTO
fakes in `recordedFeesOr`, so listing every schedule replays the other
offices' recordings; their route-list assertions now check inclusion rather
than the exact list.

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

`bun scripts/record-fees.ts cnipa dpma ipaustralia ilpo impi` recorded five
offices live on October 22, 2026 with plain requests and the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`;
no unmapped codes, complete recurring-fee coverage on every route. CIPO's
site was down for maintenance and is tested against an archived copy (see
CIPO).
Per-office tests replay them and pin amounts read off the official pages,
renewal ladders, tiers, conditions, aliases and drift failures. Across these
offices annual fees use `renewal`; the Python scrapers for CIPO, CNIPA, DPMA
and IMPI use `maintenance`, which ADD_NEW_OFFICE.md reserves for the USPTO's
3.5/7.5/11.5-year fees. The ILPO and IMPI PDFs are each fetched once for all
of their routes. `recordedFeeFetch` in the test helpers replays any recorded
fee interaction, and `cipoFixtureFetch` the archived CIPO page, so `listSchedules` can run offline.
`bun scripts/record-fees.ts` gained `ipos`, `hk-ipd` and `inpi-fr` operations;
they were recorded live on October 22, 2026 with plain requests and the
`patent-client-agents` user agent: IPOS 124 patent, 35 trademark and 26 design
fees; HK IPD 75, 42 and 37; INPI France 51, 14 and 8; no unmapped codes and
complete renewal coverage on all nine routes. [Tests](../tests/fees-ipos-hk-inpi.test.ts)
replay them and pin amounts read from the pages and the PDF, renewal ladders,
tiers, alias resolution and drift handling.

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
