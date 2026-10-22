# DPMA statutes corpus fixture

`dpma_statutes.db` is the whole DPMA statutes corpus as the Python connector
builds it: `patent-client-agents-build-dpma-statutes-corpus` run on October 22,
2026 over the bundled `src/patent_client_agents/dpma_statutes/data/seed.jsonl`
(12 rows, SHA-256 `2a84f3ce8c62056f140193dcbdc73e1bfe16efef364fa8aca62570c727d496dd`),
then moved from WAL to DELETE journal mode with `scripts/prepare-mpep-corpus.py`.
Nothing else was changed; `meta.snapshot_date` is the build date.

| Source build SHA-256 | Prepared (this file) SHA-256 | Bytes |
| --- | --- | --- |
| `6f8fc6029d883baa830d55b52990470241c7cd45779db71a9252dc861f6b8849` | `6256d69d7d32325a05c3c8e30c619ed66b61043a4b7879927b700307dcec3b98` | 53,248 |

It holds 12 sections: PatG §§ 1, 3, 139; MarkenG §§ 14, 32; GebrMG §§ 1, 11;
DesignG § 1; UrhG §§ 1, 97; GeschGehG §§ 1, 2. Each text is only the first
paragraph (or first sentence) of the section, as the Python seed stores it.
No credential or browser storage is included.
