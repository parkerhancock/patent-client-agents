# ILPO Israel statutes corpus fixture

`ilpo_statutes.db` is a 15-section subset of the real ILPO statutes build,
written by `bun scripts/build-ilpo-statutes-corpus.ts --fixture` from the
WIPO Lex English PDFs retrieved on October 22, 2026 (hashes in
`scripts/ilpo-statutes-sources.json`). It uses the same schema, text rules and
metadata as the full 576-row build; `meta.section_count` is 15 and
`meta.fixture_subset_of` is 576. `meta.statutes` describes all five statutes
in full.

| SHA-256 | Bytes |
| --- | --- |
| `2345ccc3b8c04f35decbd13165e96ff5f9760bed6df41022d4cc60777319285e` | 77,824 |

Sections, each complete as parsed: Patents Law sections 2, 3, 4, 5 and 54A;
Trade Marks Ordinance sections 8, 11 and 46A; Designs Law sections 3 and 6;
Copyright Act sections 5 and 19; Commercial Torts Law sections 5, 6 and 13.
Rebuilding from the same PDFs reproduces the file byte for byte. No
credential or browser storage is included.
