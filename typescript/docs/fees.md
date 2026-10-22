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

There is no response cache: each call fetches the source (the EPO feed is
about 23 KB, the USPTO page about 210 KB). Python caches both for seven days
and keeps a USPTO revalidation receipt; neither is ported, and the
`get_fee_schedule` and `lookup_fee` tools have no `refresh` input.
Nothing is deployed.
