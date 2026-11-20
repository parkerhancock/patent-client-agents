# Russian Civil Code Part Four corpus fixture

`rospatent_statutes.db` is a 16-article subset of the real Part Four build,
written by `bun scripts/build-rospatent-statutes-corpus.ts --fixture` from the
WIPO Lex English PDF retrieved on October 26, 2026 (hash in
`scripts/rospatent-statutes-sources.json`). It uses the same schema, text rules
and metadata as the full 329-row build; `meta.section_count` is 16 and
`meta.fixture_subset_of` is 329. The other meta keys (version note, both
"amended up to" dates, the repealed Chapter 77, the WIPO Lex record) describe
the full build.

| SHA-256 | Bytes |
| --- | --- |
| `791ba534625e2a233ae17963e4a28c4e81a6f08cb9d61df4f0cd82bf4c0ab848` | 126,976 |

Articles, each complete as parsed: 1225, 1229, 1231.1, 1248, 1252, 1259, 1270,
1350, 1358.1, 1363, 1465, 1477, 1478 (repealed), 1484, 1515 and 1541. They
cover chapters 69, 70, 72, 75 and 76, a § and a numbered sub-§ heading, two
inserted articles and the one repealed article. Rebuilding from the same PDF
reproduces the file byte for byte. No credential or browser storage is
included.
