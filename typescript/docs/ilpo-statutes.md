# ILPO Israel statutes corpus access

October 22, 2026. The TypeScript library reads the ILPO Israel statutes
corpus: the English translations of Israel's five IP statutes in one offline
SQLite/FTS5 snapshot, read through the same verified-artifact lifecycle as the
[DPMA statutes](dpma-statutes.md). No API key is needed. The MCP adapter uses
a separate `ilpo:read` scope for HTTP access.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `IlpoStatutesClient` | `search_ilpo_statutes`, `get_ilpo_section` | `ilpo-statutes://corpus/status` | `ILPO_STATUTES_CORPUS_PATH` |

Tool names and parameters (`query`, `statute`, `per_page`, `page` for search;
`citation` as a string or a list of up to 50 for get), the path variable, the
default file name (`~/.cache/patent_client_agents/ilpo_statutes.db`) and the
schema match the Python connector. Search also takes `syntax` and `sort`,
which Python's library had and its tool did not expose.
`ILPO_STATUTES_CORPUS_SHA256` pins the decoded SQLite bytes and
`ILPO_STATUTES_CORPUS_FILE_SHA256` the distributed file. Python has no facade
route for this corpus, so the curated toolset has none either. The two ILPO
trade-mark feed tools in the same Python module (`list_ilpo_tm_releases`,
`download_ilpo_tm`) belong to the separate `ilpo_tm` connector and are not
part of this port.

## Source and contents

WIPO Lex hosts English translations of the five statutes. For each one,
`scripts/build-ilpo-statutes-corpus.ts` fetches the WIPO Lex legislation page,
reads its English PDF link with the shared WIPO Lex page parser
(`parseWipoLexLegislation`), and follows that link once. WIPO signs these
links for about five minutes, so the manifest keeps the unsigned URL. Plain
HTTPS GETs with the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`;
no browser, cookie or challenge handling. Nothing blocked the requests.

| Key | Statute | WIPO Lex | PDF | Rows | Translation version |
| --- | --- | --- | --- | --- | --- |
| `patents` | Patents Law, 5727-1967 | [15167](https://www.wipo.int/wipolex/en/legislation/details/15167) | `il040en_1.pdf` | 239 | Consolidated 2014 (amendment no. 11), prepared by WIPO |
| `trademarks` | Trade Marks Ordinance [New Version], 5732-1972 | [8200](https://www.wipo.int/wipolex/en/legislation/details/8200) | `il043en.pdf` | 99 | As amended up to September 1, 2010 |
| `designs` | Designs Law, 5777-2017 | [19434](https://www.wipo.int/wipolex/en/legislation/details/19434) | `il118en.pdf` | 131 | As passed July 26, 2017 |
| `copyright` | Copyright Act, 5768-2007 | [11509](https://www.wipo.int/wipolex/en/legislation/details/11509) | `il033en.pdf` | 78 | With the 2011 amendment to section 64 (Israel's TRIPS notification) |
| `commercial_torts` | Commercial Torts Law, 5759-1999 | [2375](https://www.wipo.int/wipolex/en/legislation/details/2375) | `il012en.pdf` | 29 | As passed April 19, 1999 |

That is 576 rows: every numbered section of each statute, including repealed
ones and lettered insertions (`Section 64K1 Patents Law`, `Section 56D1 Trade
Marks Ordinance`). These are translations as WIPO Lex holds them, not
consolidated current law; later Knesset amendments are not reflected, and the
Hebrew text controls. The status resource and `listStatutes()` report WIPO's
version note for each statute so callers can say so.

The PDFs were retrieved on October 22, 2026;
[`scripts/ilpo-statutes-sources.json`](../scripts/ilpo-statutes-sources.json)
records each WIPO Lex page, WIPO's title and version note, the PDF URL and
WIPO's last-modified stamp for it, retrieval time, SHA-256, size, page count
and row count.

How the PDFs become rows. The statutes are printed as Israeli legislation
usually is: a margin column with the section heading and amendment notes, then
the section number, then the text. The builder reads positioned text items
(the shared `pdfPageItems`) instead of plain text, with the column positions
set per statute:

- A section starts at a number in the number column that can follow the
  previous one (`54` then `54A`, never back and never a jump of more than 12),
  so stray numerals in the text are not section breaks. Numbers split into
  several text items (`8`, `0`, `.`) are joined.
- The heading is the margin text beside or just above the number. Margin lines
  that are amendment notes (`(amendment no. 4) 1999`) are kept at the end of
  the text as `[Margin notes: …]`. The Commercial Torts Law has no margin; its
  headings are the line above each number.
- Text is reflowed into one line per subsection, list item or definition.
  Chapter and article headings, running heads, page numbers, footnotes and
  footnote marks are dropped; ordinal superscripts stay (`11th`). Glyph runs the
  PDF splits inside a word are rejoined from item positions.
- Each statute ends before its schedules or signatures: the Patents Law's two
  schedules (recognized states and patent attorney subjects), the Trade Marks
  Ordinance's section concordance and the signature blocks are not stored.
- The Commercial Torts Law PDF prints the second and later subsections as
  `(Two)`, `(Three)` and so on (a word-processor numbering artifact), while its
  own cross-references cite `(b)(1)` and `subsec. (a)`. They are stored as
  `(b)`, `(c)`, … so citations in the text line up.
- `source_url` on each row is the statute's WIPO Lex page. Meta adds
  `retrieved_at` and `statutes`, a JSON array with each statute's name, WIPO
  title and version note, page and PDF URLs, retrieval time and PDF SHA-256.
  `snapshot_date` is the retrieval date, so rebuilding from the same PDFs gives
  the same bytes.

A few margin headings come out imperfect where the source is: repealed
sections and some others have no heading (`title` is null), and a handful of
Designs Law headings keep the source's lowercase start or a stray fragment.
Spot checks on October 22, 2026: Patents Law sections 1 to 11 and 54A, Trade
Marks Ordinance sections 8, 46A and 72, Designs Law sections 1 to 6 and 79 to
84, Copyright Act sections 1 and 19 and all 29 sections of the Commercial
Torts Law were read against the PDFs. Compared word by word with `pdftotext`
output, each statute's rows hold all but 1 to 9 percent of the PDF's words;
the difference is the dropped tables of contents, schedules, footnotes and
signatures.

## Schema and behavior

Each row of `sections` is one section (`statute`, `section_number`,
`section_label`, `title`, `text`, `source_url`), the schema the Python builder
defines (version 1, unchanged), with the external-content FTS5 table
`sections_fts` over `statute`, `section_label`, `title` and `text` and the
`porter unicode61` tokenizer. The reader checks meta `schema_version` 1, the
columns and the FTS5 definition, and rejects WAL files, as the shared
`openCorpusSnapshot` does for every corpus.

Statute names resolve through Python's alias table (`Patents Law`, `trade
marks`, `TM`, `Copyright Act`, and `trade secret` / `trade secrets` for the
Commercial Torts Law), case-insensitively; unknown names pass through
lowercased and find nothing. `get_ilpo_section` parses `Section 3 Patents
Law`, `Article 6 Commercial Torts Law`, `§3 Patents Law`, `Patents Law §3`,
`Patents Law Section 3`, `Section 6 of the Commercial Torts Law` and
`s. 54a of the Patents Law, 5727-1967`. As in Python, a citation that cannot
be parsed or is not in the corpus returns null from the library and goes to
`not_found` in the tool (a single missing citation gives an empty list and the
summary `ILPO Israel section '…' — not found.`), never an error.

Search defaults to all-terms matching and BM25 order and returns each hit as
Python does (statute, number, label, title, a `<mark>` snippet, rank). Status
reports `corpus_version` as the build's `source_version` (`WIPO Lex English
translations, 2026-10-22`) and `corpus_synced_at` as the snapshot date at UTC
midnight.

## Python differences

Python is being retired, so these are fixed here rather than there.

- The Python builder downloads each statute's WIPO Lex legislation page (an
  HTML page) and hands it to `pypdf` as if it were the PDF. Every statute fails
  to parse and is skipped with a warning, so the builder can only write an
  empty corpus. The TypeScript builder reads the page for its English PDF link
  and downloads the PDF.
- Python's section splitter works on plain text and takes the rest of the
  number line as the title, so headings (printed in the margin, or above the
  number in the Commercial Torts Law) were lost and body text became titles.
  The TypeScript builder splits by position as described above.
- Python labels the Commercial Torts Law's sections `Article N`. The
  translation numbers them as sections (`section 6(b)(3)`, `secs. 13 through
  21`), so labels now read `Section 6 Commercial Torts Law`; `Article 6 …`
  citations still resolve.
- Python leaves bare words unquoted in FTS5 queries, so `OR`, `AND`, `NEAR`
  and `NOT` ran as operators or raised syntax errors. Every term is quoted.
- `sort='outline'` ordered section numbers as text (`10` before `2`) and still
  reported a BM25 rank. Sections now sort numerically with letter insertions
  after their number, and outline hits carry no rank.
- The citation parser rejected subsection citations (`Section 6(b) …`),
  multi-letter or digit suffixes (`56D1`) and a statute year; it also kept
  lowercase suffixes (`54a`) that never match the stored `54A`. All resolve now.

## Building, packaging and verification

The runtime never fetches or rebuilds the corpus. From `typescript/`:

```sh
bun run build:ilpo-statutes --fetch     # download the PDFs, rewrite the source manifest, build
bun run build:ilpo-statutes             # or rebuild from the archived PDFs
bun scripts/compress-corpus.ts \
  --input .data/ilpo_statutes/ilpo_statutes.db \
  --output .data/ilpo_statutes/ilpo_statutes.db.zst
bun run verify:ilpo-statutes --file .data/ilpo_statutes/ilpo_statutes.db.zst
```

The raw PDFs go to the ignored `.data/ilpo_statutes/raw/`; a rebuild checks
each against the SHA-256 and row count in the committed source manifest and
stops on a mismatch. The builder writes a standalone DELETE-journal database,
never overwrites its output, and checks integrity. `--fixture` also rewrites
the test fixture.

The October 22, 2026 build (PDFs retrieved 16:11 UTC):

| Rows | Decoded bytes | Decoded SHA-256 | Zstandard bytes | File SHA-256 |
| --- | --- | --- | --- | --- |
| 576 | 892,928 | `733e534fbe2508af8bf4ff30e97d148e2fa400f7e0a70dc25050e1fd9cc3fe11` | 250,922 | `2b78e6dec05ad9abaea1f6a292b683eeb75b81ae38a357cfc443ebfa69e2de68` |

A second build from the archived PDFs reproduced the decoded bytes exactly.
The verifier configured the packaged file and both pins, checked each
statute's row count and PDF hash against the source manifest and six section
headings, and exercised the library and the default full MCP server. The
artifacts stay under ignored `.data/` and were not deployed.

## Tests

The [fixture](../tests/fixtures/ilpo-statutes/README.md) is 15 real sections
written by the builder from the October 22 PDFs. [Builder tests](../tests/ilpo-statutes-build.test.ts)
cover item joining, footnote and running-head removal, margin headings and
notes, the number sequence guard, chapter lines, the end-of-statute stop,
headings above the number, the `(Two)` subsections, paragraph reflow and the
source manifest. [Library tests](../tests/ilpo-statutes-client.test.ts) cover
aliases, citation parsing, status and per-statute metadata, sections and
missing ones, search filters, paging, numeric outline order, FTS operator
quoting, a missing corpus, Zstandard bytes and pins.
[MCP tests](../tests/ilpo-statutes-mcp.test.ts) cover both tools against the
Python summaries and shapes, `not_found`, the status resource, the curated
toolset and the `ilpo:read` scope on the authenticated HTTP listener. Node and
browser smoke runs read the fixture as bytes. All run offline.
