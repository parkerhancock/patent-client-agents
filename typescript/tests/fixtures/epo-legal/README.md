# EPO legal corpus fixtures

Each database holds three or four real rows copied read-only from the local
Python corpora (snapshot date 2026-05-14) by
`scripts/extract-epo-legal-fixtures.py`. Compressed HTML BLOBs, the matching
Zstandard dictionary, plaintext and `meta` are copied byte for byte; the FTS5
index is rebuilt over the subset. They are compatibility samples of the real
schema-1 outline artifacts, not current or complete corpora.

| File | Rows | Edition recorded by the build | Decoded HTML SHA-256 |
| --- | --- | --- | --- |
| `epc.db` | a52, a54, r1, r71 | `epc_year=2020` | a54: `bb3a6e41c70b65a77a5ae7cbe2382a6bb3e17038ebaa7aa2d8c4a572e9713dfc` |
| `caselaw.db` | clr_foreword, clr_i_a_1, clr_i_c_5_2, clr_i_d_9_1 | `caselaw_year=2022` | clr_i_a_1: `2a7f790e1b6817d33172cc4646636e4323138d3432f426fe6cdb1d4742b0363a` |
| `guidelines.db` | a_i, g_ii_3, g_ii_3_1, g_vii_5_4 | `guidelines_year=2024` | g_ii_3_1: `c6c8969a05f2aef78bfa281d99dde59d66183c9044408d450fd129c20672e57b` |
| `pct_guidelines.db` | b_iii, b_iii_1, b_iii_2, b_iii_2_3_3 | `guidelines_year=2024` | b_iii_2_3_3: `8abf39e4e6308e5c434d727dfa97f7bee45fcc7e433cda737a52a2b344749c50` |
| `up_guidelines.db` | section_1, section_1_2_1, section_2_4 | `up_guidelines_year=2026` | section_1_2_1: `ea262d25a9a2896f454a7ae9cb2d8e755d763c1db36f7b6aab8c34addffa1ce1` |

The recorded edition years come from the crawl path the Python builder used.
They have not been checked against the editions EPO currently publishes.
The copied text preserves an upstream extraction defect: headings run into
footnote numbers (for example `Article 5442, 43Novelty`), so FTS does not
index such heading words as separate tokens. Incomplete-metadata cases are
built from these files at test time. No credential or browser storage is
included.
