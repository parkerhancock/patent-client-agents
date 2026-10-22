# DPMA statutes corpus access

October 22, 2026. The TypeScript library reads the DPMA statutes corpus: sections
of the six German IP Acts (Patentgesetz, Markengesetz, Gebrauchsmustergesetz,
Designgesetz, Urheberrechtsgesetz and Geschäftsgeheimnisgesetz) in one offline
SQLite/FTS5 snapshot, read through the same verified-artifact lifecycle as the
[UPC statutes](upc-statutes.md). No API key is needed. The MCP adapter uses a
separate `dpma:read` scope for HTTP access.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `DpmaStatutesClient` | `search_dpma_statutes`, `get_dpma_section` | `dpma-statutes://corpus/status` | `DPMA_STATUTES_CORPUS_PATH` |

Tool names and parameters (`query`, `statute`, `limit`, `offset`, `syntax`,
`sort`, `full` for search; `citation` as a string or list of up to 50 for get),
the path variable and the default file name
(`~/.cache/patent_client_agents/dpma_statutes.db`) match the Python connector.
`DPMA_STATUTES_CORPUS_SHA256` pins the decoded SQLite bytes and
`DPMA_STATUTES_CORPUS_FILE_SHA256` the distributed file. The DPMA register
connector (DPMAconnectPlus) is a separate Python module and is not ported.

The curated facade routes `search_legal_reference` and `get_legal_reference`
with `corpus='dpma'` to the same code, as the Python facade forwards to
`search_dpma_statutes` and `get_dpma_section`. The `statute` filter is passed
only for `dpma` and ignored for the other corpora. `get_legal_reference` takes
the identifier as one citation and returns the get tool's envelope, including
`not_found`.

## Source and contents

The corpus is built in TypeScript from the official consolidated texts on
gesetze-im-internet.de (Bundesministerium der Justiz / Bundesamt für Justiz),
which publishes each Act as a zip holding one XML document under the
`gii-norm` DTD 1.01. `scripts/build-dpma-statutes-corpus.ts` downloads the six
zips with one plain HTTPS GET each and the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`;
there is no browser, cookie or challenge handling. Every § of each Act is one
row, in German, as currently in force. The Python `seed.jsonl` (12 truncated
sections) is no longer used here.

| Act | Slug | Rows | Stand (as published) | Version date | Publisher build |
| --- | --- | --- | --- | --- | --- |
| PatG | `patg` | 174 | zuletzt geändert durch Art. 13 G v. 20.5.2026 I Nr. 152 | 2026-05-20 | 2026-09-30 |
| MarkenG | `markeng` | 193 | Zuletzt geändert durch Art. 14 G v. 20.5.2026 I Nr. 152 | 2026-05-20 | 2026-09-30 |
| GebrMG | `gebrmg` | 45 | zuletzt geändert durch Art. 17 G v. 15.7.2024 I Nr. 237 | 2024-07-15 | 2024-07-18 |
| DesignG | `geschmmg_2004` | 88 | Zuletzt geändert durch Art. 10 G v. 10.8.2021 I 3490 | 2021-08-10 | 2026-05-06 |
| UrhG | `urhg` | 255 | Zuletzt geändert durch Art. 2 G v. 26.5.2026 I Nr. 157 | 2026-05-26 | 2026-05-29 |
| GeschGehG | `geschgehg` | 23 | none in the source (BGBl I 2019, 466) | 2019-04-18 | 2021-01-28 |

That is 778 rows. The Designgesetz still lives under its 2004 slug
(Geschmacksmustergesetz). The GeschGehG document carries no Stand note, so
its version date is the Ausfertigungsdatum. The zips were retrieved on
October 22, 2026; [`scripts/dpma-statutes-sources.json`](../scripts/dpma-statutes-sources.json)
records each URL, retrieval time, `Last-Modified`, zip and XML SHA-256,
publisher build stamp, Stand note and row count.

How the XML becomes rows:

- A section's `enbez` (`§ 16a`) gives the number, lowercased; `titel` gives
  the title. The PatG and GebrMG have no official section headings, so their
  titles are null (the old seed's PatG titles were unofficial).
- Text keeps the structure the citation parser drops: one line per Absatz
  (`(1) …`), one line per numbered or lettered item (`1. …`, `a) …`) with two
  spaces of indent per list level, and `<BR/>` breaks kept. `get_dpma_section`
  therefore returns the whole section for `§ 139 Abs. 1 PatG`. Footnotes
  (Textnachweis and validity notes) and Fundstelle annotations are not section
  text and are left out.
- Repealed sections stay citable. A single repealed § keeps its published
  title `(weggefallen)` and text (`-`); a grouped entry such as
  `(XXXX) §§ 18 und 19` or `§§ 161 bis 163` becomes one row per number, title
  and text `(weggefallen)`.
- The UrhG's `Anlage (zu § 61a)` is stored as section `Anlage` (reach it with
  `getSection("Anlage", { statute: "UrhG" })`; the citation parser takes
  numbers only). The Inhaltsübersicht and the structural headings
  (Abschnitte, Teile) are not stored.
- Meta adds `source`, `retrieved_at` and `acts`, a JSON array with each Act's
  long title, Stand note, amendment date, Ausfertigungsdatum, Fundstelle,
  version date, publisher build stamp, source URL, retrieval time, zip
  SHA-256 and row count. `snapshot_date` is the retrieval date, so rebuilding
  from the same zips gives the same bytes.

Spot checks on October 22, 2026: § 1, § 9, § 16a and § 139 PatG, § 14
MarkenG and § 2 GeschGehG were compared with their official HTML pages
(`/patg/__139.html` and so on); text and titles are identical once whitespace
is ignored.

## Schema and behavior

Each row of `sections` is one § of one Act (`statute`, `section`, `title`,
`text`), the schema the Python builder defines (version 1, unchanged),
indexed by the external-content FTS5 table `sections_fts` over all
four columns with the `porter unicode61` tokenizer. The reader checks meta
`schema_version` 1, the columns and the FTS5 definition, and rejects WAL files,
as the shared `openCorpusSnapshot` does for every corpus.

Act names resolve through Python's alias table (`PatG`, `Patentgesetz`, `Patent
Act`, `Trade Mark Act`, `Geschäftsgeheimnisgesetz`, `Copyright Act` and the
rest, case-insensitively); unknown names pass through and find nothing.
`get_dpma_section` parses `§ 139 PatG`, `Section 14 MarkenG`, `Sec. 14 of the
Trade Mark Act`, `S. 139 PatG` and bare `139`. A bare number found in one Act
resolves; one found in several fails with the list of Acts (`AMBIGUOUS_SECTION`).
A single missing citation fails the call; in a list, missing citations go to
`not_found` while parse and ambiguity errors fail the call, as in Python.

Status adds `acts`, the parsed meta `acts` array (null for a corpus built
without it, such as the Python seed build). Each section carries its Act's
`stand` and `version_date` (null when the corpus does not record them), and
the single-section summary of `get_dpma_section` names the Stand.

Search defaults to all-terms matching and BM25 order, returns lean stubs
(statute, section, title, a 400-character snippet with `<mark>` highlights) or,
with `full`, the hit with its rank. Status reports `corpus_version` as
`source_version` when the build recorded one, otherwise `snapshot-<date>`
(Python's form, with a hyphen), and `corpus_synced_at` as that date at UTC
midnight; a missing or malformed date gives `unknown` and `null`. Section text
beyond a 32,000-character inline budget would be delivered as a text artifact,
as the other corpus tools do; the longest section in the build is about
4,500 characters.

## Python differences

Python is being retired, so these are fixed here rather than there.

- Python leaves bare words unquoted in FTS5 queries, so `OR`, `AND`, `NEAR`
  and `NOT` run as operators (`Unterlassung OR Marke` in the default `and`
  mode matches either word) or fail (`NOT` alone raises an FTS5 syntax error).
  The TypeScript reader quotes every term.
- `sort='outline'` ordered sections as text, so § 139 came before § 3. Sections
  now sort numerically within each Act, a letter section after its number
  (§ 16, § 16a, § 17) and the UrhG Anlage last. BM25 ties fall back to row
  order so pages are stable.
- The citation parser rejected German subdivisions (`§ 139 Abs. 1 PatG`,
  `§ 2 Nr. 1 GeschGehG`) and Act citations without a `§` (`139 PatG`). Both now
  resolve to the whole section. Letter suffixes are lowercased (`16A` → `16a`)
  to match gesetze-im-internet.de numbering.
- Python's facade passes its own `syntax` default (`adj`) to the DPMA search,
  so an omitted `syntax` phrase-matched although the parameter text says
  statutes default to `and`. The TypeScript facade leaves `syntax` without a
  schema default and applies `and` for `dpma`, `adj` for the manuals.

## Building, packaging and verification

The runtime never fetches or rebuilds the corpus. From `typescript/`:

```sh
bun run build:dpma-statutes --fetch     # download the zips, rewrite the source manifest, build
bun run build:dpma-statutes             # or rebuild from the archived zips
bun scripts/compress-corpus.ts \
  --input .data/dpma_statutes/dpma_statutes.db \
  --output .data/dpma_statutes/dpma_statutes.db.zst
bun run verify:dpma-statutes --file .data/dpma_statutes/dpma_statutes.db.zst
```

The raw zips go to the ignored `.data/dpma_statutes/raw/`; a rebuild checks
each against the SHA-256 and row count in the committed source manifest and
stops on a mismatch. The builder writes a standalone DELETE-journal database
(no preparation step), never overwrites its output, and checks integrity.
`--fixture` also rewrites the test fixture. When the local resolver cannot
resolve the host, `--connect-ip ADDRESS` connects to that address and still
verifies TLS against `www.gesetze-im-internet.de` (it was needed on October 22,
when the tailnet resolver failed on the host's CNAME).

The October 22, 2026 build (zips retrieved 11:59 UTC):

| Rows | Decoded bytes | Decoded SHA-256 | Zstandard bytes | File SHA-256 |
| --- | --- | --- | --- | --- |
| 778 | 1,470,464 | `211bf701e26fb7f9719d0a20929596424711ae89e43130f30d220b8e74cefee2` | 402,417 | `2a59048b1775ef370dcaf41f6196d3990e02412d50005a5af58fd390341bc83c` |

The verifier configured the packaged file and both pins, checked the per-Act
metadata against the row count, and exercised the library and the default
full and curated MCP servers. The live facade probes (`dpma search`,
`dpma section`) passed with `DPMA_STATUTES_CORPUS_PATH` set to the packaged
file. The artifacts stay under ignored `.data/` and were not deployed; the
deployed Python server still has no DPMA corpus.

## Tests

The [fixture](../tests/fixtures/dpma-statutes/README.md) is 16 real sections
written by the builder from the October 22 zips. [Builder tests](../tests/dpma-statutes-build.test.ts)
cover the XML-to-text rules, grouped repealed sections, Act metadata and the
source manifest. [Library tests](../tests/dpma-statutes-client.test.ts) cover citation
parsing, status and per-Act metadata, sections (Absatz and list lines, letter
and repealed sections, the Anlage), ambiguity and not-found errors, search syntax, Act
filters and aliases, numeric outline order, paging, FTS operator quoting,
Zstandard bytes, pins, the environment variables, WAL, schema and metadata
gaps. [MCP tests](../tests/dpma-statutes-mcp.test.ts) cover both tools against
the Python summaries and shapes, `not_found`, the status resource, the curated
facade routing (statute filter, default syntax, get envelope) and the
`dpma:read` scope on the authenticated HTTP listener. Node and browser smoke
runs read the fixture as bytes. All run offline.
