# INPI Brazil statutes (LPI) corpus access

October 22, 2026. The TypeScript library reads the Lei nº 9.279/1996 (Lei da
Propriedade Industrial, the LPI) corpus: every Article of Brazil's unified
industrial property statute, with the consolidated Portuguese text and the
WIPO Lex English translation, in one offline SQLite/FTS5 snapshot read through
the same verified-artifact lifecycle as the [DPMA statutes](dpma-statutes.md).
No API key is needed. The MCP adapter uses a separate `inpibr:read` scope for
HTTP access.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `InpiBrStatutesClient` | `search_inpi_br_statutes`, `get_inpi_br_section` | `inpi-br-statutes://corpus/status` | `INPI_BR_STATUTES_CORPUS_PATH` |

Tool names and parameters (`query`, `limit`, `offset`, `syntax`, `sort`,
`full` for search; `citation` as a string or a list of up to 50 for get), the
path variable and the default file name
(`~/.cache/patent_client_agents/inpi_br_statutes.db`) match the Python
connector. `INPI_BR_STATUTES_CORPUS_SHA256` pins the decoded SQLite bytes and
`INPI_BR_STATUTES_CORPUS_FILE_SHA256` the distributed file. The library adds
Python's `search`, `getSection`, `resolveSectionHref` and `listVersions`, plus
`getCorpusStatus`. Python's facade does not route the LPI, so neither does the
TypeScript facade. The INPI Brazil bulk-data connector (`inpi_br_bulk`) is a
separate module and is not part of this port.

## Sources and contents

`scripts/build-inpi-br-statutes-corpus.ts` builds the corpus in TypeScript
with plain HTTPS GETs and the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`;
there is no browser, cookie or challenge handling.

- **Portuguese (authoritative).** The consolidated text ("norma atualizada")
  of the Câmara dos Deputados legislative information service,
  `www2.camara.leg.br/legin/fed/lei/1996/lei-9279-14-maio-1996-374644-normaatualizada-pl.html`.
  Python reads planalto.gov.br, but on October 22, 2026 Planalto reset the
  connection right after the TLS handshake for every plain request from here,
  including its home page, with the project's user agent and with curl's default. The Câmara page is the same
  law, consolidated through Lei nº 14.852 of May 3, 2024 (the newest amending
  law it cites), with each amendment noted inline as the official
  consolidations do ("Redação dada pela Lei nº 14.195, de 26/8/2021").
- **English.** The WIPO Lex translation `br003en.pdf`, linked from WIPO Lex
  record 515 ("Law No. 9.279 of May 14, 1996 (Law on Industrial Property)").
  The record page links the PDF with a CloudFront signature that expires, so
  the builder reads the link from the page and the manifest records the
  unsigned URL. The translation is of the law as enacted in 1996. WIPO Lex has
  no English translation of the amended law, so for amended Articles the
  English differs from the Portuguese. Art. 40, for example, still has the
  sole paragraph the Supreme Court struck down in ADI 5.529 and Lei nº 14.195
  revoked. The Portuguese is authoritative and the tools say so.

[`scripts/inpi-br-statutes-sources.json`](../scripts/inpi-br-statutes-sources.json)
records each file's URL, retrieval time, SHA-256 and size, the law heading,
the newest amending law, the PDF's modification time and the access notes.
The raw files stay in the ignored `.data/inpi_br_statutes/raw/`.

The build has 248 rows: Articles 1 to 244 and the four lettered Articles
added later (Art. 71-A, 229-A, 229-B and 229-C; 229-C was later revoked and
its row holds the revocation note). 244 rows have English text; the lettered
Articles have none. How the sources become rows:

- An Article starts at a justified paragraph beginning `Art. N` (with `º`,
  a period or a `-A` letter suffix). Every following paragraph (`§ 1º`,
  incisos `I -`, `Parágrafo único.`, `Pena -`) is one line of `text_pt` until
  the next Article or heading. A quoted article of another law inside an
  amending provision (`"Art. 2º O INPI …"` in Art. 240) stays in its Article.
  The signature block after Art. 244 is dropped. The parser checks that the
  Articles run 1 to 244 in order with lettered Articles after their number.
- `title_section` is the Title the Article sits in, such as `TÍTULO V — DOS
  CRIMES CONTRA A PROPRIEDADE INDUSTRIAL`. Two Title labels are `<h2>`
  headings on the page; the parser reads both and checks that Titles I to
  VIII appear in order. Arts. 1 to 5 (the preliminary provisions) have none.
  Python never filled this column.
- In the English PDF an Article starts with its bold number (`195.`) at the
  paragraph indent; centred lines (headings, page numbers) are skipped and
  each indented line starts a paragraph. The PDF's italic font reports spaces
  as `f`; the four italic phrases in Article text (`ex officio`, `per se`,
  `force majeure`, `in camera`) are restored and any other such item fails the
  build. `text_en` starts `Article N.`, as Python's rows did.
- `title_pt` and `title_en` are the caput's first sentence (ended by `;`, `:`
  or a period before a capital letter, never at `art.` or `No.`), capped at
  120 characters. `html_pt` and `html_en` are one `<p>` per line.
- Meta keeps Python's keys (`schema_version` 1, `source_pt`, `source_en`,
  `snapshot_date`, `lpi_year` 1996, `section_count`) and adds
  `source_version` (`consolidated through Lei nº 14.852, de 3/5/2024`),
  `latest_amendment`, `source_en_version`, `source_en_record`, `retrieved_at`
  and the two source SHA-256s.

Spot checks on October 22, 2026: Arts. 6, 10, 40, 195, 229-C and 244 were
read against the Câmara page and the WIPO PDF.

## Schema and behavior

The schema is Python's (version 1, unchanged): `sections` with `href`,
`article_number`, `title_pt`, `title_en`, `title_section`, `text_pt`,
`text_en`, `html_pt`, `html_en`, indexed by the external-content FTS5 table
`sections_fts` over `article_number`, both titles and both texts with the
`porter unicode61` tokenizer, which folds diacritics (`concorrencia` matches
`concorrência`). The reader checks meta `schema_version` 1, the columns and
the FTS5 definition, and rejects WAL files.

`getSection` and `get_inpi_br_section` accept Python's forms (`Art. 6`,
`Art 6`, `Article 6`, `Artigo 6`, `art6`, `Art. 195 LPI`, `Art. 195 da LPI`,
`Art. 195(XI) LPI`, a Planalto URL with an `#Art6` anchor) plus ordinals
(`Art. 6º`) and lettered Articles (`Art. 229-C`, `art229-c`, `art229c`).
Slugs are Python's `art{n}`, with a lettered Article as `art229-c`. Anything
else, or an Article not in the snapshot, is `SECTION_NOT_FOUND` ("Could not
find LPI section …"), as in Python. A single missing citation fails the call;
in a list it goes to `not_found`. A list of one missing citation gets
Python's summary `LPI Article … — not found.` Sections carry `version`
(`current`; any other value raises `VERSION_UNAVAILABLE`), `result_url` (the
Article's anchor on the official Planalto page, as Python built it; not
reachable from here) and corpus provenance.

Search defaults to Python's `adj` phrase match and BM25 order. Lean hits are
Python's four fields (`article_number`, `title`, a 400-character snippet of
the Portuguese text, `href`); `full` adds `path`, `result_url` and `rank`.
Provenance `source_url` is the Câmara page the text came from;
`corpus_version` is `source_version`, or `lpi_year` for a corpus built
without it. Section text beyond a 64,000-character inline budget per call
would be delivered as a JSON artifact; the longest Article is far below it.

## Python differences

Python is being retired, so these are fixed here rather than there.

- Python's builder split the flattened page on every `Art. N` match,
  case-insensitively, keeping the first occurrence of each number. Cross
  references (`art. 6º` inside Art. 2, `arts. 230, 231`) therefore started
  Articles in the wrong place, and lettered Articles (`Art. 229-C`) were
  merged into their neighbours because the pattern had no hyphen.
- Its English split looked for `Article N`, but the WIPO PDF numbers Articles
  `N.`, so only cross references ("Article 84") matched. It also fetched the
  PDF and parsed it as HTML.
- `title_section` was never filled, and `corpus_version` was `lpi_year`
  (`1996`, the law's year, not a version).
- `sort='outline'` ordered `article_number` as text (`Art. 10` before
  `Art. 2`); Articles now sort by number.
- The citation parser rejected ordinals (`Art. 6º`) and lettered Articles.
- Python's search example `segredo industrial` matches nothing: the LPI does
  not use the phrase. The examples now use `dados confidenciais` and
  `concorrência desleal`.
- `version` was accepted and ignored; a value other than `current` now
  raises.

## Building, packaging and verification

The runtime never fetches or rebuilds the corpus. From `typescript/`:

```sh
bun run build:inpi-br-statutes --fetch   # download, rewrite the source manifest, build
bun run build:inpi-br-statutes           # or rebuild from the archived sources
bun scripts/compress-corpus.ts \
  --input .data/inpi_br_statutes/inpi_br_statutes.db \
  --output .data/inpi_br_statutes/inpi_br_statutes.db.zst
bun run verify:inpi-br-statutes --file .data/inpi_br_statutes/inpi_br_statutes.db.zst
```

A rebuild checks each archived file against the SHA-256 in the source
manifest, never overwrites its output and checks integrity; rebuilding from
the same files gives the same bytes. `--fixture` also rewrites the test
fixture.

The October 22, 2026 build (sources retrieved 16:12 UTC):

| Rows | Decoded bytes | Decoded SHA-256 | Zstandard bytes | File SHA-256 |
| --- | --- | --- | --- | --- |
| 248 | 847,872 | `9fa9c149cef1e11f0e2657591b9fe78c8445d0590d8c86882e027658d943b64c` | 171,645 | `dc34146f4ce2800db63ae3447cc58658a588cea460437be6015647e84452f4a0` |

The verifier configured the packaged file and both pins and exercised the
library and the default full MCP server. The artifacts stay under ignored
`.data/` and were not deployed.

## Tests

The fixture (`tests/fixtures/inpi-br-statutes/inpi_br_statutes.db`) is nine
real Articles (1, 6, 10, 40, 43, 125, 195, 229-C, 244) written by the builder
from the October 22 sources. [Builder tests](../tests/inpi-br-statutes-build.test.ts)
cover the page parser (Titles, paragraphs, lettered and quoted Articles,
loud failures), titles, the signed link and the manifest.
[Library tests](../tests/inpi-br-statutes-client.test.ts) cover citations and
slugs, status, sections in both languages, versions, search in both
languages, syntax, outline order, paging, FTS operator quoting, Zstandard
bytes, pins, the environment variables, WAL, schema and metadata gaps.
[MCP tests](../tests/inpi-br-statutes-mcp.test.ts) cover both tools against
Python's summaries and shapes, `not_found`, the status resource and the
`inpibr:read` scope on the authenticated HTTP listener. Node and browser smoke
runs read the fixture as bytes. All run offline.
