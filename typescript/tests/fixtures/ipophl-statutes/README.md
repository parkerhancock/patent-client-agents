# IPOPHL Philippines statutes corpus fixture

`ipophl_statutes.db` is a 16-section subset of the real IPOPHL statutes
build, written by `bun scripts/build-ipophl-statutes-corpus.ts --fixture`
from the LawPhil pages retrieved on October 26, 2026 (hashes in
`scripts/ipophl-statutes-sources.json`). It uses the same schema, text rules
and metadata as the full 327-row build; `meta.section_count` is 16 and
`meta.fixture_subset_of` is 327. `meta.statutes` and `meta.amendments`
describe all four Acts in full.

| SHA-256 | Bytes |
| --- | --- |
| `e279c6e4ff6bd71c563d78ddc96a5ecb707bf5fcd6567d0e395e00b6a93ea4f7` | 122,880 |

Sections, each complete as parsed: RA 8293 Sections 1, 4, 21, 22, 26, 72,
74, 123, 171 and 172; RA 9150 Sections 1 and 3; RA 9502 Sections 5 and 7
(the second with its source note); RA 10372 Sections 3 and 28. Rebuilding
from the same pages reproduces the file byte for byte. No credential or
browser storage is included.
