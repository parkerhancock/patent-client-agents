# Russian Civil Code, Part Four corpus access

October 26, 2026. The TypeScript library reads a new corpus of Part Four of the
Civil Code of the Russian Federation, Russia's single intellectual property
statute (Section VII, chapters 69 to 77, articles 1225 onward), in the English
translation WIPO Lex publishes. It is one offline SQLite/FTS5 snapshot read
through the same verified-artifact lifecycle as the
[ILPO statutes](ilpo-statutes.md). No API key is needed. The MCP adapter uses
a separate `rospatent:read` scope for HTTP access. Python had no Russia
connector, so there is nothing to match; the tools follow the ILPO pair.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `RospatentStatutesClient` | `search_rospatent_statutes`, `get_rospatent_section` | `rospatent-statutes://corpus/status` | `ROSPATENT_STATUTES_CORPUS_PATH` |

Search takes `query`, `chapter` (69 to 77), `syntax`, `sort`, `per_page` and
`page`; get takes `citation` as a string or a list of up to 50. The default
file name is `~/.cache/patent_client_agents/rospatent_statutes.db`.
`ROSPATENT_STATUTES_CORPUS_SHA256` pins the decoded SQLite bytes and
`ROSPATENT_STATUTES_CORPUS_FILE_SHA256` the distributed file. The tools are
in the full toolset only; the curated facade has no Russia route.

## Source and version

WIPO Lex holds the English text only on its record of the whole Code (Parts
One to Four). `scripts/build-rospatent-statutes-corpus.ts` fetches two WIPO Lex
legislation pages with the shared parser (`parseWipoLexLegislation`):

- [22547](https://www.wipo.int/wipolex/en/legislation/details/22547), "Civil
  Code (Parts One, Two, Three and Four)", year of version 2024, amended up to
  March 22, 2024. Its English PDF, `ru421en_1.pdf` (507 pages), is the source.
  The PDF's own title says it is amended up to Federal Law No. 48-FZ of March
  11, 2024, and its list of amending dates ends "January 30, March 11, 2024".
- [23256](https://www.wipo.int/wipolex/en/legislation/details/23256), WIPO
  Lex's latest record of the Code: the Russian text amended up to August 3,
  2025 (Federal Law No. 235-FZ of July 23, 2025, on Article 1350). It has no
  current English text and links the same 2024 English PDF "for reference".
  The builder stops if that link ever changes, since a newer English
  consolidation would then exist. WIPO Lex's separate Part Four record
  ([23255](https://www.wipo.int/wipolex/en/legislation/details/23255), with
  amendments up to Federal Law No. 190-FZ of July 22, 2024) has only Russian,
  and the earlier Part Four consolidations carry older English texts.

So the corpus is the newest English consolidation WIPO Lex has, and it lags
the Russian text. Among the amending laws WIPO Lex lists that the translation
predates are Federal Law No. 190-FZ of July 22, 2024 (Part Four, in force
October 21, 2024), No. 214-FZ of July 7, 2025 (Part Four) and No. 235-FZ of
July 23, 2025 (Article 1350). The translation is WIPO's, not an official text,
and the Russian text controls. The status resource reports
`translation_amended_up_to` (2024-03-22), `russian_amended_up_to`
(2025-08-03) and a `version_note` saying this, and the tool descriptions point
to it.

Plain HTTPS GETs with the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`;
no browser, cookie or challenge handling. Nothing blocked the requests. WIPO
signs the PDF link for a few minutes, so the manifest keeps the unsigned URL.
The PDF was retrieved on October 26, 2026 at 22:35 UTC;
[`scripts/rospatent-statutes-sources.json`](../scripts/rospatent-statutes-sources.json)
records both WIPO Lex pages and their version notes, the PDF URL and WIPO's
last-modified stamp for it (May 6, 2024), retrieval times, SHA-256
(`9701ca23…4995`), size (3,655,337 bytes), page count and the article and
repealed-article counts.

## Contents

There are 329 rows: every article from 1225 to 1541 and the twelve inserted
articles 1231.1, 1240.1, 1244.1, 1253.1, 1286.1, 1308.1, 1335.1, 1358.1,
1360.1, 1406.1, 1457.1 and 1522.1. Article 1478 is printed only as "Invalid
from June 29, 2023 - Federal Law No. 193-FZ of June 28, 2022"; its row has
`repealed` set, no title, and that note as its text. Chapter 77 (articles
1542 to 1551, the right to use results within a unified technology) is printed
only as a chapter heading with "Invalid from January 1, 2022 - Federal Law No.
456-FZ of December 22, 2020"; the translation does not list its articles, so
there are no rows for them, and the status reports the chapter and note under
`repealed_chapters`. Repealed items inside an article ("3. Abrogated from
October 1, 2014.", "Paragraph 4 is abrogated.") stay in the text as printed.

Each row carries the headings the source gives above it: `chapter` ("Chapter
72. The Patent Law"), `paragraph`, the § heading where the chapter has §s
("§ 5. Obtaining a Patent"; chapters 69, 70, 74 and 75 have none), and
`subparagraph`, the numbered heading inside § 5 of Chapter 72 and §§ 2 and 3
of Chapter 76 ("1. The Patent Application, Its Amendment and Revocation").
Section VII's heading is in meta `section_heading`. Nothing is added that the
translation does not print.

How the PDF becomes rows. Part Four (pages 378 to 507) is set in one 12-point
face with no footnotes, running heads or page numbers. The builder reads
positioned text items (the shared `pdfPageItems`):

- It starts at the centered "Section VII" line and stops at the President's
  signature.
- Paragraphs start indented (x 76) and continue at the margin (x 40); each
  item, list entry or paragraph becomes one line of `text`. Line-end hyphens
  are compounds in this translation ("one-time", "non-exclusive") and are kept.
- An article starts at "Article N." at the paragraph indent with a heading
  that begins with a capital, and only if N can follow the previous article,
  so "Article 1229 of this Code" in running text is not a break. Long headings
  wrap to x 120.6 and are joined.
- Centered lines are chapter, § and sub-§ headings, joined across wraps. Any
  other indentation, any gap in the article sequence and any text before
  Article 1225 stop the build rather than being guessed at.

`source_url` on each row is the 22547 page. `snapshot_date` is the retrieval
date, so rebuilding from the same PDF gives the same bytes.

Checks on October 26, 2026. Every row was compared with `pdftotext -layout`
output for its article (title and text reduced to letters and digits, from
its heading to the next): all 329 match, except that Article 1541's span in
the PDF ends with the Chapter 77 note, which is stored separately. Articles
1225, 1231 (wrapped heading), 1350, 1358.1, 1381, 1478 and 1484 were also
read against the PDF, and the 8 chapter, 24 § and 16 sub-§ headings stored
were checked against the PDF's headings in order. Word for word, the rows hold all of the PDF's words between "Section
VII" and the signature (91,540) except 32 that `pdftotext` spells without the
line-end hyphen ("nonexclusive" for "non-exclusive"); over all of pages 378 to
507, 0.4 percent of words are missing, all from the title block and list of
amending dates above Section VII and the signature. Source flaws are kept:
Article 1369's heading reads "Utility Model o Industrial Design" in the PDF.

## Schema and behavior

Each row of `sections` is one article with the row shape of the other statute
corpora (`statute`, `section_number`, `section_label`, `title`, `text`,
`source_url`) plus `chapter`, `paragraph`, `subparagraph` and `repealed`.
`statute` is always `civil_code` and labels read `Article 1350 Civil Code`.
The external-content FTS5 table `sections_fts` covers `statute`,
`section_label`, `title` and `text` with the `porter unicode61` tokenizer, as
in the ILPO corpus. The reader checks meta `schema_version` 1, the columns and
the FTS5 definition, and rejects WAL files, as the shared
`openCorpusSnapshot` does for every corpus.

`get_rospatent_section` parses `Article 1350 Civil Code`, `Article 1350`,
`Civil Code Art. 1350(1)`, `Art. 1484 CC RF`, `Item 1 of Article 1229 of the
Civil Code`, `Article 1350, item 2, Civil Code`, `Article 1358.1 of Part Four
of the Civil Code` and the Russian forms `ст. 1484 ГК РФ`, `п. 1 ст. 1350 ГК
РФ` and `статья 1515 Гражданского кодекса`. Item and paragraph markers are
dropped and the whole article returned; a dotted number is an inserted
article. A citation naming another statute (`Article 6 Patents Law`) or a bare
number without "Article" does not parse. As in the ILPO tools, a citation that
cannot be parsed or is not in the corpus returns null from the library and
goes to `not_found` in the tool (a single miss gives an empty list and the
summary `Russian Civil Code article '…' — not found.`), never an error. A
repealed article's summary says so.

Search defaults to all-terms matching and BM25 order; every term is quoted, so
FTS5 operators in the query are literal. `chapter` restricts hits to one
chapter. `sort='outline'` orders by article number with inserted articles
after their base (1231, 1231.1, 1232) and carries no rank. Status reports
`corpus_version` as the build's `source_version` (`WIPO Lex 22547 English
translation, amended up to 2024-03-22`) and `corpus_synced_at` as the
snapshot date at UTC midnight.

## Building, packaging and verification

The runtime never fetches or rebuilds the corpus. From `typescript/`:

```sh
bun run build:rospatent-statutes --fetch   # download the PDF, rewrite the source manifest, build
bun run build:rospatent-statutes           # or rebuild from the archived PDF
bun scripts/compress-corpus.ts \
  --input .data/rospatent_statutes/rospatent_statutes.db \
  --output .data/rospatent_statutes/rospatent_statutes.db.zst
bun run verify:rospatent-statutes --file .data/rospatent_statutes/rospatent_statutes.db.zst
```

The raw PDF goes to the ignored `.data/rospatent_statutes/raw/`; a rebuild
checks it against the SHA-256 and article count in the committed source
manifest and stops on a mismatch. The builder writes a standalone
DELETE-journal database, never overwrites its output, and checks integrity.
`--fixture` also rewrites the test fixture.

The October 26, 2026 build (PDF retrieved 22:35 UTC):

| Rows | Decoded bytes | Decoded SHA-256 | Zstandard bytes | File SHA-256 |
| --- | --- | --- | --- | --- |
| 329 | 1,097,728 | `6d15006a3c5cc690f51d6a0f50d32f0df5ba7a5a6445bf5e85e094f556576ac3` | 269,810 | `05d07af18766b4249a6e2333ca0e4795cff4eecd0813a4cdc41b894a02deaca9` |

Two further builds from the archived PDF reproduced the decoded bytes
exactly. The verifier configured the packaged file and both pins, checked the
article count and PDF hash against the source manifest, six article headings
and the repeal of Article 1478, and exercised the library and the default full
MCP server. The artifacts stay under ignored `.data/` and were not published
or deployed. `rospatent_statutes` is in the hosted bootstrap list, so it has
to be published before a hosted image from this branch will start (see
[corpus bootstrap](corpus-bootstrap.md)).

## Tests

The [fixture](../tests/fixtures/rospatent-statutes/README.md) is 16 real
articles written by the builder from the October 26 PDF.
[Builder tests](../tests/rospatent-statutes-build.test.ts) cover item joining,
line grouping, the start and stop lines, chapter, § and sub-§ headings and
their wraps, wrapped article headings, paragraph reflow, a reference that is
not a heading, the repealed article and chapter, the sequence and indentation
errors, article ordering, WIPO's "Amended up to" dates and the source
manifest. [Library tests](../tests/rospatent-statutes-client.test.ts) cover
code names, citation parsing in English and Russian, status and its version
fields, articles with their headings, the repealed and missing cases, search
with the chapter filter, paging, outline order, FTS operator quoting, a
missing corpus, Zstandard bytes and pins.
[MCP tests](../tests/rospatent-statutes-mcp.test.ts) cover both tools, their
summaries and `not_found`, the status resource, the curated toolset and the
`rospatent:read` scope on the authenticated HTTP listener. Node and browser
smoke runs read the fixture as bytes. All run offline.
