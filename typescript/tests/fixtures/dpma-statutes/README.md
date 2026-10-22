# DPMA statutes corpus fixture

`dpma_statutes.db` is a 16-section subset of the real DPMA statutes build,
written by `bun scripts/build-dpma-statutes-corpus.ts --fixture` from the
gesetze-im-internet.de XML zips retrieved on October 22, 2026 (hashes in
`scripts/dpma-statutes-sources.json`). It uses the same schema, text rules and
metadata as the full 778-row build; `meta.section_count` is 16 and
`meta.fixture_subset_of` is 778. `meta.acts` describes all six Acts in full.

| SHA-256 | Bytes |
| --- | --- |
| `7fc597bcf93eee053ef4e382cb97a636124b7bec4caba751e76c66a1efe2dd32` | 102,400 |

Sections, each complete as published: PatG §§ 1, 3, 9, 16a, 18 (one of the
grouped "§§ 18 und 19 (weggefallen)"), 139; MarkenG §§ 14, 32; GebrMG §§ 1,
11; DesignG § 1; UrhG §§ 1, 97 and the Anlage (zu § 61a); GeschGehG §§ 1, 2.
Rebuilding from the same zips reproduces the file byte for byte. No
credential or browser storage is included.
