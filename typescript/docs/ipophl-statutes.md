# IPOPHL Philippines statutes corpus access

October 26, 2026. New in the TypeScript library; Python had no Philippine
connector. The corpus holds the Intellectual Property Code of the
Philippines (Republic Act No. 8293, 1997) and the three Acts that amend it,
in one offline SQLite/FTS5 snapshot read through the same verified-artifact
lifecycle as the [ILPO statutes](ilpo-statutes.md). No API key is needed. The
MCP adapter uses a separate `ipophl:read` scope for HTTP access.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `IpophlStatutesClient` | `search_ipophl_statutes`, `get_ipophl_section` | `ipophl-statutes://corpus/status` | `IPOPHL_STATUTES_CORPUS_PATH` |

The tools take the parameters the other statute tools take (`query`,
`statute`, `syntax`, `sort`, `per_page`, `page` for search; `citation` as a
string or a list of up to 50 for get). The default file is
`~/.cache/patent_client_agents/ipophl_statutes.db`.
`IPOPHL_STATUTES_CORPUS_SHA256` pins the decoded SQLite bytes and
`IPOPHL_STATUTES_CORPUS_FILE_SHA256` the distributed file. The tools are in
the full toolset only; the curated facade has no Philippine route.

## The text is as enacted

Each Act is stored as enacted and as its own statute. RA 8293's 241 sections
carry their 1997 text; what RA 9150, RA 9502 and RA 10372 changed is in those
Acts' rows, mostly as quoted replacement text, and is not consolidated into
the Code. Section 22 of the Code, for example, reads as it did in 1997; the
2008 exclusion for new forms of known substances is in Section 5 of RA 9502.
The status resource's `text_status`, the tool descriptions and each RA 8293
section's `amended_by` say so:

- `amended_by` lists the amending-Act sections whose opening clause names the
  Code section (amends it, inserts a section after it, renumbers or deletes
  it). The builder reads those clauses ("Section 22 of Republic Act No. 8293
  … is hereby amended"), skipping clauses that name another Act (RA 9502 also
  amends the Generics Act and the Pharmacy Law). It is a pointer, not a
  consolidation: 52 Code sections have one. Section 74 points at RA 9502
  Section 8, which the source page lacks (below), and Sections 231 to 241
  point at RA 10372 Section 28, which renumbered them.
- Sections the amendments inserted (9A, 93-A and 220A, and the new Section
  230 on intellectual property policies) exist only inside the amending
  Acts' rows. A citation such as `Section 93-A IP Code` is not found; search
  or read `Section 11 RA 9502`.
- RA 10372 Section 28 renumbered 1997 Section 230 and every section after it,
  so the Effectivity clause cited today as Section 242 is `Section 241 RA
  8293` here. Cite the 1997 number.

## Source and contents

The source is the LawPhil Project of the Arellano Law Foundation, which
publishes each Republic Act as an HTML page. For each Act
`scripts/build-ipophl-statutes-corpus.ts` fetches the page once with a plain
HTTPS GET and the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`;
no browser, cookie or challenge handling. LawPhil answered every request.

| Key | Act | Approved | LawPhil page | Rows |
| --- | --- | --- | --- | --- |
| `ra8293` | Intellectual Property Code of the Philippines (RA 8293) | June 6, 1997 | [ra_8293_1997](https://lawphil.net/statutes/repacts/ra1997/ra_8293_1997.html) | 241 |
| `ra9150` | Protection of layout-designs of integrated circuits (RA 9150) | August 6, 2001 | [ra_9150_2001](https://lawphil.net/statutes/repacts/ra2001/ra_9150_2001.html) | 6 |
| `ra9502` | Universally Accessible Cheaper and Quality Medicines Act of 2008 (RA 9502) | June 6, 2008 | [ra_9502_2008](https://lawphil.net/statutes/repacts/ra2008/ra_9502_2008.html) | 48 of 49 |
| `ra10372` | Amending certain provisions of the IP Code (RA 10372) | February 28, 2013 | [ra_10372_2013](https://lawphil.net/statutes/repacts/ra2013/ra_10372_2013.html) | 32 |

That is 327 rows: every numbered section of each Act that the pages carry,
including the RA 9502 sections on drug price regulation and the Generics Act
and Pharmacy Law amendments. The pages were retrieved on October 26, 2026;
[`scripts/ipophl-statutes-sources.json`](../scripts/ipophl-statutes-sources.json)
records each page's URL, the Act's long title, the server's Last-Modified
date, retrieval time, character set (windows-1252), SHA-256, size and row
count. LawPhil's pages carry a Creative Commons BY-NC 3.0 notice for the site;
the statutes themselves are works of the Government, in which the Code
(Section 176.1) says no copyright subsists.

Other Acts and sources. LawPhil's year indexes for 1998 to 2026 list no other
Act amending RA 8293. That is a check of LawPhil's listings, not of the
official record. The Official Gazette (officialgazette.gov.ph) answers plain
requests with a Cloudflare managed challenge (HTTP 403) and was not used.
IPOPHL's own site was unreachable: `ipophil.gov.ph` redirects to
`www.ipophil.gov.ph`, which did not resolve on October 26. No IPOPHL rules
or regulations are included.

A consolidated text exists elsewhere. WIPO Lex holds the "Intellectual
Property Code of the Philippines, Republic Act No. 8293 (2015 Edition)"
([18399](https://www.wipo.int/wipolex/en/legislation/details/18399),
`ph198en.pdf`, 115 pages, a text PDF), described as amended up to RA 10372
and printing "(As amended by …)" under each changed section and the
renumbered Sections 1 to 242. WIPO Lex answered plain requests and serves the
PDF through the same signed link the ILPO builder follows. The PDF does not
name its publisher, and this corpus does not use it; a later build could add
it as a consolidated `ip_code` statute alongside these rows.

How the pages become rows:

- A section starts at an unquoted paragraph that opens `Section N.`, `SEC.
  N.` or (RA 9150) `Section 1,` and whose number is the next in sequence, so
  cross-references ("Section 5 of this Act") and the quoted sections an
  amending Act inserts (`"SEC. 22. …`) never start a row. The Act ends at the
  `Approved` line after its last section; signature blocks are not stored.
- The heading is the italic text after the number (`Section 21.
  *Patentable Inventions.* -`); RA 9502 Section 16 sets its heading in roman
  type and is read up to the `. -`. Sections of the amending Acts that only
  amend or insert text have no heading, so `title` is null for 45 rows: RA
  9150 Section 1, 16 RA 9502 sections and RA 10372 Sections 1 to 28.
- The text is one line per paragraph, subsection, list item or table row,
  with whitespace collapsed and nothing else changed: the source's derivation
  notes (`(n)`, `(Sec. 8, R.A. No. 165a)`), its quotation marks around
  inserted text, its `x x x` elisions and its misprints (`Chapter XIIl`,
  `Conditions/or Protection`) stay. RA 8293 Section 119 lists the patent
  provisions that apply to industrial designs in a table; each row is a line
  (`Section 21 - Novelty:`).
- RA 8293's Part and Chapter headings (centred paragraphs between sections)
  are dropped. In the amending Acts centred text is kept, because it is
  quoted amendment text (RA 10372 Section 7 replaces a Chapter title).
- RA 9502 on LawPhil is defective: the page repeats part of the new Section
  72 in Section 7, lacks the rest of Section 7 and the start of Section 8
  (which amends Section 74, Use of Invention by Government), and has no
  Section 8. The quoted subsections 74.3 and 74.4 that survive fall at the
  end of Section 7. The builder stores the page as it is, records Section 8
  as missing in the manifest and the status, and closes Section 7 with a
  `[Source note: …]` saying so. LawPhil's PDF of the Act is a scanned image,
  and WIPO Lex's copy (`ph047en_1.pdf`) is OCR with frequent errors, so
  neither was used to fill the gap.
- `source_url` on each row is the Act's LawPhil page. Meta adds
  `retrieved_at`, `text_status`, `statutes` (each Act's names, role, approval
  date, long title, page URL, Last-Modified, retrieval time, SHA-256 and
  missing sections) and `amendments` (the `amended_by` index).
  `snapshot_date` is the retrieval date, so rebuilding from the same pages
  gives the same bytes.

Spot checks on October 26, 2026, read against the pages: RA 8293 Sections 1,
4, 7, 21, 22, 119, 123, 171, 172 and 241; RA 9150 Sections 1 and 6; RA 9502
Sections 7, 11 and 49; RA 10372 Sections 3, 7, 28 and 32. Word coverage,
comparing each page's text from Section 1 to the final approval line with the
rows: RA 8293's rows hold all but 175 of 32,484 words (99.5 percent), the
missing words being the 38 Part and Chapter headings; for RA 9150 (37 of
2,352), RA 9502 (61 of 8,840, beside the `SEC.` prefixes the rows do not
repeat) and RA 10372 (68 of 3,689) the missing words are the signature
blocks and RA 10372's legislative-history note. LawPhil also serves RA 8293
as a 109-page text PDF; compared word by word with its `pdftotext` output,
the rows lack the PDF's 241 `SEC.` prefixes, its headings and page numbers,
and the two differ in 36 words, from hyphenation.

## Schema and behavior

Each row of `sections` is one section (`statute`, `section_number`,
`section_label`, `title`, `text`, `source_url`), the schema version 1 the
ILPO and other statute corpora use, with the external-content FTS5 table
`sections_fts` over `statute`, `section_label`, `title` and `text` and the
`porter unicode61` tokenizer. Labels read `Section 21 RA 8293`. The reader
checks meta `schema_version` 1, the columns and the FTS5 definition, and
rejects WAL files, as the shared `openCorpusSnapshot` does for every corpus.

Statute names resolve case-insensitively: `IP Code`, `Intellectual Property
Code (of the Philippines)` and `Cheaper Medicines Act`, and any Republic Act
number (`RA 8293`, `R.A. No. 9502`, `Republic Act No. 10372`, `ra9150`).
Unknown names pass through lowercased and find nothing. `get_ipophl_section`
parses `Section 21 IP Code`, `Sec. 123.1(d) RA 8293`, `Section 3 RA 10372`,
`RA 8293 Sec. 22`, `R.A. No. 8293, Section 72.1`, `§ 72.1 R.A. No. 8293` and
`Section 22 of the Intellectual Property Code of the Philippines`;
subsections and paragraphs return the whole section, and `93-A` is looked up
as `93A`. A citation that cannot be parsed or is not in the corpus returns
null from the library and goes to `not_found` in the tool, never an error.
A found RA 8293 section with amendments has a summary like `**Section 22 RA
8293** — Non-Patentable Inventions (as enacted; see Section 5 RA 9502)`.

Search defaults to all-terms matching and BM25 order, quotes every term so
FTS5 operators are literal, and returns statute, number, label, title, a
`<mark>` snippet and rank. `sort='outline'` orders by Act (RA 8293, 9150,
9502, 10372) and then numerically, with no rank. Status reports
`corpus_version` as the build's `source_version` (`LawPhil, Acts as enacted,
2026-10-26`) and `corpus_synced_at` as the snapshot date at UTC midnight.

## Building, packaging and verification

The runtime never fetches or rebuilds the corpus. From `typescript/`:

```sh
bun run build:ipophl-statutes --fetch     # download the pages, rewrite the source manifest, build
bun run build:ipophl-statutes             # or rebuild from the archived pages
bun scripts/compress-corpus.ts \
  --input .data/ipophl_statutes/ipophl_statutes.db \
  --output .data/ipophl_statutes/ipophl_statutes.db.zst
bun run verify:ipophl-statutes --file .data/ipophl_statutes/ipophl_statutes.db.zst
```

The raw pages go to the ignored `.data/ipophl_statutes/raw/`; a rebuild
checks each against the SHA-256 and row count in the committed source
manifest and stops on a mismatch. The builder writes a standalone
DELETE-journal database, never overwrites its output, and checks integrity.
`--fixture` also rewrites the test fixture.

The October 26, 2026 build (pages retrieved 22:44 UTC):

| Rows | Decoded bytes | Decoded SHA-256 | Zstandard bytes | File SHA-256 |
| --- | --- | --- | --- | --- |
| 327 | 618,496 | `b22751bd0e3718a9295eab39855a0f5aeba3edae5adb8532675b6ae5f2c88264` | 180,390 | `8020ce5d8c6c973193a514c611232b62b8cb206261eaccc581ef4c4674bc4672` |

A second build from the archived pages reproduced the decoded bytes exactly.
The verifier configured the packaged file and both pins, checked each Act's
row count and page hash against the source manifest, eight section headings
and the Section 22 amendment pointer, and exercised the library and the
default full MCP server. The artifacts stay under ignored `.data/` and were
not published or deployed; `ipophl_statutes` is registered in the corpus
bootstrap and `publish-corpora.ts` for when they are.

## Tests

The [fixture](../tests/fixtures/ipophl-statutes/README.md) is 16 real
sections written by the builder from the October 26 pages. [Builder
tests](../tests/ipophl-statutes-build.test.ts) cover the windows-1252
decoding, section starts (quoted, out-of-sequence and cross-reference
paragraphs never start one), italic and roman headings, dropped Part and
Chapter lines, table rows, the `Approved` stop, missing sections and source
notes, the amendment index and the source manifest. [Library
tests](../tests/ipophl-statutes-client.test.ts) cover aliases and Republic
Act numbers, citation parsing, status and per-Act metadata, sections,
`amended_by` and missing ones, search filters, paging, Act-then-number
outline order, FTS operator quoting, a missing corpus, Zstandard bytes and
pins. [MCP tests](../tests/ipophl-statutes-mcp.test.ts) cover both tools,
the as-enacted wording in their descriptions, `not_found`, the status
resource, the curated toolset and the `ipophl:read` scope on the
authenticated HTTP listener. Node and browser smoke runs read the fixture as
bytes. All run offline.
