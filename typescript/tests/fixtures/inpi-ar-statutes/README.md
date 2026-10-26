# INPI Argentina statutes corpus fixture

`inpi_ar_statutes.db` is a 16-article subset of the real INPI Argentina
statutes build, written by `bun scripts/build-inpi-ar-statutes-corpus.ts
--fixture` from the Infoleg pages retrieved on October 26, 2026 (hashes in
`scripts/inpi-ar-statutes-sources.json`). It uses the same schema, text rules
and metadata as the full 301-row build; `meta.section_count` is 16 and
`meta.fixture_subset_of` is 301. `meta.statutes` describes all five statutes
in full.

| SHA-256 | Bytes |
| --- | --- |
| `99cce888ab0ae667e39b98d99121c70328940a90c872e6e3480ea2835e86d63d` | 86,016 |

Articles, each complete as parsed: Ley 24.481 articles 4, 8, 12 and 90; Ley
22.362 articles 3, 10, 19 (repealed) and 23 (an inline inciso note); Decreto-Ley
6673/63 articles 3 and 14 (repealed); Ley 11.723 articles 1, 5 bis, 36 quáter
and 74 bis (repealed); Ley 24.766 articles 1 and 15. Rebuilding from the same
pages reproduces the file byte for byte. No credential or browser storage is
included.
