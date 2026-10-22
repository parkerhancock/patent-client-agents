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

There is no response cache: each call fetches the source (the EPO feed is
about 23 KB, the USPTO page about 210 KB). Python caches both for seven days
and keeps a USPTO revalidation receipt; neither is ported, and the
`get_fee_schedule` and `lookup_fee` tools have no `refresh` input.
Nothing is deployed.
