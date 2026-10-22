# Légifrance IP corpus access

October 22, 2026. The TypeScript library reads the Légifrance IP corpus: every
article in force of the legislative part of the Code de la propriété
intellectuelle (CPI) and the trade-secret articles of the Code de commerce
(L151-1 to L154-1), in one offline SQLite/FTS5 snapshot read through the same
verified-artifact lifecycle as the [DPMA statutes](dpma-statutes.md). No API
key is needed. The MCP adapter uses a separate `legifrance:read` scope for
HTTP access.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `LegifranceIpClient` | `search_legifrance_ip`, `get_legifrance_section` | `legifrance-ip://corpus/status` | `LEGIFRANCE_IP_CORPUS_PATH` |

Tool names and parameters (`query`, `statute` for search; `citation` as a
string or a list of up to 50 for get), the path variable and the default file
name (`~/.cache/patent_client_agents/legifrance_ip.db`) match the Python
connector; search adds `limit` and `offset`. `LEGIFRANCE_IP_CORPUS_SHA256`
pins the decoded SQLite bytes and `LEGIFRANCE_IP_CORPUS_FILE_SHA256` the
distributed file. The library ports Python's `search`, `getSection` (citation),
`getBySectionNumber`, `parseLegifranceCitation`, the `LEGIFRANCE_STATUTES`
vocabulary and `getCorpusStatus`. Python's facade does not route this corpus,
so neither does the TypeScript facade.

## Source and contents

Python's connector ships a seven-row `seed.jsonl` of hand-written summaries
with invented article titles; it never read Légifrance. The TypeScript corpus
is built from the official data instead.

legifrance.gouv.fr answered a plain GET for the CPI page with HTTP 403 and a
Cloudflare managed challenge on October 22, 2026, so its pages are not read
(and the PISTE Légifrance API needs registered OAuth credentials). DILA, which
runs Légifrance, publishes the same database as open data at
`https://echanges.dila.gouv.fr/OPENDATA/LEGI/`: a full export
(`Freemium_legi_global_*.tar.gz`, 1.17 GB) plus daily increments
(`LEGI_*.tar.gz`). `scripts/build-legifrance-ip-corpus.ts` reads them with
plain HTTPS GETs and the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`.

The builder streams the newest full export (July 13, 2025) and every later
increment through gunzip and a small tar reader (ustar, GNU long names, pax
paths), keeps the article files (`LEGIARTI…xml`) under the two codes'
directories (`LEGITEXT000006069414`, `LEGITEXT000005634379`) whose number is a
CPI `L…` article or a Code de commerce `L151`-`L154` article, and writes them
as one gzipped layer per archive under the ignored `.data/legifrance_ip/raw/`.
Each increment's `liste_suppression_legi*.dat` lines that touch the two codes
are kept with its layer. The build applies the layers in archive order
(deletions, then new and replaced files) and selects, for each article
number, the version whose `ETAT` is in force and whose `DATE_DEBUT`/`DATE_FIN`
span contains the date of the last increment applied. Two versions in force
for one number fail the build.

[`scripts/legifrance-ip-sources.json`](../scripts/legifrance-ip-sources.json)
records the listing URL, and for every archive its URL, retrieval time,
`Last-Modified`, size, SHA-256, how many article files and deletion lines it
contributed, and the SHA-256 of its layer. A rebuild checks every layer
against it.

How an article becomes a row:

- `section` is the LEGI `NUM` (`L611-10`); `statute` is `CPI` or
  `Code de commerce`, Python's vocabulary.
- French articles have no heading of their own, so `title` is the heading of
  the innermost code division containing the article (for L611-10,
  `Section 1 : Inventions brevetables`), and the new `breadcrumb` column holds
  the whole path from `Partie législative` down, using the headings in force
  on the snapshot date.
- `text` is the article's `CONTENU` as plain text: one line per paragraph or
  line break, table cells joined by ` | `, entities decoded.
- New columns `article_id` (the `LEGIARTI` id of the version in force) and
  `in_force_since` (its `DATE_DEBUT`). Sections returned by the library add
  `url`, the article's Légifrance page
  (`https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI…`).
- Meta keeps Python's keys (`schema_version` 1, `snapshot_date`,
  `source_version`, `section_count`) and adds `source`, `full_export`,
  `last_increment`, `archive_count`, `retrieved_at` and `codes`, a JSON array
  with each code's id, title, number rule and article count. `snapshot_date`
  is the date the selected versions are in force on (the last increment's
  date) and `source_version` is `LEGI <stamp of the last increment>`.

The October 22, 2026 build applied 473 archives (3.2 GB): the July 13, 2025
full export, which held 1,867 article files of the two codes (every version,
in force or not), and 472 increments through `LEGI_20261021-213023`, 86 of
which touched the two codes. No deletion line touched them. The selected
versions are those in force on October 21, 2026: 897 rows, 877 CPI articles
(Book I 178, II 59, III 190, IV 25, V 56, VI 226, VII 131, VIII 12) and 20
Code de commerce articles (L151-1 to L154-1). The longest article is 12,542
characters. Spot checks: the texts of L611-10 (patentability), L611-11
(novelty) and L151-1 (trade-secret definition) were read for completeness, and
their headings, breadcrumbs and version dates checked (L611-10 in force since
August 6, 2008; L613-3 since June 1, 2023, the date of the UPC ordinance).

## Schema and behavior

The schema is Python's (version 1) with the three added columns, which the
Python reader ignores: `sections` (`statute`, `section`, `title`, `text`,
`article_id`, `in_force_since`, `breadcrumb`, unique on statute and section),
indexed by the external-content FTS5 table `sections_fts` over `title` and
`text` with `unicode61 remove_diacritics 2`, so `brevetabilite` matches
`brevetabilité`. The reader checks meta `schema_version` 1, the columns and
the FTS5 definition, and rejects WAL files. It also reads a corpus without the
added columns (a Python seed build); those fields are then null.

`get_legifrance_section` parses Python's forms (`L. 611-10 CPI`,
`Art. L. 611-10 CPI`, `L611-10 CPI`, `L. 151-1 Code de commerce`,
`L 611.10 CPI`) plus the long code names (`article L. 613-3 du code de la
propriété intellectuelle`), `C. com.`, numbers with more than three parts and
a bare `L. 611-10`, which resolves when the number exists in one code only
(otherwise `AMBIGUOUS_SECTION`). An unparseable citation fails the call
(`INVALID_CITATION`, Python's ValidationError); a missing article is
`SECTION_NOT_FOUND`, which fails a single citation and goes to `not_found` in a
list, with Python's summaries. Search returns Python's lean hits (`statute`,
`section`, `title`, a 400-character snippet with `<mark>` highlights), all
terms required, in BM25 order with row order breaking ties; the statute filter
accepts only `CPI` or `Code de commerce`. Status reports `corpus_version` as
`source_version` and `corpus_synced_at` as `snapshot_date` at UTC midnight.

## Python differences

- The corpus is the full legislative CPI and the Code de commerce trade-secret
  title from the official data, not seven paraphrased rows. The seed's titles
  ("Brevetabilité", "Marques") are not official; `title` is now the real
  containing heading.
- `search_legifrance_ip` always returned the first 25 hits with no way to
  page; it now takes `limit` and `offset` (defaults 25 and 0) and reports
  `more_available`.
- The citation parser required the code name and at most three number parts;
  see above for the forms now accepted.

## Building, packaging and verification

The runtime never fetches or rebuilds the corpus. From `typescript/`:

```sh
bun run build:legifrance-ip --fetch      # read the archives, rewrite the source manifest, build
bun run build:legifrance-ip              # or rebuild from the extracted layers
bun scripts/compress-corpus.ts \
  --input .data/legifrance_ip/legifrance_ip.db \
  --output .data/legifrance_ip/legifrance_ip.db.zst
bun run verify:legifrance-ip --file .data/legifrance_ip/legifrance_ip.db.zst
```

With `--fetch`, `--archives DIR` reads archives already downloaded to `DIR`
under their published names instead of downloading them again; they are
hashed the same way. The full export used here was downloaded once with the
same user agent and read with `--archives`. The builder never overwrites its
output, checks integrity and gives the same bytes from the same layers.
`--fixture` also rewrites the test fixture.

The October 22, 2026 build (archives read October 22, 2026 from 16:27 UTC):

| Rows | Decoded bytes | Decoded SHA-256 | Zstandard bytes | File SHA-256 |
| --- | --- | --- | --- | --- |
| 897 | 2,015,232 | `b9556aa5777cc86acdc43cdeb200ff5e6cbcb595cacaf2835ee33d6d11e6a0f4` | 454,465 | `7101448e7e0d4046e43dd4cf870229e2b528fa627bff17d568805461805dbfc4` |

The 473 layers take 3.1 MB. The verifier configured the packaged file and
both pins, checked the per-code counts against the row count, and exercised
the library and the default full MCP server. The artifacts stay under ignored
`.data/` and were not deployed.

## Tests

The fixture (`tests/fixtures/legifrance-ip/legifrance_ip.db`) is 13 real
articles (CPI L111-1, L122-5, L511-1, L611-1, L611-10, L611-11, L613-3,
L615-1, L711-1, L713-2; Code de commerce L151-1, L151-4, L152-1) written by
the builder from the October 22 build. [Builder tests](../tests/legifrance-ip-build.test.ts)
cover article XML (text, tables, headings in force), the streaming tar reader
with long names and archive hashing, layer order, deletions, version
selection, the listing and the manifest. [Library tests](../tests/legifrance-ip-client.test.ts)
cover citations, status, sections, the statute filter, paging, diacritic
folding, FTS operator quoting, Zstandard bytes, pins, the environment
variables, a Python seed build, WAL and schema errors.
[MCP tests](../tests/legifrance-ip-mcp.test.ts) cover both tools against
Python's summaries and shapes, `not_found`, the status resource and the
`legifrance:read` scope on the authenticated HTTP listener. Node and browser
smoke runs read the fixture as bytes. All run offline.
