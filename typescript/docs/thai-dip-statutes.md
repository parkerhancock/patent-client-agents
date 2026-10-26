# Thailand IP statutes corpus access

October 26, 2026. New in the TypeScript library (Python never had it): the
English translations of Thailand's Patent Act, Trademark Act, Copyright Act
and Trade Secrets Act in one offline SQLite/FTS5 snapshot, read through the
same verified-artifact lifecycle as the [ILPO statutes](ilpo-statutes.md). No
API key is needed.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `ThaiDipStatutesClient` | `search_thai_dip_statutes`, `get_thai_dip_section` | `thai-dip-statutes://corpus/status` | `THAI_DIP_STATUTES_CORPUS_PATH` |

The tools take the same parameters as the other statute corpora (`query`,
`statute`, `per_page`, `page`, `syntax`, `sort` for search; `citation` as a
string or a list of up to 50 for get). The default file is
`~/.cache/patent_client_agents/thai_dip_statutes.db`;
`THAI_DIP_STATUTES_CORPUS_SHA256` pins the decoded SQLite bytes and
`THAI_DIP_STATUTES_CORPUS_FILE_SHA256` the distributed file. The corpus id
for the hosted bootstrap is `thai_dip_statutes`. There is no curated facade
route.

Scope: the MCP adapter uses `thai_dip:read` on the HTTP listener. The
existing `thai_dip` connector (DIP Data Exchange, bring-your-own token) lives
only in the Python package and has not been ported, so the TypeScript server
had no Thailand scope to reuse. `thai_dip:read` is named for that connector's
id so that a future port of the Data Exchange tools can share it as a
Thailand-wide scope, as `ilpo:read` covers the Israeli statutes and
registers.

## Source and contents

The Office of the Council of State (OCS) publishes official English
translations of Thai acts at <https://www.ocs.go.th/searchlaw-law-eng>. It
answers plain requests, but its English list (146 acts on October 26, 2026,
read through the page's own `searchlaw/indexs/list_table_search` endpoint)
has none of the four IP acts, so OCS is not used; the source manifest records
why. WIPO Lex hosts English translations of all four, and
`scripts/build-thai-dip-statutes-corpus.ts` fetches each WIPO Lex legislation
page, reads its English PDF link with the shared WIPO Lex page parser
(`parseWipoLexLegislation`), skipping the `-wto` TRIPS notification copies,
and follows the link once. WIPO signs these links for about five minutes, so
the manifest keeps the unsigned URL. Plain HTTPS GETs with the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`;
no browser, cookie or challenge handling. Nothing blocked the requests.

| Key | Act | WIPO Lex | PDF | Rows | Translation version |
| --- | --- | --- | --- | --- | --- |
| `patent` | Patent Act B.E. 2522 (1979) | [3807](https://www.wipo.int/wipolex/en/legislation/details/3807) | `th007en_1.pdf` | 111 | As amended by the Patent Act (No. 2) B.E. 2535 (1992) and (No. 3) B.E. 2542 (1999); an English consolidation prepared for WIPO Lex (TH007EN) that names no translator |
| `trademark` | Trademark Act B.E. 2534 (1991) | [17164](https://www.wipo.int/wipolex/en/legislation/details/17164) | `th040en_1.pdf` | 148 | As amended by the Trademark Act (No. 2) B.E. 2543 (2000) and (No. 3) B.E. 2559 (2016); unofficial DIP translation |
| `copyright` | Copyright Act B.E. 2537 (1994) | [23909](https://www.wipo.int/wipolex/en/legislation/details/23909) | `th052en_0.pdf` | 103 | As amended by the Copyright Act (No. 2) and (No. 3) B.E. 2558 (2015), (No. 4) B.E. 2561 (2018) and (No. 5) B.E. 2565 (2022); unofficial DIP translation |
| `trade_secrets` | Trade Secrets Act B.E. 2545 (2002) | [17163](https://www.wipo.int/wipolex/en/legislation/details/17163) | `th039en.pdf` | 39 | As amended by the Trade Secrets Act (No. 2) B.E. 2558 (2015); unofficial DIP translation |

That is 401 rows: every numbered section of each act, including repealed
ones (`Section 23 Trademark Act` reads `(Repealed)`) and inserted sections
(`Section 36bis Patent Act`, `Section 65decies Patent Act`, `Section 28/1
Copyright Act`, `Section 79/1` to `79/15 Trademark Act`, the Madrid Protocol
chapter). The version column is each translation's own title page; WIPO
Lex's description (year of version, enactment date) is kept beside it as
`wipo_summary`. Later Thai amendments are not reflected: the Patent Act
translation stops at No. 3 of 1999, and WIPO Lex holds nothing later for it.

The Thai text controls. The three Department of Intellectual Property PDFs
say so on every page or in a starred note: they have "no legal force", and
the Thai text published in the Government Gazette is the only authoritative
version. The Patent Act consolidation has no such note but is equally
unofficial. The meta table, the status resource, every section returned
(`authority`) and both tool summaries carry that statement.

The PDFs were retrieved on October 26, 2026 (22:41 UTC);
[`scripts/thai-dip-statutes-sources.json`](../scripts/thai-dip-statutes-sources.json)
records each WIPO Lex page, WIPO's title and description, the translation's
version note, the PDF URL and WIPO's last-modified stamp for it, retrieval
time, SHA-256, size, page count and row count, plus the OCS source that was
looked at and not used.

How the PDFs become rows. Thai acts print each section as `Section 12` at the
paragraph indent followed by its text (the Patent Act consolidation prints a
bare `12.`), with no section headings. The builder reads positioned text items
(the shared `pdfPageItems`) instead of plain text:

- A section starts at its number at the paragraph indent, and only if the
  number can follow the previous one (`36` then `36bis`, `28` then `28/1`;
  never back and never a jump of more than 12). Paragraphs that begin
  `Section 12 shall apply mutatis mutandis` or wrapped lines that begin with
  a cross-reference stay in the text.
- Inserted sections use the Latin suffixes in statutory order (bis, ter,
  quater, … decies) or a slash. Numbers are stored without spaces and
  lowercased (`36bis`, `109/1`). The Trademark Act prints `106quarter` and
  the Patent Act `65novies`; they are stored as `106quater` and `65nonies`,
  and both spellings resolve. The Thai text confirms that the Patent Act's
  `65novies` is `มาตรา ๖๕ นว`.
- Raised footnote marks are taken out of the text. In the three DIP PDFs a
  footnote starts at a small mark at the left margin; each footnote a section
  cites is kept at the end of its text as `[Notes: Section 4 amended by
  Trademark Act (No. 3) B.E. 2559]`. The Patent Act consolidation collects
  its notes on the last page as a line of marks over a line of separators
  (`(9) to (12)`); those ranges are expanded, so a section reads `[Notes: as
  revised by the Patent Act (No. 3) B.E. 2542]`. Every mark in each PDF
  matched a footnote.
- Text is reflowed into one line per paragraph, subsection, list item or
  definition: a line at the indent opens one, a line at the margin continues
  it. Chapter and part headings and transitional-provision headings
  (centred, or right of the indent) are dropped, as are the preambles, tables
  of contents, running heads, page numbers and the DIP's "Remark : This is an
  unofficial translation…" footer on every Trademark Act page.
- Each act ends at its signature (`Countersigned by`) or schedule: the Patent
  Act's list of maximum fees and the Trademark Act's official fees are not
  stored, nor are the "Remarks" giving reasons for enactment, nor the
  sections of the amending acts printed after the signature (their
  commencement and transitional provisions).
- `title` is always null, since the acts print no section headings.
  `source_url` on each row is the act's WIPO Lex page. Meta adds
  `retrieved_at`, `authority` and `statutes`, a JSON array with each act's
  name, WIPO title and description, version note, page and PDF URLs,
  retrieval time and PDF SHA-256. `snapshot_date` is the retrieval date, so
  rebuilding from the same PDFs gives the same bytes.

Spot checks on October 26, 2026, read against the PDFs: Patent Act sections
2, 3, 5, 6, 36, 36bis, 65bis, 65octies, 65nonies, 65decies and 88; Trademark
Act sections 4, 6, 28bis, 30, 31, 79/2 and 109/1; Copyright Act sections 2, 4,
15, 32/1 and 61; Trade Secrets Act sections 1, 3, 6, 7, 16 and 18. Two checks
cover all rows. Paragraph by paragraph (letters only, case folded), 1,060 of
the 1,067 stored paragraphs appear verbatim in `pdftotext` output; the other
seven straddle a page break, where `pdftotext` has the running head or footer
in between. Word by word, the rows hold 94.5 percent of the Patent Act PDF's
words, 74.9 percent of the Trademark Act's, 96.4 percent of the Copyright
Act's and 88.1 percent of the Trade Secrets Act's. The Trademark Act shortfall
is its per-page translation remark (2,090 words), fee schedule (655) and
post-signature remarks and amending acts (1,252), which together account for
all of it; elsewhere the difference is preambles, contents pages, uncited
footnotes and signatures.

Imperfect where the source is: the Patent Act consolidation's endnotes give
only which amending act revised a section, not what changed; the Trade
Secrets Act PDF was produced through a paper-capture step, though its text
layer read cleanly.

## Schema and behavior

Each row of `sections` is one section (`statute`, `section_number`,
`section_label`, `title`, `text`, `source_url`), schema version 1 as the
other statute corpora use it, with the external-content FTS5 table
`sections_fts` over `statute`, `section_label`, `title` and `text` and the
`porter unicode61` tokenizer. The reader checks meta `schema_version` 1, the
columns and the FTS5 definition, and rejects WAL files, as the shared
`openCorpusSnapshot` does for every corpus.

Act names resolve through an alias table (`Patent Act`, `petty patent`,
`trade marks`, `TM`, `Copyright Act`, `trade secrets`), case-insensitively;
unknown names pass through lowercased and find nothing.
`get_thai_dip_section` parses `Section 36 Patent Act`, `Patent Act s. 36`,
`Section 6 Trade Secrets Act`, `Section 36 bis Patent Act`, `s. 36bis Patent
Act`, `Section 109/1 Trademark Act`, `Trademark Act, Section 109 / 1`, `§ 6
Trade Secrets Act`, `Section 31 paragraph one Trademark Act` and `s. 15(5) of
the Copyright Act B.E. 2537 (1994)`; subsection and paragraph markers return
the whole section. A citation that cannot be parsed or is not in the corpus
returns null from the library and goes to `not_found` in the tool (a single
missing citation gives an empty list and the summary `Thailand section '…' —
not found.`), never an error.

Search defaults to all-terms matching and BM25 order; every term is quoted,
so `OR`, `NEAR` and punctuation are literal text. `sort='outline'` returns
the acts in key order and each act's sections in printed order (`36`,
`36bis`, `37`; `28`, `28/1`, `29`), which is the row order, and outline hits
carry no rank. Status reports `corpus_version` as the build's
`source_version` (`WIPO Lex English translations, 2026-10-26`),
`corpus_synced_at` as the snapshot date at UTC midnight, `authority`, and per
act its version note, WIPO description, PDF URL and hash.

## Building, packaging and verification

The runtime never fetches or rebuilds the corpus. From `typescript/`:

```sh
bun run build:thai-dip-statutes --fetch   # download the PDFs, rewrite the source manifest, build
bun run build:thai-dip-statutes           # or rebuild from the archived PDFs
bun scripts/compress-corpus.ts \
  --input .data/thai_dip_statutes/thai_dip_statutes.db \
  --output .data/thai_dip_statutes/thai_dip_statutes.db.zst
bun run verify:thai-dip-statutes --file .data/thai_dip_statutes/thai_dip_statutes.db.zst
```

The raw PDFs go to the ignored `.data/thai_dip_statutes/raw/`; a rebuild
checks each against the SHA-256 and row count in the committed source
manifest and stops on a mismatch. The builder writes a standalone
DELETE-journal database, never overwrites its output, and checks integrity.
`--fixture` also rewrites the test fixture.

The October 26, 2026 build (PDFs retrieved 22:41 UTC):

| Rows | Decoded bytes | Decoded SHA-256 | Zstandard bytes | File SHA-256 |
| --- | --- | --- | --- | --- |
| 401 | 548,864 | `b9801b5daa6adf4ac055d8068887a8b173d5a6687a63492b3a735864ab0c973b` | 144,201 | `417e6202b1dfa60b11e06da5dc5d54946fbba258fafe9ebc827c6e21ebed81c3` |

A second build from the archived PDFs reproduced the decoded bytes exactly.
The verifier configured the packaged file and both pins, checked each act's
row count and PDF hash against the source manifest and a phrase from eight
sections (including `36 bis`, `65decies`, `109/1` and `32/1`), and exercised
the library and the default full MCP server. The artifacts stay under ignored
`.data/` and were not published or deployed; `scripts/publish-corpora.ts`
knows the local path for when they are.

## Tests

The [fixture](../tests/fixtures/thai-dip-statutes/README.md) is 16 real
sections written by the builder from the October 26 PDFs.
[Builder tests](../tests/thai-dip-statutes-build.test.ts) cover item joining,
number ordering and the sequence guard, raised marks, footnotes, running
heads and the translation footer, the Patent Act endnote ranges, paragraph
reflow, section starts at the indent, centred headings, the end-of-act stop
and the source manifest. [Library tests](../tests/thai-dip-statutes-client.test.ts)
cover aliases, citation parsing, status, authority and per-act versions,
sections and missing ones, search filters, paging, printed outline order, FTS
operator quoting, a missing corpus, Zstandard bytes and both pins.
[MCP tests](../tests/thai-dip-statutes-mcp.test.ts) cover both tools'
parameters, summaries and shapes, `not_found`, the status resource, the
curated toolset and the `thai_dip:read` scope on the authenticated HTTP
listener. Node and browser smoke runs read the fixture as bytes. All run
offline.
