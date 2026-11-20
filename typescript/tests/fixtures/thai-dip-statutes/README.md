# Thailand IP statutes corpus fixture

`thai_dip_statutes.db` is a 16-section subset of the real Thailand IP
statutes build, written by `bun scripts/build-thai-dip-statutes-corpus.ts
--fixture` from the WIPO Lex English PDFs retrieved on October 26, 2026
(hashes in `scripts/thai-dip-statutes-sources.json`). It uses the same schema,
text rules and metadata as the full 401-row build; `meta.section_count` is 16
and `meta.fixture_subset_of` is 401. `meta.statutes` describes all four acts in
full.

| SHA-256 | Bytes |
| --- | --- |
| `b8cbb3671b86ea3ec4e542a35d77634923bd6b177bf0bfe219764c78e71d175d` | 98,304 |

Sections, each complete as parsed: Patent Act sections 3, 5, 36, 36bis and
65bis; Trademark Act sections 4, 6, 28bis and 109/1; Copyright Act sections 4,
15, 32 and 32/1; Trade Secrets Act sections 3, 6 and 7. Rebuilding from the same
PDFs reproduces the file byte for byte. No credential or browser storage is
included.
