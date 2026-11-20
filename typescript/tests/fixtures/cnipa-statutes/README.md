# CNIPA China statutes corpus fixture

`cnipa_statutes.db` is a 13-provision subset of the real CNIPA statutes build,
written by `bun scripts/build-cnipa-statutes-corpus.ts --fixture` from the
WIPO Lex English PDFs retrieved on October 26, 2026 (hashes in
`scripts/cnipa-statutes-sources.json`). It uses the same schema, text rules and
metadata as the full 476-row build; `meta.section_count` is 13 and
`meta.fixture_subset_of` is 476. `meta.statutes` describes all six statutes
in full, including each translation's version and the Chinese PDF that
controls.

| SHA-256 | Bytes |
| --- | --- |
| `55faf434518fb0e5c1fb9709f276f5abf2c1560f2313c94d13068f96a265fa28` | 86,016 |

Provisions, each complete as parsed: Patent Law Articles 2, 22, 26 and 82;
Patent Implementing Regulations (2010) Rules 6 and 20; Trademark Law (2019)
Articles 13 and 57; Trademark Implementing Regulations Article 3;
Anti-Unfair Competition Law Articles 9 and 32; Copyright Law Articles 3 and
24. Rebuilding from the same PDFs reproduces the file byte for byte. No
credential or browser storage is included.
