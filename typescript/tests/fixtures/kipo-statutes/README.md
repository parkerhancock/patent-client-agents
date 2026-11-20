# KIPO Korea statutes corpus fixture

`kipo_statutes.db` is a 14-article subset of the real KIPO statutes build,
written by `bun scripts/build-kipo-statutes-corpus.ts --fixture` from the KLRI
English translations retrieved from elaw.klri.re.kr on October 26, 2026
(hashes in `scripts/kipo-statutes-sources.json`). It uses the same schema,
text rules and metadata as the full 1,202-row build; `meta.section_count` is
14 and `meta.fixture_subset_of` is 1202. `meta.statutes` describes all seven
statutes in full.

| SHA-256 | Bytes |
| --- | --- |
| `b0adf0ef56b2190faa0da9ddf70de85b19fac328a587c31649bca1020f54bbba` | 135,168 |

Articles, each complete as parsed: Patent Act Articles 2, 7-2 (a branch
article), 26 (deleted), 29 and 94; Utility Model Act Article 4; Design
Protection Act Articles 33 and 76 (the article whose text the source splits
into a second block); Trademark Act Articles 33 and 34; Unfair Competition
Prevention and Trade Secret Protection Act Articles 2 and 10; Invention
Promotion Act Article 10; Copyright Act Article 35-5. Rebuilding from the same
HTML reproduces the file byte for byte. No credential or browser storage is
included.
