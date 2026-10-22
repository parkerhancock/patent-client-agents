# IPO India statutes and MPPP

October 22, 2026. The TypeScript library reads two Indian Patent Office
corpora: the IP statutes (Patents Act 1970, Patents Rules 2003, Designs Act
2000, Trade Marks Act 1999, Copyright Act 1957) and the Manual of Patent
Office Practice and Procedure (MPPP v3.0, 2019). Both are offline SQLite/FTS5
snapshots read through the same verified-artifact lifecycle as
[MPEP](mpep.md) and the [UPC statutes](upc-statutes.md), and both are built
from the official texts by `scripts/build-ipo-in-corpora.ts`. No API key is
needed. The MCP adapter uses a separate `ipoin:read` scope for HTTP access.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `IpoInStatutesClient` | `search_ipo_in_statutes`, `get_ipo_in_section` | `ipo-in-statutes://corpus/status` | `IPO_IN_STATUTES_CORPUS_PATH` |
| `IpoInMpppClient` | `search_ipo_in_mppp`, `get_ipo_in_mppp_section` | `ipo-in-mppp://corpus/status` | `IPO_IN_MPPP_CORPUS_PATH` |

Tool names and parameters (`query`, `statute`, `limit`, `offset`, `syntax`,
`sort`, `full` for search; `citation` as a string or list for get), the path
variables and the default file names
(`~/.cache/patent_client_agents/ipo_in_statutes.db`, `ipo_in_mppp.db`) match
Python, and so does the SQLite schema (version 1), so Python's readers can
open these files too. `<PREFIX>_CORPUS_SHA256` pins the decoded SQLite bytes
and `<PREFIX>_CORPUS_FILE_SHA256` the distributed file.

The curated facade routes `search_legal_reference` / `get_legal_reference`
with `corpus='india_statutes'` and `'india_mppp'` to the same functions, so
results keep the India hit shape (`statute_name`, `section_number`, `title`,
`snippet`; MPPP adds `chapter`) and summaries. The `statute` filter applies
to `india_statutes` only.

## Sources and versions

Every source file is listed with its URL, retrieval time, byte count and
SHA-256 in [`references/ipo-in/sources.json`](../references/ipo-in/sources.json).
All were fetched on October 22, 2026 with plain GETs and the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`.

| Text | Source | Version it reflects | Rows |
| --- | --- | --- | --- |
| Patents Act, 1970 | ipindia.gov.in PDF, "The Patents Act, 1970 (incorporating all amendments till 01-08-2024)" (665,996 bytes, SHA-256 `d5708488…6e0678`) | Consolidated through the Jan Vishwas (Amendment of Provisions) Act, 2023, in force 01-08-2024 | 175 sections |
| Patents Rules, 2003 | ipindia.gov.in e-Version, one HTML page per rule (148 pages plus the index), which states it "is updated till 01-08-2024"; Chapter XIV-A from the Patents (Amendment) Rules, 2025, G.S.R. 865(E), Gazette of India Extraordinary No. 779, 25 November 2025 (ipindia PDF, 1,458,903 bytes, `25d1dc09…7a34a71`) | The e-Version for rules 1–139, with rules 107A–107G as substituted in full by the 2025 Rules. The e-Version itself lacks Chapter XIV-A | 155 rules |
| Designs Act, 2000 | ipindia.gov.in e-Version, one HTML page per section (48 pages plus the index) | The page states no amendment date and ipindia lists no amending Act | 48 sections |
| Trade Marks Act, 1999 | WIPO Lex entry 22958, "amended up to Act No. 18 of 2023" (India Code typesetting; 494,939 bytes, `e1283596…1cd4071f`) | Consolidated through the Jan Vishwas Act, 2023 (w.e.f. 1-8-2024) | 169 sections |
| Copyright Act, 1957 | WIPO Lex entry 22949, "amended up to Act No. 18 of 2023" (534,087 bytes, `05f47cc9…3f843c4a`) | Consolidated through the Jan Vishwas Act, 2023 (w.e.f. 1-8-2024) | 105 sections |
| MPPP | ipindia.gov.in PDF, "Manual of Patent Office Practice and Procedure, Version 3.0, 26th November, 2019" (1,658,264 bytes, `73d52f8b…fbb311`) | Version 3.0 of 26 November 2019, the manual in force. ipindia also lists a draft revision for comment (August 2026), which is not adopted and not used | 260 rows |

Why these sources:

- India Code (`www.indiacode.nic.in`) answered HTTP 403 "Access Denied"
  (Akamai) to plain requests for a handle page, its root and a bitstream PDF,
  and `www.legislative.gov.in` answered 403 too. No other access method was
  tried.
- ipindia.gov.in has a consolidated Patents Act PDF and e-Versions of the
  Patents Rules and Designs Act, but for the Trade Marks Act only the 1999
  Gazette text and the 2010 amending Act, and no dated consolidation of the
  Copyright Act. WIPO Lex republishes the India Code consolidations of the Trade
  Marks and Copyright Acts (amended up to Act 18 of 2023), so those come from
  WIPO Lex. Its PDF links are short-lived signed URLs, which the builder reads
  from the entry page; the manifest records the unsigned path.
- The ipindia Patents Act e-Version (HTML) was not used: it lacks sections
  124A and 124B and still shows section 121, all changed by the Jan Vishwas
  Act with effect from 01-08-2024. The PDF has them.
- The Patents Rules e-Version was checked against ipindia's consolidated PDF
  "incorporating all amendments till 21-09-2021": every rule in that PDF is
  in the e-Version, which adds the later rules (29A, 70A and others). Its
  rule 131 reads "once in respect of every period of three financial years",
  the March 2024 amendment.

The statutes snapshot has no single `source_version`; the status `metadata`
carries one `source_<act>` entry per text with the title and version above,
and `corpus_version` is `snapshot-2026-10-22` (the retrieval date). The
MPPP's `source_version` is `v3.0 (2019-11-26)`.

## How the text is extracted

PDF text comes from `pdfjs-dist` 4.10.38, a pinned dev dependency, which
reports each glyph run's font size and position. That makes the cleanup
deterministic rather than heuristic over plain text:

- India Code-style PDFs (Patents, Trade Marks, Copyright Acts). Superscript
  amendment markers (7 pt) are dropped, so "⁶[(d) the mere discovery…"
  reads "[(d) the mere discovery…"; the brackets and `* * *` omission marks
  of the official text stay. Page-foot amendment footnotes ("1. Subs. by Act
  38 of 2002, s. 4…", 8–9 pt) are dropped as the trailing run of small lines
  on each page, and running page numbers too. Chapter headings are dropped.
  Parsing starts at "BE it enacted", and the parsed section numbers must
  equal the Act's own arrangement of sections exactly or the build fails.
  Omitted sections keep their official one-line entry ("5. [Inventions where
  only methods or processes of manufacture patentable.] Omitted by the
  Patents (Amendment) Act, 2005 …").
- ipindia e-Version pages (Rules, Designs Act). The rule or section body
  becomes one line per paragraph; titles come from the index. The two
  omitted ranges listed only as "Rule 39-54" and "Rule 64-65" are not rows.
  Schedules and forms of the Rules are not included.
- MPPP. Numbered headings at the left margin (`09.03.05.04`) open a row;
  a chapter's text before its first numbered heading is the chapter row
  (`09`). The statutory references printed in the right margin ("Section 13",
  "Rule 24B, 24C") are kept off the paragraph text and appended as a last
  line, `[Marginal references: …]`. Bullets set in a symbol font and the
  manual's mis-mapped curly quotes (―, ‖, ‗) are normalized. Where a heading
  is the start of a sentence (09.03.05.x), the title is the heading line and
  the text repeats the whole sentence. A heading with no text of its own
  (07.02, 09.03) has the heading line as its text.
- The manual numbers two paragraphs 14.02.01.04; the second ("Terms and
  Conditions") is kept inside the first, with its heading as a line of
  text. The heading printed as `02.0218` is stored as 02.02.18.

Checks in the builder: per-Act required provisions and counts, no footnote
wording in any non-omitted section, MPPP titles for 04.01, 07.02, 09.03 and
09.03.05.04, and the arrangement comparison above. Comparing 8-word windows
of the stored text with `pdftotext` output of the same PDFs, about 1% or fewer
of windows differ for the Acts, all at page breaks where `pdftotext` keeps
the footnotes.

## Building

From `typescript/`:

```sh
bun run fetch:ipo-in           # download and archive the sources, rewrite the manifest, build
bun run build:ipo-in           # rebuild from the archive in .data/ipo-in/sources/
bun run build:ipo-in --fixtures   # also rewrite tests/fixtures/ipo-in/
for name in ipo_in_statutes ipo_in_mppp; do
  bun scripts/compress-corpus.ts \
    --input .data/ipo-in/build/$name.db --output .data/ipo-in/$name.db.zst
done
bun run verify:ipo-in \
  --statutes .data/ipo-in/ipo_in_statutes.db.zst \
  --mppp .data/ipo-in/ipo_in_mppp.db.zst
```

The raw sources (gzipped, about 9 MB with the HTML pages) and the built
databases stay under the ignored `.data/ipo-in/`. The builder writes DELETE
journal mode directly, so no preparation step is needed, and the build is
byte-reproducible from the archive (`snapshot_date` is the retrieval date).
`--fetch` first checks that each ipindia listing page still names the
document and version it expects, and that the Rules e-Version still says
"updated till 01-08-2024"; a changed listing stops the refresh for review.

| Corpus | Rows | Decoded bytes | Zstandard bytes | Decoded SHA-256 | File SHA-256 |
| --- | --- | --- | --- | --- | --- |
| Statutes | 652 | 1,404,928 | 388,487 | `82bfaea2cabe9dda467590bed2af231edafaf683308f69f09015ee72b5314671` | `96aeed06437c05bdaef4f943c7b1b81599dd6f315ee433d158fe151a8bf9f55f` |
| MPPP | 260 | 688,128 | 199,121 | `b2e440776a7b45048ec20b37b5054d327cde309978cb87a4c2899911bc9f6b5b` | `00905acf0d481c4323fd8cd6ebb47915a49b7c55c515749c7b5a426770affe7d` |

The verifier checks the pins, compares every stored row (text hash, title,
source URL) with a fresh parse of the archived sources, spot-checks Patents
Act ss. 3(d), 25 and 107A, Rule 13, Trade Marks Act s. 9 and MPPP 09.03 and
07.02 against wording in the source documents, and calls the full and
curated servers. The artifacts were not deployed.

Python's seeds (`src/patent_client_agents/ipo_in_statutes/data/seed.jsonl`,
26 rows; `ipo_in_mppp/data/seed.jsonl`, 12 rows) are no longer used. The
MPPP seed did not match the manual (it labelled 07.02 as Form 27; the
manual's 07.02 is International Application under PCT and examination is
Chapter 09), and its texts were paraphrase.

## Citations and source links

Rows store whole sections and rules. A citation of a sub-section or clause
(`Section 3(d) Patents Act`, `Section 25(2)`) returns the enclosing section
(3, 25) with `subdivision` set to the cited part (`(d)`, `(2)`), and the get
summary says the cited part is within the section text. Each row's
`source_url` points at its source: the PDF with a `#page=` fragment for the
Patents Act and the MPPP, the WIPO Lex entry page with `#page=` for the
Trade Marks and Copyright Acts, the e-Version page for each rule or Designs
Act section, and the 2025 Gazette PDF for rules 107A–107G. This replaces the
seed's links, which gave the Designs and Trade Marks Acts the same India
Code handle and pointed two rows at ipindia pages that return 404.

"Section"/"§"/"S." citations without an Act never match a Patents Rule, so
`§107A` is Patents Act s. 107A although rule 107A also exists; a bare
`107A` without an Act is ambiguous and fails, as Python's would.

## Behavior and Python bugs fixed

Search matches Python: BM25 rank, the same `<mark>` snippets (40 tokens),
`limit + 1` paging and the same lean projection (snippets cut at 400
characters). Ties in rank fall back to row order. Python behavior the port
corrects:

1. FTS5 operators ran from caller text. Python quoted only tokens with
   punctuation, so `infringement OR zzz` returned hits and a bare `NOT`
   raised an FTS5 syntax error. Every term is now quoted text; `syntax='or'`
   is the way to widen.
2. Outline sort was lexicographic (`107A`, `122`, `146`, `2`, `25`, …). It
   is now natural section order within each Act (`2`, `3`, `11A`, `25`,
   `107A`, …), applied before paging.
3. Citation parsing rejected or mis-resolved common forms: `§107A` raised
   "could not parse" (the tool description advertises it);
   `Section 25(2) of the Patents Act, 1970` looked up an Act named
   "Patents Act, 1970"; `Section 3(d) of Patents Act` looked up "of Patents
   Act"; `Patents Act section 3` failed. All now resolve. Statute names ignore
   case, punctuation, a leading "the" and a trailing year, and accept singular
   spellings ("Patent Act", "Trade Mark Act").
4. Section numbers were case-sensitive (`107a` was not found). They now match
   case-insensitively, and spaces inside `3 (d)` are ignored.
5. A `Rule N` citation without an Act searched every Act, so `Rule 13`
   returned Copyright Act section 13. It now means the Patents Rules.
6. MPPP references had to use the stored two-digit form; `MPPP 9.3.5.4` was
   not found. Unpadded components now match.

An ambiguous bare number (`Section 2`, in all four Acts) or an unparseable
citation fails the whole call, as Python's `ValueError` does, including
inside a list; missing sections in a list go to `not_found`, and a single
missing string is an error. Section texts beyond a 32,000-character inline
budget would be delivered as text artifacts, as the other corpus tools do;
the longest row (Copyright Act s. 52, about 13,400 characters) stays inline.

The facade's `syntax` parameter has no schema default. The Python facade
forwarded its own `'adj'` default to `india_statutes` although its
description says statute corpora default to all-terms matching; the port
applies `'and'` for `india_statutes` and `'adj'` for every other corpus when
the caller gives none.

## Tests

The fixtures in `tests/fixtures/ipo-in/` are subsets of the real builds
(37 statute rows across all five texts, 14 MPPP rows), written by
`build:ipo-in --fixtures`. [Library tests](../tests/ipo-in-client.test.ts)
cover citation and reference parsing, status and source metadata, search
with and without the statute filter, natural outline paging, clause
citations, the 2025 Chapter XIV-A rules, footnote-free section text, MPPP
marginal references, FTS operator quoting, Zstandard bytes, missing, WAL,
schema and pin failures, metadata gaps and the environment variables.
[MCP tests](../tests/ipo-in-mcp.test.ts) cover the four tools, `not_found`,
the status resources, the curated facade routing (including the per-corpus
syntax default) and the `ipoin:read` scope on the authenticated HTTP
listener. All run offline. The Node smoke run reads the statutes fixture as
Zstandard bytes and the browser smoke run the MPPP fixture as bytes.
`scripts/live-facade.ts` has four India probes, which need the two path
variables set.
