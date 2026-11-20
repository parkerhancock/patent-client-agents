# CNIPA China statutes corpus access

October 26, 2026. New in the TypeScript port; the Python package never had a
China statutes corpus. The TypeScript library reads English translations of
six Chinese IP laws and regulations in one offline SQLite/FTS5 snapshot,
through the same verified-artifact lifecycle as the
[ILPO Israel statutes](ilpo-statutes.md). No API key is needed. The MCP
adapter uses a separate `cnipa:read` scope for HTTP access.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `CnipaStatutesClient` | `search_cnipa_statutes`, `get_cnipa_section` | `cnipa-statutes://corpus/status` | `CNIPA_STATUTES_CORPUS_PATH` |

**The Chinese text controls.** These are the English translations WIPO Lex
holds, published for reference (the Trademark Law PDF prints "The English
text is for reference only"). The status resource, `getCorpusStatus()` and
the corpus meta carry the notice `English translations for reference only;
the Chinese text controls.`, and each statute's entry links the Chinese PDF
on the same WIPO Lex page (`zh_pdf_url`). Two translations are older than the
Chinese text WIPO lists and a third predates a 2025 revision, with different
numbering; see the version column
below before relying on an Article or Rule number as current law.

Tool parameters follow the other statute corpora (`query`, `statute`,
`per_page`, `page`, `syntax`, `sort` for search; `citation` as a string or a
list of up to 50 for get), as do the default file name
(`~/.cache/patent_client_agents/cnipa_statutes.db`) and the row schema.
`CNIPA_STATUTES_CORPUS_SHA256` pins the decoded SQLite bytes and
`CNIPA_STATUTES_CORPUS_FILE_SHA256` the distributed file. The curated toolset
has no route for this corpus. The tool prefix is the office abbreviation
(§5.7 of the connector standards).

Scope. The China SPC IP Court connector registers its tools under
`spc:read`, a scope named after the court whose records it reads. These
statutes are legislation, not court records, and the office-scoped readers
of statutes elsewhere in the port use the office's own scope (`ilpo:read`,
`ipoin:read`). So this corpus gets `cnipa:read`: an operator can grant the
statutes without the court tools, or the reverse, and a later CNIPA register
or guidelines connector can share the scope. The listener test checks that a
`spc:read` token does not see these tools.

## Source and contents

For each statute, `scripts/build-cnipa-statutes-corpus.ts` fetches the WIPO
Lex legislation page, reads the named English PDF link with the shared WIPO
Lex page parser (`parseWipoLexLegislation`), and follows that link once. The
pages also link WTO-notification copies (`…en-wto.pdf`), Spanish and French
texts; the builder names the file it wants rather than taking the first
English link. WIPO signs PDF links for a few minutes, so the manifest keeps
the unsigned URL. Plain HTTPS GETs with the user agent
`patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)`;
no browser, cookie or challenge handling. Nothing blocked the requests.

| Key | Statute | WIPO Lex | PDF | Rows | What the English text is |
| --- | --- | --- | --- | --- | --- |
| `patent_law` | Patent Law | [21027](https://www.wipo.int/wipolex/en/legislation/details/21027) | `cn411en_1.pdf` | 82 Articles | As amended October 17, 2020 (fourth amendment, in force June 1, 2021); current |
| `patent_regulations` | Implementing Regulations of the Patent Law | [13395](https://www.wipo.int/wipolex/en/legislation/details/13395) | `cn078en.pdf` | 123 Rules | As amended January 9, 2010 (in force February 1, 2010). **Not current**: WIPO's entry is the December 11, 2023 revision (in force January 20, 2024), Chinese only, which numbers 149 Articles |
| `trademark_law` | Trademark Law | [23875](https://www.wipo.int/wipolex/en/legislation/details/23875) | `cn410en_1.pdf` | 73 Articles | As amended April 23, 2019. **Superseded January 1, 2027**: WIPO's entry is the June 26, 2026 revision (87 Articles, in force January 1, 2027), Chinese only |
| `trademark_regulations` | Regulations for the Implementation of the Trademark Law | [15011](https://www.wipo.int/wipolex/en/legislation/details/15011) | `cn342en_1.pdf` | 98 Articles | As revised April 29, 2014 (in force May 1, 2014) |
| `anti_unfair_competition` | Anti-Unfair Competition Law | [19557](https://www.wipo.int/wipolex/en/legislation/details/19557) | `cn409en.pdf` | 33 Articles | As amended April 23, 2019, the latest version WIPO Lex lists. **Not current**: the law was revised again on June 27, 2025 (in force October 15, 2025, with more Articles); WIPO Lex had no entry for that revision on October 26, 2026, so it is not reflected and Article numbers may differ |
| `copyright_law` | Copyright Law | [21065](https://www.wipo.int/wipolex/en/legislation/details/21065) | `cn413en_1.pdf` | 67 Articles | As amended November 11, 2020 (third amendment, in force June 1, 2021); current |

That is 476 rows: every numbered Article or Rule of each translation. The
version column is the builder's `translation_version` for each source, read
from the PDF's own promulgation note and WIPO's entry; it is stored in the
source manifest and corpus meta and reported per statute by the status
resource and `listStatutes()`, next to WIPO's own description (`version`).
WIPO's description of entries 23875 and 13395 is of the newer Chinese texts,
so it must not be read as the translation's date.

I looked for cleaner official English on CNIPA's site
(english.cnipa.gov.cn). Its law pages redirect to the home page for plain
requests and no 2023 Implementing Regulations or 2026 Trademark Law
translation was reachable there, so WIPO Lex is the only source. Unofficial
commercial translations of the 2023 Regulations exist and were not used.

The PDFs were retrieved on October 26, 2026;
[`scripts/cnipa-statutes-sources.json`](../scripts/cnipa-statutes-sources.json)
records each WIPO Lex page, WIPO's title and description, the translation
version, the English PDF URL and WIPO's last-modified stamp for it, the
Chinese PDF URL, retrieval time, SHA-256, size, page count and row count.

How the PDFs become rows. Unlike the Israeli gazette layout, these PDFs
print each provision as `Article N` (`Article N.` in the Patent Law,
`Rule N` on its own line in the Regulations) at the start of a paragraph,
with centered chapter and section headings and no per-article headings. The
builder reads positioned text items (`pdfPageItems`, joined into lines by the
ILPO builder's `pageLines`):

- A provision starts at a line beginning with its unit and the next number
  in sequence, followed by nothing, a capital or a parenthesis. Cross
  references that wrap to a line start (`Article 13 of this Law`,
  `Rule 28 of these Implementing Rules`) fail one of those tests. Every
  statute must yield exactly its configured count or the build stops.
- `title` is the chapter, and the section where there is one, that the
  provision sits in (`Chapter II Copyright, Section 4 Limitations on
  Rights`), as printed; the translations have no article headings and none
  are invented. Chapter numerals are kept as printed (Roman, or Arabic in the
  Regulations), except two Cyrillic look-alikes in the Patent Law PDF
  (`Chapter П`, `Chapter Ш`) read as II and III.
- `text` holds one line per paragraph or numbered item. Paragraphs are
  rebuilt from indentation (Patent Law, Trademark Law and Regulations) or
  from line spacing (Patent Implementing Regulations, Anti-Unfair Competition
  Law, Copyright Law). Line-end hyphens in compounds stay
  (`invention-creation`).
- Page numbers, the "for reference only" footer, titles, promulgation notes,
  tables of contents and the Patent Law PDF's opening 2020 amending Decision
  (pages 1 to 7) are not stored.
- The 2010 Regulations translation annotates many Rules with their 2001
  numbering (`Rule 6 (Incorporating original Rule 7)`, `Rule 8 (Newly
  added)`). These close the text as `[Note: Incorporating original Rule 7]`.
- `source_url` on each row is the statute's WIPO Lex page.
  `snapshot_date` is the retrieval date, so rebuilding from the same PDFs
  gives the same bytes.

Source defects kept as printed. The Regulations PDF heads Rule 26 `Article
26 (Newly added)`; the builder accepts that one misprint by configuration.
Its Rule 51 first paragraph breaks off mid-sentence (`…the applicant for a`)
in the PDF itself. That translation also has typographical slips (`Article
l8`, `the the applicant`). The Anti-Unfair Competition Law PDF uses a
full-width comma in Article 31.

Spot checks on October 26, 2026, read against the PDFs: Patent Law Articles
1, 2, 22, 26 and 82; Regulations Rules 6, 20, 26, 51 and 123; Trademark Law
Articles 13, 57 and 73; Trademark Regulations Article 3; Anti-Unfair
Competition Law Articles 9, 31 and 32; Copyright Law Articles 3, 24 and 67.
Mechanically, every stored paragraph of all 476 rows (renumbering notes
aside) was found verbatim in `pdftotext` output once whitespace, page
numbers and the footer were removed, except three where `pdftotext` is the
one that differs: Patent Law Articles 8 and 9, where it drops the hyphen in
`invention-creation` at a line end, and Anti-Unfair Competition Law Article
31, where it reads the line out of order. Compared word by word with
`pdftotext`, the rows' text holds all but 1.8 to 6.2 percent of each PDF's
words (the Patent Law measured from page 7, after the Decision); the
difference is the Article and Rule numbers (in `section_label`), chapter
headings (in `title`), titles, promulgation notes and tables of contents.

## Schema and behavior

Each row of `sections` is one provision (`statute`, `section_number`,
`section_label`, `title`, `text`, `source_url`), the statute schema (version
1) the ILPO corpus uses, with the external-content FTS5 table
`sections_fts` over `statute`, `section_label`, `title` and `text` and the
`porter unicode61` tokenizer. The reader checks meta `schema_version` 1, the
columns and the FTS5 definition, and rejects WAL files, as the shared
`openCorpusSnapshot` does for every corpus. Labels read `Article 22 Patent
Law`, `Rule 20 Patent Implementing Regulations`, `Article 9 Anti-Unfair
Competition Law`.

Statute names resolve case-insensitively through an alias table (`Patent
Law`, `Implementing Regulations`, `TM`, `Trademark Implementing
Regulations`, `AUCL`, `Law Against Unfair Competition`, and `trade secret` /
`trade secrets` for the Anti-Unfair Competition Law), ignoring "of the
People's Republic of China", a `PRC` / `China` / `Chinese` prefix and a
trailing year. `Implementing Regulations` alone means the patent regulations.
`get_cnipa_section` parses `Article 22 Patent Law`, `Patent Law Art. 22(3)`,
`Article 22 of the Patent Law of the People's Republic of China`, `Art. 22,
paragraph 3 Patent Law`, `Rule 20 Implementing Regulations` and `Article 9
AUCL`; paragraph markers are dropped and the whole provision returned. The
unit must match the translation: the patent regulations resolve only by
`Rule`, because `Article 20` of the 2023 Regulations is a different provision
from 2010 Rule 20, and `Rule N` of a statute numbered by Article resolves to
nothing. A 2026 Trademark Law Article number resolves to the 2019 Article of
that number; the version note is the only guard. A citation that cannot be
parsed or is not in the corpus returns null from the library and goes to
`not_found` in the tool (a single missing citation gives an empty list and
the summary `CNIPA China provision '…' — not found.`), never an error.

Search defaults to all-terms matching and BM25 order, quotes every term so
`OR`, `NEAR` and punctuation never run as FTS5 syntax, and returns statute,
number, label, title (the chapter), a `<mark>` snippet and rank. Outline
order lists the statutes in key order, then provisions numerically, with no
rank. Status reports `corpus_version` as the build's `source_version` (`WIPO
Lex English translations, 2026-10-26`), `corpus_synced_at` as the snapshot
date at UTC midnight, and the controlling-text `notice`.

## Building, packaging and verification

The runtime never fetches or rebuilds the corpus. From `typescript/`:

```sh
bun run build:cnipa-statutes --fetch     # download the PDFs, rewrite the source manifest, build
bun run build:cnipa-statutes             # or rebuild from the archived PDFs
bun scripts/compress-corpus.ts \
  --input .data/cnipa_statutes/cnipa_statutes.db \
  --output .data/cnipa_statutes/cnipa_statutes.db.zst
bun run verify:cnipa-statutes --file .data/cnipa_statutes/cnipa_statutes.db.zst
```

The raw PDFs go to the ignored `.data/cnipa_statutes/raw/`; a rebuild checks
each against the SHA-256 and row count in the committed source manifest and
stops on a mismatch. The builder writes a standalone DELETE-journal database,
never overwrites its output, and checks integrity. `--fixture` also rewrites
the test fixture.

The October 26, 2026 build (PDFs retrieved 22:41 UTC):

| Rows | Decoded bytes | Decoded SHA-256 | Zstandard bytes | File SHA-256 |
| --- | --- | --- | --- | --- |
| 476 | 798,720 | `c10216f02e2b1a21087539380be2c3c3f0c9615b666ce14a9760ba617c418ebb` | 194,828 | `90dcc9ec02056df4c0e12d989f4e3057f2f62490d74c03a3310ad9dc631b3c5a` |

A second build from the archived PDFs reproduced the decoded bytes exactly.
The verifier configured the packaged file and both pins, checked each
statute's row count and PDF hash against the source manifest, the
controlling-text notice, and a phrase and chapter in one provision of each
statute, and exercised the library and the default full MCP server. The
artifacts stay under ignored `.data/` and were not published or deployed.

Publish before deploying. `cnipa_statutes` is in the corpus bootstrap list
(`CNIPA_STATUTES`) and in `scripts/publish-corpora.ts`, but the published
manifest does not have it yet. A hosted image built from this branch with
`CORPORA_MANIFEST_URI` set will refuse to start (`CORPUS_MISSING`) until the
corpus is published, as happened with the ILPO corpus.

## Tests

The [fixture](../tests/fixtures/cnipa-statutes/README.md) is 13 real
provisions written by the builder from the October 26 PDFs.
[Builder tests](../tests/cnipa-statutes-build.test.ts) cover indented and
gap-separated paragraphs, chapter and section headings over a table of
contents, the Cyrillic numerals, wrapped cross-references, Rule headings with
renumbering notes, the misprinted heading, page-break continuation, the count
and heading guards, and the source manifest.
[Library tests](../tests/cnipa-statutes-client.test.ts) cover aliases,
citation parsing and the unit check, status with the notice and per-statute
versions, provisions and missing ones, search filters, paging, outline order,
FTS operator quoting, a missing corpus, Zstandard bytes and pins.
[MCP tests](../tests/cnipa-statutes-mcp.test.ts) cover both tools' summaries
and shapes, `not_found`, the status resource, the curated toolset and the
`cnipa:read` scope on the authenticated HTTP listener (a `spc:read` token
sees none of these tools). Node and browser smoke runs read the fixture as
bytes. All run offline.
