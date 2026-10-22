# IPO India corpus fixtures

`ipo_in_statutes.db` and `ipo_in_mppp.db` are the complete corpora, not
subsets: the Python builders (`patent-client-agents-build-ipo-in-statutes-corpus`
and `patent-client-agents-build-ipo-in-mppp-corpus`) ingest only the seeds
bundled with the Python package, so the full snapshots are this small. They
were built on October 22, 2026 and prepared into DELETE journal mode with
`scripts/prepare-mpep-corpus.py`.

| File | Rows | Seed SHA-256 | Prepared SHA-256 |
| --- | --- | --- | --- |
| `ipo_in_statutes.db` | 26 sections | `efbee2e3e51cd9b440ec65ccd81a79ba84c94ef12e45e1b37f865f47133fba83` | `229ff9cba90ab13cdb86391cc79222fa72f8a2584fab7809848a94a93b4a42d8` |
| `ipo_in_mppp.db` | 12 sections | `c40fb9f0f49cf98b58780fc278b674ecb4c6b7704fe9e76dc0155e675b8e7160` | `856b91aa136641e71f508bfe3cce5d692345aeddf009c0a567c52ee29ba58884` |

`meta.snapshot_date` is the build date (2026-10-22), not a source retrieval
date; the seed texts are curated excerpts, not official consolidated text.
