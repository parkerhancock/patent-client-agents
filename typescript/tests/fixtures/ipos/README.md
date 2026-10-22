# IPOS Singapore corpus fixtures

`ipos_statutes.db` and `ipos_manuals.db` are subsets of the real corpora,
written by `bun scripts/build-ipos-corpora.ts --fixtures` from the same parse
of the official sources listed in `references/ipos/sources.json` (retrieved
October 22, 2026). The row text is exactly as in the full build; only the row
selection is smaller. `meta` carries the full build's source metadata, with
`section_count` the fixture's own row count.

| File | Rows |
| --- | --- |
| `ipos_statutes.db` | 19: Patents Act 2, 13, 14, 15, 29A, 66, 109, Schedule; Trade Marks Act 2, 7, 8, 27, First Schedule; Registered Designs Act 2, 5, 68A; Copyright Act 9, 190, 191 |
| `ipos_manuals.db` | 11: Examination Guidelines (PEG) 1.1, 1.3, 4.1, 4.2, 8.12; TM Work Manual 1.1, 7.5.2.5.2, 7.5.2.5.3, 17.3.1; Registered Designs guidelines 1.1, 2.1 |
