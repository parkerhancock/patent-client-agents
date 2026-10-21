# Fee schedules

October 21, 2026. EPO fees are the first TypeScript fee connector and the
reference for porting the other 23 offices in the Python `fees` package.

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

## MCP

`get_fee_schedule`, `list_fee_jurisdictions` and `lookup_fee` keep the Python
names and lookup semantics (no year excludes renewal rows; tier applies only to
tiered rows). They are registered unconditionally because the EPO feed needs no
credentials, and they require the `fees:read` scope over HTTP.

## Verification and limits

`bun run record:fees` recorded both routes live on October 21, 2026: 112 EPC
fees and 41 Unitary Patent fees, no unmapped codes, complete renewal coverage.
[Tests](../tests/fees.test.ts) replay those recordings and check specific
amounts, the 50% late-fee relation for every year, the Article 2 cross-check,
amount parsing, drift detection, schema rules, resolver parity, MCP filters and
the `fees:read` scope.

There is no response cache: each call fetches the feed (about 23 KB). Python
caches for seven days. Python's USPTO-only `refresh` option is not ported.
Nothing is deployed.
