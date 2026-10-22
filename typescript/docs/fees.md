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
