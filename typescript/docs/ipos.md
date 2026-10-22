# IPOS Singapore statutes and manuals

October 22, 2026. The TypeScript library reads two Singapore corpora: the IP
statutes administered by IPOS (Patents Act 1994, Trade Marks Act 1998,
Registered Designs Act 2000, Copyright Act 2021) and the IPOS examination
manuals (Examination Guidelines for Patent Applications, the Trade Marks Work
Manual, and the Registered Designs guidelines for non-physical products).
Both are offline SQLite/FTS5 snapshots read through the same verified-artifact
lifecycle as the [IPO India](ipo-in.md) and [DPMA](dpma-statutes.md) corpora,
built from the official texts by `scripts/build-ipos-corpora.ts`. No API key
is needed. The MCP adapter uses a separate `ipos:read` scope for HTTP access.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `IposStatutesClient` | `search_ipos_statutes`, `get_ipos_section`, `list_ipos_statutes` | `ipos-statutes://corpus/status` | `IPOS_STATUTES_CORPUS_PATH` |
| `IposManualsClient` | `search_ipos_manuals`, `get_ipos_manual_section`, `list_ipos_manuals` | `ipos-manuals://corpus/status` | `IPOS_MANUALS_CORPUS_PATH` |

The tool names and parameters match Python (`query`, `statute`/`manual`,
`per_page`, `page` for search, plus optional `syntax` and `sort`; `citation`
as a string or list for get). So do the path variables, the default files
(`~/.cache/patent_client_agents/ipos_statutes.db`, `ipos_manuals.db`), and
the SQLite schema (version 1). The statutes table adds one column, `sso_url`,
and the reader also opens Python-built files without it. `<PREFIX>_CORPUS_SHA256`
pins the decoded SQLite bytes and `<PREFIX>_CORPUS_FILE_SHA256` the
distributed file. Library operations are Python's: `listStatutes`/`listManuals`,
`getSection`, `getByCitation`, `search` and `meta`, plus `getCorpusStatus`.

## Sources and versions

Every source file is listed with its URL, retrieval time, byte count and
SHA-256 in [`references/ipos/sources.json`](../references/ipos/sources.json).
All were fetched on October 22, 2026 with plain GETs and the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`.

| Text | Source | Version it reflects | Rows |
| --- | --- | --- | --- |
| Patents Act 1994 | WIPO Lex entry 23204, the Singapore Statutes Online (SSO) PDF (682,152 bytes, SHA-256 `81ec0f1a…18326c92`) | 2020 Revised Edition, informal consolidation in force from 9 March 2025 | 125 sections and the Schedule |
| Trade Marks Act 1998 | WIPO Lex entry 23203, SSO PDF (596,283 bytes, `84d9881b…b2c088de`) | Same | 129 sections and three Schedules |
| Registered Designs Act 2000 | WIPO Lex entry 23205, SSO PDF (501,606 bytes, `bdfce883…c4bf849a`) | Same | 108 sections and the Schedule |
| Copyright Act 2021 | WIPO Lex entry 23201, SSO PDF (1,198,846 bytes, `fc6850e5…11a5373e`) | Same | 541 sections |
| Examination Guidelines for Patent Applications (PEG) | ipos.gov.sg Patents guides page, PDF on isomer-user-content.by.gov.sg (4,253,483 bytes, `6d00e54f…cb490c44`) | Version Oct 2023, released 11 October 2023 | 1,138 numbered paragraphs, chapters 1–11 |
| Trade Marks Work Manual | ipos.gov.sg Trade Marks guides page: a cover file and 22 chapter PDFs | Each chapter's own version, from Version 3 (March 2017) for chapter 1 to Version 5.1 (September 2025) for chapter 22, recorded per row and in the status metadata | 434 headed sections |
| Registered Designs — Guidelines for Non-Physical Products | ipos.gov.sg Designs guides page (893,623 bytes, `109b2fa9…ed740147`) | Version Jun 2022, released 2 June 2022 | 54 numbered paragraphs |

Why these sources:

- Singapore Statutes Online (`sso.agc.gov.sg`, CloudFront), which Python's
  builder used, answered HTTP 403 "Request blocked" to plain requests for
  `/Act/PA1994`, `/Act/PA1994?WholeDoc=1`, the site root and `robots.txt`,
  with this user agent and with curl's default one. No other access method
  was tried. WIPO Lex republishes the SSO PDF of each Act (the pages carry
  SSO's "Informal Consolidation – version in force from 9/3/2025" footer),
  so the Acts come from there. Its PDF links are short-lived signed URLs that
  the builder reads from the entry page; the manifest records the unsigned
  path. Each row still carries `sso_url`, the provision on SSO
  (`https://sso.agc.gov.sg/Act/PA1994?ProvIds=pr13-#pr13-`).
- The three `www.ipos.gov.sg/docs/default-source/…` PDF paths in Python's
  manuals builder answer HTTP 404. IPOS now serves its documents from
  `isomer-user-content.by.gov.sg` and `file.go.gov.sg`, linked from the
  guides pages, which the builder reads for the current links.
- The Trade Marks Work Manual is published as 22 chapter PDFs plus a cover
  and contents file, not as one PDF.
- IPOS no longer publishes a Registered Designs (Industrial Designs) Work
  Manual. The Designs guides page lists an infopack, information notes and
  "Registered Designs - Guidelines for Non-Physical Products", the only
  examination guidance there with numbered paragraphs. It is the `designs`
  manual, with the short name "Designs Guidelines"; Python's aliases ("Designs
  Work Manual", "dwm") still resolve to it.

The statutes snapshot's `source_version` is `2020 Revised Edition, in force
from 2025-03-09`, which is its `corpus_version`; the status `metadata` has a
`source_<act>` entry for each Act. The manuals snapshot has no single
version, so its `corpus_version` is `snapshot 2026-10-22` (Python's label
format); `metadata.source_tm` lists every chapter's version, and each row's
`source_version` is that of its manual or chapter.

## How the text is extracted

PDF text comes from `pdfjs-dist` 4.10.38, which reports each text run's font,
size and position.

- Acts. The arrangement of sections at the front of each PDF gives every
  section's number, title, Part, Division and Subdivision in order. Parsing
  starts at the long title ("An Act to …"); each section starts at the line
  whose first run is its number in the heading font, and every section in
  the arrangement must be found in order or the build fails. The Part,
  Division and section headings before the next section (and the amendment
  references such headings carry) are cut from the end of a section. Running
  headers and the SSO footer are dropped. The amendment references after
  subsections (`[15/2012]`, `[Act 7 of 2022 wef 26/05/2022]`) stay, as SSO
  prints them. Schedules become rows labelled `Schedule`, `First Schedule` and
  so on; the legislative history and comparative tables after them are not
  included. The Registered Designs Act's arrangement and body both print
  "PART ??" for the border-measures Part, so that Part is named by its title
  alone in breadcrumbs.
- PEG and the designs guidelines. A row is a numbered paragraph (`8.12`),
  accepted only in sequence (the next number in the chapter, or 1 of a later
  chapter). Its title is the nearest heading above it (the section "A."
  heading or a sub-heading), and the breadcrumb runs from the chapter title
  through the headings. Footnotes and superscript markers (set below 85% of
  the body size) are dropped, as are running headers and page footers.
- Trade Marks Work Manual. Each chapter's own contents list gives its
  numbered headings (`5`, `5.2`, `5.2.5.3.1`); each is found in the body by
  its number and the start of its title, and owns the text to the next one.
  Rows are labelled chapter-first (`7.5.2` is chapter 7, heading 5.2).
  Headings with no text of their own (a heading followed directly by its
  first subheading) are not rows. Two contents entries (8.7 and 11.5) are not
  matched in the body, so their text stays with the heading before them.

Paragraph breaks follow the source: subsection, item and definition starts in
the Acts, larger line gaps and list markers in the manuals. Checks in the
builder: required provisions and minimum counts per Act, no SSO footer text in
any row, spot texts for PEG 1.1 and 8.12, TM 1.1 and 7.5.2.5.2 and designs
1.1, minimum row counts per manual, and at most 15 unmatched TM headings.

## Building

From `typescript/`:

```sh
bun run fetch:ipos            # download and archive the sources, rewrite the manifest, build
bun run build:ipos            # rebuild from the archive in .data/ipos/sources/
bun run build:ipos --fixtures # also rewrite tests/fixtures/ipos/
for name in ipos_statutes ipos_manuals; do
  bun scripts/compress-corpus.ts \
    --input .data/ipos/build/$name.db --output .data/ipos/$name.db.zst
done
bun run verify:ipos \
  --statutes .data/ipos/ipos_statutes.db.zst \
  --manuals .data/ipos/ipos_manuals.db.zst
```

The raw sources (gzipped) and the built databases stay under the ignored
`.data/ipos/`. The builder writes DELETE journal mode directly and is
byte-reproducible from the archive (`snapshot_date` is the retrieval date).
`--fetch` first checks that WIPO Lex still lists each Act under its entry and
that each IPOS guides page still links the manual it expects.

| Corpus | Rows | Decoded bytes | Zstandard bytes | Decoded SHA-256 | File SHA-256 |
| --- | --- | --- | --- | --- | --- |
| Statutes | 908 | 2,277,376 | 517,369 | `ab9d1012e538f587e85561db5d5da06109978056df91d3c74202cea0d2043fa5` | `eedca0886ba7caa1d1ef70149af4711ec3d01bf885e172cdb8c42bfff0fccd92` |
| Manuals | 1,626 | 3,563,520 | 934,115 | `ca73b953f48ab03cd2c9ef4928fcd71101ef681ecd60867c0d54bb4c97d72cb0` | `f58bf8a1b88065e64d4850f752e6813a5e69b0f37972e1e316ef33775430aa3c` |

The verifier checks the pins, compares every stored row (text, title,
breadcrumb, SSO link, source URL and version) with a fresh parse of the
archived sources, spot-checks Patents Act ss. 13 and 15, Trade Marks Act
s. 8(2), Copyright Act s. 190, Registered Designs Act s. 5, the Trade Marks
Act First Schedule, PEG 8.12 and 4.1, TM Work Manual 7.5.2.5.2 and 17.3.1 and
designs guidelines 2.1 against wording in the source documents, and calls
all six MCP tools. The artifacts were not published or deployed.

## Citations and source links

`get_ipos_section` accepts Python's forms (`Section 13 Patents Act`,
`Patents Act s. 13`, `s 27(1) Trade Marks Act`, `13 Patents Act`,
`Patents Act 13`) and also `§13 Patents Act`, `Section 13 of the Patents Act
1994`, Act abbreviations (`PA1994`, `TMA1998`, `RDA2000`, `CA2021`) and
Schedules (`First Schedule Trade Marks Act`, `Schedule to the Patents Act`).
Rows store whole sections, so a subsection citation returns the section with
`subdivision` set (`(1)`), and the summary says the cited part is within the
section text. A section number without an Act resolves when exactly one Act
has it and is an error naming the Acts otherwise.

`get_ipos_manual_section` accepts `IPOS PEG 8.12`, `PEG 4.1`,
`TM Work Manual 7.5.2`, `7.5.2 of the IPOS TM Work Manual` and
`Designs Guidelines 2.1`. Each manual row's `source_url` is its PDF with the
page (`…examination-guidelines-for-patent-applications.pdf#page=294`), and a
single-citation get uses it as the provenance URL; statute gets use the
section's SSO link.

## Behavior and Python bugs fixed

Search keeps Python's response: BM25 rank, `<mark>` snippets of 40 tokens,
`per_page + 1` paging, full hit rows, and the summary
"IPOS Singapore statutes — `query` (statute=all): N hits (page 1).". Get keeps
`corpus_get`: input order, `not_found`, and no error for an unparseable or
missing citation, for a single string too. Section text beyond a
32,000-character inline budget per call becomes a text artifact, as in the
other corpus tools. Python behavior the port corrects:

1. Neither builder works against today's sources: SSO refuses the requests
   (above) and all three manual URLs are 404. Had the Act pages loaded,
   the statutes builder split tag-stripped text on any line shaped like
   `12. Heading`, which also matches Schedule paragraphs and the legislative
   history, and a repeated label violates `UNIQUE(statute, section_label)`,
   which would abort the write.
2. `get_ipos_section` provenance pointed at `https://sso.agc.gov.sg/Act/PATENTS#pr13-`,
   built from the corpus key instead of the SSO Act code, which is not an SSO
   page. It is now the stored SSO link of the section. `get_ipos_manual_section`
   pointed every manual at `…/about-ip/patents/guides#<manual>-<label>`; it
   is now the PDF page.
3. Citation parsing read `Copyright Act 2021` as section 2021, sent
   `Section 13 of the Patents Act` to an Act named "of the patents act", and
   had no form for `§`, Schedules or a trailing year. A subsection citation
   looked up a row labelled `27(1)`, which no build produces.
4. FTS5 operators ran from caller text: Python quoted only tokens with
   punctuation, so a bare `AND`, `NOT` or `NEAR` acted as an operator or
   raised a syntax error. Every term is now quoted; `syntax='or'` widens.
5. `sort='statute'` ordered sections as strings (`10` before `2`). It now
   keeps each Act (or manual) in document order.
6. The manual citation pattern allowed at most four label components, too
   few for Trade Marks Work Manual rows such as `7.5.2.5.3.1`.

The source name in provenance is "IPOS Singapore — IP statutes" or "IPOS
Singapore — examination manuals"; Python used "IPOS Singapore" for both.

## Tests

The fixtures in `tests/fixtures/ipos/` are subsets of the real builds (19
statute rows across all four Acts, 11 manual rows across the three manuals),
written by `build:ipos --fixtures`. [Library tests](../tests/ipos-client.test.ts)
cover citation parsing, alias resolution, status and source metadata,
`meta`, lists, search with filters, paging and document order, subsection and
Schedule citations, ambiguous and missing sections, FTS operator quoting,
Zstandard bytes, Python-built files without `sso_url`, missing, WAL, schema
and pin failures and the environment variables. [MCP tests](../tests/ipos-mcp.test.ts)
cover the six tools, summaries, `not_found`, the status resources and the
`ipos:read` scope on the authenticated HTTP listener.
[Build tests](../tests/ipos-build.test.ts) cover the guides-page link parser
and the source manifest. All run offline.
