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
