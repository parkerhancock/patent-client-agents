# UPC statutes corpus fixture

`upc_statutes.db` holds four real rows, copied read-only from the pre-built
corpus the deploy image ships (`patent-client-agents-deploy/corpora/upc_statutes.db`,
source SHA-256 `6eaef0e48d0ef896b20f79f6cf0367a4ebad575f988391a7fe1727c7df96fce6`,
snapshot date 2026-05-14) by `scripts/extract-upc-statutes-fixtures.py`. Rows,
rowids and `meta` are copied as stored; the FTS5 index is rebuilt over the
subset. `meta.instrument_count` still says 9, the full corpus's count.

| Instrument | Language | Characters | Text SHA-256 |
| --- | --- | --- | --- |
| `upca` (UPCA with the Statute as Annex I) | en | 125,255 | `98e59e5145eeeade781586178311ab249dae77a5b8fe2ab5ec8230fe37fe21be` |
| `fees` (Table of Court Fees) | en | 6,178 | `38a1285665917473a24612c2543537983fc5f7f6271466854fb31609d10c954e` |
| `fees` | fr | 6,998 | `69f50ff3b025346f1ee90c632f96d47a49688b725fd87f4502fb8946cc92e214` |
| `fees` | de | 6,505 | `3dac405788e8498826ec9bd86458fdc37c373a1ae1819d1e38137e3ad6dce30f` |

The Rules of Procedure rows (130 KB to 360 KB each) are left out to keep the
fixture small, so tests use `rop` as an installed-elsewhere, missing-here key.
This is a compatibility sample of the real schema-1 artifact, not a current or
complete corpus. No credential or browser storage is included.
