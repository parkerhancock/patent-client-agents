# IPO India corpus fixtures

`ipo_in_statutes.db` and `ipo_in_mppp.db` are subsets of the real corpora,
written by `bun scripts/build-ipo-in-corpora.ts --fixtures` from the same
parse of the official sources listed in `references/ipo-in/sources.json`
(retrieved October 22, 2026). The row text is exactly as in the full build;
only the row selection is smaller. `meta` carries the full build's source
metadata, with `section_count` the fixture's own row count.

| File | Rows |
| --- | --- |
| `ipo_in_statutes.db` | 37: Patents Act 1, 2, 3, 5, 8, 11A, 25, 48, 53, 84, 107A, 122, 124A, 146; Patents Rules 2, 13, 24B, 55, 71, 107A, 131, 138; Designs Act 2, 4, 11, 22; Trade Marks Act 2, 9, 11, 29, 36A; Copyright Act 2, 13, 14, 22, 52, 63 |
| `ipo_in_mppp.db` | 14: 01, 04.01, 04.02, 07.02, 07.02.01, 09, 09.01, 09.03, 09.03.01, 09.03.05, 09.03.05.04, 09.03.05.10, 09.04, 14.01 |
