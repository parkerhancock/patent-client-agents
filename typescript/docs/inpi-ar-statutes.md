# INPI Argentina statutes corpus access

October 26, 2026. The TypeScript library reads a new INPI Argentina statutes
corpus: Argentina's five IP statutes in Spanish, as Infoleg (the Ministry of
Justice's legislative information service) keeps them, in one offline
SQLite/FTS5 snapshot read through the same verified-artifact lifecycle as the
[ILPO Israel statutes](ilpo-statutes.md). Python had no Argentina connector;
this one is new. No API key is needed. The MCP adapter uses a separate
`inpi_ar:read` scope for HTTP access.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `InpiArStatutesClient` | `search_inpi_ar_statutes`, `get_inpi_ar_section` | `inpi-ar-statutes://corpus/status` | `INPI_AR_STATUTES_CORPUS_PATH` |

The tools take the ILPO statutes parameters (`query`, `statute`, `per_page`,
`page`, `syntax`, `sort` for search; `citation` as a string or a list of up to
50 for get). The default file is
`~/.cache/patent_client_agents/inpi_ar_statutes.db`.
`INPI_AR_STATUTES_CORPUS_SHA256` pins the decoded SQLite bytes and
`INPI_AR_STATUTES_CORPUS_FILE_SHA256` the distributed file; the bootstrap id is
`inpi_ar_statutes`. The curated toolset does not route this corpus.

**What the texts are.** Infoleg publishes an updated text ("Texto actualizado
de la norma", `texact.htm`) for most laws, with each amendment worked in and
noted, and the text as published ("Texto completo de la norma", `norma.htm`).
These are Infoleg's texts, not official Boletín Oficial publications. The
status resource, `listStatutes()`, both tool descriptions and meta `notice`
say so, and record for each statute which of the two pages was used.

## Sources and contents

`scripts/build-inpi-ar-statutes-corpus.ts` fetches, for each statute, the
Infoleg norm page `verNorma.do?id=N`, checks that the page describes the
expected norm, reads its text links, and downloads `texact.htm` where the page
offers one and `norma.htm` otherwise. Plain HTTPS GETs with the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`;
no browser, cookie or challenge handling. Nothing blocked the requests. One
oddity: Infoleg's load balancer alternates between two nodes, and on October
26 one of them (`IDNODO=.cluster2`) answered the Ley 22.362 page with HTTP 200
and an empty body while the other served it in full. The builder asks for
identity encoding and retries an empty or non-HTML reply up to five times with
the same plain request.

The norm ids were found with Infoleg's own search (`buscarNormas.do` by type
and number), not guessed, and each norm page was read before use:

| Key | Statute | Infoleg norm | Text used | Articles | Notes | Newest note |
| --- | --- | --- | --- | --- | --- | --- |
| `patents` | Ley 24.481 de Patentes de Invención y Modelos de Utilidad, t.o. 1996 | [35001](https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do?id=35001) (Decreto 260/96) | `texact.htm`, Anexo I | 105 | 24 | 2025-09-03 |
| `trademarks` | Ley 22.362 de Marcas y Designaciones | [18803](https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do?id=18803) | `texact.htm` | 52 | 20 | 2025-12-11 |
| `designs` | Decreto-Ley 6673/63 de Modelos y Diseños Industriales (ratified by Ley 16.478) | [27687](https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do?id=27687) | `texact.htm` | 31 | 14 | 2018-06-18 |
| `copyright` | Ley 11.723 de Propiedad Intelectual | [42755](https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do?id=42755) | `texact.htm` | 98 | 31 | 2020-12-16 |
| `trade_secrets` | Ley 24.766 de Confidencialidad | [41094](https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do?id=41094) | `norma.htm` (no updated text on Infoleg) | 15 | 0 | none |

That is 301 rows: every numbered article of each statute, including repealed
ones (their row holds Infoleg's repeal note, for example Ley 22.362 art. 19,
Decreto-Ley 6673/63 art. 14, Ley 11.723 arts. 69, 70 and 74 bis) and the
inserted articles of Ley 11.723 (5 bis, 34 bis, 36 bis, 36 ter, 36 quáter, 36
quinquies, 55 bis, 72 bis, 74 bis).

Ley 24.481 itself (Infoleg 27289) has only the text as enacted in 1995.
Infoleg keeps the law up to date as Anexo I of Decreto 260/96, which approved
the texto ordenado with the Ley 24.572 corrections, so that page is the
source. Its updated text carries the Ley 25.859 (2004) and Ley 27.444 (2018)
substitutions and, for arts. 90 to 94 (the INPI), Decreto 627/2025 restoring
the earlier text. The trademark and design texts carry the Ley 27.444
amendments; Ley 22.362 also carries Infoleg's notes on INPI Resoluciones
26/2018, 101/2018, 144/2018 and 583/2025. "Newest note" is the latest
Boletín Oficial date the article notes cite, a rough guide to how far
Infoleg's consolidation reaches; it is not a guarantee that later changes are
absent. Ley 16.478 (Infoleg 62867) kept in force, as law, the decretos-leyes of
the de facto government of March 29, 1962 to October 12, 1963 that had not been
repealed, which includes Decreto-Ley 6673/63; it is accepted as a name for the
design decree but not stored.

[`scripts/inpi-ar-statutes-sources.json`](../scripts/inpi-ar-statutes-sources.json)
records, per statute, the norm page URL and Infoleg's heading, date,
publication line and summary for it, the text page URL and kind, the
`norma.htm` URL, the declared charset, retrieval time, SHA-256 and size of the
text page and of the norm page, article and note counts, the newest note date
and the word coverage below. The raw pages stay in the ignored
`.data/inpi_ar_statutes/raw/`.

How the pages become rows:

- **Encoding.** The pages declare `windows-1252` (Ley 24.481, 22.362, 11.723)
  or `ISO-8859-1` (Decreto-Ley 6673/63); Ley 24.766 is plain ASCII with
  entities. The builder honours the declared charset with `TextDecoder`, which
  decodes ISO-8859-1 as windows-1252 per WHATWG, so the dashes and curly quotes
  in 0x80-0x9F survive. A page without a declaration is read as windows-1252.
  Accents, ñ, º and ° come through; the builder tests check this on
  windows-1252 bytes.
- **Paragraphs.** The page is parsed with linkedom (through the client
  package's DOM helper). Block elements and `<br>` break paragraphs; the
  Infoleg banner and scripts are removed. Whether a paragraph is centered is
  kept, since headings are centered.
- **Articles.** An article starts at a paragraph opening with `ARTICULO 4º —`,
  `Artículo 1°. —`, `Art. 5º bis. —`, `Art. 34 bis:`, `ARTICULO 57. -` or
  `ARTICULO 1°-`, when the number can follow the previous one (the next one to
  three numbers, or a later bis/ter/quáter suffix on the same number), so a
  cross-reference at the start of a paragraph cannot start an article. Ley
  24.766 prints its last article as `ARTICULO l5`; the lowercase l is read as
  1. The builder checks that each statute's article numbers run from 1 to its
  last article (105, 52, 31, 89, 15) without a gap. The marker itself is
  dropped from the text; `section_label` carries it.
- **Where each statute starts and stops.** Ley 24.481 starts after `ANEXO I`
  and stops at `ANEXO II`, so Decreto 260/96's own articles, the reglamento
  (Anexo II) and Anexo III are not stored. The other statutes stop at the
  signatures (`VIDELA`, `GUIDO`, `Dada en la Sala de Sesiones…`). Preambles,
  vistos and considerandos before article 1, signatures, Ley 24.766's two
  country lists (Anexos I and II) and its promulgating Decreto 1607/96, and
  Infoleg's closing "Antecedentes Normativos" history list are not stored.
- **Infoleg's notes.** A paragraph in parentheses that starts like a note
  (`(Artículo sustituido…`, `(Inciso incorporado…`, `(Nota Infoleg: …`, `(Por
  art. …`, `(Texto Original restituido…`) and cites a Ley, Decreto, Resolución
  or B.O. is a note, and so is such a parenthesis at the end of a paragraph
  (`c) Por la declaración de nulidad o caducidad del registro. (Inciso
  sustituido por art. 72 de la Ley N° 27.444 B.O. 18/6/2018)`). Notes are
  moved after the article's paragraphs, separated by a blank line, in page
  order; a note moved off an inciso keeps the inciso's marker (`c) (Inciso
  sustituido …)`). A note that runs over several paragraphs is kept whole. A
  note between a heading and the next article (Ley 22.362's note on Sección
  2ª) goes with that next article. Inciso markers inside a note (`incisos b),
  d) e i)`) do not unbalance it.
- **Titles.** Argentine statutes have no article headings, so `title` is the
  Título, Capítulo and Sección headings the article sits under, outermost
  first and joined by ` / `, each label with its name: `TITULO II — DE LAS
  PATENTES DE INVENCION / CAPITULO I — PATENTABILIDAD`. Ley 11.723's unlabeled
  centered headings (`DE LA EDICION`) and Ley 24.766's bare Roman numerals
  (`II — Protección de la información…`) are read the same way. The design
  decree, Ley 11.723 arts. 1 to 12 and Ley 24.766 arts. 1 to 3 have none
  (`title` is null).
- **Labels.** `section_number` is `4`, `5 bis`, `36 quáter`; `section_label`
  is `Artículo 4° Ley 24.481`, `Artículo 5° bis Ley 11.723`, `Artículo 36
  quáter Ley 11.723`, `Artículo 3° Decreto-Ley 6673/63` (the degree sign up to
  9, as Infoleg prints it). `source_url` on each row is the text page parsed.
- **Meta.** `schema_version` 1, `snapshot_date` (the retrieval date),
  `source_version` (`Infoleg updated texts, 2026-10-26`), `section_count`,
  `retrieved_at`, `language` (`es`), `notice` and `statutes`, a JSON array with
  each statute's names, Infoleg id, norm and text URLs, text kind, text
  SHA-256, retrieval time, newest note date and article count. Rebuilding from
  the same pages gives the same bytes.

**Word coverage.** For each statute the builder compares the words of the page
from article 1 to the stop line with the words of its rows (labels, titles and
text; lowercased, accents and ordinal marks folded, as a multiset). The rows
hold 100 percent (rounded) of the patent, trademark and design texts, 99.9
percent of Ley 24.766 (the `l5` typo) and 98.8 percent of Ley 11.723; the
missing words are the article markers (`Art.`) the text drops. Against whole
pages the share is 53.5 percent for Decreto 260/96 (the reglamento and Anexo
III are most of the page), 56.8 percent for the design decree (long
considerandos), 87.7, 94.0 and 91.0 percent for the others.

**Spot checks** on October 26, 2026, comparing each row's words with the
archived page, by an independent regex parser rather than the builder's own:
Ley 24.481 arts. 4, 8, 12, 83, 90, 92 and 105; Ley 22.362 arts. 3, 10, 16, 19,
23 and 31; Decreto-Ley 6673/63 arts. 1, 6, 14 and 21; Ley 11.723 arts. 1, 5
bis, 36, 36 quinquies, 57, 74 bis and 84; Ley 24.766 arts. 1, 5, 11 and 15.
All 28 matched word for word, except where the rules above say otherwise: the
inciso markers added to moved notes (Ley 24.481 art. 92, Ley 22.362 art. 23),
the Sección 2ª note attached to Ley 22.362 art. 10, the heading after Ley
11.723 art. 36 quinquies, and the signatures and annexes after Ley 24.766 art.
15. Arts. 4, 8, 27, 83 and 90 to 92 of Ley 24.481, arts. 3, 10, 16 and 23 of
Ley 22.362 and arts. 1, 5 bis, 36, 57 and 74 bis of Ley 11.723 were also read
by eye against the pages.

Known imperfections: `SECCION 1a` keeps Infoleg's superscript as a plain `a`;
the Decreto 260/96 page's notes on arts. 90 to 94 (Decreto 627/2025) describe
a restoration whose legal effect this corpus does not assess; the
"Antecedentes Normativos" list, which records earlier amendments by decree and
resolution (for example the Decreto 27/2018 substitutions), is dropped rather
than attached to articles.

## Schema and behavior

Each row of `sections` is one article (`statute`, `section_number`,
`section_label`, `title`, `text`, `source_url`), the ILPO statutes schema
(version 1), with the external-content FTS5 table `sections_fts` over
`statute`, `section_label`, `title` and `text`. The tokenizer is `unicode61
remove_diacritics 2`: accents fold in both directions (`informacion` finds
`información`, `DISEÑO` finds `diseno`), and there is no stemming, because
Porter stemming is English-only. Search terms ending in `*` are prefixes
(`patentable*` finds `patentables`); every term is otherwise quoted, so FTS5
operators in a query are plain words. The reader checks meta `schema_version`
1, the columns, the FTS5 definition including `remove_diacritics 2`, and
rejects WAL files, as the shared `openCorpusSnapshot` does for every corpus.

Statute names resolve through an alias table after lowercasing, folding
accents, dropping `Nº`/`N°` and parentheticals and removing the dots in law
numbers: `Ley 24.481`, `ley 24481`, `Ley N° 24.481 (t.o. 1996)`, `Ley de
Patentes`, `patent law`; `Ley 22.362`, `marcas`, `trademarks`; `Decreto-Ley
6673/63`, `DL 6673/63`, `diseños industriales`, `Ley 16.478`; `Ley 11.723`,
`propiedad intelectual`, `derecho de autor`, `copyright`; `Ley 24.766`,
`confidencialidad`, `información confidencial`, `trade secrets`. Unknown
names pass through normalized and find nothing.

`get_inpi_ar_section` and `getSectionByCitation` parse `Artículo 4 Ley
24.481`, `art. 4 ley 24481`, `Ley 22.362 art. 3`, `Article 4 Patent Law`,
`Artículo 4° de la Ley N° 24.481`, `Ley 24.481, artículo 83`, `Art. 5° bis de
la Ley 11.723`, `art. 36 quater ley 11723` and `art. 3 inc. a) Ley 22.362`
(subdivisions are dropped and the whole article returned). `getSection` takes
`4`, `4°`, `5bis` or `36 quater`. A citation that cannot be parsed or is not
in the corpus returns null from the library and goes to `not_found` in the
tool (a single miss gives the summary `INPI Argentina article '…' — not
found.`), never an error.

Search defaults to all-terms matching and BM25 order and returns statute,
number, label, title, a `<mark>` snippet and rank. `sort: "outline"` orders by
statute (patents, trademarks, designs, copyright, trade secrets), article
number and then the insertion suffix (5, 5 bis, 5 ter, … 6), with no rank.
Status reports `corpus_version` as `source_version` and `corpus_synced_at` as
the snapshot date at UTC midnight, plus `notice` and, per statute, the norm
page, text page and kind, a version line (`Ley 22362, Publicada en el Boletín
Oficial del 02-ene-1981; Infoleg updated text (texto actualizado)`), the
newest note date, the text SHA-256 and retrieval time.

## Building, packaging and verification

The runtime never fetches or rebuilds the corpus. From `typescript/`:

```sh
bun run build:inpi-ar-statutes --fetch     # download, rewrite the source manifest, build
bun run build:inpi-ar-statutes             # or rebuild from the archived pages
bun scripts/compress-corpus.ts \
  --input .data/inpi_ar_statutes/inpi_ar_statutes.db \
  --output .data/inpi_ar_statutes/inpi_ar_statutes.db.zst
bun run verify:inpi-ar-statutes --file .data/inpi_ar_statutes/inpi_ar_statutes.db.zst
```

A rebuild checks each archived text page against the SHA-256 and the article
and note counts in the source manifest and stops on a mismatch. The builder
writes a standalone DELETE-journal database, never overwrites its output, and
checks integrity. `--fixture` also rewrites the test fixture.

The October 26, 2026 build (pages retrieved 22:45 UTC):

| Rows | Decoded bytes | Decoded SHA-256 | Zstandard bytes | File SHA-256 |
| --- | --- | --- | --- | --- |
| 301 | 446,464 | `bfb717000cfcd90279525ce0f180c0b516d0e09d5af72de28ae4e8f8afc2e448` | 128,457 | `97e74504aeb6b414668a20a6cefa7ef54002c2332e62f58896d153a28f48478b` |

A second build from the archived pages reproduced the decoded bytes exactly.
The verifier configured the packaged file and both pins, checked each
statute's article count, text hash and text kind against the source manifest
and the opening words of six articles, and exercised the library and the
default full MCP server. The artifacts stay under ignored `.data/` and were
not published or deployed.

## Tests

The [fixture](../tests/fixtures/inpi-ar-statutes/README.md) is 16 real
articles written by the builder from the October 26 pages.
[Builder tests](../tests/inpi-ar-statutes-build.test.ts) cover windows-1252 and
ISO-8859-1 decoding, paragraphs and centering, every article-opening form and
the `l5` typo, note recognition (whole, trailing, multi-paragraph, after a
heading, with inciso markers), heading titles, the decree start and stop
markers, gap and missing-end failures, the norm page parser, word coverage and
the source manifest. [Library tests](../tests/inpi-ar-statutes-client.test.ts)
cover aliases, citation parsing, article normalization, prefix queries,
status and per-statute metadata, articles with notes, repealed and inserted
articles, accent-folded search, filters, paging, outline order, FTS operator
quoting, a missing corpus, Zstandard bytes and both pins.
[MCP tests](../tests/inpi-ar-statutes-mcp.test.ts) cover both tools'
summaries and shapes, `not_found`, the status resource and its notice, the
curated toolset and the `inpi_ar:read` scope on the authenticated HTTP
listener. Node and browser smoke runs read the fixture as bytes. All run
offline.
