# KIPO Korea statutes corpus access

October 26, 2026. The TypeScript library reads a new KIPO Korea statutes
corpus: the English translations of seven Korean IP statutes in one offline
SQLite/FTS5 snapshot, read through the same verified-artifact lifecycle as the
[ILPO Israel statutes](ilpo-statutes.md). Python had no Korean statute corpus,
so there is nothing to compare against. No API key is needed. The MCP adapter
reuses the `kipo:read` scope of the [KIPRIS](kipris.md) connector for HTTP
access.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `KipoStatutesClient` | `search_kipo_statutes`, `get_kipo_section` | `kipo-statutes://corpus/status` | `KIPO_STATUTES_CORPUS_PATH` |

The tools take the parameters the other statute tools take (`query`,
`statute`, `syntax`, `sort`, `per_page`, `page` for search; `citation` as a
string or a list of up to 50 for get). The default file is
`~/.cache/patent_client_agents/kipo_statutes.db`;
`KIPO_STATUTES_CORPUS_SHA256` pins the decoded SQLite bytes and
`KIPO_STATUTES_CORPUS_FILE_SHA256` the distributed file. The corpus id for
[bootstrap](corpus-bootstrap.md) and `scripts/publish-corpora.ts` is
`kipo_statutes`. There is no curated facade route.

**The Korean text controls.** These are the Korea Legislation Research
Institute's (KLRI) translations. KLRI provides them for reference: they have
no legal authority or official effect and may not reflect the most recent
amendments. The status resource carries this as `authority_note`, and both
tool descriptions say so.

## Source and contents

KLRI publishes its translations at
[elaw.klri.re.kr](https://elaw.klri.re.kr/eng_service/main.do), and the
government's law.go.kr English service shows the same translations. For each
statute, `scripts/build-kipo-statutes-corpus.ts --fetch` looks the act up by
its English name in elaw's statute-title list, takes the row whose English
name matches exactly (elaw lists the current translation only, with its
Korean name), and downloads the full text from `lawViewContent.do`. The
title search is the site's own form, a form-encoded POST to
`lawNameList.do`; the translation itself is a plain HTTPS GET. Both use the
user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`;
no browser, cookie or challenge handling. Nothing blocked the requests.

law.go.kr was tried first and dropped. Its English list answers plain GETs,
but a translation's body (`engLsInfoR.do`) answers only the form POST the
page itself sends, and GETs of the same URL hang. Large bodies take minutes:
the Design Protection Act took 163 seconds, and the Copyright Act never
loaded: on every try the server closed the connection at 180 seconds. law.go.kr
also had older translations of two statutes than elaw (Design Protection Act
Act No. 19494 of June 20, 2023 and Trademark Act Act No. 19809 of October 31,
2023). WIPO Lex was not needed.

| Key | Statute | Korean | elaw hseq | Rows | Deleted | Branch | Translation reflects |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `patent` | Patent Act | 특허법 | [68595](https://elaw.klri.re.kr/eng_service/lawView.do?hseq=68595&lang=ENG) | 297 | 30 | 65 | Act No. 20322, February 20, 2024 |
| `utility_model` | Utility Model Act | 실용신안법 | [71512](https://elaw.klri.re.kr/eng_service/lawView.do?hseq=71512&lang=ENG) | 65 | 4 | 13 | Act No. 21065, October 1, 2025 |
| `design` | Design Protection Act | 디자인보호법 | [68475](https://elaw.klri.re.kr/eng_service/lawView.do?hseq=68475&lang=ENG) | 237 | 1 | 8 | Act No. 20200, February 6, 2024 |
| `trademark` | Trademark Act | 상표법 | [68477](https://elaw.klri.re.kr/eng_service/lawView.do?hseq=68477&lang=ENG) | 246 | 2 | 9 | Act No. 20200, February 6, 2024 |
| `unfair_competition` | Unfair Competition Prevention and Trade Secret Protection Act | 부정경쟁방지 및 영업비밀보호에 관한 법률 | [71518](https://elaw.klri.re.kr/eng_service/lawView.do?hseq=71518&lang=ENG) | 47 | 1 | 27 | Act No. 21065, October 1, 2025 |
| `invention_promotion` | Invention Promotion Act | 발명진흥법 | [71705](https://elaw.klri.re.kr/eng_service/lawView.do?hseq=71705&lang=ENG) | 114 | 18 | 54 | Act No. 21065, October 1, 2025 |
| `copyright` | Copyright Act | 저작권법 | [74342](https://elaw.klri.re.kr/eng_service/lawView.do?hseq=74342&lang=ENG) | 196 | 2 | 54 | Act No. 21336, February 10, 2026 |

That is 1,202 rows: every numbered article of each statute, including deleted
articles (`Article 26 Patent Act` is `Deleted. <Dec. 2, 2011>`) and branch
articles (`Article 7-2 Patent Act`, `Article 35-5 Copyright Act`). Each
statute's row count is its highest article number plus its branch articles,
so no number is missing. The version column is elaw's own line for the latest
amendment translated, the Act number and its promulgation date; elaw does not
state an enforcement date (law.go.kr's copies give, for example, August 21,
2024 for the Patent Act). The three October 1, 2025 entries are amendments by
another Act (law.go.kr labels Act No. 21065 that way); their text renames
KIPO's minister, for example `Minister of Intellectual Property` in Invention
Promotion Act Article 10(4). Whether a later Korean amendment exists that KLRI
has not translated cannot be told from the translation; check the Korean text
on law.go.kr before relying on an article as current.

The translations were retrieved on October 26, 2026 between 23:05:02 and
23:05:21 UTC.
[`scripts/kipo-statutes-sources.json`](../scripts/kipo-statutes-sources.json)
records, per statute, the English and Korean titles, the version line, Act
number and promulgation date, elaw's hseq, page and content URLs, retrieval
time, SHA-256, size, and the row, deleted and branch counts.

How the HTML becomes rows. elaw prints each article as a `div.JO` after an
anchor whose id encodes the number (`JO0029020` is Article 29-2), with a
heading cell and one block per paragraph, subparagraph or item:

- The heading `Article 2 (Definitions)` gives the number and the title. A
  deleted article's heading is the whole article (`Article 26 Deleted. <Dec.
  2, 2011>`); its title is null and its text is `Deleted. <…>`.
- Each block becomes one line of `text`, with its marker cell and text joined
  (`(1) …`, `1. …`, `(a) …`). Amendment notes stay where the translation
  prints them: inline `<Amended on …>` and closing lines such as `[This
  Article Wholly Amended on Jun. 11, 2014]`.
- The anchor's number must match the heading's and each number appears once;
  otherwise the build stops.
- Chapter, section and subsection headings, the amendment history list and
  every addendum (supplementary provisions, `ADDENDA <Act No. …>`) are not
  stored. Addenda carry their own `Article 1`, `Article 2` and so on, which
  would collide with the main articles.
- `source_url` on each row is the statute's elaw page. Meta adds
  `retrieved_at`, `authority_note` and `statutes`, a JSON array with each
  statute's titles, version, hseq, URLs, retrieval time and hash.
  `snapshot_date` is the retrieval date, so rebuilding from the same HTML
  gives the same bytes.

Two source defects are handled and recorded in the manifest. elaw splits the
one sentence of Design Protection Act Article 76 into a second block whose
heading reads `Article 135 (excluding subparagraph 6 thereof) shall apply
mutatis mutandis …`; law.go.kr prints that sentence as Article 76's text. A
block whose heading is not an article heading is joined to the article before
it (`continuations: ["76"]`), so there is no false second Article 135. elaw
also prints Design Protection Act Article 141-2 after Article 142
(`out_of_order: ["141-2"]`); the row keeps the source's number and
`sort='outline'` places it after 141.

Spot checks on October 26, 2026, read against the elaw pages: Patent Act
Articles 1, 2, 7-2, 26, 29, 30 and 94; Design Protection Act Articles 33, 76
and 141-2; Trademark Act Articles 33 and 34; Unfair Competition Prevention and
Trade Secret Protection Act Articles 2, 9-8 and 10; Invention Promotion Act
Article 10; Copyright Act Articles 2 and 35-5. Two automatic comparisons
covered the rest:

- Word coverage. Counted word by word per block, the rows hold every word of
  every article block on each page, with nothing extra. Article text is 76 to
  95 percent of each page's words; the rest is the amendment history list,
  chapter and section headings and the addenda.
- law.go.kr. For the four statutes law.go.kr holds at the same amendment
  (Patent, Utility Model, Unfair Competition Prevention and Invention
  Promotion Acts), its copy was parsed separately and compared article by
  article after normalizing quotation marks and spaces. All 523 articles are
  present in both, and all but one match exactly: Patent Act Article 61 reads
  "in preference to separate patent applications" on elaw and "other patent
  applications" on law.go.kr, a later wording revision.

## Schema and behavior

Each row of `sections` is one article (`statute`, `section_number`,
`section_label`, `title`, `text`, `source_url`), the statute schema version 1
the ILPO and DPMA corpora use, with the external-content FTS5 table
`sections_fts` over `statute`, `section_label`, `title` and `text` and the
`porter unicode61` tokenizer. `section_number` is `29` or `29-2`;
`section_label` is `Article 29-2 Patent Act`. The reader checks meta
`schema_version` 1, the columns and the FTS5 definition, and rejects WAL
files, as the shared `openCorpusSnapshot` does for every corpus.

Statute names resolve case-insensitively through an alias table: the keys,
the English names (`Patent Act`, `Design Protection Act`), short forms
(`trademarks`, `TM`, `utility model`), `trade secret` / `trade secrets` and
`UCPA` for the Unfair Competition Prevention and Trade Secret Protection Act,
and the Korean names (`특허법`, `상표법`, `부정경쟁방지법`). Unknown names pass
through lowercased and find nothing. `get_kipo_section` parses `Article 29
Patent Act`, `Patent Act Art. 29(1)`, `Article 29-2 of the Patent Act`,
`Art. 2(1) 3 Trademark Act`, `Copyright Act Article 35-5`, `§ 94 Patent Act`
and `특허법 제29조`. Paragraph, subparagraph and item markers are dropped and
the whole article is returned. A citation that cannot be parsed or is not in
the corpus returns null from the library and goes to `not_found` in the tool
(a single miss gives an empty list and the summary `KIPO Korea article '…' —
not found.`), never an error.

Search defaults to all-terms matching and BM25 order and returns statute,
number, label, title, a `<mark>` snippet and rank. Every term is quoted, so
FTS5 operators in a query are plain words. `sort='outline'` orders by the
corpus statute order, then article number, then branch (`29`, `29-2`,
`29-10`, `30`), with no rank. Status reports `corpus_version` as the build's
`source_version` (`KLRI English translations (elaw.klri.re.kr), 2026-10-26`),
`corpus_synced_at` as the snapshot date at UTC midnight, the authority note,
and each statute's version, Act number, promulgation date, URLs and hash.

## Building, packaging and verification

The runtime never fetches or rebuilds the corpus. From `typescript/`:

```sh
bun run build:kipo-statutes --fetch     # download the translations, rewrite the source manifest, build
bun run build:kipo-statutes             # or rebuild from the archived HTML
bun scripts/compress-corpus.ts \
  --input .data/kipo_statutes/kipo_statutes.db \
  --output .data/kipo_statutes/kipo_statutes.db.zst
bun run verify:kipo-statutes --file .data/kipo_statutes/kipo_statutes.db.zst
```

The raw HTML goes to the ignored `.data/kipo_statutes/raw/` (one file per
statute key); a rebuild checks each against the SHA-256 and row count in the
committed source manifest and stops on a mismatch. The builder writes a
standalone DELETE-journal database, never overwrites its output, and checks
integrity. `--fixture` also rewrites the test fixture. The builder parses
HTML with linkedom, now also a root development dependency so scripts can
import it.

The October 26, 2026 build:

| Rows | Decoded bytes | Decoded SHA-256 | Zstandard bytes | File SHA-256 |
| --- | --- | --- | --- | --- |
| 1,202 | 2,465,792 | `1120eb30acff0fc325829b56ce5348742c4c8488958ec0976701c04e02ca2082` | 603,453 | `cdb7aa9dfae2397e068a8b4e4f61d7d11fbbcd1c63d9a1eeddfb79830d180299` |

A second build from the archived HTML reproduced the decoded bytes exactly.
The verifier configured the packaged file and both pins, checked each
statute's row count, hash and version against the source manifest, checked
eight article headings and that the nonexistent `Article 29-2 Patent Act`
does not resolve, and exercised the library and the default full MCP server.
The artifacts stay under ignored `.data/` and were not published or deployed.

## Tests

The [fixture](../tests/fixtures/kipo-statutes/README.md) is 14 real articles
written by the builder from the October 26 HTML. [Builder
tests](../tests/kipo-statutes-build.test.ts) cover article blocks, headings,
deleted and branch articles, marker cells, inline links and italics, the
excluded chapters and addenda, the Article 76 continuation, out-of-order
numbers, anchor and duplicate checks, the version line, the statute-title
list and the source manifest. [Library tests](../tests/kipo-statutes-client.test.ts)
cover aliases including Korean names, citation parsing, status with the
authority note and per-statute versions, articles and missing ones, search
filters, paging, outline order with branch articles, FTS operator quoting, a
missing corpus, Zstandard bytes and pins. [MCP tests](../tests/kipo-statutes-mcp.test.ts)
cover both tools' parameters, summaries and shapes, `not_found`, the status
resource, the curated toolset and the `kipo:read` scope on the authenticated
HTTP listener. Node and browser smoke runs read the fixture as bytes. All run
offline.
